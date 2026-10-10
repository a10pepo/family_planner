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
| Datos | Tablas members (foto opcional) y events (categoría), all_day_notices, tasks, task_assignments y task_completions; identidades y sesiones administradas por Keycloak. |
| Movimiento | Cambia fecha y hora conservando integrante; formulario y redimensionado permiten cambiar duración. |
| Idiomas | Interfaz y documentación en español; código en inglés. Valor inicial adoptado en este MVP. |
| Zona | Europe/Madrid configurable; instantes persistidos con zona horaria. |
| Ejecución | Docker Compose; por defecto solo se expone localhost:8080. `scripts/configure_lan_tls.py` permite pruebas HTTPS en la red doméstica conservando PKCE. |
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

## Configuración y rutinas (issue #6)

Pedro aprobó expresamente: «Sí, implementar esta estructura», en respuesta a la propuesta de fotos opcionales de integrantes, avisos de día completo y tareas asignables para un día o todos los días con estado por persona y fecha. La propuesta indicaba validación y reducción de fotos en la API, conservación de integrantes y eventos, archivo de tareas sin perder marcas anteriores y ausencia de servicios AWS.

La migración `003_profiles_daily_tasks` añade `members.photo_data` nullable y cuatro tablas nuevas. Las fotos se almacenan como JPEG de 256 × 256 en PostgreSQL; no hay almacenamiento externo ni peticiones a URLs de fotografías. El navegador admite archivos de 5 MB y prepara una imagen pequeña; la API verifica independientemente JPG/PNG/WebP de hasta 2 MB y 20 millones de píxeles, recorta, elimina metadatos y reencodea con Pillow. La ausencia del campo en una edición conserva la foto; `null` la quita.

Los avisos tienen integrante, fecha local, título e icono. Las rutinas tienen icono, título, frecuencia (`daily`/`once`), fecha inicial, asignaciones y estado activo. La fecha corresponde al día del calendario familiar, sin hora. Las marcas se guardan con clave única tarea/integrante/fecha; escribir el mismo estado es idempotente. Una edición de la definición aplica a todas sus fechas y conserva las marcas incluso al quitar y volver a asignar un integrante. Archivar oculta la rutina y no elimina sus registros de completado. La progresión sigue pendiente.

La reversión de la migración elimina exclusivamente la columna de fotos y las nuevas tablas, perdiendo sus fotos, avisos, tareas y marcas; conserva integrantes, eventos y categorías. Guardar copia antes de revertir. Pruebas con PostgreSQL desechable comprueban que la actualización mantiene los datos previos y coincide con los modelos de persistencia.

La demo añade tres rutinas diarias para Jaime y Lucía y dos avisos sintéticos. Las demos reconocidas sin ninguna tarea se amplían una vez sin sustituir perfiles o eventos; las rutinas archivadas no se recrean. Las instalaciones normales no reciben fixtures.

## Catálogo de iconos y legibilidad (issue #9)

Pedro autorizó «Sí, guardar el catálogo y las referencias» y confirmó el uso en tareas, avisos y eventos. También precisó que los bloques a ensanchar y mostrar con letra mayor son los eventos con horario.

La migración `004_reusable_icons` añade `custom_icons` (UUID, nombre, imagen normalizada y fecha de creación) y una referencia nullable en `tasks`, `all_day_notices` y `events`. Los elementos existentes reciben `null` y conservan su icono incluido. La omisión de la referencia en una edición la conserva, mientras que `null` vuelve a la opción incluida. Se validan las referencias en el dominio y con claves foráneas. Las categorías y los colores de eventos no cambian al elegir una imagen personalizada.

El navegador admite JPG/PNG/WebP hasta 5 MB y prepara una imagen pequeña; la API verifica independientemente un máximo de 2 MB y 20 millones de píxeles y reencodea un PNG de 128 × 128, sin metadatos, preservando proporciones y transparencia. Se almacena en PostgreSQL, sin servicios AWS ni URLs externas. El alta del icono es independiente del guardado del elemento; cancelar su edición conserva la nueva opción global. No se implementan borrado ni edición del catálogo en este alcance.

La reversión retira exclusivamente las referencias y el catálogo, perdiendo las imágenes personalizadas y recuperando los iconos incluidos; conserva actividades, integrantes y marcas. Guardar copia antes de revertir. Pruebas verifican migración, reutilización entre los tres tipos, errores de entrada y referencias, compatibilidad con ediciones anteriores y persistencia al recargar y reiniciar.

## Vistas y gestión familiar (issue #11)

Pedro autorizó el 8 de octubre de 2026 «Sí, eventos familiares y archivo con restauración» y confirmó «Sí, filtrar sus eventos». La propuesta incluía conservación del historial, reversión que elimina los nuevos eventos familiares y vuelve a mostrar a integrantes archivados, sin AWS ni cambios de autenticación.

La migración `005_family_views` añade `members.active` (true para datos existentes) y `family_all_day_events` (UUID, fecha local, título, icono incluido y referencia nullable a `custom_icons`). Las fechas son de un día, sin zona horaria ni repetición anual automática. Los cumpleaños y otras actividades globales se muestran junto a la fecha en Día y en el área de todo el día en Semana. El icono puede reutilizar el catálogo común; omitirlo al editar conserva la referencia y null recupera la opción incluida.

