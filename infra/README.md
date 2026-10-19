# Terraform para AWS — issue #13

Este stack despliega la aplicación Family Planner en AWS usando Lambda, DynamoDB y Cognito. Docker Compose conserva PostgreSQL y Keycloak para el desarrollo local. La tabla AWS comienza vacía; no se importan datos del calendario local. Los comandos de despliegue no inician sesión: usan el perfil AWS CLI ya activo.

## Recursos y separación

`bootstrap/` prepara el bucket privado de estado, conserva dos buckets heredados de artefactos y crea repositorios ECR separados. `environments/preview/` y `environments/production/` son raíces independientes que reutilizan `modules/application/`. Son dos entornos persistentes, no un entorno por PR.

Cada entorno tiene S3 privado para la web, CloudFront con OAC y HTTPS, API Gateway HTTP, Lambda Python 3.12 desde imagen ECR, DynamoDB on-demand, Cognito y sus roles/registros. La Lambda implementa el contrato `/api/v1` mediante la capa de dominio y el adaptador DynamoDB. CloudFront sirve la API por `/api/*` sin caché. Solo `GET /api/health` y `GET /api/v1/config` son públicos; el resto exige un JWT de acceso válido del cliente Cognito del entorno.

El endpoint MCP vive en `/mcp` dentro de la misma distribución CloudFront y API Gateway, sin caché. Una Lambda independiente usa el mismo artefacto ECR, un rol IAM separado y solo operaciones necesarias para leer/escribir eventos en la tabla del entorno; no tiene permiso para borrar eventos. Cognito emite los scopes `calendar.read` y `calendar.write` ligados a la audiencia del MCP. La Lambda comprueba firma, emisor de Cognito, tipo de token, audiencia, scope y `sub` antes de construir los repositorios familiares. La Lambda publica metadata de recurso OAuth y una metadata de autorización compatible con Codex (PKCE S256 y scopes), que delega las rutas de autorización/token en el User Pool de ese entorno. Cognito no tiene DCR, por lo que Codex usa el `client_id` público preconfigurado. No se modifica el esquema DynamoDB.

#### Conectar Codex a los endpoints MCP

Consulta las salidas `mcp_url`, `mcp_oauth_client_id` y `mcp_oauth_callback_url` para revisar la configuración. Codex debe usar el puerto de callback `1455`, cuyo path específico queda registrado en Cognito para cada URL MCP.

Al finalizar `make deploy preview` o `make deploy production`, Make fija también `mcp_oauth_callback_port = 1455` en la configuración global de Codex (`$CODEX_HOME/config.toml` o `~/.codex/config.toml`) y reemplaza la entrada `family-planner-<entorno>` con la URL CloudFront y el cliente OAuth recién aplicados. Así la CLI y la app Codex comparten el callback que Cognito registra (`http://127.0.0.1:1455/callback/<id>`), incluso al volver a autorizar desde la app. El ajuste es global para los inicios OAuth de servidores MCP de Codex y conserva el resto de preferencias. Codex inicia el flujo OAuth dentro del mismo comando. Abre la URL de autorización que muestra Codex y termina el inicio de sesión antes de cerrar el despliegue. La sincronización se omite con un aviso si Codex CLI no está instalado o no puede modificar la configuración; el despliegue AWS ya completado no se revierte. Para repetir la autorización más adelante, ejecuta:

```sh
codex mcp login family-planner-preview -c mcp_oauth_callback_port=1455
```

Para producción, sustituye `preview` por `production`. La configuración MCP es compartida por la aplicación Codex, la CLI y la extensión IDE.

Para una configuración manual inicial, fija primero `mcp_oauth_callback_port = 1455` en la configuración global de Codex; después, `codex mcp add` inicia OAuth con el callback registrado. Si solo necesitas volver a autorizar una entrada existente, usa `codex mcp login` como en el ejemplo anterior. El argumento `-c mcp_oauth_callback_port=1455` solo afecta a esa invocación y no sustituye la preferencia global necesaria para futuros inicios OAuth desde la app.

Para registrar manualmente el servidor:

```sh
codex mcp add family-planner-preview \
  -c mcp_oauth_callback_port=1455 \
  --url "$(terraform -chdir=infra/environments/preview output -raw mcp_url)" \
  --oauth-client-id "$(terraform -chdir=infra/environments/preview output -raw mcp_oauth_client_id)"
```

