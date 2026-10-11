terraform {
  required_version = ">= 1.10.0, < 2.0.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "6.68.0" }
  }
}

provider "aws" {
  region              = var.aws_region
  allowed_account_ids = [var.aws_account_id]
  default_tags {
    tags = {
      Project     = var.project
      Environment = "bootstrap"
      ManagedBy   = "terraform"
    }
  }
}

variable "project" {
  type    = string
  default = "family-planner"
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,28}$", var.project))
    error_message = "Usa 3–29 caracteres, minúsculas y guiones."
  }
}

variable "aws_account_id" {
  type = string
  validation {
    condition     = can(regex("^[0-9]{12}$", var.aws_account_id))
    error_message = "Indica el ID de 12 cifras de la cuenta destino."
  }
}

variable "aws_region" {
  type    = string
  default = "eu-west-1"
}

locals {
  buckets = {
    state      = "${var.project}-${var.aws_account_id}-terraform-state"
    preview    = "${var.project}-preview-${var.aws_account_id}-artifacts"
    production = "${var.project}-production-${var.aws_account_id}-artifacts"
  }
}

resource "aws_s3_bucket" "storage" {
  for_each      = local.buckets
  bucket        = each.value
  force_destroy = false
  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_public_access_block" "storage" {
  for_each                = local.buckets
  bucket                  = aws_s3_bucket.storage[each.key].id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "storage" {
  for_each = local.buckets
  bucket   = aws_s3_bucket.storage[each.key].id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_versioning" "storage" {
  for_each = local.buckets
  bucket   = aws_s3_bucket.storage[each.key].id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "storage" {
  for_each = local.buckets
  bucket   = aws_s3_bucket.storage[each.key].id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_policy" "storage" {
  for_each = local.buckets
  bucket   = aws_s3_bucket.storage[each.key].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "RequireTLS"
      Effect    = "Deny"
      Principal = "*"
      Action    = "s3:*"
      Resource  = [aws_s3_bucket.storage[each.key].arn, "${aws_s3_bucket.storage[each.key].arn}/*"]
      Condition = { Bool = { "aws:SecureTransport" = "false" } }
    }]
  })
  depends_on = [aws_s3_bucket_public_access_block.storage]
}

resource "aws_ecr_repository" "lambda" {
  for_each             = toset(["preview", "production"])
  name                 = "${var.project}-${each.value}"
  image_tag_mutability = "MUTABLE"
  force_delete         = false
  image_scanning_configuration { scan_on_push = true }
  encryption_configuration { encryption_type = "AES256" }
}

resource "aws_ecr_lifecycle_policy" "lambda" {
  for_each   = aws_ecr_repository.lambda
  repository = each.value.name
  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Remove dangling layers shortly after their tags are deleted"
        selection    = { tagStatus = "untagged", countType = "sinceImagePushed", countUnit = "days", countNumber = 1 }
        action       = { type = "expire" }
      },
      {
        rulePriority = 2
        description  = "Keep the 30 newest SHA-versioned builds for rollback"
        selection    = { tagStatus = "tagged", tagPrefixList = ["sha-"], countType = "imageCountMoreThan", countNumber = 30 }
        action       = { type = "expire" }
      }
    ]
  })
}

output "state_bucket" {
  value = aws_s3_bucket.storage["state"].id
}

output "artifact_buckets" {
  value = { for env in ["preview", "production"] : env => aws_s3_bucket.storage[env].id }
}

output "backend_keys" {
  value = { preview = "preview/terraform.tfstate", production = "production/terraform.tfstate" }
}

output "lambda_repositories" {
  value = { for environment, repository in aws_ecr_repository.lambda : environment => repository.repository_url }
}

data "aws_iam_openid_connect_provider" "github" {
  arn = "arn:aws:iam::${var.aws_account_id}:oidc-provider/token.actions.githubusercontent.com"
}

resource "aws_iam_role" "github_preview" {
  name = "${var.project}-preview-github-actions"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Federated = data.aws_iam_openid_connect_provider.github.arn }
      Action    = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = { "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com" }
        StringLike   = { "token.actions.githubusercontent.com:sub" = "repo:a10pepo/family_planner:ref:refs/heads/main" }
      }
    }]
  })
}

