# family_planner

Aplicación web de calendario familiar para una pantalla táctil en casa. Una cuenta familiar permite gestionar integrantes y sus eventos compartidos.

## Documentación

- [AGENTS.md](AGENTS.md): instrucciones de trabajo, issues, aprobaciones y validación.
- [application.md](application.md): alcance inicial y referencia de interfaz.
- [Guardrails de arquitectura](docs/architecture.md): separación frontend/backend, API, datos y requisitos de CI/CD.
- [Decisiones y pendientes](docs/decisions.md): acuerdos confirmados y preguntas antes de implementar.

## Estado

El repositorio contiene la definición inicial y las reglas de trabajo. Aún no incluye aplicación, Docker Compose ni pipelines. La implementación deberá ejecutarse localmente con Compose y tendrá CI/CD; el despliegue futuro a AWS requiere una propuesta y aprobación de seguridad y costes.

## Contribuir

Todo cambio parte de un issue en [GitHub](https://github.com/a10pepo/family_planner/issues), etiquetado `feature` para nuevas funcionalidades o `issue` para errores y cambios de seguridad. Consultar `AGENTS.md` antes de empezar y vincular el PR al issue.