Repite con `family-planner-production` y las salidas de `infra/environments/production`. La conexión solicita OAuth con PKCE; preview apunta a su propio User Pool y datos ficticios, producción al User Pool de producción. Codex recibe las herramientas `list_events` y `save_event`; la segunda crea un evento si no tiene `event_id` o actualiza uno existente si lo incluye. No se exponen tareas, perfiles, rutinas ni borrado de eventos. Para consultar o guardar eventos se usan fechas ISO-8601 con zona horaria, y para crear se requiere `member_id`.

Cada registro usa `PK=FAMILY#<sub de Cognito>` y `SK=TIPO#id`; GSIs de día, series y marcas incluyen ese mismo identificador. Las excepciones de series y marcas de tareas también usan la partición familiar. El backend crea repositorios por petición a partir del `sub` del token ya validado, consulta con `Query` y no usa `Scan`. Las escrituras condicionadas/transacciones impiden que una familia referencie integrantes o elementos de otra. Pedro aprobó el cambio el 10 de octubre de 2026; preview empieza vacío y producción no se modifica ni migra.

Las asignaciones a tareas admiten hasta 99 integrantes por escritura: la transacción DynamoDB reserva la operación restante para guardar la tarea junto con los controles de estado de cada perfil.

Las etiquetas de imagen `sha-<commit>` son únicas por commit; Terraform fija el digest inmutable en cada despliegue. Los repositorios escanean las imágenes y retienen las últimas 30 versiones SHA. Los roles de ejecución Lambda solo pueden acceder a su tabla y registros; no tienen acceso a ECR ni a la tabla del otro entorno. Cada familia se registra e inicia sesión desde la pantalla propia usando correo verificado y una cuenta común por familia.

Producción activa recuperación a un momento dado (PITR) y protección contra borrado de DynamoDB, protección de Cognito y 30 días de registros. Preview conserva registros 7 días, sin PITR. Todos los buckets tienen cifrado AES256, bloqueo de acceso público, versionado y rechazo de HTTP. No se vacían automáticamente al destruir; los buckets del bootstrap tienen además `prevent_destroy`. `make destroy preview` conserva los repositorios ECR y el rol OIDC del bootstrap. Preview añade un secreto recuperable en Secrets Manager con coste estimado autorizado de 0,40 USD/mes, más solicitudes.

Sin dominio propio se usan las direcciones HTTPS de CloudFront y Cognito. Opcionalmente se acepta un dominio y un certificado ACM **ya existente en us-east-1 y en la misma cuenta**. Solo si también se indica una zona Route53 existente se crean registros A/AAAA. No se crean dominio, zona ni certificado.

## Comprobar sin sesión AWS

Requisitos: Terraform 1.10 o posterior (CI usa 1.16.5), Node 24 y conexión al registro público para descargar el proveedor AWS 6.68.0. Estos comandos no acceden a una cuenta AWS:

```sh
terraform fmt -check -recursive infra
for root in infra/bootstrap infra/modules/application infra/environments/preview infra/environments/production; do
  terraform -chdir="$root" init -backend=false -input=false -lockfile=readonly
  terraform -chdir="$root" validate
done
terraform -chdir=infra/bootstrap test
terraform -chdir=infra/modules/application test
node --test infra/tests/spa.test.mjs
```

Los `.tftest.hcl` utilizan `mock_provider "aws"`, incluso en los casos `command = apply`: son operaciones simuladas en memoria. No ejecutar `terraform plan`, `apply` o `init` con backend remoto para estas comprobaciones. Los lockfiles verifican los proveedores descargados; no contienen claves.

## Despliegue manual posterior

Los pasos siguientes sí requieren que **Pedro haya iniciado sesión por su cuenta** con AWS CLI y revisado seguridad, coste y plan. No se ejecutan desde CI. Usa credenciales temporales mediante un perfil local; nunca añadas claves o contraseñas a `.tfvars`, código o GitHub. Sustituye los ejemplos `111111111111` y elige la región antes de continuar. Los proveedores rechazan una cuenta distinta a `aws_account_id`.

### Atajos con Make

Desde la raíz del repositorio, una vez configurados los archivos locales de Terraform:

```sh
make bootstrap
make plan preview
make plan production
make deploy preview
make deploy production
make destroy preview
make preview-credentials
```

`make plan <entorno>` y `make deploy <entorno>` preparan Terraform 1.16.5 en la caché local `build/tools` sin reemplazar el Terraform global. Construyen la imagen Lambda x86_64/Python 3.12 y el frontend con Node 24 dentro de Docker; Node/npm locales no intervienen. Se necesita Docker y AWS CLI. El Makefile obtiene el ID de cuenta de `aws sts get-caller-identity`, usa `AWS_PROFILE` cuando se establezca y crea los archivos locales ignorados de Terraform si faltan. La región predeterminada es `eu-west-1`; se puede cambiar con `AWS_REGION=...`.

