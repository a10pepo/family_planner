# Decisión de implementación del MVP — issue #3

Estado: implementación autorizada por Pedro Nieto, con la corrección de usar OAuth con usuario y contraseña. La preparación de seguridad para acceso público queda para el despliegue posterior.

## Implementación elegida

- React + TypeScript + Vite y FullCalendar para vista semanal, arrastre y redimensionado táctil.
- FastAPI y OpenAPI bajo /api/v1, SQLAlchemy y migraciones Alembic.
- PostgreSQL para integrantes y eventos, accesible solo por backend.
- Keycloak en Docker para una única cuenta familiar. Authorization Code con PKCE S256; el usuario introduce las credenciales en el proveedor y el cliente usa tokens Bearer solo en memoria.
- nginx sirve la interfaz y dirige /api al backend y /auth a Keycloak. Solo publica 127.0.0.1:8080.
- Interfaz y documentación en español, código en inglés; zona familiar Europe/Madrid configurable.

## Estructura inicial

No había datos previos. La migración 001_calendar crea:

| Tabla | Campos y restricciones |
| --- | --- |
| members | id UUID, name de 1–80 caracteres, color hexadecimal, created_at con zona horaria. |
| events | id UUID, member_id obligatorio con referencia a integrante, title de 1–200 caracteres, starts_at, ends_at, created_at, updated_at con zona horaria; fin posterior al inicio e índice por integrante y fechas. |

Las entidades de dominio son independientes de HTTP y PostgreSQL. Keycloak conserva cuenta y sesiones en su propio volumen; la propuesta inicial de sesiones opacas y contraseña Argon2 administradas por la aplicación fue sustituida por la petición de OAuth. No existen tablas de cuentas, sesiones o tareas de la aplicación.

## Comportamiento y límites

Se pueden añadir integrantes, seleccionarlos, crear eventos, moverlos por arrastre o por el formulario, cambiar título y duración y eliminarlos con confirmación. Mover conserva el integrante; no hay recurrencias, eventos compartidos ni rutinas diarias. La API acepta instantes con desplazamiento UTC y PostgreSQL los almacena con zona horaria; la interfaz usa la zona familiar y rechaza entradas ambiguas o inexistentes en cambios horarios.

Las actividades son visibles y editables desde la cuenta familiar. El backend verifica firma, emisor, audiencia, caducidad y rol del token. Keycloak gestiona la contraseña y limita intentos de login. La sesión SSO dura hasta 30 días y el token de acceso 5 minutos; [api.md](api.md) detalla el cierre de sesión.

El modo local de Keycloak no constituye una configuración pública. .env y .local/ están excluidos de Git y de las imágenes. La configuración inicial del proveedor contiene la contraseña elegida para importarla por primera vez; el directorio local tiene acceso restringido. Las pruebas usan una cuenta explícitamente ficticia y bases separadas.

## Verificación y entrega

CI comprueba trazabilidad al issue, formato, análisis estático, tipos, arquitectura, contrato, pruebas backend con PostgreSQL y pruebas de navegador contra OAuth real; construye y arranca Compose, y comprueba un reinicio de servicios. Tras merge a main, empaqueta las imágenes validadas para entrega local. No configura merge automático, protección de ramas ni despliegue remoto.

README documenta preparación, arranque, pruebas, logs, parada, conservación de datos y cambio de contraseña. No se crean recursos AWS ni servicios de pago.
