# Infraestructura AWS — issue #13

Pedro solicitó S3/CloudFront, DynamoDB, Lambda y Cognito, con preview y producción en la misma cuenta. Después precisó: **«no quiero que inicies sesión solo crea el terraform yo haré el login antes de desplegar»**. El alcance final de este trabajo es Terraform, documentación y validación simulada. No se ha accedido a AWS, creado recursos, cambiado la aplicación ni migrado datos.

La implementación y los comandos están en [infra/README.md](../infra/README.md). El stack Docker local conserva PostgreSQL y Keycloak; los artefactos actuales no son compatibles todavía con este destino AWS.

## Definición preparada

- Un bootstrap con bucket privado de estado y buckets versionados de ZIPs separados por entorno. Su estado inicial es local y debe conservarse de forma segura.
- Dos raíces de Terraform, preview y production, con estados S3 independientes y bloqueo nativo de S3 (`use_lockfile`), sin DynamoDB para locks.
- Por entorno: web en S3 privado y CloudFront/OAC; API Gateway HTTP y Lambda Python 3.12; tabla DynamoDB on-demand cifrada (`pk` y `sk`); Cognito propio; IAM mínimo y registros con retención acotada.
- API sin caché, con JWT y alcance propio. Solo salud/configuración pública quedan sin autenticación. API Gateway no valida grupos: el futuro handler deberá comprobar `family-app`.
- Cognito con registro público cerrado y cliente público para código OAuth; el cliente de aplicación futuro deberá implementar PKCE. No se crean cuentas ni contraseñas con Terraform.
- Protección contra borrado y PITR en DynamoDB de producción; protección de Cognito. Buckets versionados y sin vaciado automático. Dominio opcional con certificado ACM existente en us-east-1; ninguna compra o alta automática de dominios.

La separación limita los roles de ejecución y las identidades del producto. No constituye aislamiento frente a administradores de la cuenta. Este cambio no crea roles de despliegue ni GitHub OIDC; configurar CD remoto y sus permisos queda pendiente.

## Contrato para implementación posterior

La función requiere un ZIP Linux x86_64/Python 3.12 con handler compatible con API Gateway HTTP payload v2, versión S3 y SHA-256 explícitos. El Terraform no genera código ficticio ni transforma el backend PostgreSQL en un adaptador DynamoDB. La web requiere un cliente Cognito compatible; las salidas contienen su configuración pública.

Quedan pendientes el adaptador de persistencia, diseño lógico de registros, condiciones/transacciones, handler Lambda, validación de grupo/cliente/tipo de token y adaptación OAuth del frontend. Se deberá preservar el contrato OpenAPI y las reglas de negocio, comprobándolos sin dependencia de AWS en dominio y pruebas. El código no debe dar acceso directo del navegador a DynamoDB.

Terraform solo define una tabla vacía con `pk`/`sk`; no implementa un esquema de entidades ni importa datos. La estructura de registros, migración desde PostgreSQL y reversión se propondrán y aprobarán antes de implementarlas. No se traslada información familiar a preview. No hay sincronización entre el calendario local y AWS.

## Coste al aplicar

Referencia orientativa: **2–10 USD/mes para ambos entornos** con uso doméstico de hasta 100.000 llamadas y 1 GB de transferencia al mes. No es una tarifa garantizada ni un tope. Región, duración de Lambda, tamaño de imágenes, lecturas, versiones de objetos, registros, PITR y consumo compartido de la cuenta afectan al coste. No se depende de la capa gratuita.

Los recursos facturables son S3, CloudFront, API Gateway HTTP, Lambda, DynamoDB on-demand/PITR, Cognito y CloudWatch; DNS solo si se configura una zona existente. No hay NAT, RDS, contenedores siempre activos ni concurrencia provisionada. Antes de aplicar, Pedro deberá revisar el plan y recalcular el consumo con AWS Pricing Calculator.

Fuentes consultadas el 8 de octubre de 2026: [DynamoDB](https://aws.amazon.com/dynamodb/pricing/on-demand/), [Lambda](https://aws.amazon.com/lambda/pricing/), [API Gateway](https://aws.amazon.com/api-gateway/pricing/), [Cognito](https://aws.amazon.com/cognito/pricing/), [CloudFront](https://aws.amazon.com/cloudfront/pricing/) y [S3](https://aws.amazon.com/s3/pricing/).

Referencias técnicas: [estado S3 y bloqueo de Terraform](https://developer.hashicorp.com/terraform/language/backend/s3), [OAC para S3 privado](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-restricting-access-to-s3.html), [reenvío de cabeceras hacia API Gateway](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/using-managed-origin-request-policies.html) y [validación JWT de API Gateway](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-jwt-authorizer.html).

## Revisión, puesta en marcha y reversión

CI comprueba formato, validación de las cuatro raíces, recursos con proveedor simulado y navegación SPA. No usa credenciales, backend remoto ni recursos facturables. Estas pruebas no confirman cuota disponible, nombre de bucket libre, certificado válido, un plan real ni comportamiento del calendario en AWS.

La creación real se hará después del login manual de Pedro y revisión de recursos, costes y seguridad. La guía explica bootstrap, publicación de artefactos, estados y planes separados, configuración de cuenta familiar y comprobaciones funcionales posteriores. No se activa despliegue automático.

Los ZIPs y archivos web se versionan para revertir código; los datos requieren un procedimiento independiente. PITR restaura otra tabla, no revierte automáticamente la original. No se destruye producción para hacer rollback. El estado local del bootstrap y los estados remotos deben mantenerse seguros y fuera de Git.
