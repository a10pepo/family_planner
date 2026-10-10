# Instrucciones para agentes

## Contexto y fuentes

- Proyecto: Family Planner, repositorio `a10pepo/family_planner`.
- Propietario y responsable de decisiones: Pedro Nieto. Cuando el usuario diga «yo» o «me», se refiere a Pedro Nieto.
- Lee [application.md](application.md) antes de cambiar comportamiento de producto y [docs/architecture.md](docs/architecture.md) antes de implementar código.
- Consulta [docs/decisions.md](docs/decisions.md) para distinguir acuerdos de decisiones pendientes. No conviertas una propuesta en una decisión aprobada.
- Las instrucciones explícitas de Pedro tienen prioridad sobre estos documentos. Si cambia una decisión, actualiza sus referencias en el mismo trabajo.
- Estado actual: MVP local React/TypeScript + FastAPI + PostgreSQL + Keycloak OAuth, ejecutable con Docker Compose. Issues de implementación: [#3](https://github.com/a10pepo/family_planner/issues/3) y [#5](https://github.com/a10pepo/family_planner/issues/5), ampliados en [#6](https://github.com/a10pepo/family_planner/issues/6). No inventes resultados de validación.

## Producto y alcance

- Aplicación web táctil para una pantalla en la nevera de una casa, con conexión permanente a internet.
- Una única cuenta de familia protegida con contraseña. Los integrantes son perfiles de la familia; no cuentas de acceso independientes.
- Tras iniciar sesión, todas las actividades son visibles y editables por la familia. «Públicas» significa compartidas dentro de la sesión familiar, no accesibles sin autenticación en internet.
- MVP confirmado: añadir integrantes; seleccionar un integrante; crear eventos para él; mover eventos en el calendario; eliminarlos; persistir los cambios.
- Eventos y tareas son conceptos distintos. Las tareas son rutinas diarias de los niños que podrán marcarse como hechas. Las tareas asignables para un día o todos los días están implementadas, con marcas independientes por persona y fecha; la progresión corresponde a versiones futuras.
- No añadir por iniciativa propia múltiples familias, roles individuales, funcionamiento offline, integraciones de calendarios o servicios de pago.
- Mantener interacción táctil con objetivos mínimos de 44 × 44 px y un número variable de integrantes.

## Límites de arquitectura

- Frontend y backend separados. El frontend consume la API; solo el backend puede acceder a la base de datos.
- La validación y las reglas de negocio se aplican en el backend, aunque la interfaz también valide para mejorar la experiencia.
- El contrato de la API debe estar documentado y comprobarse automáticamente. No romper consumidores sin una estrategia explícita de compatibilidad.
- Separar presentación, negocio y persistencia. Las reglas de negocio deben poder probarse sin navegador, base de datos real ni AWS.
- El entorno local deberá ejecutarse con Docker Compose. No depender de AWS para desarrollar o ejecutar pruebas.
- Consultar los guardrails completos en [docs/architecture.md](docs/architecture.md).

## Trabajo basado en issues de GitHub

- El seguimiento de este repositorio se realiza exclusivamente mediante GitHub Issues. No crear, abrir ni solicitar tickets en Jira (incluido CPT): CPT corresponde a otro proyecto.
- Antes de cualquier desarrollo o cambio del repositorio, localizar un issue que cubra el trabajo o crearlo. No implementar trabajo sin issue.
- Usar la etiqueta `issue` para errores o cambios de seguridad y `feature` para nuevas funcionalidades. La preparación inicial del repositorio se registra como `feature`.
- Cada issue debe explicar el problema u objetivo, el alcance y criterios de aceptación verificables. No mezclar mejoras ajenas al issue.
- Usar una rama `codex/<numero-issue>-<descripcion>`; no trabajar directamente en `main`.
- Vincular el PR al issue. Usar `Closes #<numero>` solo cuando el PR complete todo su alcance; en trabajos parciales, usar `Refs #<numero>`.
- No cerrar un issue hasta completar sus criterios de aceptación. No interpretar un issue abierto como aprobación de decisiones sensibles.
- Las plantillas están en `.github/ISSUE_TEMPLATE/` y `.github/pull_request_template.md`.
- Issue de este trabajo inicial: [#1](https://github.com/a10pepo/family_planner/issues/1).

## Consultas obligatorias

Preguntar a Pedro antes de ejecutar cualquiera de estas acciones:

- Definir la estructura de datos inicial o cambiarla: entidades, relaciones, campos persistidos, restricciones, migraciones o transformaciones de datos existentes.
- Crear, modificar o desplegar recursos de AWS que generen o aumenten costes; activar servicios externos de pago.
- Introducir cambios con riesgo de seguridad: autenticación, sesiones, manejo de contraseñas o secretos, permisos, exposición de servicios o datos y reducción de controles de seguridad.

Antes de solicitar aprobación, preparar una propuesta concreta: qué cambia, por qué, impactos, alternativas relevantes y cómo se verificará. Para costes, incluir recursos y estimación; para datos existentes, explicar migración y reversión. Registrar la respuesta en el issue o en la documentación del cambio, sin publicar información sensible.

La aprobación debe cubrir la acción concreta. Una preferencia general por AWS, una contraseña compartida o un issue etiquetado `issue` no autoriza cualquier implementación. Continuar mientras tanto con tareas independientes que sí estén autorizadas.

Los cambios rutinarios dentro del alcance y los límites acordados no necesitan nueva confirmación.

Para el MVP local Pedro ha autorizado implementar la propuesta con OAuth y usuario/contraseña. Se usa Authorization Code + PKCE, con cuenta compartida en Keycloak, y tablas de integrantes y eventos. No se implementan las sesiones opacas de la propuesta anterior. La preparación de seguridad para acceso público queda fuera de este issue; no pedir otra aprobación para los controles básicos del OAuth local ya autorizado.

La vista vigente es diaria, con una columna y cara ilustrada por integrante; el menú lateral contiene solo iconos. Las categorías de evento tienen color pastel e icono, y se guardan en `events.category` tras aprobación expresa de Pedro (issue #5). Los eventos anteriores reciben `other`; una edición sin categoría conserva la existente. La demo explícita tiene los cuatro nombres solicitados por Pedro, caras genéricas y actividades ficticias; el arranque normal no incorpora estos datos. No modificar o recrear datos familiares para preparar una demo.

Pedro aprobó expresamente la estructura del issue #6: fotos opcionales validadas y reducidas en la API, avisos por integrante y fecha, rutinas asignables para un día o todos los días y marcas por tarea/integrante/fecha. La migración `003_profiles_daily_tasks` es aditiva y conserva los datos anteriores. Archivar conserva las marcas históricas; no añadir borrado físico, analítica o servicios AWS sin un nuevo acuerdo. La edición de perfiles mantiene sus identificadores y sus eventos. Los iconos de avisos y tareas aparecen bajo las caras; el menú incluye Configuración y Tareas.

Pedro aprobó el catálogo persistente de iconos y sus referencias opcionales en tareas, avisos y eventos (issue #9). La migración `004_reusable_icons` añade `custom_icons` y campos `custom_icon_id` nullable. Omitir la referencia al editar conserva el icono; `null` recupera el icono incluido. La API valida y normaliza las imágenes a PNG de 128 × 128 con transparencia, conservando el dibujo completo. El catálogo es común y no se elimina al archivar una tarea. Los cambios de ancho y letra se aplican a eventos con horario; muestran solo el icono de categoría, conservando su nombre accesible.

Pedro aprobó «Sí, eventos familiares y archivo con restauración» y «Sí, filtrar sus eventos» (issue #11, 8 de octubre de 2026). La migración `005_family_views` añade `members.active` y `family_all_day_events` con fecha, título, icono y referencia opcional al catálogo. Retirar se confirma en la interfaz y archiva sin borrar historia; restaurar recupera la columna y sus actividades. No aceptar nuevas actividades o marcas para integrantes archivados; mantener sus asignaciones anteriores al editar una rutina compartida. La demo no repuebla perfiles archivados. Día muestra retratos grandes y rutinas verticales a su izquierda, más una línea de hora actual; Semana reúne eventos en siete columnas lunes-domingo, sin rutinas, con filtros temporales por cara. Los eventos familiares se muestran junto a la fecha y en el área de todo el día de la semana. No incorporar la integración Google Calendar evaluada anteriormente en este alcance.

## Comandos y estructura actual

- `frontend/src/`: interfaz y cliente OAuth/API. `backend/app/api.py` y `api_daily.py`: adaptadores HTTP y DTO. `backend/app/domain/`: negocio puro y puerto de repositorio. `backend/app/adapters/`: PostgreSQL y validación OAuth.
- `backend/migrations/`: migraciones Alembic. Keycloak gestiona su propio almacén de identidad; nunca accede a la base de datos del calendario.
- Demo: `python3 scripts/setup.py --demo`, solo en una instalación sin configuración; se conserva entre reinicios.
- Arranque: preparar configuración con `python3 scripts/setup.py` o su equivalente Docker del README; después `docker compose up --build -d`.
- Backend: `docker compose --profile test up -d --wait db-test` y `docker compose run --rm backend pytest -q`.
- Código: `ruff check --config backend/pyproject.toml backend scripts`; `ruff format --config backend/pyproject.toml --check backend scripts`.
- Pruebas del arranque y utilidades: `pytest -q scripts/tests`.
- Arquitectura y contrato: `python scripts/check_architecture.py`; `python scripts/export_openapi.py --check`; `npm --prefix frontend run api:check`.
- Frontend: `npm --prefix frontend ci`; `npm --prefix frontend run format:check`; `npm --prefix frontend run lint`; `npm --prefix frontend test`; `npm --prefix frontend run build`.
- Artefactos AWS: `make build-aws`; Node 24 se ejecuta dentro del constructor Docker. `make bootstrap`, `make plan preview|production`, `make deploy preview|production` y `make destroy preview` descargan Terraform 1.16.5 verificado a la caché local `build/tools` y usan el perfil AWS activo, sin cambiar herramientas globales; solicitan confirmación explícita para bootstrap, apply y destroy. Destroy solo elimina recursos Terraform y artefactos versionados de preview; conserva el bootstrap y producción.
- Navegador: `npm --prefix frontend run test:e2e`, solo contra una instancia aislada con configuración ficticia `scripts/setup.py --test`; no ejecutar sobre datos familiares reales.
- Node 24 y Python 3.12 o posterior para controles fuera de Docker. El README incluye los comandos completos.

## Validación y entrega

- Todo código nuevo debe ser comprobable automáticamente en CI. Diseñar pruebas de comportamiento, evitando pruebas que solo reproduzcan la implementación.
- El bootstrap del stack debe incluir los comandos reproducibles de instalación, formato, análisis estático, pruebas y compilación, junto con CI; documentarlos aquí y en README.
- La CI deberá verificar reglas de arquitectura y contrato API, pruebas de backend con base de datos desechable, y flujos principales de interfaz.
- Probar autenticación, edición de nombres y fotos, eventos (creación, movimiento y eliminación), avisos, rutinas (asignación y archivo), independencia de las marcas por integrante y día y persistencia después de recargar y reiniciar.
- Ejecutar los controles pertinentes antes de entregar. Si no pueden ejecutarse, indicar exactamente qué queda sin verificar.
- No sustituir pruebas automáticas por comprobaciones visuales. Verificar también la experiencia táctil cuando se cambie la interfaz.
- `main` debe recibir cambios mediante PR con CI satisfactoria. La protección de rama deberá exigir los controles cuando estos existan.
- CI/CD es un requisito del proyecto. La construcción y validación local pueden prepararse sin AWS; el despliegue real requiere definir destino y aprobar seguridad y costes antes de activarlo.
- Nunca incluir secretos o datos reales de la familia en código, imágenes, documentación, fixtures, logs o artefactos de CI.
- En la entrega, resumir lo cambiado, las verificaciones realizadas y las limitaciones pendientes. No declarar CI, protección de ramas o despliegues activos sin comprobarlos.

## Terraform AWS (issue #13)

- Pedro solicitó S3/CloudFront, DynamoDB, Lambda y Cognito, con preview y producción en la misma cuenta. No iniciar sesión por Pedro. Make usa el perfil AWS CLI que ya esté conectado, muestra los planes y exige frases de confirmación antes de crear el bootstrap o aplicar un entorno; no ejecutar esos comandos automáticamente desde una tarea de código.
- Leer [infra/README.md](infra/README.md) y [docs/aws-proposal.md](docs/aws-proposal.md). Runtime AWS aprobado: Cognito y DynamoDB mediante Lambda; Docker local conserva PostgreSQL y Keycloak. Producción inicia vacía; no se migran datos familiares ni se usa información familiar en preview.
- `infra/bootstrap/`: buckets privados de estado/artefactos, estado inicial local. `infra/environments/preview/` y `production/`: estados separados con bloqueo S3 nativo. `infra/modules/application/`: recursos compartidos parametrizados, IAM propio por entorno y login sin contraseñas en Terraform. No crear roles de despliegue/CI por iniciativa propia.
- Pedro aprobó el 9 de octubre de 2026 el runtime AWS con Cognito, Lambda y DynamoDB, incluido el esquema `FAMILY#default`, índices, excepciones y marcas; producción comienza vacía y no se migra información local. Los Makefile generan configuración local desde la sesión AWS CLI y construyen artefactos; el despliegue requiere la confirmación explícita en terminal.
- Comprobaciones sin sesión: `terraform fmt -check -recursive infra`; en las cuatro raíces, `terraform init -backend=false -input=false -lockfile=readonly` y `terraform validate`; `terraform -chdir=infra/bootstrap test`; `terraform -chdir=infra/modules/application test`; `node --test infra/tests/spa.test.mjs`. Las pruebas utilizan `mock_provider "aws"` y no acceden a recursos AWS. CI usa Terraform 1.16.5 y AWS provider 6.68.0.
- Nunca añadir estados, planes, claves, contraseñas ni configuración efectiva al repositorio. Conservar ejemplos y lockfiles. No utilizar datos familiares en preview. Los permisos de ejecución limitan el acceso a la tabla propia; administradores y credenciales de despliegue requieren revisión adicional.
