ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
DEPLOY_ENV := $(filter preview production,$(MAKECMDGOALS))

LAMBDA_ZIP ?= build/aws/api-compatible.zip
FRONTEND_DIST ?= build/aws/frontend-compatible/dist

.PHONY: help bootstrap plan deploy preview production

help:
	@printf '%s\n' \
	  'make bootstrap          Plan and confirm the one-time AWS bucket bootstrap' \
	  'make plan preview       Show the configured preview Terraform plan' \
	  'make plan production    Show the configured production Terraform plan' \
	  'make deploy preview     Deploy the configured preview artifacts and infrastructure' \
	  'make deploy production  Deploy the configured production artifacts and infrastructure' \
	  'Override artifact paths with LAMBDA_ZIP=... and FRONTEND_DIST=...'

bootstrap:
	@sh "$(ROOT)/scripts/deploy_aws.sh" bootstrap

plan:
	@sh "$(ROOT)/scripts/deploy_aws.sh" plan $(DEPLOY_ENV)

deploy:
	@LAMBDA_ZIP="$(LAMBDA_ZIP)" FRONTEND_DIST="$(FRONTEND_DIST)" \
	  sh "$(ROOT)/scripts/deploy_aws.sh" deploy $(DEPLOY_ENV)

preview production:
	@case " $(MAKECMDGOALS) " in \
	  *' deploy '*|*' plan '*) ;; \
	  *) printf '%s\n' 'Use: make plan preview, make plan production, make deploy preview, or make deploy production'; exit 2 ;; \
	esac
