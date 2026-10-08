# API v1

El contrato versionado está en [openapi.json](openapi.json). Con Compose abierto, la documentación interactiva está en `http://localhost:8080/api/docs`.

## Acceso

El cliente inicia sesión en Keycloak con la cuenta familiar mediante OAuth 2.0 / OpenID Connect, Authorization Code y PKCE S256. El formulario de usuario y contraseña pertenece al proveedor de acceso. El cliente conserva los tokens solo en memoria y envía `Authorization: Bearer <access_token>` a la API. El flujo password grant está desactivado.

El backend verifica firma RS256, caducidad, emisor, audiencia `family-api` y rol `family-app`. Las cuentas administrativas de Keycloak no reciben acceso a los datos familiares por ser administradoras. La sesión SSO dura hasta 30 días; los tokens de acceso duran 5 minutos y se renuevan antes de las peticiones. Al cerrar sesión se elimina la sesión SSO y se borran los tokens del cliente; un token ya emitido puede ser válido hasta su caducidad.

## Operaciones

| Método | Ruta | Comportamiento |
| --- | --- | --- |
| GET | `/api/health` | Disponibilidad de la base de datos y de la migración; público. |
| GET | `/api/v1/config` | Zona familiar y configuración pública de OAuth; no devuelve secretos. |
| GET | `/api/v1/members` | Lista de integrantes activos; `include_archived=true` añade los archivados. |
| DELETE | `/api/v1/members/{id}` | Archivar integrante conservando historia (204), idempotente. |
| POST | `/api/v1/members/{id}/restore` | Restaurar el mismo integrante e historia, idempotente. |
| POST | `/api/v1/members` | Alta con `name` y `color`; devuelve 201. |
| GET / POST | `/api/v1/family-events` | Listar con `start` y `end` (fechas) / crear evento familiar de todo el día (201). |
| PUT / DELETE | `/api/v1/family-events/{id}` | Editar fecha, título e icono / eliminar evento familiar (204). |
| GET / POST | `/api/v1/icons` | Listar catálogo común / subir nombre e imagen (201). |
| PUT | `/api/v1/members/{id}` | Editar nombre y foto opcional, manteniendo ID y color. |
| GET | `/api/v1/events?start=…&end=…&member_id=…` | Eventos que se solapan con el intervalo; integrante opcional. |
| POST | `/api/v1/events` | Alta con integrante, título, inicio, fin y categoría; devuelve 201. |
| PUT | `/api/v1/events/{id}` | Cambiar título, fecha, hora, duración y categoría; mantiene el integrante. |
| DELETE | `/api/v1/events/{id}` | Elimina un evento; devuelve 204. |
| GET / POST | `/api/v1/notices` | Listar por `day=YYYY-MM-DD` / crear aviso para integrante y fecha (201). |
| PUT / DELETE | `/api/v1/notices/{id}` | Editar fecha, título e icono / eliminar (204). |
| GET / POST | `/api/v1/tasks` | Listar rutinas activas / crear con título, icono, frecuencia, fecha inicial e integrantes (201). |
| PUT / DELETE | `/api/v1/tasks/{id}` | Editar definición y asignaciones / archivar conservando marcas (204). |
| GET | `/api/v1/task-occurrences?day=YYYY-MM-DD` | Rutinas de esa fecha expandidas por integrante, con estado `completed`. |
| PUT | `/api/v1/tasks/{id}/completion` | Establecer estado con `member_id`, `day` y booleano `completed`; devuelve la ocurrencia. |

Todas las operaciones de integrantes, eventos, avisos y tareas requieren un token válido. Los identificadores son UUID. Las fechas de los eventos deben incluir desplazamiento UTC; la persistencia usa PostgreSQL `timestamptz`. El intervalo es de inicio incluido y final excluido, con eventos que se solapan incluidos aunque empiecen antes. El fin siempre debe ser posterior al inicio. Un evento puede cruzar la medianoche o un cambio horario.

Los errores usan `detail`: 401 para acceso ausente o inválido, 403 para cuenta sin rol, 404 para entidad inexistente, 422 para datos inválidos y 503 si un servicio necesario no está disponible. La respuesta de validación 422 puede contener una lista de errores de campos.

## Categorías

`category` usa `school` (Colegio), `activities` (Extraescolares), `medical` (Médicos), `friends` (Amigos) u `other` (Otros). Se devuelve en todos los eventos. El alta sin categoría usa `other`; una edición que omite la categoría o envía `null` conserva el valor previo, para mantener compatibilidad con clientes anteriores. Un valor desconocido se rechaza con 422. La migración añade el campo y asigna `other` a los eventos existentes sin eliminarlos.