Retirar un perfil equivale a archivo, con confirmación en Configuración. Las consultas ordinarias solo incluyen integrantes activos y sus actividades; `include_archived=true` permite gestionar y restaurar perfiles. Los eventos, avisos, asignaciones y marcas permanecen en sus tablas. No se crean actividades ni se completan rutinas para un perfil archivado. La edición de rutinas compartidas admite sus asignaciones previas archivadas, conservándolas hasta restaurar al integrante. Las rutinas que solo tienen integrantes archivados no aparecen en la lista activa. Se pueden archivar todos los integrantes sin que la demo los repueble al reiniciar.

Semana comienza en lunes y acaba en domingo, reúne eventos por día e identifica a la persona en cada tarjeta. Las caras alternan filtros de eventos con horario; los eventos familiares siguen visibles y las rutinas nunca se incluyen. Los filtros son temporales, se conservan durante la navegación de esa sesión y se reinician al recargar. La línea del día actual avanza cada 15 segundos; la semanal usa el indicador de FullCalendar. Se mantienen las interacciones de edición, arrastre y duración.

El downgrade borra exclusivamente `family_all_day_events` y `members.active`; pierde los nuevos eventos globales y vuelve a mostrar todos los perfiles, conservando actividades anteriores y marcas. Guardar copia antes de revertir. Las pruebas usan PostgreSQL y un stack OAuth con datos ficticios, comprueban archivo/restauración, migración, confirmaciones, filtros, hora actual y persistencia tras recargar y reiniciar.

## Próximas versiones

- Seguimiento y progresión histórica de las rutinas.
- Eventos compartidos con horario y vista mensual si se aprueba su alcance.
- Cambiar el integrante asignado a un evento, reasignación y gestión avanzada de perfiles.
- Configuración para la pantalla de la nevera por red doméstica y despliegue público, incluyendo HTTPS y OAuth para su URL real.
- Adaptación y puesta en marcha en AWS, revisión del coste real y seguridad para acceso público.
- Protección de main con checks obligatorios, política de revisión y eventual merge automático.
- Tablero de GitHub Projects si se desea; actualmente se usan los issues del repositorio.

Los cambios de datos posteriores siguen requiriendo consulta. Los requisitos de versiones futuras no se incorporan automáticamente al MVP por aparecer en la referencia UI inicial.

## Eventos recurrentes (issue #18)

Pedro aprobó el 9 de octubre de 2026 añadir series recurrentes y excepciones, manteniendo intactos los eventos puntuales existentes. La migración aditiva `006_recurring_events` incorpora `event_series` y `event_exceptions`; la expansión es por rango consultado y no crea filas por cada fecha futura. La reversión elimina las series y sus excepciones, sin cambiar integrantes ni eventos puntuales.

Una serie guarda integrante, título, fecha y hora local de inicio, duración, zona IANA, frecuencia diaria/semanal/mensual, intervalo, días semanales opcionales, categoría e icono opcional. El final se expresa como nunca, fecha inclusiva o cantidad total de ocurrencias. Para series semanales sin días se usa el día de inicio. En la frecuencia mensual se repite el mismo número de día y se omiten los meses que no lo contienen. La hora de pared se mantiene en la zona configurada a través de cambios DST; el intervalo de duración se suma a cada inicio local.

Una excepción se identifica por serie, fecha local de inicio original y hora local de inicio original. Puede cancelar esa ocurrencia o sobrescribir hora, duración, título, categoría e icono. Editar la serie cambia su regla; eliminarla elimina también sus excepciones. El calendario consulta y expande únicamente el rango visible, y no permite arrastrar una ocurrencia recurrente como si fuera un evento puntual.

## Acceso desde la red doméstica (issue #25)

Pedro solicitó habilitar el acceso desde una tablet en la misma red doméstica para probar la aplicación, y aprobó HTTPS local al descubrir que PKCE no puede usar Web Crypto desde una dirección HTTP privada. La publicación del puerto 8080 sigue limitada a `127.0.0.1`; `scripts/configure_lan_tls.py` configura un certificado local para la IPv4 elegida, actualiza el origen del cliente Keycloak sin borrar su volumen y `compose.lan-tls.yaml` publica HTTPS en el puerto 8443. Pedro instala y confía manualmente en la tablet la CA pública; la clave privada de CA queda en `.local`. No configura acceso público, router ni DNS.

## Infraestructura AWS (issue #13)

Pedro eligió S3/CloudFront para la web, DynamoDB para los datos, Lambda para la API y Cognito para el acceso, con preview y producción separados en una misma cuenta. El runtime AWS ya implementa ese destino; Docker local conserva PostgreSQL y Keycloak y no depende de AWS. Los comandos Make usan la sesión AWS CLI activa y no inician sesión.

El 9 de octubre de 2026 Pedro aprobó el esquema DynamoDB: una tabla por entorno; `PK=FAMILY#default` y `SK=TIPO#id` para entidades familiares; GSIs para intervalos de eventos, elementos por día, series por integrante y marcas por día; excepciones con `PK=SERIES#id`; marcas con `PK=MEMBER#id`; escrituras condicionadas/transacciones, sin `Scan`; producción vacía sin migración. Cognito será el proveedor AWS; Keycloak se mantiene solo para Docker local. No se migran datos ni se hace despliegue real en esta implementación. Los detalles están en [aws-proposal.md](aws-proposal.md) e [infra/README.md](../infra/README.md).
