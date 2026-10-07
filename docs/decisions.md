# Decisiones y pendientes

Fuente: respuestas de Pedro Nieto del 7 de octubre de 2026. Configuración inicial: [issue #1](https://github.com/a10pepo/family_planner/issues/1); implementación: [issue #3](https://github.com/a10pepo/family_planner/issues/3).

## MVP implementado

| Tema | Decisión |
| --- | --- |
| Alcance | Añadir integrantes y crear, mover, editar y eliminar sus eventos. |
| Interfaz | Calendario diario táctil con una columna y cara ilustrada por integrante; menú lateral de iconos y creación desde el calendario. |
| Acceso | Una cuenta familiar con usuario y contraseña; OAuth con Authorization Code + PKCE. |
| Identidad | Keycloak local con cuenta compartida; sin cuentas separadas para los integrantes. |
| Visibilidad | Actividades compartidas y editables dentro de la cuenta familiar. |
| Stack | React y TypeScript, Vite y FullCalendar; FastAPI y SQLAlchemy; PostgreSQL y Alembic. |
| Arquitectura | Frontend y backend separados; solo backend accede a la base de datos del calendario. |
| Contrato | OpenAPI bajo /api/v1; tipos del cliente generados y comprobados en CI. |
| Datos | Tablas members y events, con categoría de evento; identidades y sesiones administradas por Keycloak. |
| Movimiento | Cambia fecha y hora conservando integrante; formulario y redimensionado permiten cambiar duración. |
| Idiomas | Interfaz y documentación en español; código en inglés. Valor inicial adoptado en este MVP. |
| Zona | Europe/Madrid configurable; instantes persistidos con zona horaria. |
| Ejecución | Docker Compose; solo se expone localhost:8080. |
| Calidad | CI con arquitectura, contrato, formato, tipos, pruebas, Docker y OAuth real. |
| Entrega | Imágenes validadas como artefacto tras merge a main; despliegue público y merge automático pendientes. |
| Seguimiento | Issues de GitHub con etiquetas feature o issue. |

## Autorización y ajuste de la propuesta

Pedro solicitó implementar la propuesta y crear la PR del issue #3, con la corrección expresa de que el cliente debe usar OAuth con usuario y contraseña. También indicó que la preparación de seguridad para acceso público se abordará al desplegar. La implementación usa los integrantes y eventos propuestos, sustituyendo las sesiones de aplicación por el proveedor OAuth; no hay contraseña familiar en PostgreSQL ni tabla de sesiones de la aplicación.

El detalle final está en [mvp-proposal.md](mvp-proposal.md), [api.md](api.md) y README. No se despliega AWS ni se publica la aplicación en internet.

## Ajuste de la demo y vista diaria (issue #5)

Pedro solicitó sustituir la demo por Laura (Mamá), Pedro (Papá), Jaime (Tete) y Lucía (Teta), con caras sobre sus columnas, vista de día por defecto, colores pastel por categoría e iconos y menú estrecho sin textos. Las caras son ilustraciones genéricas, sin fotografías; las actividades son ficticias. Estos nombres se incluyen por solicitud expresa de Pedro.

Pedro aprobó expresamente añadir la categoría persistente. La migración `002_event_category` añade `events.category`, con `school`, `activities`, `medical`, `friends` y `other`; los eventos actuales quedan en `other`. El alta que no envía categoría usa `other`; la edición que no la envía conserva la existente. La reversión quita la columna y sus valores, sin borrar eventos. Pruebas comprueban migración, validación y conservación de la categoría al mover.

El modo demo es explícito e idempotente; no sustituye bases con perfiles existentes. La renovación de esta demo local se limitó a los antiguos perfiles ficticios de las pruebas, tras guardar una copia en `.local`, excluida de Git. Una instalación normal sigue empezando vacía y permite más integrantes.

## Próximas versiones

- Rutinas diarias de los niños y marcado como completadas; progreso posterior.
- Eventos compartidos, recurrencias y vistas semanales o mensuales si se aprueba su alcance.
- Cambiar el integrante asignado a un evento, gestionar perfiles existentes y fotos.
- Configuración para la pantalla de la nevera por red doméstica y despliegue público, incluyendo HTTPS y OAuth para su URL real.
- Destino de despliegue AWS, estimación de costes y seguridad para acceso público.
- Protección de main con checks obligatorios, política de revisión y eventual merge automático.
- Tablero de GitHub Projects si se desea; actualmente se usan los issues del repositorio.

Los cambios de datos posteriores siguen requiriendo consulta. Los requisitos de versiones futuras no se incorporan automáticamente al MVP por aparecer en la referencia UI inicial.
