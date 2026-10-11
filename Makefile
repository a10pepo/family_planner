ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
DEPLOY_ENV := $(filter preview production,$(MAKECMDGOALS))
AWS_REGION ?= eu-west-1
TERRAFORM_VERSION ?= 1.16.5

FRONTEND_DIST ?= $(ROOT)/build/aws/frontend-compatible/dist

.PHONY: help build-aws bootstrap plan deploy destroy preview-credentials preview production

help:
	@printf '%s\n' \
	  'make bootstrap          Plan and confirm the one-time AWS bucket bootstrap' \
	  'make plan preview       Show the configured preview Terraform plan' \
	  'make plan production    Show the configured production Terraform plan' \
	  'make deploy preview     Deploy the configured preview image and infrastructure' \
	  'make deploy production  Deploy the configured production image and infrastructure' \
	  'make destroy preview    Destroy preview resources and web assets' \
	  'make preview-credentials  Read the synthetic preview account from Secrets Manager' \
	  'Make selects Terraform $(TERRAFORM_VERSION) locally and builds the frontend with Node 24 in Docker.' \
	  'No AWS login is started.'

build-aws:
	@AWS_BUILD_DIR="$(ROOT)/build/aws" sh "$(ROOT)/scripts/build_aws.sh"

bootstrap:
	@printf 'Preparando bootstrap AWS con Terraform %s...\n' "$(TERRAFORM_VERSION)"
	@TERRAFORM_VERSION="$(TERRAFORM_VERSION)" AWS_REGION="$(AWS_REGION)" \
	  sh "$(ROOT)/scripts/run_aws_with_terraform.sh" bootstrap

plan:
	@printf 'Preparando plan Terraform para %s...\n' "$(DEPLOY_ENV)"
	@TERRAFORM_VERSION="$(TERRAFORM_VERSION)" AWS_REGION="$(AWS_REGION)" \
	  sh "$(ROOT)/scripts/run_aws_with_terraform.sh" plan $(DEPLOY_ENV)

deploy:
	@printf 'Preparando despliegue %s...\n' "$(DEPLOY_ENV)"
	@TERRAFORM_VERSION="$(TERRAFORM_VERSION)" AWS_REGION="$(AWS_REGION)" \
	  FRONTEND_DIST="$(FRONTEND_DIST)" \
	  sh "$(ROOT)/scripts/run_aws_with_terraform.sh" deploy $(DEPLOY_ENV)

destroy:
	@printf 'Preparando destroy de %s...\n' "$(DEPLOY_ENV)"
	@TERRAFORM_VERSION="$(TERRAFORM_VERSION)" AWS_REGION="$(AWS_REGION)" \
	  sh "$(ROOT)/scripts/run_aws_with_terraform.sh" destroy $(DEPLOY_ENV)

preview-credentials:
	@printf 'Consultando credenciales de preview en Secrets Manager...\n'
	@TERRAFORM_VERSION="$(TERRAFORM_VERSION)" AWS_REGION="$(AWS_REGION)" \
	  sh "$(ROOT)/scripts/run_aws_with_terraform.sh" preview-credentials

preview production:
	@case " $(MAKECMDGOALS) " in \
	  *' deploy '*|*' plan '*|*' destroy '*) ;; \
	  *) printf '%s\n' 'Use: make plan preview, make plan production, make deploy preview, make deploy production, or make destroy preview'; exit 2 ;; \
	esac
