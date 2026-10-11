# Proveedor simulado: ninguna llamada a AWS ni creación de recursos.
mock_provider "aws" {
  mock_resource "aws_s3_bucket" {
    defaults = { arn = "arn:aws:s3:::mock-web", bucket_regional_domain_name = "mock-web.s3.eu-west-1.amazonaws.com" }
  }
  mock_resource "aws_dynamodb_table" {
    defaults = { arn = "arn:aws:dynamodb:eu-west-1:111111111111:table/mock-calendar" }
  }
  mock_resource "aws_iam_role" {
    defaults = { arn = "arn:aws:iam::111111111111:role/mock-lambda" }
  }
  mock_resource "aws_cloudwatch_log_group" {
    defaults = { arn = "arn:aws:logs:eu-west-1:111111111111:log-group:mock" }
  }
  mock_resource "aws_lambda_function" {
    defaults = { invoke_arn = "arn:aws:apigateway:eu-west-1:lambda:path/2015-03-31/functions/arn:aws:lambda:eu-west-1:111111111111:function:mock/invocations" }
  }
  mock_resource "aws_apigatewayv2_api" {
    defaults = { api_endpoint = "https://mock.execute-api.eu-west-1.amazonaws.com", execution_arn = "arn:aws:execute-api:eu-west-1:111111111111:mock" }
  }
  mock_resource "aws_cognito_user_pool" {
    defaults = { id = "eu-west-1_mock123" }
  }
  mock_resource "aws_cloudfront_function" {
    defaults = { arn = "arn:aws:cloudfront::111111111111:function/mock-spa" }
  }
  mock_resource "aws_cloudfront_distribution" {
    defaults = { domain_name = "mock.cloudfront.net", arn = "arn:aws:cloudfront::111111111111:distribution/MOCK" }
  }
  mock_data "aws_cloudfront_cache_policy" {
    defaults = { id = "4135ea2d-6df8-44a3-9df3-4b5a84be39ad" }
  }
  mock_data "aws_cloudfront_origin_request_policy" {
    defaults = { id = "b689b0a8-53d0-40ab-baf2-68738e2966ac" }
  }
}
variables {
  environment      = "preview"
  aws_account_id   = "111111111111"
  aws_region       = "eu-west-1"
  lambda_image_uri = "111111111111.dkr.ecr.eu-west-1.amazonaws.com/family-planner-preview@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
}
run "preview" {
  command = apply
  assert {
    condition     = aws_dynamodb_table.calendar.name == "family-planner-preview" && !aws_dynamodb_table.calendar.deletion_protection_enabled && !aws_dynamodb_table.calendar.point_in_time_recovery[0].enabled
    error_message = "Preview debe tener tabla propia sin protecciones de producción."
  }
  assert {
    condition     = length(aws_secretsmanager_secret.preview_test_account) == 1 && aws_secretsmanager_secret.preview_test_account[0].recovery_window_in_days == 0 && output.preview_test_secret_arn == aws_secretsmanager_secret.preview_test_account[0].arn
    error_message = "Solo preview debe guardar credenciales recuperables en Secrets Manager, sin versión en Terraform."
  }
  assert {
    condition     = aws_s3_bucket.frontend.bucket == "family-planner-preview-111111111111-web" && aws_s3_bucket_public_access_block.frontend.block_public_policy && aws_s3_bucket_public_access_block.frontend.restrict_public_buckets && aws_s3_bucket_public_access_block.frontend.block_public_acls && aws_s3_bucket_public_access_block.frontend.ignore_public_acls
    error_message = "El bucket de preview debe ser privado y propio."
  }
  assert {
    condition     = jsondecode(aws_s3_bucket_policy.frontend.policy).Statement[0].Condition.StringEquals["AWS:SourceArn"] == aws_cloudfront_distribution.frontend.arn && jsondecode(aws_s3_bucket_policy.frontend.policy).Statement[1].Effect == "Deny"
    error_message = "Solo la distribución propia debe leer el sitio y se debe exigir TLS."
  }
  assert {
    condition     = jsondecode(aws_iam_role_policy.lambda.policy).Statement[0].Resource == [aws_dynamodb_table.calendar.arn, "${aws_dynamodb_table.calendar.arn}/index/*"] && !contains(jsondecode(aws_iam_role_policy.lambda.policy).Statement[0].Action, "dynamodb:Scan") && length(jsondecode(aws_iam_role_policy.lambda.policy).Statement) == 2
    error_message = "Lambda solo debe acceder a su tabla y sus registros."
  }
  assert {
    condition     = aws_apigatewayv2_route.protected.authorization_type == "JWT" && aws_apigatewayv2_route.protected.authorization_scopes == null && toset(keys(aws_apigatewayv2_route.public)) == toset(["GET /api/health", "GET /api/v1/config"])
    error_message = "La API debe exigir un JWT de cliente propio salvo salud/configuración públicas."
  }
  assert {
    condition     = !aws_cognito_user_pool_client.web.generate_secret && contains(aws_cognito_user_pool_client.web.explicit_auth_flows, "ALLOW_USER_PASSWORD_AUTH") && !aws_cognito_user_pool.family.admin_create_user_config[0].allow_admin_create_user_only && aws_cognito_user_pool.family.auto_verified_attributes == toset(["email"]) && aws_cognito_user_pool_client.web.callback_urls == toset(["https://mock.cloudfront.net/"])
    error_message = "Cognito debe permitir registro propio con cliente público y correo verificado."
  }
  assert {
    condition     = aws_cloudfront_distribution.frontend.ordered_cache_behavior[0].path_pattern == "/api/*" && aws_cloudfront_distribution.frontend.ordered_cache_behavior[0].cache_policy_id == data.aws_cloudfront_cache_policy.disabled.id && aws_cloudfront_distribution.frontend.ordered_cache_behavior[0].origin_request_policy_id == data.aws_cloudfront_origin_request_policy.api.id && length(aws_cloudfront_distribution.frontend.ordered_cache_behavior[0].function_association) == 0 && length(aws_cloudfront_distribution.frontend.custom_error_response) == 0
    error_message = "La API no se debe cachear ni convertir sus errores en HTML."
  }
  assert {
    condition     = length(aws_cloudfront_distribution.frontend.ordered_cache_behavior) == 2 && alltrue([for b in aws_cloudfront_distribution.frontend.ordered_cache_behavior : b.target_origin_id == "api" && b.cache_policy_id == data.aws_cloudfront_cache_policy.disabled.id]) && anytrue([for o in aws_cloudfront_distribution.frontend.origin : o.origin_id == "frontend" && o.origin_access_control_id == aws_cloudfront_origin_access_control.frontend.id && length(o.s3_origin_config) == 1])
    error_message = "API raíz y subrutas deben usar el origen API sin caché; S3 debe tener OAC."
  }
  assert {
    condition     = aws_lambda_function.api.package_type == "Image" && aws_lambda_function.api.image_uri == var.lambda_image_uri && aws_lambda_function.api.environment[0].variables["DYNAMODB_TABLE"] == aws_dynamodb_table.calendar.name && aws_lambda_function.api.environment[0].variables["OAUTH_USER_POOL_ID"] == aws_cognito_user_pool.family.id
    error_message = "Lambda debe usar una imagen inmutable y configuración propia."
  }
}
run "production" {
  command = apply
  variables {
    environment      = "production"
    lambda_image_uri = "111111111111.dkr.ecr.eu-west-1.amazonaws.com/family-planner-production@sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
  }
  assert {
    condition     = aws_dynamodb_table.calendar.name != run.preview.table_name && aws_dynamodb_table.calendar.name == "family-planner-production" && aws_dynamodb_table.calendar.deletion_protection_enabled && aws_dynamodb_table.calendar.point_in_time_recovery[0].enabled
    error_message = "Producción debe estar aislada de preview y conservar recuperación y protección."
  }
  assert {
    condition     = length(aws_secretsmanager_secret.preview_test_account) == 0 && output.preview_test_secret_arn == null
    error_message = "Producción no debe crear ni conservar el secreto de pruebas."
  }
  assert {
    condition     = aws_s3_bucket.frontend.bucket == "family-planner-production-111111111111-web" && aws_lambda_function.api.function_name != run.preview.lambda_function_name && aws_cognito_user_pool.family.name == "family-planner-production" && aws_cognito_user_pool.family.deletion_protection == "ACTIVE" && aws_cloudwatch_log_group.lambda.retention_in_days == 30
    error_message = "Recursos de producción deben tener identidad propia y protecciones."
  }
}
run "reject_cross_environment_image" {
  command = plan
  variables {
    environment      = "production"
    lambda_image_uri = "111111111111.dkr.ecr.eu-west-1.amazonaws.com/family-planner-preview@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  }
  expect_failures = [var.lambda_image_uri]
}
run "reject_unknown_environment" {
  command = plan
  variables { environment = "staging" }
  expect_failures = [var.environment]
}
run "reject_mutable_image_reference" {
  command = plan
  variables { lambda_image_uri = "latest" }
  expect_failures = [var.lambda_image_uri]
}
run "reject_domain_without_certificate" {
  command = plan
  variables { domain_name = "calendar.example.com" }
  expect_failures = [var.certificate_arn]
}

run "reject_other_repository_image" {
  command = plan
  variables { lambda_image_uri = "111111111111.dkr.ecr.eu-west-1.amazonaws.com/other@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" }
  expect_failures = [var.lambda_image_uri]
}
run "custom_domain" {
  command = apply
  variables {
    domain_name     = "calendar.example.com"
    certificate_arn = "arn:aws:acm:us-east-1:111111111111:certificate/00000000-0000-0000-0000-000000000000"
    route53_zone_id = "ZEXAMPLE"
  }
  assert {
    condition     = output.site_url == "https://calendar.example.com" && aws_cognito_user_pool_client.web.callback_urls == toset(["https://calendar.example.com/"]) && length(aws_route53_record.frontend) == 2
    error_message = "El dominio propio debe configurar el sitio, callback y DNS IPv4/IPv6."
  }
}

run "reject_project_exceeding_bucket_limit" {
  command = plan
  variables { project = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" }
  expect_failures = [var.project]
}
