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
    condition     = can(regex("^[a-z][a-z0-9-]{2,28}$", var.project))
    error_message = "Usa un nombre de proyecto de 3–29 caracteres, minúsculas y guiones."
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

variable "user_pool_tier" {
  type    = string
  default = "LITE"
  validation {
    condition     = contains(["LITE", "ESSENTIALS", "PLUS"], var.user_pool_tier)
    error_message = "El plan Cognito debe ser LITE, ESSENTIALS o PLUS."
  }
}

variable "managed_login_version" {
  type    = number
  default = 1
  validation {
    condition     = contains([1, 2], var.managed_login_version)
    error_message = "La versión de login de Cognito debe ser 1 (clásica) o 2 (Managed Login)."
  }
}

variable "lambda_image_uri" {
  type = string
  validation {
    condition     = can(regex("^[0-9]{12}\\.dkr\\.ecr\\.[a-z0-9-]+\\.amazonaws\\.com/${var.project}-${var.environment}(@sha256:[a-f0-9]{64}|:sha-[a-f0-9]{40})$", var.lambda_image_uri))
    error_message = "Usa una URI inmutable del repositorio ECR del entorno, fijada por digest o por etiqueta SHA."
  }
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
