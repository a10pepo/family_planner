terraform {
  required_version = ">= 1.10.0, < 2.0.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "6.68.0" }
  }
  backend "s3" {}
}

provider "aws" {
  region              = var.aws_region
  allowed_account_ids = [var.aws_account_id]
  default_tags {
    tags = {
      Project     = var.project
      Environment = "preview"
      ManagedBy   = "terraform"
    }
  }
}

module "application" {
  source                  = "../../modules/application"
  environment             = "preview"
  project                 = var.project
  aws_account_id          = var.aws_account_id
  aws_region              = var.aws_region
  lambda_artifact_bucket  = var.lambda_artifact_bucket
  lambda_artifact_key     = var.lambda_artifact_key
  lambda_artifact_version = var.lambda_artifact_version
  lambda_artifact_sha256  = var.lambda_artifact_sha256
  lambda_handler          = var.lambda_handler
  family_timezone         = var.family_timezone
  domain_name             = var.domain_name
  certificate_arn         = var.certificate_arn
  route53_zone_id         = var.route53_zone_id
}
