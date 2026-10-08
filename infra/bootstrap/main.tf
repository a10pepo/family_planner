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
    condition     = can(regex("^[a-z][a-z0-9-]{2,29}$", var.project))
    error_message = "Usa 3–30 caracteres, minúsculas y guiones."
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

output "state_bucket" {
  value = aws_s3_bucket.storage["state"].id
}

output "artifact_buckets" {
  value = { for env in ["preview", "production"] : env => aws_s3_bucket.storage[env].id }
}

output "backend_keys" {
  value = { preview = "preview/terraform.tfstate", production = "production/terraform.tfstate" }
}
