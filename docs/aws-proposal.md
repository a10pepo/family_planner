# Infraestructura AWS — issue #13

Pedro solicitó S3/CloudFront, DynamoDB, Lambda y Cognito, con preview y producción en la misma cuenta. Después confirmó que usará su sesión AWS CLI antes de desplegar. La implementación prepara el runtime y los comandos de despliegue, pero no inicia sesión ni despliega recursos por su cuenta.

La implementación y los comandos están en [infra/README.md](../infra/README.md). El stack Docker local conserva PostgreSQL y Keycloak; AWS usa DynamoDB y Cognito.

## Definición preparada

- Un bootstrap con bucket privado de estado y buckets versionados de ZIPs separados por entorno. Su estado inicial es local y debe conservarse de forma segura.
- Dos raíces de Terraform, preview y production, con estados S3 independientes y bloqueo nativo de S3 (`use_lockfile`), sin DynamoDB para locks.
- Por entorno: web en S3 privado y CloudFront/OAC; API Gateway HTTP y Lambda Python 3.12; tabla DynamoDB on-demand cifrada; Cognito propio; IAM mínimo y registros con retención acotada.
- API sin caché, con JWT y alcance propio. Solo salud/configuración pública quedan sin autenticación. API Gateway comprueba token, emisor, cliente y alcance; la Lambda valida además tipo access y grupo `family-app`.
- Cognito con registro público cerrado y cliente público para código OAuth. El frontend implementa PKCE y no persiste los tokens. No se crean cuentas ni contraseñas con Terraform.
- Protección contra borrado y PITR en DynamoDB de producción; protección de Cognito. Buckets versionados y sin vaciado automático. Dominio opcional con certificado ACM existente en us-east-1; ninguna compra o alta automática de dominios.

La separación limita los roles de ejecución y las identidades del producto. No constituye aislamiento frente a administradores de la cuenta. Este cambio no crea roles de despliegue ni GitHub OIDC; configurar CD remoto y sus permisos queda pendiente.

## Contrato para implementación posterior

La función se construye como ZIP Linux x86_64/Python 3.12 con handler compatible con API Gateway HTTP payload v2, versión S3 y SHA-256 explícitos. Se conserva el contrato OpenAPI y las reglas de negocio sin dar acceso directo del navegador a DynamoDB.

Pedro aprobó el 9 de octubre de 2026 una tabla por entorno con `PK=FAMILY#default`, registros por tipo, GSIs para consulta de eventos por fin, avisos/eventos familiares por día, series por integrante y marcas de tareas por día. Excepciones se almacenan en `PK=SERIES#id`; completados en `PK=MEMBER#id`. Las escrituras relevantes usan condiciones/transacciones y no se utiliza `Scan`. Producción empieza vacía, sin importación ni migración; no hay sincronización con el calendario local.

## Coste al aplicar

Referencia orientativa: **2–10 USD/mes para ambos entornos** con uso doméstico de hasta 100.000 llamadas y 1 GB de transferencia al mes. No es una tarifa garantizada ni un tope. Región, duración de Lambda, tamaño de imágenes, lecturas, versiones de objetos, registros, PITR y consumo compartido de la cuenta afectan al coste. No se depende de la capa gratuita.

Los recursos facturables son S3, CloudFront, API Gateway HTTP, Lambda, DynamoDB on-demand/PITR, Cognito y CloudWatch; DNS solo si se configura una zona existente. No hay NAT, RDS, contenedores siempre activos ni concurrencia provisionada. Antes de aplicar, Pedro deberá revisar el plan y recalcular el consumo con AWS Pricing Calculator.

Fuentes consultadas el 8 de octubre de 2026: [DynamoDB](https://aws.amazon.com/dynamodb/pricing/on-demand/), [Lambda](https://aws.amazon.com/lambda/pricing/), [API Gateway](https://aws.amazon.com/api-gateway/pricing/), [Cognito](https://aws.amazon.com/cognito/pricing/), [CloudFront](https://aws.amazon.com/cloudfront/pricing/) y [S3](https://aws.amazon.com/s3/pricing/).

Referencias técnicas: [estado S3 y bloqueo de Terraform](https://developer.hashicorp.com/terraform/language/backend/s3), [OAC para S3 privado](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-restricting-access-to-s3.html), [reenvío de cabeceras hacia API Gateway](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/using-managed-origin-request-policies.html) y [validación JWT de API Gateway](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-jwt-authorizer.html).

## Revisión, puesta en marcha y reversión

CI comprueba formato, validación de las cuatro raíces, recursos con proveedor simulado y navegación SPA. No usa credenciales, backend remoto ni recursos facturables. Estas pruebas no confirman cuota disponible, nombre de bucket libre, certificado válido, un plan real ni comportamiento del calendario en AWS.

La creación real se hará después del login manual de Pedro y revisión de recursos, costes y seguridad. La guía explica bootstrap, publicación de artefactos, estados y planes separados, configuración de cuenta familiar y comprobaciones funcionales posteriores. No se activa despliegue automático.

Los ZIPs y archivos web se versionan para revertir código; los datos requieren un procedimiento independiente. PITR restaura otra tabla, no revierte automáticamente la original. No se destruye producción para hacer rollback. El estado local del bootstrap y los estados remotos deben mantenerse seguros y fuera de Git.
