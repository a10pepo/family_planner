locals {
  prefix           = "${var.project}-${var.environment}"
  bucket_name      = "${local.prefix}-${var.aws_account_id}-web"
  issuer           = "https://cognito-idp.${var.aws_region}.amazonaws.com/${aws_cognito_user_pool.family.id}"
  site_url         = "https://${var.domain_name != null ? var.domain_name : aws_cloudfront_distribution.frontend.domain_name}"
  login_host       = "${aws_cognito_user_pool_domain.family.domain}.auth.${var.aws_region}.amazoncognito.com"
  scope            = "${aws_cognito_resource_server.api.identifier}/access"
  cognito_base     = "https://${local.login_host}"
  production       = var.environment == "production"
  mcp_resource_url = "${local.site_url}/mcp"
  mcp_scope_read   = "${local.mcp_resource_url}/calendar.read"
  mcp_scope_write  = "${local.mcp_resource_url}/calendar.write"
  mcp_callback_id  = substr(replace(replace(trimsuffix(base64sha256(local.mcp_resource_url), "="), "+", "-"), "/", "_"), 0, 12)
  mcp_callback_url = "http://127.0.0.1:1455/callback/${local.mcp_callback_id}"
}

resource "aws_dynamodb_table" "calendar" {
  name                        = local.prefix
  billing_mode                = "PAY_PER_REQUEST"
  hash_key                    = "pk"
  range_key                   = "sk"
  deletion_protection_enabled = local.production
  attribute {
    name = "pk"
    type = "S"
  }
  attribute {
    name = "sk"
    type = "S"
  }
  attribute {
    name = "gsi1pk"
    type = "S"
  }
  attribute {
    name = "gsi1sk"
    type = "S"
  }
  attribute {
    name = "gsi2pk"
    type = "S"
  }
  attribute {
    name = "gsi2sk"
    type = "S"
  }
  global_secondary_index {
    name            = "by-calendar-end"
    hash_key        = "gsi1pk"
    range_key       = "gsi1sk"
    projection_type = "ALL"
  }
  global_secondary_index {
    name            = "by-day"
    hash_key        = "gsi1pk"
    range_key       = "gsi1sk"
    projection_type = "ALL"
  }
  global_secondary_index {
    name            = "by-member"
    hash_key        = "gsi2pk"
    range_key       = "gsi2sk"
    projection_type = "ALL"
  }
  global_secondary_index {
    name            = "by-completion-day"
    hash_key        = "gsi2pk"
    range_key       = "gsi2sk"
    projection_type = "ALL"
  }
  server_side_encryption { enabled = true }
  point_in_time_recovery { enabled = local.production }
}

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${local.prefix}-api"
  retention_in_days = local.production ? 30 : 7
}

resource "aws_cloudwatch_log_group" "mcp_lambda" {
  name              = "/aws/lambda/${local.prefix}-mcp"
  retention_in_days = local.production ? 30 : 7
}

resource "aws_cloudwatch_log_group" "api" {
  name              = "/aws/apigateway/${local.prefix}"
  retention_in_days = local.production ? 30 : 7
}

resource "aws_iam_role" "lambda" {
  name = "${local.prefix}-lambda"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "lambda.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}

resource "aws_iam_role_policy" "lambda" {
  name = "${local.prefix}-execution"
  role = aws_iam_role.lambda.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "CalendarOnly"
        Effect   = "Allow"
        Action   = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:DeleteItem", "dynamodb:Query", "dynamodb:BatchGetItem", "dynamodb:DescribeTable", "dynamodb:ConditionCheckItem", "dynamodb:TransactWriteItems"]
        Resource = [aws_dynamodb_table.calendar.arn, "${aws_dynamodb_table.calendar.arn}/index/*"]
      },
      {
        Sid      = "OwnLogsOnly"
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.lambda.arn}:*"
      }
    ]
  })
}

resource "aws_iam_role" "mcp_lambda" {
  name = "${local.prefix}-mcp-lambda"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "lambda.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}

resource "aws_iam_role_policy" "mcp_lambda" {
  name = "${local.prefix}-mcp-execution"
  role = aws_iam_role.mcp_lambda.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "CalendarEventsOnly"
        Effect   = "Allow"
        Action   = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:Query", "dynamodb:ConditionCheckItem", "dynamodb:TransactWriteItems"]
        Resource = [aws_dynamodb_table.calendar.arn, "${aws_dynamodb_table.calendar.arn}/index/*"]
      },
      {
        Sid      = "OwnLogsOnly"
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.mcp_lambda.arn}:*"
      }
    ]
  })
}

