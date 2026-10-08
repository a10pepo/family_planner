output "site_url" {
  value = module.application.site_url
}

output "cloudfront_distribution_id" {
  value = module.application.cloudfront_distribution_id
}

output "cloudfront_domain" {
  value = module.application.cloudfront_domain
}

output "frontend_bucket" {
  value = module.application.frontend_bucket
}

output "table_name" {
  value = module.application.table_name
}

output "lambda_function_name" {
  value = module.application.lambda_function_name
}

output "api_url" {
  value = module.application.api_url
}

output "cognito_user_pool_id" {
  value = module.application.cognito_user_pool_id
}

output "runtime_config" {
  value = module.application.runtime_config
}
