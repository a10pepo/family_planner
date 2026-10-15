output "site_url" { value = local.site_url }

output "cloudfront_distribution_id" { value = aws_cloudfront_distribution.frontend.id }

output "cloudfront_domain" { value = aws_cloudfront_distribution.frontend.domain_name }

output "frontend_bucket" { value = aws_s3_bucket.frontend.id }

output "table_name" { value = aws_dynamodb_table.calendar.name }

output "lambda_function_name" { value = aws_lambda_function.api.function_name }

output "mcp_lambda_function_name" { value = aws_lambda_function.mcp.function_name }

output "mcp_url" { value = local.mcp_resource_url }

output "mcp_oauth_client_id" { value = aws_cognito_user_pool_client.mcp.id }

output "mcp_oauth_callback_url" { value = local.mcp_callback_url }

output "api_url" { value = aws_apigatewayv2_api.api.api_endpoint }

output "cognito_user_pool_id" { value = aws_cognito_user_pool.family.id }

output "preview_test_secret_arn" {
  value = try(aws_secretsmanager_secret.preview_test_account[0].arn, null)
}

output "runtime_config" {
  value = {
    environment             = var.environment
    timezone                = var.family_timezone
    api_base_path           = "/api/v1"
    oauth_provider          = "cognito"
    issuer                  = local.issuer
    authorization_endpoint  = "https://${local.login_host}/oauth2/authorize"
    token_endpoint          = "https://${local.login_host}/oauth2/token"
    logout_endpoint         = "https://${local.login_host}/logout"
    client_id               = aws_cognito_user_pool_client.web.id
    user_pool_id            = aws_cognito_user_pool.family.id
    aws_region              = var.aws_region
    preview_test_secret_arn = try(aws_secretsmanager_secret.preview_test_account[0].arn, null)
    scopes                  = ["openid", "email", "profile", local.scope]
    redirect_uri            = "${local.site_url}/"
    mcp_url                 = local.mcp_resource_url
    mcp_oauth_client_id     = aws_cognito_user_pool_client.mcp.id
    mcp_oauth_callback_url  = local.mcp_callback_url
    mcp_scopes              = [local.mcp_scope_read, local.mcp_scope_write]
  }
}