## Perfiles y fotos

`PUT /members/{id}` recibe `name` (1–80 caracteres tras recortar) y `photo_data` opcional. Omitir la foto conserva la existente; enviar `null` la elimina. Para subirla se envía un data URI en base64 de JPEG, PNG o WebP. La API limita la imagen a 2 MB y 20 millones de píxeles, verifica su contenido y guarda una copia JPEG de 256 × 256 sin metadatos. La interfaz admite archivos de hasta 5 MB porque los reduce antes del envío. `GET /members` devuelve la foto normalizada o `null`; los nuevos integrantes empiezan sin foto. No se modifica el color ni el identificador y se mantienen eventos y asignaciones.

`active` aparece en las respuestas de integrantes. Archivar no borra datos: eventos, avisos, asignaciones y marcas se ocultan y se recuperan al restaurar. No se permiten nuevas actividades ni marcas de un integrante archivado. La edición de una rutina puede conservar asignaciones previas archivadas, pero no añadir otras archivadas. Las rutinas activas sin ninguna asignación a un integrante activo no aparecen en GET /tasks.

## Eventos familiares de día completo

`family-events` usa `{id, day, title, icon, custom_icon_id}`. `day` es una fecha local `YYYY-MM-DD` y el título admite 1–80 caracteres. Iconos incluidos: `birthday`, `celebration`, `trip`, `other`. Se comparte el catálogo de imágenes con las demás actividades y se aplican las reglas de omisión/null en ediciones. No tiene integrante, hora ni repetición automática. GET requiere `start` incluido y `end` excluido; un intervalo vacío o invertido devuelve 422. Son operaciones autenticadas con la misma cuenta familiar.

## Avisos y rutinas

Un aviso contiene `member_id`, `day`, `title` (1–80) e `icon`: `uniform`, `tracksuit`, `trip` u `other`. Son fechas de calendario familiar sin hora ni conversión UTC. Una edición mantiene el integrante; un aviso no se repite automáticamente.

Una rutina contiene `title` (1–80), `icon` (`tooth`, `backpack`, `bed`, `other`), `frequency` (`daily` por defecto o `once`), `starts_on` y `member_ids` (1–100 integrantes existentes, sin duplicados). `daily` aparece desde la fecha inicial inclusive; `once` aparece solo ese día. No genera filas de eventos repetidos. Cada ocurrencia devuelve `task_id`, `member_id`, `day`, título, icono y estado.

La escritura de una marca establece el estado solicitado: repetir `completed=true` no lo alterna ni duplica registros. Una persona sin asignación, una fecha fuera de la rutina o una tarea archivada se rechazan con 422. Un identificador inexistente produce 404. El estado de otro integrante o día no cambia. Editar la definición conserva las marcas y afecta a todas las fechas; cambiar asignaciones oculta los iconos de quienes se quitan sin eliminar sus marcas. Archivar es idempotente para un ID existente, oculta la rutina en todas las fechas y conserva las marcas almacenadas; no hay endpoint de analítica ni de borrado físico.

## Catálogo común de iconos

`GET /icons` lista `{id, name, image_data}`. `POST /icons` recibe nombre de 1–80 caracteres e imagen base64 en data URI JPG, PNG o WebP; requiere OAuth igual que las actividades. La API verifica el contenido, máximo 2 MB y 20 millones de píxeles, conserva proporciones y transparencia y devuelve PNG de 128 × 128 sin metadatos. El cliente puede admitir archivos mayores (hasta 5 MB) porque los reduce antes del envío. El icono queda en el catálogo aunque no se guarde después una actividad; no hay endpoint de borrado en este alcance.

Eventos, eventos familiares, avisos, tareas y ocurrencias añaden `custom_icon_id` nullable. El alta puede usar un UUID del catálogo o `null` para el icono incluido. En una edición, omitir el campo conserva la referencia y enviar `null` la elimina. Una referencia desconocida produce 404 y no guarda el elemento. Archivar una tarea conserva el icono global y sus marcas. La categoría y color de un evento se mantienen independientes de su icono personalizado. Las respuestas del catálogo contienen las imágenes normalizadas; las actividades devuelven solamente su referencia.

## Evolución del contrato

Para un cambio aprobado:

```bash
python scripts/export_openapi.py
npm --prefix frontend run api:generate
```

La CI compara el contrato con la API y los tipos generados del cliente, evitando que diverjan. El endpoint público sigue siendo `/api/v1`; un cambio incompatible requiere un issue y estrategia de compatibilidad.
