ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
DEPLOY_ENV := $(filter preview production,$(MAKECMDGOALS))
AWS_REGION ?= eu-west-1
TERRAFORM_VERSION ?= 1.16.5

LAMBDA_ZIP ?= $(ROOT)/build/aws/api-compatible.zip
FRONTEND_DIST ?= $(ROOT)/build/aws/frontend-compatible/dist

.PHONY: help build-aws bootstrap plan deploy preview production

help:
	@printf '%s\n' \
	  'make bootstrap          Plan and confirm the one-time AWS bucket bootstrap' \
	  'make plan preview       Show the configured preview Terraform plan' \
	  'make plan production    Show the configured production Terraform plan' \
	  'make deploy preview     Deploy the configured preview artifacts and infrastructure' \
	  'make deploy production  Deploy the configured production artifacts and infrastructure' \
	  'Make selects Terraform $(TERRAFORM_VERSION) locally and builds the frontend with Node 24 in Docker.' \
	  'No AWS login is started.'

build-aws:
	@AWS_BUILD_DIR="$(ROOT)/build/aws" sh "$(ROOT)/scripts/build_aws.sh"

bootstrap:
	@TERRAFORM_VERSION="$(TERRAFORM_VERSION)" AWS_REGION="$(AWS_REGION)" \
	  sh "$(ROOT)/scripts/run_aws_with_terraform.sh" bootstrap

plan:
	@TERRAFORM_VERSION="$(TERRAFORM_VERSION)" AWS_REGION="$(AWS_REGION)" \
	  sh "$(ROOT)/scripts/run_aws_with_terraform.sh" plan $(DEPLOY_ENV)

deploy:
	@TERRAFORM_VERSION="$(TERRAFORM_VERSION)" AWS_REGION="$(AWS_REGION)" \
	  LAMBDA_ZIP="$(LAMBDA_ZIP)" FRONTEND_DIST="$(FRONTEND_DIST)" \
	  sh "$(ROOT)/scripts/run_aws_with_terraform.sh" deploy $(DEPLOY_ENV)

preview production:
	@case " $(MAKECMDGOALS) " in \
	  *' deploy '*|*' plan '*) ;; \
	  *) printf '%s\n' 'Use: make plan preview, make plan production, make deploy preview, or make deploy production'; exit 2 ;; \
	esac