resource "aws_lambda_function" "api" {
  function_name = "${local.prefix}-api"
  role          = aws_iam_role.lambda.arn
  package_type  = "Image"
  architectures = ["x86_64"]
  image_uri     = var.lambda_image_uri
  memory_size   = 512
  timeout       = 15
  environment {
    variables = {
      APP_ENVIRONMENT              = var.environment
      APP_ORIGIN                   = local.site_url
      STORAGE_BACKEND              = "dynamodb"
      DYNAMODB_TABLE               = aws_dynamodb_table.calendar.name
      FAMILY_TIMEZONE              = var.family_timezone
      OAUTH_PROVIDER               = "cognito"
      OAUTH_ISSUER                 = local.issuer
      OAUTH_JWKS_URL               = "${local.issuer}/.well-known/jwks.json"
      OAUTH_CLIENT_ID              = aws_cognito_user_pool_client.web.id
      OAUTH_USER_POOL_ID           = aws_cognito_user_pool.family.id
      OAUTH_REQUIRED_SCOPE         = ""
      OAUTH_REQUIRED_GROUP         = ""
      OAUTH_SCOPES                 = "openid email profile ${local.scope}"
      OAUTH_AUTHORIZATION_ENDPOINT = "${local.cognito_base}/oauth2/authorize"
      OAUTH_TOKEN_ENDPOINT         = "${local.cognito_base}/oauth2/token"
      OAUTH_LOGOUT_ENDPOINT        = "${local.cognito_base}/logout"
    }
  }
  depends_on = [aws_iam_role_policy.lambda, aws_cloudwatch_log_group.lambda]
}

resource "aws_lambda_function" "mcp" {
  function_name = "${local.prefix}-mcp"
  role          = aws_iam_role.mcp_lambda.arn
  package_type  = "Image"
  architectures = ["x86_64"]
  image_uri     = var.lambda_image_uri
  memory_size   = 512
  timeout       = 15
  logging_config {
    log_format            = "JSON"
    application_log_level = var.environment == "preview" ? "INFO" : "WARN"
    system_log_level      = var.environment == "preview" ? "INFO" : "WARN"
  }
  image_config {
    command = ["app.mcp_lambda_handler.handler"]
  }
  environment {
    variables = {
      APP_ENVIRONMENT            = var.environment
      MCP_DIAGNOSTIC_LOGS        = var.environment == "preview" ? "true" : "false"
      STORAGE_BACKEND            = "dynamodb"
      DYNAMODB_TABLE             = aws_dynamodb_table.calendar.name
      FAMILY_TIMEZONE            = var.family_timezone
      OAUTH_PROVIDER             = "cognito"
      OAUTH_ISSUER               = local.issuer
      OAUTH_JWKS_URL             = "${local.issuer}/.well-known/jwks.json"
      MCP_OAUTH_CLIENT_ID        = aws_cognito_user_pool_client.mcp.id
      MCP_RESOURCE_URL           = local.mcp_resource_url
      MCP_SCOPE_READ             = local.mcp_scope_read
      MCP_SCOPE_WRITE            = local.mcp_scope_write
      MCP_AUTHORIZATION_ENDPOINT = "${local.cognito_base}/oauth2/authorize"
      MCP_TOKEN_ENDPOINT         = "${local.cognito_base}/oauth2/token"
    }
  }
  depends_on = [aws_iam_role_policy.mcp_lambda, aws_cloudwatch_log_group.mcp_lambda]
}

resource "aws_apigatewayv2_api" "api" {
  name          = "${local.prefix}-api"
  protocol_type = "HTTP"
  tags          = { Project = var.project, Environment = var.environment }
}

resource "aws_apigatewayv2_integration" "lambda" {
  api_id                 = aws_apigatewayv2_api.api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.api.invoke_arn
  payload_format_version = "2.0"
  timeout_milliseconds   = 16000
}

resource "aws_apigatewayv2_integration" "mcp_lambda" {
  api_id                 = aws_apigatewayv2_api.api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.mcp.invoke_arn
  payload_format_version = "2.0"
  timeout_milliseconds   = 16000
}

resource "aws_apigatewayv2_authorizer" "cognito" {
  api_id           = aws_apigatewayv2_api.api.id
  name             = "${local.prefix}-cognito"
  authorizer_type  = "JWT"
  identity_sources = ["$request.header.Authorization"]
  jwt_configuration {
    issuer   = local.issuer
    audience = [aws_cognito_user_pool_client.web.id]
  }
}

resource "aws_apigatewayv2_route" "protected" {
  api_id             = aws_apigatewayv2_api.api.id
  route_key          = "$default"
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
}

resource "aws_apigatewayv2_route" "public" {
  for_each           = toset(["GET /api/health", "GET /api/v1/config", "POST /api/v1/auth/session", "POST /api/v1/auth/refresh", "POST /api/v1/auth/logout"])
  api_id             = aws_apigatewayv2_api.api.id
  route_key          = each.value
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorization_type = "NONE"
}

resource "aws_apigatewayv2_route" "mcp" {
  api_id             = aws_apigatewayv2_api.api.id
  route_key          = "POST /mcp"
  target             = "integrations/${aws_apigatewayv2_integration.mcp_lambda.id}"
  authorization_type = "NONE"
}

