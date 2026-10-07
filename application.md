# Definición de producto y referencia UI/UX

## Alcance vigente

Decisiones de Pedro Nieto del 7 de octubre de 2026, implementadas en los issues [#3](https://github.com/a10pepo/family_planner/issues/3) y [#5](https://github.com/a10pepo/family_planner/issues/5):

- Calendario familiar táctil para una pantalla doméstica en la nevera, con conexión permanente a internet.
- Una única cuenta con usuario y contraseña mediante OAuth, Authorization Code y PKCE. Todos los integrantes y sus actividades son visibles y editables dentro de la sesión familiar.
- Añadir integrantes, crear eventos para ellos y mover, editar o eliminar eventos, conservando los cambios.
- Frontend y backend separados; la API del backend es la única vía de acceso del cliente a los datos.
- Docker Compose en local; AWS será un destino futuro.

## Pantalla principal

La vista por defecto es **Día**. Cada columna corresponde a un integrante y muestra su cara ilustrada, nombre y apodo sobre sus eventos. Se elimina el título «Nuestro calendario» y los rótulos como «LA FAMILIA». La fecha, **Hoy** y las flechas permiten navegar entre días.

El menú izquierdo es estrecho y contiene únicamente iconos, con nombres accesibles para lectores de pantalla: calendario, añadir integrante y cerrar sesión. Los eventos se añaden tocando una hora o seleccionando un intervalo en la columna correspondiente. El «+» de la cabecera ofrece la misma acción para teclado y pantalla táctil.

Las tarjetas muestran horario, título, icono y nombre de categoría. El color depende de la categoría, con una paleta pastel:

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

## Versiones posteriores

Los eventos son elementos del calendario. Las tareas son rutinas diarias de los niños —desayunar, hacer la cama, vestirse, lavarse los dientes, hacer deberes— que podrán marcarse como hechas. Las tareas y su progresión quedan para versiones futuras.

La exploración inicial contemplaba vistas semanal, mensual y lista, filtros combinados de integrantes, fotografías, eventos compartidos, recurrencias, ajustes y badges de rutinas pendientes. Estas ideas requieren sus propios issues y decisiones; no forman parte de esta entrega.

Consultar [docs/decisions.md](docs/decisions.md) y [docs/architecture.md](docs/architecture.md) para acuerdos técnicos y límites de implementación.
