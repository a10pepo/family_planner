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
  source                = "../../modules/application"
  environment           = "preview"
  project               = var.project
  aws_account_id        = var.aws_account_id
  aws_region            = var.aws_region
  lambda_image_uri      = var.lambda_image_uri
  user_pool_tier        = "ESSENTIALS"
  managed_login_version = 2
  family_timezone       = var.family_timezone
  domain_name           = var.domain_name
  certificate_arn       = var.certificate_arn
  route53_zone_id       = var.route53_zone_id
}