resource "aws_apigatewayv2_route" "mcp_metadata" {
  for_each           = toset(["GET /.well-known/oauth-protected-resource/mcp", "GET /mcp/.well-known/oauth-protected-resource", "GET /.well-known/oauth-authorization-server"])
  api_id             = aws_apigatewayv2_api.api.id
  route_key          = each.value
  target             = "integrations/${aws_apigatewayv2_integration.mcp_lambda.id}"
  authorization_type = "NONE"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.api.id
  name        = "$default"
  auto_deploy = true
  default_route_settings {
    throttling_burst_limit = 20
    throttling_rate_limit  = 10
  }
  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api.arn
    format          = jsonencode({ requestId = "$context.requestId", status = "$context.status", responseLength = "$context.responseLength", integrationStatus = "$context.integrationStatus" })
  }
}

resource "aws_lambda_permission" "api" {
  statement_id  = "ApiGatewayOnly"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.api.execution_arn}/*/*"
}

resource "aws_lambda_permission" "mcp" {
  statement_id  = "ApiGatewayMcpOnly"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.mcp.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.api.execution_arn}/*/*"
}

resource "aws_cognito_user_pool" "family" {
  name                     = local.prefix
  user_pool_tier           = "LITE"
  deletion_protection      = local.production ? "ACTIVE" : "INACTIVE"
  alias_attributes         = ["email"]
  auto_verified_attributes = ["email"]
  admin_create_user_config { allow_admin_create_user_only = false }
  password_policy {
    minimum_length                   = 14
    require_lowercase                = true
    require_uppercase                = true
    require_numbers                  = true
    require_symbols                  = true
    temporary_password_validity_days = 3
  }
  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }
}

resource "aws_cognito_user_pool_domain" "family" {
  domain                = "${local.prefix}-${var.aws_account_id}"
  user_pool_id          = aws_cognito_user_pool.family.id
  managed_login_version = 1
}

resource "aws_cognito_resource_server" "api" {
  identifier   = "${local.prefix}-api"
  name         = "${local.prefix}-api"
  user_pool_id = aws_cognito_user_pool.family.id
  scope {
    scope_name        = "access"
    scope_description = "Leer y editar el calendario familiar"
  }
}

resource "aws_cognito_resource_server" "mcp" {
  identifier   = local.mcp_resource_url
  name         = "${local.prefix}-mcp"
  user_pool_id = aws_cognito_user_pool.family.id
  scope {
    scope_name        = "calendar.read"
    scope_description = "Consultar los eventos del calendario familiar desde MCP."
  }
  scope {
    scope_name        = "calendar.write"
    scope_description = "Crear y editar eventos del calendario familiar desde MCP."
  }
}

resource "aws_cognito_user_pool_client" "web" {
  name                                 = "${local.prefix}-web"
  user_pool_id                         = aws_cognito_user_pool.family.id
  generate_secret                      = false
  supported_identity_providers         = ["COGNITO"]
  explicit_auth_flows                  = ["ALLOW_USER_PASSWORD_AUTH", "ALLOW_REFRESH_TOKEN_AUTH", "ALLOW_USER_SRP_AUTH"]
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_scopes                 = ["openid", "email", "profile", local.scope]
  callback_urls                        = ["${local.site_url}/"]
  logout_urls                          = ["${local.site_url}/"]
  prevent_user_existence_errors        = "ENABLED"
  enable_token_revocation              = true
  access_token_validity                = 15
  id_token_validity                    = 15
  refresh_token_validity               = 1
  token_validity_units {
    access_token  = "minutes"
    id_token      = "minutes"
    refresh_token = "days"
  }
}

resource "aws_cognito_user_pool_client" "mcp" {
  name                                 = "${local.prefix}-mcp-codex"
  user_pool_id                         = aws_cognito_user_pool.family.id
  generate_secret                      = false
  supported_identity_providers         = ["COGNITO"]
  explicit_auth_flows                  = ["ALLOW_REFRESH_TOKEN_AUTH"]
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_scopes                 = ["openid", local.mcp_scope_read, local.mcp_scope_write]
  callback_urls                        = [local.mcp_callback_url]
  logout_urls                          = [local.mcp_callback_url]
  prevent_user_existence_errors        = "ENABLED"
  enable_token_revocation              = true
  access_token_validity                = 15
  id_token_validity                    = 15
  refresh_token_validity               = 1
  token_validity_units {
    access_token  = "minutes"
    id_token      = "minutes"
    refresh_token = "days"
  }
  depends_on = [aws_cognito_resource_server.mcp]
}

resource "aws_secretsmanager_secret" "preview_test_account" {
  count                   = local.production ? 0 : 1
  name                    = "${local.prefix}/test-account"
  description             = "Credenciales de la familia sintética de preview."
  recovery_window_in_days = 0
}