Ambos comandos comprueban el bootstrap. Si no existe el estado local y tampoco existe el bucket de estado, crean buckets bootstrap privados y los repositorios ECR. Si el bucket ya existe pero falta el estado local, se detienen para evitar recrear o adoptar recursos sin estado. `make plan` publica la imagen SHA en ECR y muestra el plan del entorno; no aplica recursos del entorno. `make deploy preview` publica la imagen, muestra el plan y aplica sin confirmación adicional, según aprobó Pedro. `make deploy production` requiere escribir `APPLY production` después de revisar el plan. Ambos publican la web y solicitan una invalidación de CloudFront.

`make destroy preview` requiere el estado remoto de preview y el bootstrap local existente. Muestra un plan de destrucción, pide escribir exactamente `DESTROY preview` y elimina los recursos Terraform de preview, incluido el secreto de prueba, los objetos versionados de su bucket web y los artefactos bajo `preview/`. No construye ni sube artefactos. El bucket de estado compartido, los buckets bootstrap, el estado remoto vacío y todos los recursos de producción permanecen. Este comando no borra recursos que no estén registrados en el estado de Terraform. `make preview-credentials` recupera y muestra en la terminal local el usuario, correo y contraseña almacenados en Secrets Manager.

Ejemplo con un perfil ya conectado: `AWS_PROFILE=mi-perfil make plan preview`. No se guardan credenciales en los archivos generados.

`make build-aws` construye la imagen Lambda local y genera la web en `build/aws/frontend-compatible/dist/`, sin publicar en AWS.

### 1. Bootstrap

Desde la raíz del repositorio, el target Make prepara Terraform 1.16.5 en la caché local y toma la cuenta/región de la sesión AWS activa:

```sh
make bootstrap
```

Para ejecutar Terraform manualmente fuera de Make, el operador debe seleccionar una versión compatible (1.10 o posterior) por su cuenta.

El bootstrap usa **estado local** porque el bucket remoto aún no existe. Conserva una copia segura de `infra/bootstrap/terraform.tfstate` y sus backups; no se sincroniza solo con S3. Estado, configuración efectiva y planes están excluidos de Git, pero deben protegerse en el equipo. No ejecutar el bootstrap desde otra carpeta o equipo sin recuperar su estado: intentaría crear buckets que ya existen.

### 2. Construir imágenes y web

`make build-aws` construye `backend/Dockerfile.lambda` para Linux x86_64/Python 3.12 y compila React con Node 24 usando Docker. El handler verifica la firma y el emisor del JWT, su tipo `access` y el cliente Cognito del entorno. El frontend registra y confirma el correo, inicia sesión y recupera contraseñas mediante una pantalla propia; los tokens solo viven en memoria. No se incluyen credenciales ni datos familiares en la imagen.

En los despliegues manuales Make publica `sha-<commit>` en ECR, consulta su digest e introduce la URI inmutable en el plan Terraform. Producción también mueve el alias `latest`; el estado Terraform permanece fijado al digest aplicado para permitir una reversión reproducible.

### 3. Inicializar y revisar preview

```sh
cp infra/environments/preview/backend.hcl.example infra/environments/preview/backend.hcl
cp infra/environments/preview/terraform.tfvars.example infra/environments/preview/terraform.tfvars
# Editar la cuenta y región; `make plan/deploy` publica y resuelve la imagen ECR.
terraform -chdir=infra/environments/preview init -backend-config=backend.hcl
terraform -chdir=infra/environments/preview plan -var="lambda_image_uri=URI_ECR_FIJADA_POR_DIGEST" -out=preview.tfplan
# Revisar el plan y el coste antes de aplicar.
terraform -chdir=infra/environments/preview apply preview.tfplan
terraform -chdir=infra/environments/preview output
```

El backend S3 usa `preview/terraform.tfstate` y bloqueo nativo `use_lockfile = true`, sin tabla DynamoDB de locks. El bucket de estado debe coincidir con el bootstrap y la región. Los comandos Make generan `backend.hcl` y `terraform.tfvars` ignorados por Git cuando no existen; revisa la cuenta y la región antes de confirmar cualquier plan. No copiar estado de preview a producción.

### 4. Publicar la web y crear la cuenta familiar

Una vez probado y compilado el **frontend compatible con Cognito**, obtiene el bucket y la distribución con `terraform output frontend_bucket` y `cloudfront_distribution_id`. La salida `runtime_config` contiene configuración pública, no credenciales, y sirve de contrato para `/api/v1/config`.

