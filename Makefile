ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
DEPLOY_ENV := $(filter preview production,$(MAKECMDGOALS))
AWS_REGION ?= eu-west-1

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
	  'The build uses Python 3, pip and npm; no AWS login is started.'

build-aws:
	@AWS_BUILD_DIR="$(ROOT)/build/aws" sh "$(ROOT)/scripts/build_aws.sh"

bootstrap:
	@AWS_REGION="$(AWS_REGION)" sh "$(ROOT)/scripts/deploy_aws.sh" bootstrap

plan:
	@AWS_REGION="$(AWS_REGION)" sh "$(ROOT)/scripts/deploy_aws.sh" plan $(DEPLOY_ENV)

deploy:
	@AWS_REGION="$(AWS_REGION)" LAMBDA_ZIP="$(LAMBDA_ZIP)" FRONTEND_DIST="$(FRONTEND_DIST)" \
	  sh "$(ROOT)/scripts/deploy_aws.sh" deploy $(DEPLOY_ENV)

preview production:
	@case " $(MAKECMDGOALS) " in \
	  *' deploy '*|*' plan '*) ;; \
	  *) printf '%s\n' 'Use: make plan preview, make plan production, make deploy preview, or make deploy production'; exit 2 ;; \
	esac
