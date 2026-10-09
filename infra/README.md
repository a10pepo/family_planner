# Terraform para AWS — issue #13

Este cambio prepara **solo la infraestructura**, según la indicación de Pedro: «no quiero que inicies sesión solo crea el terraform yo haré el login antes de desplegar». No se ha iniciado sesión, consultado la cuenta, aplicado un plan ni migrado datos. CI valida con proveedores simulados, sin credenciales.

**La aplicación actual no es todavía compatible con este destino.** FastAPI usa PostgreSQL y el cliente OAuth usa Keycloak. Antes de desplegar el calendario funcional hace falta implementar y probar el adaptador DynamoDB, el handler Lambda y el login Cognito. Este Terraform requiere un ZIP compatible proporcionado expresamente; no genera un handler ficticio ni empaqueta el backend actual como si pudiera ejecutarse. Docker Compose sigue funcionando con su configuración habitual.

## Recursos y separación

`bootstrap/` prepara un bucket privado de estado y dos buckets privados para ZIPs. `environments/preview/` y `environments/production/` son raíces independientes que reutilizan `modules/application/`. Son dos entornos persistentes, no un entorno por PR.

Cada entorno tiene S3 privado para la web, CloudFront con OAC y HTTPS, API Gateway HTTP, Lambda Python 3.12, DynamoDB on-demand, Cognito y sus roles/registros. CloudFront sirve la API por `/api/*` sin caché y conserva sus errores HTTP. Solo `GET /api/health` y `GET /api/v1/config` son públicos; su implementación futura debe devolver exclusivamente salud y configuración pública. El resto exige JWT del pool propio y el alcance `<proyecto>-<entorno>-api/access`.

Los nombres, buckets de artefactos y claves de estado distinguen entorno y cuenta. Los roles de ejecución Lambda solo pueden acceder a su tabla y registros; no tienen acceso a S3 ni a la tabla del otro entorno. Los usuarios Cognito también son independientes. Un administrador o las credenciales de despliegue de la cuenta pueden gestionar ambos entornos: no se crean aquí roles de despliegue ni políticas de aislamiento para administradores. Para automatizar CD habrá que aprobar y configurar esos permisos por separado.

Producción activa recuperación a un momento dado (PITR) y protección contra borrado de DynamoDB, protección de Cognito y 30 días de registros. Preview conserva registros 7 días, sin PITR. Todos los buckets tienen cifrado AES256, bloqueo de acceso público, versionado y rechazo de HTTP. No se vacían automáticamente al destruir; los buckets del bootstrap tienen además `prevent_destroy`.

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

Desde la raíz del repositorio, una vez configurados los archivos efectivos y los artefactos compatibles:

```sh
make bootstrap
make plan preview
make plan production
make deploy preview
make deploy production
```

`make bootstrap` crea el estado remoto inicial solo después de mostrar el plan y pedir `APPLY bootstrap`. Los targets `make plan <entorno>` validan cuenta y backend, inicializan Terraform y muestran el plan usando los valores ya guardados en el `terraform.tfvars` de ese entorno; no suben ZIPs ni aplican cambios. Para desplegar, cada comando comprueba la sesión AWS activa contra `aws_account_id`, la configuración del backend y los artefactos; sube el ZIP de Lambda con versión inmutable, genera y muestra el plan, y solo aplica si escribes exactamente `APPLY preview` o `APPLY production`. Después publica la web y solicita una invalidación de CloudFront. Puedes seleccionar un perfil ya autenticado con `AWS_PROFILE=nombre make plan preview` o `AWS_PROFILE=nombre make deploy preview`; los comandos no inician sesión ni solicitan credenciales.

Los artefactos predeterminados para `deploy` son `build/aws/api-compatible.zip` y `build/aws/frontend-compatible/dist/`. Si están en otras rutas, pásalas como variables: `make deploy preview LAMBDA_ZIP=/ruta/api.zip FRONTEND_DIST=/ruta/dist`. `plan` usa los valores de artefacto de `terraform.tfvars` y, por ello, requiere referencias válidas de bucket, clave, versión y hash; no necesita tener el ZIP local. Prepara primero `infra/bootstrap/terraform.tfvars`, su estado local, y los `backend.hcl` y `terraform.tfvars` de cada entorno; consulta los pasos siguientes. El ZIP Lambda y la web tienen que ser compatibles con la infraestructura descrita aquí. **Hoy la aplicación del repositorio todavía no genera esos artefactos ni es compatible con Lambda/Cognito**, por lo que estos comandos no convierten ni compilan automáticamente la aplicación actual. Si cancelas un `deploy` después de subir el ZIP, queda una versión adicional en el bucket de artefactos.

### 1. Bootstrap

Desde la raíz del repositorio:

```sh
cp infra/bootstrap/terraform.tfvars.example infra/bootstrap/terraform.tfvars
# Editar terraform.tfvars: cuenta y región.
terraform -chdir=infra/bootstrap init
terraform -chdir=infra/bootstrap plan -out=bootstrap.tfplan
# Revisar recursos y cuenta del plan antes de aplicarlo.
terraform -chdir=infra/bootstrap apply bootstrap.tfplan
terraform -chdir=infra/bootstrap output
```

