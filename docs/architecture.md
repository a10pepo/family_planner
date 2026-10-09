# Guardrails de arquitectura

Estado: MVP local implementado. `scripts/check_architecture.py` comprueba las dependencias del frontend y el dominio; CI valida contrato, tipos, pruebas y despliegue local. Las restricciones adicionales siguen siendo criterios de revisión; el script no detecta todos los patrones dinámicos de importación.

## 1. Separación cliente, API y datos

El flujo permitido es:

```text
Frontend → API del backend → lógica de negocio → persistencia → base de datos
```

- El frontend no incorpora clientes de base de datos, credenciales de persistencia, consultas SQL ni importaciones de módulos internos del backend.
- El backend es la única aplicación con acceso a la base de datos. La API es la única vía de acceso del cliente a los datos.
- Los detalles de almacenamiento no se filtran al contrato público: no devolver filas o entidades del ORM directamente.
- Las validaciones de negocio y de acceso deben aplicarse en el servidor. La selección de un integrante en la interfaz no concede permisos.
- La base de datos no debe exponerse públicamente. En Compose será accesible por la red interna; cualquier exposición adicional para administración necesita revisión de seguridad.

## 2. Límites internos y dependencias

- La presentación se ocupa de interacción y estado visual; no define reglas de persistencia o de negocio.
- Los puntos de entrada HTTP traducen el contrato y llaman a los casos de uso; no concentran reglas de negocio.
- La lógica de negocio no importa código de interfaz, frameworks HTTP, ORM ni SDK de AWS. Esos detalles se conectan mediante interfaces o adaptadores.
- La persistencia implementa el acceso a los datos requerido por los casos de uso.
- No crear dependencias circulares ni importar desde frontend implementaciones internas del backend.
- El contrato de API puede compartirse o generar tipos de cliente; los modelos de persistencia no constituyen un contrato compartido.
- Evitar servicios adicionales hasta que un requisito concreto del issue los justifique.

Las rutas son `frontend/src`, `backend/app/api.py` / `api_daily.py`, `backend/app/domain` y `backend/app/adapters`. El contrato OpenAPI se encuentra en `docs/openapi.json` y genera los tipos `frontend/src/api-schema.ts`. El proveedor OAuth conserva sus identidades en su propio volumen, sin acceso a PostgreSQL del calendario.

## 3. Contrato API estable

- Definir y versionar en el repositorio un contrato de operaciones, entradas, salidas y errores antes de implementar sus consumidores.
- El formato de contrato es OpenAPI; `scripts/export_openapi.py --check` detecta cambios y `npm --prefix frontend run api:check` comprueba los tipos generados del cliente.
- Las pruebas deben detectar discrepancias entre el contrato, el backend y el cliente.
- Mantener compatibilidad con los consumidores existentes. Documentar y coordinar cualquier cambio incompatible mediante su issue.
- Validar entradas y referencias en el backend. No asumir que los datos recibidos vienen de la interfaz oficial.
- Las reglas de fechas, horas, zona horaria y movimiento de eventos deben ser explícitas y verificables; no depender de la zona horaria del servidor.
- No publicar un contrato inicial que fije la estructura de datos sin la aprobación correspondiente.

## 4. Datos y conceptos de producto

- Una cuenta familiar autentica el acceso; los integrantes son perfiles seleccionables.
- Un evento es un elemento situado en el calendario. Una tarea es una rutina diaria que puede completarse. No tratarlos como sinónimos.
- Las tareas se expanden por fecha en el dominio; no crear eventos con horario por cada repetición. Guardar las marcas por tarea/integrante/fecha y archivar sin borrarlas. Los avisos de día completo no tienen horario.
- Validar y reducir fotos en el adaptador del backend; el dominio recibe la imagen normalizada. No confiar en la conversión del navegador.
- El catálogo de iconos es común a eventos, avisos y tareas, con referencias opcionales validadas en el dominio y en PostgreSQL. No guardar imágenes repetidas en cada actividad ni quitar el catálogo al archivar una rutina.
- Archivar un integrante conserva todos sus datos y oculta sus actividades y marcas en las consultas normales. Restaurarlo recupera las mismas identidades y asignaciones; no usar borrado en cascada. Los eventos familiares de día completo no dependen de un integrante y usan fechas locales, sin conversión a instantes UTC. Los filtros semanales afectan solo a la presentación.
- La progresión de tareas pertenece a versiones futuras; no crear tablas o endpoints de analítica para anticiparla.
- La estructura inicial de datos y cualquier cambio posterior requieren propuesta y aprobación previa de Pedro.
- Cuando exista esquema, versionar las migraciones y probarlas con una base de datos desechable. No ejecutar cambios destructivos sobre datos reales sin aprobación expresa.
- Los datos de prueba deben ser sintéticos. No usar fotografías, contraseñas ni actividades reales de la familia.

