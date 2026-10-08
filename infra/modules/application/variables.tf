variable "environment" {
  type = string
  validation {
    condition     = contains(["preview", "production"], var.environment)
    error_message = "El entorno debe ser preview o production."
  }
}

variable "project" {
  type    = string
  default = "family-planner"
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,29}$", var.project))
    error_message = "Usa un nombre de proyecto de 3–30 caracteres, minúsculas y guiones."
  }
}

variable "aws_account_id" {
  type = string
  validation {
    condition     = can(regex("^[0-9]{12}$", var.aws_account_id))
    error_message = "Indica el ID de 12 cifras de la cuenta AWS destino."
  }
}

variable "aws_region" { type = string }

variable "lambda_artifact_bucket" {
  type = string
  validation {
    condition     = var.lambda_artifact_bucket == "${var.project}-${var.environment}-${var.aws_account_id}-artifacts"
    error_message = "El ZIP debe estar en el bucket de artefactos del mismo proyecto, entorno y cuenta."
  }
}

variable "lambda_artifact_key" {
  type = string
  validation {
    condition     = startswith(var.lambda_artifact_key, "${var.environment}/") && endswith(var.lambda_artifact_key, ".zip")
    error_message = "La clave del ZIP debe empezar por el entorno y terminar en .zip."
  }
}

variable "lambda_artifact_version" {
  type = string
  validation {
    condition     = length(trimspace(var.lambda_artifact_version)) > 0 && var.lambda_artifact_version != "null"
    error_message = "Indica una versión real del objeto S3; no se despliega un ZIP mutable sin versión."
  }
}

variable "lambda_artifact_sha256" {
  type = string
  validation {
    condition     = can(regex("^[A-Za-z0-9+/]{43}=$", var.lambda_artifact_sha256))
    error_message = "El hash del ZIP debe ser SHA-256 codificado en base64."
  }
}

variable "lambda_handler" {
  type        = string
  default     = "app.lambda_handler.handler"
  description = "Entrada del artefacto compatible con API Gateway HTTP payload v2."
}

variable "family_timezone" {
  type    = string
  default = "Europe/Madrid"
}

variable "domain_name" {
  type     = string
  default  = null
  nullable = true
  validation {
    condition     = var.domain_name == null ? true : can(regex("^[a-z0-9.-]+\\.[a-z]{2,}$", var.domain_name))
    error_message = "Indica un nombre DNS sin https:// ni rutas."
  }
}

variable "certificate_arn" {
  type     = string
  default  = null
  nullable = true
  validation {
    condition     = var.domain_name == null ? var.certificate_arn == null : can(regex("^arn:aws:acm:us-east-1:${var.aws_account_id}:certificate/", var.certificate_arn))
    error_message = "Un dominio propio requiere un certificado ACM existente en us-east-1. Sin dominio, deja el certificado vacío."
  }
}

variable "route53_zone_id" {
  type     = string
  default  = null
  nullable = true
  validation {
    condition     = var.route53_zone_id == null || var.domain_name != null
    error_message = "Una zona Route53 requiere un dominio propio."
  }
}
