# Definición de producto y referencia UI/UX

## Alcance vigente

Decisiones de Pedro Nieto del 7 de octubre de 2026, implementadas en los issues [#3](https://github.com/a10pepo/family_planner/issues/3) y [#5](https://github.com/a10pepo/family_planner/issues/5):

- Calendario familiar táctil para una pantalla doméstica en la nevera, con conexión permanente a internet.
- Una única cuenta con usuario y contraseña mediante OAuth, Authorization Code y PKCE. Todos los integrantes y sus actividades son visibles y editables dentro de la sesión familiar.
- Añadir integrantes, crear eventos para ellos y mover, editar o eliminar eventos, conservando los cambios.
- Frontend y backend separados; la API del backend es la única vía de acceso del cliente a los datos.
- Docker Compose en local; AWS será un destino futuro.

## Pantalla principal

La vista por defecto es **Día**. Cada columna corresponde a un integrante y muestra su foto o cara ilustrada ampliada, nombre y apodo sobre sus eventos. Las rutinas tienen iconos grandes a la izquierda de la cara, en una cuadrícula vertical que admite varias filas; tocarlos marca o desmarca la tarea. Se elimina el título «Nuestro calendario» y los rótulos como «LA FAMILIA». La fecha, **Hoy** y las flechas permiten navegar entre días.

El menú izquierdo es estrecho y contiene únicamente iconos, con nombres accesibles para lectores de pantalla: calendario, Eventos recurrentes, Tareas, Configuración (engranaje), añadir integrante y cerrar sesión. Los eventos puntuales se añaden tocando una hora o seleccionando un intervalo en la columna correspondiente. El «+» de la cabecera ofrece la misma acción para teclado y pantalla táctil. Eventos permite crear y administrar series recurrentes.

Las tarjetas muestran horario, título con letra más grande e icono de categoría, aprovechando el ancho disponible. El nombre de categoría se conserva en la leyenda, tooltip y descripción accesible; no aparece dentro de la tarjeta. El color depende de la categoría, con una paleta pastel:

| Categoría | Color | Icono |
| --- | --- | --- |
| Colegio | Azul | Birrete |
| Extraescolares | Amarillo | Balón |
| Médicos | Rosa | Cruz |
| Amigos | Lila | Corazón |
| Otros | Verde | Estrella |

La categoría se guarda en cada evento. Los eventos anteriores conservan sus datos y reciben la categoría Otros. El formulario permite editar la categoría junto con el título, inicio y fin.

Arrastrar un evento cambia su horario, manteniendo el integrante y la categoría. La pulsación prolongada permite el arrastre táctil. La edición por formulario es una alternativa accesible. Para borrar se pide confirmación.

Los controles tienen un objetivo mínimo de 44 × 44 px. En pantallas estrechas, el calendario desplaza sus columnas horizontalmente y conserva las caras sobre ellas y una escala horaria común.

## Demo

Contiene exactamente Laura (Mamá), Pedro (Papá), Jaime (Tete) y Lucía (Teta), por solicitud expresa de Pedro. Usa caras ilustradas genéricas y actividades ficticias. No requiere fotografías familiares. Una instalación normal empieza vacía y admite un número variable de integrantes.

## Configuración, avisos y tareas (issue #6)

Configuración permite editar nombre y foto de cada integrante, manteniendo sus eventos y asignaciones. La foto es opcional: elegir JPG, PNG o WebP, recortar al centro y guardar; quitarla recupera la ilustración.

Debajo del conjunto de cara y tareas hay una fila de avisos de día completo (uniforme, chándal, excursión u otro) para esa persona y fecha. Se añaden desde su «+» y se editan o eliminan pulsando el icono. Se muestran separados de los eventos con horario.

Tareas permite crear y editar rutinas con icono, título, integrantes y frecuencia: todos los días desde una fecha o solo un día. Los iconos se muestran a la izquierda de sus integrantes en el calendario diario. Tocarlos marca o desmarca la tarea para esa persona en el día seleccionado; un check y el color verde indican que está hecha. Al navegar al día siguiente las marcas son independientes. Archivar oculta la rutina y conserva sus marcas para un seguimiento futuro; editar la definición se aplica a todas las fechas conservando las marcas.

Pedro aprobó la migración de estos datos, conservando los integrantes y eventos actuales y sin añadir servicios AWS.

## Iconos reutilizables (issue #9)

Los editores de tareas, avisos y eventos comparten un catálogo de iconos. Subir un fichero validado añade una opción persistente para cualquier integrante y cualquiera de esos formularios. El icono se guarda al subirlo; cancelar el formulario no lo retira del catálogo. Guardar el elemento aplica la selección. Se mantienen las opciones incluidas, las categorías y sus colores, las actividades y las marcas de tareas.

## Vistas y gestión familiar (issue #11)

Día sigue siendo la vista inicial. Una línea común muestra la hora actual en la zona de la familia, se actualiza cada 15 segundos y solo aparece en la fecha de hoy. Los eventos familiares de día completo, como cumpleaños, se muestran junto a la fecha; se añaden desde su «+» y permiten editar fecha, título e icono o eliminar con confirmación. El catálogo de imágenes es compartido con el resto de actividades. Una fecha no implica repetición anual automática.

Semana muestra lunes a domingo, con una columna por día que reúne los eventos con horario de todos los integrantes, tarjetas más compactas y el nombre de la persona. Las rutinas diarias no aparecen. Tocar la cara de un integrante muestra u oculta sus eventos, sin cambiar datos ni ocultar eventos familiares. Los filtros se mantienen al cambiar de día a semana y al navegar; recargar recupera todos los integrantes. El área de todo el día contiene los eventos familiares de cada fecha. Se puede crear un evento desde una hora vacía, editarlo, arrastrarlo y ajustar su duración. La navegación avanza o retrocede semanas completas.

Configuración permite retirar un integrante tras una confirmación que explica el archivo. Desaparece su columna y dejan de mostrarse sus actividades y ocurrencias; se conservan perfil, eventos, avisos, asignaciones y marcas. Se puede restaurar desde Integrantes archivados. Se admite retirar todos los integrantes; los eventos familiares siguen disponibles.

Pedro aprobó el esquema de eventos familiares y archivo con restauración, y confirmó que los filtros semanales afectan a eventos con horario, sin mostrar rutinas.

## Eventos recurrentes (issue #18)

El menú Eventos permite crear, editar y eliminar series recurrentes por integrante. Cada serie conserva título, hora local de inicio, duración, zona horaria, categoría e icono; la repetición puede ser diaria, semanal (uno o varios días) o mensual en el mismo número de día del mes. Se configura un intervalo y se puede finalizar sin límite, en una fecha o después de un número de ocurrencias. Los meses sin el día configurado se omiten. Una repetición semanal sin días explícitos toma el día de inicio.

El calendario calcula las ocurrencias al consultar el rango visible y conserva la hora local configurada al cambiar entre horario de verano e invierno. No materializa eventos futuros. Desde el calendario se puede cancelar una ocurrencia sin afectar al resto de la serie. Las excepciones también pueden cambiar hora, duración, título, categoría o icono. Al eliminar una serie se eliminan sus excepciones; los eventos puntuales existentes no se modifican.

## Versiones posteriores

Los eventos son elementos del calendario. Las tareas son rutinas diarias de los niños —desayunar, hacer la cama, vestirse, lavarse los dientes, hacer deberes— que podrán marcarse como hechas. El marcado diario de tareas ya está implementado; su progresión queda para versiones futuras.

La exploración inicial contemplaba vistas mensual y lista, recurrencias de eventos y ajustes adicionales. Estas ideas requieren sus propios issues y decisiones; no forman parte de esta entrega.

Consultar [docs/decisions.md](docs/decisions.md) y [docs/architecture.md](docs/architecture.md) para acuerdos técnicos y límites de implementación.