resource "aws_iam_role_policy" "github_preview" {
  name = "${var.project}-preview-deploy"
  role = aws_iam_role.github_preview.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "PushPreviewImage"
        Effect   = "Allow"
        Action   = ["ecr:BatchCheckLayerAvailability", "ecr:CompleteLayerUpload", "ecr:DescribeImages", "ecr:DescribeRepositories", "ecr:GetDownloadUrlForLayer", "ecr:InitiateLayerUpload", "ecr:PutImage", "ecr:UploadLayerPart"]
        Resource = aws_ecr_repository.lambda["preview"].arn
      },
      {
        Sid      = "EcrAuthentication"
        Effect   = "Allow"
        Action   = ["ecr:GetAuthorizationToken"]
        Resource = "*"
      },
      {
        Sid      = "PreviewStateAndSite"
        Effect   = "Allow"
        Action   = ["s3:GetBucketLocation", "s3:ListBucket"]
        Resource = [aws_s3_bucket.storage["state"].arn, "arn:aws:s3:::${var.project}-preview-${var.aws_account_id}-web"]
      },
      {
        Sid      = "ManagePreviewSiteBucket"
        Effect   = "Allow"
        Action   = ["s3:CreateBucket", "s3:DeleteBucket", "s3:GetBucketAcl", "s3:GetBucketLocation", "s3:GetBucketPolicy", "s3:GetBucketPublicAccessBlock", "s3:GetBucketOwnershipControls", "s3:GetBucketVersioning", "s3:GetEncryptionConfiguration", "s3:PutBucketPolicy", "s3:PutBucketPublicAccessBlock", "s3:PutBucketOwnershipControls", "s3:PutBucketVersioning", "s3:PutEncryptionConfiguration", "s3:DeleteBucketPolicy", "s3:DeleteBucketPublicAccessBlock", "s3:DeleteBucketOwnershipControls", "s3:DeleteBucketVersioning", "s3:DeleteEncryptionConfiguration", "s3:ListBucket"]
        Resource = "arn:aws:s3:::${var.project}-preview-${var.aws_account_id}-web"
      },
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
        Resource = ["${aws_s3_bucket.storage["state"].arn}/preview/*", "${aws_s3_bucket.storage["state"].arn}/preview/terraform.tfstate.tflock", "arn:aws:s3:::${var.project}-preview-${var.aws_account_id}-web/*"]
      },
      {
        Sid       = "CreateTaggedPreviewCredentialSecret"
        Effect    = "Allow"
        Action    = ["secretsmanager:CreateSecret"]
        Resource  = "*"
        Condition = { StringEquals = { "aws:RequestTag/Environment" = "preview" } }
      },
      {
        Sid      = "ManagePreviewCredentialSecret"
        Effect   = "Allow"
        Action   = ["secretsmanager:DescribeSecret", "secretsmanager:GetSecretValue", "secretsmanager:PutSecretValue", "secretsmanager:UpdateSecret", "secretsmanager:DeleteSecret", "secretsmanager:TagResource", "secretsmanager:UntagResource"]
        Resource = "arn:aws:secretsmanager:${var.aws_region}:${var.aws_account_id}:secret:${var.project}-preview/test-account-*"
      },
      {
        Sid    = "ManagePreviewData"
        Effect = "Allow"
        Action = ["dynamodb:*", "lambda:*", "logs:*", "cognito-idp:*", "apigateway:GET", "apigateway:POST", "apigateway:PUT", "apigateway:PATCH", "apigateway:DELETE", "cloudfront:CreateInvalidation", "cloudfront:DeleteDistribution", "cloudfront:DeleteOriginAccessControl", "cloudfront:GetDistribution", "cloudfront:GetDistributionConfig", "cloudfront:GetInvalidation", "cloudfront:GetOriginAccessControl", "cloudfront:ListTagsForResource", "cloudfront:TagResource", "cloudfront:UntagResource", "cloudfront:UpdateDistribution", "cloudfront:UpdateOriginAccessControl"]
        Resource = [
          "arn:aws:dynamodb:${var.aws_region}:${var.aws_account_id}:table/${var.project}-preview",
          "arn:aws:dynamodb:${var.aws_region}:${var.aws_account_id}:table/${var.project}-preview/index/*",
          "arn:aws:lambda:${var.aws_region}:${var.aws_account_id}:function:${var.project}-preview-*",
          "arn:aws:logs:${var.aws_region}:${var.aws_account_id}:log-group:/aws/lambda/${var.project}-preview-*",
          "arn:aws:logs:${var.aws_region}:${var.aws_account_id}:log-group:/aws/apigateway/${var.project}-preview*",
          "arn:aws:cognito-idp:${var.aws_region}:${var.aws_account_id}:userpool/*",
          "arn:aws:apigateway:${var.aws_region}::/apis/*",
          "arn:aws:cloudfront::${var.aws_account_id}:distribution/*",
          "arn:aws:cloudfront::${var.aws_account_id}:origin-access-control/*"
        ]
        Condition = { StringEquals = { "aws:ResourceTag/Environment" = "preview" } }
      },
      {
        Sid      = "CreateTaggedPreviewResources"
        Effect   = "Allow"
        Action   = ["dynamodb:CreateTable", "lambda:CreateFunction", "logs:CreateLogGroup", "cognito-idp:CreateUserPool", "apigateway:POST"]
        Resource = "*"
        Condition = {
          StringEquals = { "aws:RequestTag/Environment" = "preview" }
        }
      },
      {
        Sid      = "CreatePreviewEdgeResources"
        Effect   = "Allow"
        Action   = ["cloudfront:CreateDistribution"]
        Resource = "*"
        Condition = {
          StringEquals = { "aws:RequestTag/Environment" = "preview" }
        }
      },
      {
        Sid      = "CreatePreviewOriginAccessControl"
        Effect   = "Allow"
        Action   = ["cloudfront:CreateOriginAccessControl"]
        Resource = "*"
      },
      {
        Sid      = "PassPreviewLambdaRole"
        Effect   = "Allow"
        Action   = ["iam:AttachRolePolicy", "iam:CreateRole", "iam:DeleteRole", "iam:DeleteRolePolicy", "iam:DetachRolePolicy", "iam:GetRole", "iam:GetRolePolicy", "iam:ListAttachedRolePolicies", "iam:ListRolePolicies", "iam:PassRole", "iam:PutRolePolicy", "iam:TagRole", "iam:UntagRole", "iam:UpdateAssumeRolePolicy"]
        Resource = "arn:aws:iam::${var.aws_account_id}:role/${var.project}-preview-lambda"
      }
    ]
  })
}

output "github_preview_role_arn" {
  value = aws_iam_role.github_preview.arn
}