## 5. Seguridad

- Las actividades se comparten dentro de la cuenta familiar autenticada. No son públicas en internet.
- No incluir contraseñas o secretos en el frontend ni en control de versiones. Las variables de configuración que recibe el navegador son públicas.
- No persistir contraseñas en texto plano ni crear credenciales predeterminadas utilizables fuera de pruebas.
- No registrar secretos, credenciales o detalles personales innecesarios.
- OAuth local autorizado por Pedro: Keycloak con cuenta familiar, Authorization Code + PKCE, tokens solo en memoria y validación en el backend. La duración y cierre de sesión y la recuperación de acceso se documentan en `docs/api.md` y README. El despliegue público requiere revisar la configuración; el modo `start-dev` se limita a local.
- Al desplegar, revisar transporte cifrado, cookies o tokens, exposición de servicios y permisos del entorno.
- Cualquier cambio con riesgo de seguridad requiere consulta previa, incluso si su objetivo es corregir una vulnerabilidad.

## 6. Entorno local y portabilidad a AWS

- Docker Compose debe levantar frontend, backend y base de datos con pasos documentados, comprobaciones de disponibilidad y persistencia local.
- La configuración debe suministrarse desde el entorno. Publicar solo ejemplos sin secretos.
- Las pruebas y el desarrollo local no necesitan cuenta de AWS ni recursos facturables.
- Evitar dependencias directas de AWS en el negocio. Aislar mediante adaptadores las integraciones que se aprueben más adelante.
- Pedro ha elegido S3/CloudFront, DynamoDB, Lambda y Cognito con preview y producción en la misma cuenta (issue #13). El alcance autorizado ahora es preparar Terraform y pruebas simuladas; no iniciar sesión, provisionar ni activar despliegue remoto. Véase [infra/README.md](../infra/README.md). La adaptación del código y la migración siguen pendientes.
- Cada propuesta de despliegue debe especificar entorno, recursos, permisos, costes estimados, secretos, migraciones y procedimiento de reversión antes de su aprobación.

## 7. CI/CD y controles de merge

- El bootstrap del stack debe incluir CI reproducible y comandos equivalentes para ejecutarla localmente.
- En los PR: comprobar trazabilidad al issue, formato, análisis estático y tipos cuando correspondan, pruebas, contrato API, reglas de dependencias y compilación.
- Usar base de datos desechable para integración y probar los flujos principales contra la API y en el navegador.
- Verificar creación, movimiento y eliminación de eventos con persistencia tras recargar; incluir fechas y cambios horarios cuando se defina su semántica.
- Las pruebas no deben depender de AWS, datos de producción ni servicios externos de pago.
- Exigir CI satisfactoria para mergear a `main` mediante protección de rama. La política de revisión y de merge automático aún está pendiente.
- Construir artefactos identificables por versión o commit y desplegar únicamente artefactos validados.
- El destino y el disparador de despliegue están pendientes. No activar publicación de imágenes o despliegue hasta acordarlos y aprobar sus implicaciones de seguridad y coste.
- No confundir un workflow de compilación con un despliegue ni un workflow existente con una protección de rama activa.

## 8. Registro de excepciones

Si un issue exige saltarse un límite, preparar una decisión de arquitectura que describa necesidad, alternativas, consecuencias y aprobación requerida. No introducir excepciones silenciosas ni desactivar un control para hacer pasar CI.
