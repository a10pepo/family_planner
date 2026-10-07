# family_planner

Aplicación web de calendario familiar para una pantalla táctil en casa. Una cuenta familiar permite añadir integrantes y crear, mover y eliminar sus eventos en un calendario diario con una columna por persona.

Frontend React + TypeScript, backend FastAPI, PostgreSQL y acceso OAuth con usuario y contraseña mediante Keycloak. La API es la única vía de acceso a los datos del calendario.

## Ejecutar en local con Docker

Requisitos: Docker Desktop iniciado y Docker Compose v2.12 o posterior. No hace falta instalar Node ni Python para ejecutar la aplicación.

Desde la raíz del repositorio, prepara una vez el usuario y la contraseña familiar:

```bash
docker run --rm -it --user "$(id -u):$(id -g)" \
  -v "$PWD:/workspace" -w /workspace \
  python:3.12-alpine python scripts/setup.py
```

El asistente pide usuario y contraseña, genera credenciales locales para los servicios y crea `.env` y `.local/family-realm.json`, excluidos de Git. No sobrescribe una configuración existente. La contraseña familiar debe tener al menos 12 caracteres. Si ya tienes Python 3.12 o posterior, también puedes ejecutar `python3 scripts/setup.py`.

Construye y arranca los servicios:

```bash
docker compose up --build -d
docker compose ps
```

