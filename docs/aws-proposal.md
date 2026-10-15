# Infraestructura AWS — issue #13

Pedro solicitó S3/CloudFront, DynamoDB, Lambda y Cognito, con preview y producción en la misma cuenta. Make usa la sesión AWS CLI que Pedro ya inició; el despliegue automático a preview se limita a commits de `main` que pasaron CI mediante GitHub OIDC.

La implementación y los comandos están en [infra/README.md](../infra/README.md). El stack Docker local conserva PostgreSQL y Keycloak; AWS usa DynamoDB y Cognito.

## Definición preparada

- Un bootstrap con bucket privado de estado y repositorios ECR separados por entorno. Su estado inicial es local y debe conservarse de forma segura.
- Dos raíces de Terraform, preview y production, con estados S3 independientes y bloqueo nativo de S3 (`use_lockfile`), sin DynamoDB para locks.
- Por entorno: web en S3 privado y CloudFront/OAC; API Gateway HTTP y Lambda Python 3.12 en imagen ECR; tabla DynamoDB on-demand cifrada; Cognito propio; IAM mínimo y registros con retención acotada.
- Issue #55 añade una Lambda MCP por entorno, su rol IAM/log group, una ruta en el API Gateway/CloudFront existentes y un cliente/scope MCP en Cognito. No añade distribución, API, tabla o migración.
- API sin caché, con JWT del cliente Cognito propio. Solo salud/configuración pública quedan sin autenticación. API Gateway comprueba el emisor y cliente; la Lambda valida además firma, caducidad, `token_use=access`, cliente y `sub`.
- Cognito con registro mediante pantalla propia, cuenta familiar compartida, correo verificado, cliente público para la API de usuario y OAuth. El frontend usa PKCE para las llamadas y no persiste tokens. La cuenta ficticia de preview se crea durante el despliegue, y su contraseña vive en Secrets Manager; no se guarda en Terraform state, CI, logs ni repositorio.
- Protección contra borrado y PITR en DynamoDB de producción; protección de Cognito. Buckets versionados y sin vaciado automático. Dominio opcional con certificado ACM existente en us-east-1; ninguna compra o alta automática de dominios.

La separación limita los roles de ejecución y las identidades del producto. No constituye aislamiento frente a administradores de la cuenta. La automatización de despliegue requiere un rol GitHub OIDC con permisos mínimos y confianza limitada al repositorio y rama main.

## Contrato para implementación posterior

La función se construye como imagen Lambda Linux x86_64/Python 3.12 en ECR. Las etiquetas SHA identifican commits; Terraform fija el digest inmutable. Se conserva el contrato OpenAPI y las reglas de negocio sin dar acceso directo del navegador a DynamoDB.

Pedro aprobó el 9 de octubre de 2026 una tabla por entorno con registros por tipo e índices para el calendario. El 10 de octubre aprobó el aislamiento multi-familia usando `PK=FAMILY#<sub de Cognito>` y el prefijo en GSIs; excepciones y marcas también se guardan dentro de esa partición. Las escrituras relevantes usan condiciones/transacciones y no se utiliza `Scan`. Preview se reinicia vacío para aplicar el esquema; producción no se toca ni migra.

## Coste al aplicar

Referencia orientativa: **2–10 USD/mes para ambos entornos** con uso doméstico de hasta 100.000 llamadas y 1 GB de transferencia al mes, más aproximadamente **0,75–1,50 USD/mes de ECR** al conservar hasta 30 imágenes de 250–500 MB cada una antes de deduplicar capas y **0,40 USD/mes por cada secreto** de Secrets Manager, más solicitudes. No son tarifas garantizadas ni topes. Región, duración de Lambda, tamaño de imágenes, lecturas, versiones de objetos, registros, PITR y consumo compartido de la cuenta afectan al coste. No se depende de la capa gratuita.

Los recursos facturables son S3, CloudFront, API Gateway HTTP, Lambda, DynamoDB on-demand/PITR, Cognito y CloudWatch; DNS solo si se configura una zona existente. No hay NAT, RDS, contenedores siempre activos ni concurrencia provisionada. Antes de aplicar, Pedro deberá revisar el plan y recalcular el consumo con AWS Pricing Calculator.

Para la Lambda MCP, una hipótesis de 10.000 solicitudes/mes por entorno, 512 MB y 300 ms por invocación da cerca de 1.500 GB-s de cómputo (aprox. USD 0,025 al precio de referencia de Lambda) más USD 0,002 por solicitudes; API Gateway añade su tarifa por petición. No incluye logs ni transferencia. Es una estimación de consumo, no una factura prevista; el uso compartido de la capa gratuita y la región modifican el resultado. Revisar de nuevo con la [página de precios de Lambda](https://aws.amazon.com/lambda/pricing/) y la [página de precios de API Gateway](https://aws.amazon.com/api-gateway/pricing/) antes de aplicar.

Fuentes consultadas el 8 de octubre de 2026: [DynamoDB](https://aws.amazon.com/dynamodb/pricing/on-demand/), [Lambda](https://aws.amazon.com/lambda/pricing/), [API Gateway](https://aws.amazon.com/api-gateway/pricing/), [Cognito](https://aws.amazon.com/cognito/pricing/), [CloudFront](https://aws.amazon.com/cloudfront/pricing/) y [S3](https://aws.amazon.com/s3/pricing/).

Referencias técnicas: [estado S3 y bloqueo de Terraform](https://developer.hashicorp.com/terraform/language/backend/s3), [OAC para S3 privado](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-restricting-access-to-s3.html), [reenvío de cabeceras hacia API Gateway](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/using-managed-origin-request-policies.html) y [validación JWT de API Gateway](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-jwt-authorizer.html).

## Revisión, puesta en marcha y reversión

CI comprueba formato, validación de las cuatro raíces, recursos con proveedor simulado y navegación SPA. No usa credenciales, backend remoto ni recursos facturables. Estas pruebas no confirman cuota disponible, nombre de bucket libre, certificado válido, un plan real ni comportamiento del calendario en AWS.

La creación real se realiza con el login manual de Pedro y la revisión de recursos, costes y seguridad. La guía explica bootstrap, publicación de imágenes, estados y planes separados, configuración de cuenta familiar y comprobaciones funcionales posteriores.

Las imágenes ECR fijadas por digest y los archivos web permiten revertir código; los datos requieren un procedimiento independiente. PITR restaura otra tabla, no revierte automáticamente la original. No se destruye producción para hacer rollback. El estado local del bootstrap y los estados remotos deben mantenerse seguros y fuera de Git.
