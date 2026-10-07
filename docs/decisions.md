# Decisiones y preguntas pendientes

Fuente: respuestas de Pedro Nieto del 7 de octubre de 2026. Trabajo inicial: [issue #1](https://github.com/a10pepo/family_planner/issues/1).

## Acuerdos confirmados

| Tema | Decisión |
| --- | --- |
| MVP | Añadir integrantes y crear, mover y eliminar eventos para el integrante seleccionado. |
| Uso | Pantalla doméstica en la nevera, con conexión permanente. |
| Acceso | Una cuenta y contraseña de familia; acceso compartido a todos los perfiles. |
| Visibilidad | Todas las actividades visibles y editables dentro de la cuenta familiar. |
| Arquitectura | Frontend y backend separados, con una API establecida entre ambos. |
| Datos | Solo el backend accede a la base de datos. |
| Ejecución | Docker Compose local inicialmente; migración a AWS en el futuro. |
| Eventos | Elementos situados en el calendario. |
| Tareas | Rutinas diarias de los niños que pueden marcarse como completadas. |
| Progresión | Seguimiento del progreso de tareas en versiones futuras. |
| Aprobaciones | Estructura de datos, acciones con coste en AWS y cambios con riesgo de seguridad. |
| Calidad | Todo código debe ser comprobable automáticamente en CI; el proyecto debe incluir CI/CD para merge y despliegue. |
| Trabajo | Basado siempre en issues de GitHub, sin Jira CPT. |
| Etiquetas | `issue`: error o cambio de seguridad. `feature`: nueva funcionalidad. |

## Pendiente de respuesta de Pedro

1. ¿Las tareas diarias y su marcado como completadas entran en el MVP o en una segunda versión?
2. Al mover un evento, ¿solo cambia su fecha y hora o también puede cambiar de integrante? ¿Se permite cambiar su duración? Esto debe aclararse antes del modelo y contrato iniciales.
3. ¿Qué política de sesión necesita la pantalla doméstica: cuánto tiempo debe permanecer abierta y cómo se recupera el acceso si se pierde la contraseña? Preparar después una propuesta de seguridad concreta para aprobación.
4. ¿Se mantiene el merge manual después de pasar CI o se quiere merge automático? ¿Qué destino debe tener el primer despliegue, dado que por ahora solo está acordada la ejecución local?
5. ¿Español para interfaz y documentación e inglés para código? ¿La zona horaria familiar inicial es Europe/Madrid?
6. ¿«Proyecto de GitHub» se refiere a los issues del repositorio o también a un tablero de GitHub Projects? Si hay tablero, hace falta identificarlo.

## Pendiente de propuesta técnica

- Elegir stack de frontend, backend, base de datos y herramientas de pruebas. Pedro no tiene preferencia; preparar una propuesta compatible con cliente-servidor, Compose y portabilidad a AWS.
- Elegir formato y estrategia de compatibilidad del contrato API.
- Preparar estructura de datos inicial y propuesta de autenticación para aprobación antes de implementarlas.
- Definir estructura de carpetas y controles ejecutables de arquitectura con el stack.
- Definir workflows de CI/CD y documentar sus comandos reales al hacer el bootstrap.
- Concretar requisitos adicionales de calendario —recurrencias, eventos de día completo, edición de detalles e integraciones— solo cuando se apruebe su alcance.

## Estado de implementación

Se han documentado acuerdos y guardrails y se han preparado plantillas de issues y PR. No hay todavía código de aplicación, esquema, contrato API, Compose, workflows de CI/CD ni infraestructura. No se han configurado protección de ramas ni despliegues.

No presentar las decisiones pendientes como hechos ni añadir funcionalidades de futuras versiones al MVP por aparecer en la exploración de UI de `application.md`.
