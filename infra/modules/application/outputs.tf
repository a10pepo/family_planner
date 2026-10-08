output "site_url" { value = local.site_url }

output "cloudfront_distribution_id" { value = aws_cloudfront_distribution.frontend.id }

output "cloudfront_domain" { value = aws_cloudfront_distribution.frontend.domain_name }

output "frontend_bucket" { value = aws_s3_bucket.frontend.id }

output "table_name" { value = aws_dynamodb_table.calendar.name }

output "lambda_function_name" { value = aws_lambda_function.api.function_name }

output "api_url" { value = aws_apigatewayv2_api.api.api_endpoint }

output "cognito_user_pool_id" { value = aws_cognito_user_pool.family.id }

output "runtime_config" {
  value = {
    environment            = var.environment
    timezone               = var.family_timezone
    api_base_path          = "/api/v1"
    oauth_provider         = "cognito"
    issuer                 = local.issuer
    authorization_endpoint = "https://${local.login_host}/oauth2/authorize"
    token_endpoint         = "https://${local.login_host}/oauth2/token"
    logout_endpoint        = "https://${local.login_host}/logout"
    client_id              = aws_cognito_user_pool_client.web.id
    scopes                 = ["openid", "email", "profile", local.scope]
    required_group         = aws_cognito_user_group.family.name
    redirect_uri           = "${local.site_url}/"
  }
}
