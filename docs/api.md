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
| GET | `/api/v1/members` | Lista de integrantes. |
| POST | `/api/v1/members` | Alta con `name` y `color`; devuelve 201. |
| GET | `/api/v1/events?start=…&end=…&member_id=…` | Eventos que se solapan con el intervalo; integrante opcional. |
| POST | `/api/v1/events` | Alta con integrante, título, inicio y fin; devuelve 201. |
| PUT | `/api/v1/events/{id}` | Cambiar título, fecha, hora y duración; mantiene el integrante. |
| DELETE | `/api/v1/events/{id}` | Elimina un evento; devuelve 204. |

Todas las operaciones de integrantes y eventos requieren un token válido. Los identificadores son UUID. Las fechas de entrada deben incluir desplazamiento UTC; la persistencia usa PostgreSQL `timestamptz`. El intervalo es de inicio incluido y final excluido, con eventos que se solapan incluidos aunque empiecen antes. El fin siempre debe ser posterior al inicio. Un evento puede cruzar la medianoche o un cambio horario.

Los errores usan `detail`: 401 para acceso ausente o inválido, 403 para cuenta sin rol, 404 para entidad inexistente, 422 para datos inválidos y 503 si un servicio necesario no está disponible. La respuesta de validación 422 puede contener una lista de errores de campos.

## Evolución del contrato

Para un cambio aprobado:

```bash
python scripts/export_openapi.py
npm --prefix frontend run api:generate
```

La CI compara el contrato con la API y los tipos generados del cliente, evitando que diverjan. El endpoint público sigue siendo `/api/v1`; un cambio incompatible requiere un issue y estrategia de compatibilidad.