```sh
aws s3 sync /ruta/absoluta/frontend-compatible/dist/ s3://BUCKET_WEB/ \
  --exclude index.html --cache-control 'public,max-age=31536000,immutable'
aws s3 cp /ruta/absoluta/frontend-compatible/dist/index.html s3://BUCKET_WEB/index.html \
  --content-type text/html --cache-control 'no-cache'
aws cloudfront create-invalidation --distribution-id DISTRIBUTION_ID --paths '/*'
```

Solo los archivos con nombre que cambia al cambiar su contenido deben tener caché `immutable`; los demás deben publicarse con `no-cache`. La primera publicación debe incluir todos los archivos; los assets de versiones anteriores se conservan para evitar romper sesiones y permitir reversión. Terraform no publica el contenido web ni invalida caché.

El formulario propio permite registrar la familia con correo, confirmar el código y recuperar acceso. Cada cuenta queda aislada en DynamoDB mediante su `sub` verificado de Cognito. Preview crea una cuenta `test` con datos enteramente ficticios y guarda la contraseña en Secrets Manager, fuera del estado de Terraform. Recupera las credenciales con `make preview-credentials`; no se imprimen en CI. El cargador solo añade datos cuando no existen y se detiene si encuentra perfiles ajenos a la familia ficticia.

Verifica registro/verificación de correo, login/logout/renovación, rechazo anónimo, token de preview rechazado en producción, CRUD, imágenes, tareas y persistencia antes de dar por activo el servicio. Las pruebas simuladas de este repositorio no sustituyen estas comprobaciones reales.

### 5. Producción

Repite los pasos con `infra/environments/production`, la imagen de su repositorio ECR y la clave `production/terraform.tfstate`; revisa un plan independiente y publica su frontend. Empieza con tabla vacía. Este cambio no crea registros del calendario ni importa PostgreSQL. La migración de datos reales y su reversión requieren una propuesta y autorización específicas.

## Coste, actualización y reversión

Los recursos generan costes al aplicarse. Referencia orientativa para dos entornos domésticos: **2–10 USD/mes** con hasta 100.000 llamadas y 1 GB/mes; no es un presupuesto garantizado ni un límite. ECR añade unos **0,75–1,50 USD/mes** con 30 imágenes de 250–500 MB antes de deduplicar; Secrets Manager añade aproximadamente **0,40 USD/mes por el secreto de prueba de preview**, más solicitudes. PITR, almacenamiento y versiones web, registros, transferencia, región y consumo compartido de la cuenta afectan al coste. Recalcular con AWS Pricing Calculator antes de aplicar; no se depende de créditos ni de capa gratuita. No hay NAT, RDS, VPC ni concurrencia provisionada. Fuentes y propuesta: [docs/aws-proposal.md](../docs/aws-proposal.md).

Para actualizar Lambda, publica una etiqueta `sha-<commit>`, revisa el plan y despliega el digest inmutable. Producción actualiza además el alias `latest`, pero Terraform registra el digest real. Para revertir, vuelve a aplicar el digest anterior. Revertir código no revierte datos: DynamoDB requiere copias/PITR y un procedimiento de restauración separado. Restaurar PITR crea otra tabla; no modifica la original automáticamente. No destruir producción como mecanismo de rollback ni desactivar sus protecciones de forma rutinaria.

El workflow `CI` publica automáticamente en preview solo después de que pasen los controles de código, integración, navegador y Terraform en `main`. Usa GitHub OIDC; no guarda claves AWS estáticas. Después de `make bootstrap`, configura las variables de repositorio `AWS_ACCOUNT_ID` y `AWS_REGION` en GitHub. Terraform reutiliza el proveedor OIDC GitHub administrado centralmente y limita el rol al subject inmutable de `a10pepo/family_planner` (`owner ID 29485524`, `repository ID 1408456566`) en `refs/heads/main`. El rol de Preview separa las escrituras por recursos del entorno y concede aparte las lecturas globales de metadatos que AWS requiere sin ARN (`DescribeLogGroups`, `DescribeUserPoolDomain` y listados de políticas CloudFront); las lecturas del bucket web, incluida su configuración de aceleración, y del secreto de prueba usan ARNs de Preview; las lecturas del OAC y las políticas de CloudFront se limitan a sus tipos de recurso en la cuenta, y la consulta de etiquetas de funciones al prefijo Preview. Producción sigue siendo manual mediante `make deploy production`.