Abre [http://localhost:8080](http://localhost:8080). La primera vez, Keycloak puede tardar uno o dos minutos en arrancar. Pulsa **Entrar al calendario** e introduce la cuenta familiar. Si aparece el mensaje de arranque, pulsa **Volver a intentar** cuando el proveedor esté disponible.

1. Añade los integrantes desde el icono de personas del menú lateral.
2. Toca una hora en la columna de la persona, selecciona un intervalo o pulsa el «+» de esa columna para añadir un evento.
3. Elige su categoría: Colegio, Extraescolares, Médicos, Amigos u Otros. Cada categoría tiene un color pastel y un icono propio.
4. Arrastra un evento para moverlo; en pantalla táctil, mantén pulsado antes de arrastrar. También puedes pulsarlo y editar inicio, fin, título y categoría.
5. Para eliminarlo, abre el evento y confirma su eliminación. Usa **Hoy** y las flechas para cambiar de día.

Las cuatro caras ilustradas de la demo encabezan sus columnas; las instalaciones normales admiten un número variable de integrantes. Las horas se presentan en `Europe/Madrid`, configurable mediante `FAMILY_TIMEZONE` en `.env`. El formulario rechaza las horas inexistentes o ambiguas durante el cambio horario para evitar guardarlas con un desplazamiento incorrecto.

## Demo local

En un clon sin configuración, prepara la demo con el mismo asistente Docker añadiendo `--demo`:

```bash
docker run --rm --user "$(id -u):$(id -g)" \
  -v "$PWD:/workspace" -w /workspace \
  python:3.12-alpine python scripts/setup.py --demo
docker compose up --build -d
```

La demo usa `test-family` / `Fictional-test-password-42` y `DEMO_MODE=1`. Crea solo **Laura (Mamá), Pedro (Papá), Jaime (Tete) y Lucía (Teta)**, con caras ilustradas y ocho actividades ficticias para el día del primer arranque. No contiene fotografías reales. Los reinicios conservan la demo y sus cambios; no vuelven a crear los perfiles ni desplazan los eventos al día actual. Las pruebas usan la misma demo con `--test`.

El modo normal configura `DEMO_MODE=0` y empieza vacío. Activar la demo sobre una base con integrantes no los sustituye. Solo para renovar una instalación ficticia conocida, tras guardar una copia, puede ejecutarse `docker compose exec backend python -m app.demo --replace-test-fixtures`: exige el modo demo y rechaza perfiles que no sean los cuatro de la demo o los antiguos `Alex <número>` / `Sam <número>`. No utilizar este comando en una instalación familiar.

La migración de categorías conserva los eventos existentes con categoría **Otros**. No requiere borrar volúmenes.

## Parar, actualizar y consultar logs

```bash
# Consultar logs
docker compose logs -f backend identity frontend

# Parar y quitar contenedores, conservando los datos
docker compose down

# Reconstruir después de actualizar el código
docker compose up --build -d
```

Los volúmenes `calendar-data` e `identity-data` conservan actividades y cuenta OAuth entre reinicios. No ejecutes `docker compose down -v` sobre tus datos familiares: elimina los volúmenes.

Keycloak importa la cuenta solo cuando crea el realm por primera vez. Editar el archivo de importación después no cambia la contraseña existente. Para cambiarla o recuperar acceso, usa la consola local [Keycloak Admin](http://localhost:8080/auth/admin/master/console/) con `KC_ADMIN_USERNAME` y `KC_ADMIN_PASSWORD` de `.env`; selecciona el realm `family`, el usuario familiar y la pestaña **Credentials**. No hace falta borrar el volumen para cambiar una contraseña.

La configuración incluida se limita al equipo local (`127.0.0.1`); Keycloak usa su modo de desarrollo. La configuración para acceder desde la pantalla de la nevera por la red doméstica o para un despliegue público queda para un issue posterior. El cliente y la base de datos no exponen puertos adicionales. `.local/family-realm.json` contiene la contraseña inicial para importar la cuenta: conserva estos archivos fuera de Git.

## Pruebas y desarrollo

Las pruebas de backend se ejecutan dentro del contenedor contra una base de datos separada y desechable; no usan la base familiar:

```bash
docker compose --profile test up -d --wait db-test
docker compose run --rm backend pytest -q
docker compose stop db-test
```

Para desarrollar y ejecutar controles de código en el equipo, instala Python 3.12 o posterior y Node 24:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
npm --prefix frontend ci

ruff check --config backend/pyproject.toml backend scripts
ruff format --config backend/pyproject.toml --check backend scripts
python scripts/check_architecture.py
python scripts/export_openapi.py --check
npm --prefix frontend run api:check
npm --prefix frontend run format:check
npm --prefix frontend run lint
npm --prefix frontend test
npm --prefix frontend run build
```

Las pruebas de navegador requieren una instancia local aislada con la **cuenta ficticia de pruebas**. No las ejecutes contra tu calendario familiar: añaden integrantes y crean, mueven y eliminan eventos de prueba. En un clon o worktree sin configuración previa:

```bash
python3 scripts/setup.py --test
docker compose up --build -d
python3 scripts/wait_for_app.py
cd frontend
npm ci
npx playwright install chromium
npm run test:e2e
```

El asistente `--test` configura únicamente datos ficticios (`test-family` / `Fictional-test-password-42`). Nunca se usan como valores predeterminados del arranque normal.

## CI y entrega

[GitHub Actions](.github/workflows/ci.yml) valida que la PR esté vinculada a un issue etiquetado, comprueba formato, análisis estático, tipos, límites de arquitectura y contrato API, ejecuta pruebas de backend con PostgreSQL desechable y pruebas de navegador con OAuth real, y verifica un reinicio de servicios y la persistencia de la demo y las categorías.

Tras un merge a `main`, empaqueta las imágenes de aplicación validadas en un artefacto identificado por el commit. No activa merge automático ni un despliegue remoto. La protección de ramas y el destino de despliegue público siguen pendientes; no se crean recursos AWS.

Para ejecutar una entrega ya validada sin reconstruir, descarga el artefacto de esa ejecución de Actions y extrae el archivo `family-planner-images.tar.gz`. Con la configuración local preparada, carga las imágenes y sustituye `SHA_DEL_COMMIT` por el commit del artefacto:

```bash
gzip -dc family-planner-images.tar.gz | docker load
APP_VERSION=SHA_DEL_COMMIT docker compose -f compose.yaml -f compose.images.yaml up -d --no-build
```

Las imágenes se etiquetan `family-planner-backend:<commit>` y `family-planner-frontend:<commit>`. La configuración OAuth y los volúmenes locales siguen siendo propios de cada instalación; no forman parte del artefacto.

## Documentación

- [AGENTS.md](AGENTS.md): instrucciones de trabajo, issues, aprobaciones y validación.
- [application.md](application.md): alcance inicial y referencia de interfaz.
- [Guardrails de arquitectura](docs/architecture.md): separación frontend/backend, API, datos y requisitos de CI/CD.
- [Decisiones y pendientes](docs/decisions.md): acuerdos confirmados y preguntas antes de implementar.
- [API v1](docs/api.md): OAuth, operaciones, fechas y evolución del contrato.

## Estado

MVP local implementado en el [issue #3](https://github.com/a10pepo/family_planner/issues/3); vista diaria y demo actualizadas en el [issue #5](https://github.com/a10pepo/family_planner/issues/5). Las tareas diarias, el seguimiento de progreso y el despliegue público pertenecen a versiones posteriores.

## Contribuir

Todo cambio parte de un issue en [GitHub](https://github.com/a10pepo/family_planner/issues), etiquetado `feature` para nuevas funcionalidades o `issue` para errores y cambios de seguridad. Consultar `AGENTS.md` antes de empezar y vincular el PR al issue.