El bootstrap usa **estado local** porque el bucket remoto aún no existe. Conserva una copia segura de `infra/bootstrap/terraform.tfstate` y sus backups; no se sincroniza solo con S3. Estado, configuración efectiva y planes están excluidos de Git, pero deben protegerse en el equipo. No ejecutar el bootstrap desde otra carpeta o equipo sin recuperar su estado: intentaría crear buckets que ya existen.

### 2. Preparar un ZIP compatible por entorno

El bucket de artefactos debe existir antes de crear Lambda. El ZIP futuro debe incluir dependencias Linux x86_64/Python 3.12, el handler indicado y soporte API Gateway HTTP payload v2. No incluir secretos, fotos ni fixtures familiares. El IAM de ejecución admite consultas y escrituras condicionadas en su tabla (`pk`/`sk`), sin `Scan`; el diseño lógico y la migración se acordarán al implementar el adaptador.

El handler deberá conservar el contrato `/api/v1`, validar pertenencia a `family-app` y la identidad del cliente/token, aplicar las reglas de negocio y consumir `DYNAMODB_TABLE`, `FAMILY_TIMEZONE` y las variables `OAUTH_*`. API Gateway comprueba firma, emisor, audiencia/cliente y alcance; **no comprueba el grupo**. Los tokens de identidad no deben servir para acceder al calendario. El frontend compatible usará Authorization Code + PKCE y las URLs de salida de Terraform.

Ejemplo de carga manual, una vez disponible ese artefacto (no se proporciona en este cambio):

```sh
aws s3api put-object \
  --bucket family-planner-preview-111111111111-artifacts \
  --key preview/COMMIT.zip \
  --body /ruta/absoluta/api-compatible.zip
openssl dgst -sha256 -binary /ruta/absoluta/api-compatible.zip | openssl base64 -A
```

Guarda el `VersionId` devuelto por S3 y el hash base64. Producción requiere su propio bucket y prefijo `production/`. Terraform exige bucket del mismo entorno, clave con prefijo de entorno, versión inmutable y hash del ZIP; no inspecciona su lógica ni verifica que ese hash corresponda al objeto de S3. La publicación futura deberá comprobarlo y ejecutar sus pruebas antes de crear el plan.

### 3. Inicializar y revisar preview

```sh
cp infra/environments/preview/backend.hcl.example infra/environments/preview/backend.hcl
cp infra/environments/preview/terraform.tfvars.example infra/environments/preview/terraform.tfvars
# Editar ambos archivos: cuenta/región reales, bucket, clave, VersionId y hash.
terraform -chdir=infra/environments/preview init -backend-config=backend.hcl
terraform -chdir=infra/environments/preview plan -out=preview.tfplan
# Revisar el plan y el coste antes de aplicar.
terraform -chdir=infra/environments/preview apply preview.tfplan
terraform -chdir=infra/environments/preview output
```

El backend S3 usa `preview/terraform.tfstate` y bloqueo nativo `use_lockfile = true`, sin tabla DynamoDB de locks. El bucket de estado debe coincidir con el bootstrap y la región. Un cambio de perfil/cuenta/backend requiere revisar el estado y ejecutar `init -reconfigure` solo cuando corresponda; no copiar estado de preview a producción.

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

Crea la cuenta familiar desde Cognito, añade esa cuenta al grupo `family-app` y establece/cambia su contraseña fuera de Terraform. No se crean usuarios ni contraseñas en el estado. El registro público está cerrado y la recuperación es administrativa. Preview usará una cuenta y datos ficticios.

Verifica login/logout/renovación, rechazo anónimo, token de preview rechazado en producción, permisos del grupo, CRUD, imágenes, tareas y persistencia antes de dar por activo el servicio. Las pruebas simuladas de este repositorio no sustituyen estas comprobaciones reales.

### 5. Producción

Repite los pasos con `infra/environments/production`, sus ejemplos, ZIP en su bucket y clave `production/terraform.tfstate`; revisa un plan independiente y publica su frontend. Empieza con tabla vacía. Este cambio no crea registros del calendario ni importa PostgreSQL. La migración de datos reales y su reversión requieren una propuesta y autorización específicas.

## Coste, actualización y reversión

Los recursos generan costes al aplicarse. Referencia orientativa para dos entornos domésticos: **2–10 USD/mes** con hasta 100.000 llamadas y 1 GB/mes; no es un presupuesto garantizado ni un límite. PITR, almacenamiento/versiones de ZIPs y web, registros, transferencia, región y consumo compartido de la cuenta afectan al coste. Recalcular con AWS Pricing Calculator antes de aplicar; no se depende de créditos ni de capa gratuita. No hay NAT, RDS, VPC ni concurrencia provisionada. Fuentes y propuesta: [docs/aws-proposal.md](../docs/aws-proposal.md).

Para actualizar Lambda, carga un nuevo ZIP versionado, modifica clave/versión/hash y revisa otro plan. Para revertir, recupera los tres valores de la versión anterior y vuelve a publicar la web compatible de esa versión. Revertir código no revierte datos: DynamoDB requiere copias/PITR y un procedimiento de restauración separado. Restaurar PITR crea otra tabla; no modifica la original automáticamente. No destruir producción como mecanismo de rollback ni desactivar sus protecciones de forma rutinaria.

El CD remoto, roles GitHub OIDC, handler Lambda, adaptador DynamoDB, login Cognito de la aplicación y migración permanecen pendientes. El workflow actual incorpora validación de Terraform sin permisos AWS y mantiene las pruebas y artefactos Docker existentes.
