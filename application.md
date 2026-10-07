# Definición de producto y referencia UI/UX

## 0. Alcance confirmado del MVP

Decisiones de Pedro Nieto del 7 de octubre de 2026:

- Añadir integrantes de una familia, con un número variable de perfiles.
- Seleccionar un integrante y crear eventos en el calendario para él.
- Mover eventos por el calendario y eliminarlos, conservando los cambios.
- Acceder mediante una única cuenta familiar con usuario y contraseña, utilizando OAuth con Authorization Code y PKCE. Todos los perfiles y actividades están disponibles y son editables dentro de la sesión familiar.
- Uso táctil en una pantalla doméstica en la nevera, con conexión permanente a internet.
- Frontend y backend separados; el frontend accede a los datos exclusivamente a través de la API del backend.
- Ejecución local con Docker Compose; AWS será un destino futuro.

Los **eventos** son elementos del calendario. Las **tareas** son rutinas diarias de los niños —desayunar, hacer la cama, vestirse, lavarse los dientes, hacer deberes— que podrán marcarse como hechas. Su inclusión en el MVP está pendiente de confirmar; el seguimiento de progresión pertenece a versiones futuras.

Las secciones siguientes conservan la exploración inicial de interfaz. No convierten automáticamente en requisitos del MVP las vistas adicionales, las tareas, las categorías o los eventos compartidos. Sus referencias a tareas en el calendario deben entenderse como eventos; el marcado de rutinas pertenece al concepto separado de tareas. Las cuatro columnas de la propuesta diaria son ilustrativas y deben adaptarse al número real de integrantes.

Para las preguntas abiertas y decisiones técnicas, consultar [docs/decisions.md](docs/decisions.md). Los límites de implementación están en [docs/architecture.md](docs/architecture.md).

## Referencia UI/UX: Pantalla Principal (Vista de Calendario Familiar)

## 1. Visión General
Esta pantalla actúa como la vista principal de la aplicación web del Calendario Familiar, optimizada para dispositivos táctiles (móviles y tablets). Permite a la familia visualizar y gestionar sus actividades compartidas e individuales de forma rápida e intuitiva mediante colores codificados por integrante.

---

## 2. Layout y Estructura General

### 2.1 Menú Lateral / Navegación Izquierda (Sidebar)
* **Propósito:** Navegación global de la aplicación.
* **Comportamiento Táctil:** Collapsible/desplegable en móviles; fijo o minimizable en tablets.
* **Componentes:**
  * **Logotipo / Título App:** "Family Connect" (o nombre de la app).
  * **Navegación Principal:**
    * `Inicio` / `Home`
    * `Vistas de Calendario` (Menú desplegable / Selector de vista):
      * **Vista Semanal** *(por defecto)*
      * **Vista Diaria** *(desglosada por columnas de integrantes)*
      * **Vista Mensual**
      * **Vista Lista**
  * **Acciones:**
    * Botón primario prominente `+ Añadir Evento` / `Add Event`
  * **Secciones Secundarias:**
    * `Tareas` / `Tasks`
    * `Ajustes` / `Settings`

---

## 3. Zona Superior: Barra de Integrantes de la Familia (Header Filter)
* **Proporción en pantalla:** Ocupa aprox. el 20% superior de la vista.
* **Estructura:** Scroll horizontal si el número de miembros excede el ancho de la pantalla.
* **Componentes por Miembro:**
  1. **Avatar Circular:** Foto de perfil del integrante.
  2. **Anillo de Color (Border/Ring):** Borde circular envolvente codificado por color único para identificativo de cada miembro:
     * *Ejemplo:*
       * Padre: Azul (`#2196F3`)
       * Madre: Rosa/Morado (`#E91E63`)
       * Hijo 1: Verde (`#4CAF50`)
       * Hijo 2: Naranja (`#FF9800`)
  3. **Etiqueta de Nombre:** Situada debajo de la foto.
  4. **Badge de Tareas Pendientes (Opcional):** Indicador numérico pequeño sobre la foto con las tareas del día.
* **Interactividad / Lógica Táctil:**
  * Al pulsar sobre un integrante, actúa como **filtro toggle**:
    * **Seleccionado:** Muestra sus tareas en el calendario.
    * **Deseleccionado:** Oculta sus tareas individuales y opaca su avatar.
    * **Pulsación múltiple:** Permite filtrar combinaciones de miembros o seleccionar "Todos".

---

## 4. Area Principal: Vista de Calendario

### A. Vista Semanal (Vista por Defecto)
* **Header del Calendario:**
  * Selector/Indicador del rango de fechas (`Mon Oct 21 - Sun Oct 27`).
  * Botones de navegación: `Anterior (<)`, `Siguiente (>)`, `Hoy / Today`.
  * Indicador de vista activa (`Semana`).
* **Grilla / Grid Semanal:**
  * Columnas correspondientes a los 7 días de la semana (Lunes a Domingo).
  * Marcador de tiempo actual (Línea horizontal roja que indica la hora actual).
  * Eje vertical con marcas de hora (ej. 8:00 AM - 9:00 PM).
* **Tarjetas de Eventos / Tareas:**
  * Bloques rectangulares de color correspondiente al color asignado del integrante.
  * Muestran: Hora inicio-fin, título del evento, icono de categoría (ej. deporte, médico, colegio) y miniatura/s del o los integrantes asignados.
  * Si la tarea es de categoría **Familiar/Grupal**, utiliza un badge o diseño combinado con avatares múltiples.

### B. Vista Diaria (Columnas por Integrante)
* **Header del Calendario:**
  * Selector de fecha específica (`Tuesday, October 22`).
  * Botón `Hoy`.
* **Grilla de Distribución:**
  * La pantalla se divide en **4 columnas verticales principales** (una por cada integrante de la familia).
  * En la parte superior de cada columna se reitera el avatar mini con su nombre y anillo de color.
* **Visualización de Tareas:**
  * Cada tarea o evento del día aparece ordenado cronológicamente en la columna correspondiente al integrante responsable.
  * Para eventos compartidos (ej. "Comida familiar"), la tarjeta abarca o se replica visualmente en las columnas de los involucrados.

---

## 5. Requerimientos Táctiles y UX/UI
1. **Target Touch Size:** Todos los elementos interactivos (botones, avatares, tarjetas de eventos) deben cumplir con un área de toque mínima de **44x44 px**.
2. **Modal Rápido:** Al pulsar una tarjeta de evento en el calendario, se debe abrir un modal táctil simple con:
   * Detalle del evento.
   * Asignados.
   * Botón de marcar como completado.
   * Botón de editar/eliminar.
3. **Animaciones:** Transiciones suaves al cambiar entre la vista semanal y diaria, así como al aplicar filtros por integrante.
