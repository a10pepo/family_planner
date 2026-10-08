locals {
  prefix      = "${var.project}-${var.environment}"
  bucket_name = "${local.prefix}-${var.aws_account_id}-web"
  issuer      = "https://cognito-idp.${var.aws_region}.amazonaws.com/${aws_cognito_user_pool.family.id}"
  site_url    = "https://${var.domain_name != null ? var.domain_name : aws_cloudfront_distribution.frontend.domain_name}"
  login_host  = "${aws_cognito_user_pool_domain.family.domain}.auth.${var.aws_region}.amazoncognito.com"
  scope       = "${aws_cognito_resource_server.api.identifier}/access"
  production  = var.environment == "production"
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
  server_side_encryption { enabled = true }
  point_in_time_recovery { enabled = local.production }
}

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${local.prefix}-api"
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
        Action   = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:DeleteItem", "dynamodb:Query", "dynamodb:BatchGetItem", "dynamodb:DescribeTable", "dynamodb:ConditionCheckItem"]
        Resource = aws_dynamodb_table.calendar.arn
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

resource "aws_lambda_function" "api" {
  function_name     = "${local.prefix}-api"
  role              = aws_iam_role.lambda.arn
  runtime           = "python3.12"
  architectures     = ["x86_64"]
  handler           = var.lambda_handler
  s3_bucket         = var.lambda_artifact_bucket
  s3_key            = var.lambda_artifact_key
  s3_object_version = var.lambda_artifact_version
  source_code_hash  = var.lambda_artifact_sha256
  memory_size       = 512
  timeout           = 15
  environment {
    variables = {
      APP_ENVIRONMENT      = var.environment
      APP_ORIGIN           = local.site_url
      STORAGE_BACKEND      = "dynamodb"
      DYNAMODB_TABLE       = aws_dynamodb_table.calendar.name
      FAMILY_TIMEZONE      = var.family_timezone
      OAUTH_PROVIDER       = "cognito"
      OAUTH_ISSUER         = local.issuer
      OAUTH_CLIENT_ID      = aws_cognito_user_pool_client.web.id
      OAUTH_REQUIRED_SCOPE = local.scope
      OAUTH_REQUIRED_GROUP = aws_cognito_user_group.family.name
    }
  }
  depends_on = [aws_iam_role_policy.lambda, aws_cloudwatch_log_group.lambda]
}

resource "aws_apigatewayv2_api" "api" {
  name          = "${local.prefix}-api"
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_integration" "lambda" {
  api_id                 = aws_apigatewayv2_api.api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.api.invoke_arn
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
  api_id               = aws_apigatewayv2_api.api.id
  route_key            = "$default"
  target               = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorization_type   = "JWT"
  authorizer_id        = aws_apigatewayv2_authorizer.cognito.id
  authorization_scopes = [local.scope]
}

resource "aws_apigatewayv2_route" "public" {
  for_each           = toset(["GET /api/health", "GET /api/v1/config"])
  api_id             = aws_apigatewayv2_api.api.id
  route_key          = each.value
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
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

resource "aws_cognito_user_pool" "family" {
  name                = local.prefix
  user_pool_tier      = "LITE"
  deletion_protection = local.production ? "ACTIVE" : "INACTIVE"
  admin_create_user_config { allow_admin_create_user_only = true }
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
      name     = "admin_only"
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

resource "aws_cognito_user_group" "family" {
  name         = "family-app"
  description  = "Cuenta familiar autorizada de ${var.environment}"
  user_pool_id = aws_cognito_user_pool.family.id
}

resource "aws_cognito_user_pool_client" "web" {
  name                                 = "${local.prefix}-web"
  user_pool_id                         = aws_cognito_user_pool.family.id
  generate_secret                      = false
  supported_identity_providers         = ["COGNITO"]
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
  explicit_auth_flows = ["ALLOW_REFRESH_TOKEN_AUTH"]
}
