#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
BOOTSTRAP_DIR="$ROOT/infra/bootstrap"
BOOTSTRAP_VARS="$BOOTSTRAP_DIR/terraform.tfvars"
API_ZIP=${LAMBDA_ZIP:-$ROOT/build/aws/api-compatible.zip}
FRONTEND_DIST=${FRONTEND_DIST:-$ROOT/build/aws/frontend-compatible/dist}
AWS_REGION=${AWS_REGION:-eu-west-1}

usage() {
  printf '%s\n' \
    'Usage: make bootstrap' \
    '       make plan preview' \
    '       make plan production' \
    '       make deploy preview' \
    '       make deploy production'
}

fail() {
  printf 'Error: %s\n' "$1" >&2
  exit 1
}

read_tfvar() {
  key=$1
  file=$2
  awk -F= -v key="$key" '
    $1 ~ "^[[:space:]]*" key "[[:space:]]*$" {
      value = $2
      sub(/[[:space:]]*#.*/, "", value)
      gsub(/["[:space:]]/, "", value)
      print value
      exit
    }
  ' "$file"
}

require_file() {
  [ -f "$1" ] || fail "Falta $1. Prepara la configuración indicada en infra/README.md."
}

require_tools() {
  for tool in aws openssl python3; do
    command -v "$tool" >/dev/null 2>&1 || fail "No se encuentra '$tool' en PATH."
  done
}

active_account() {
  aws sts get-caller-identity --query Account --output text 2>/dev/null ||
    fail "No hay una sesión AWS CLI válida. Inicia sesión localmente y vuelve a ejecutar make."
}

prepare_config() {
  account=$(active_account)
  region=$AWS_REGION
  if [ -z "$region" ] && [ -n "${AWS_PROFILE:-}" ]; then
    region=$(aws configure get region --profile "$AWS_PROFILE" 2>/dev/null || true)
  fi
  region=${region:-eu-west-1}
  export AWS_REGION="$region" AWS_DEFAULT_REGION="$region"
  mkdir -p "$BOOTSTRAP_DIR"
  if [ ! -f "$BOOTSTRAP_VARS" ]; then
    cat > "$BOOTSTRAP_VARS" <<EOF
aws_account_id = "$account"
aws_region     = "$region"
EOF
    printf 'Configuración local creada: %s (cuenta %s, región %s).\n' "$BOOTSTRAP_VARS" "$account" "$region"
  fi
  bootstrap_region=$(read_tfvar aws_region "$BOOTSTRAP_VARS")
  [ "$bootstrap_region" = "$region" ] ||
    fail "$BOOTSTRAP_VARS usa la región $bootstrap_region, pero el perfil/comando selecciona $region."
  project=$(read_tfvar project "$BOOTSTRAP_VARS")
  project=${project:-family-planner}
  for config_environment in preview production; do
    environment_dir="$ROOT/infra/environments/$config_environment"
    mkdir -p "$environment_dir"
    variables_file="$environment_dir/terraform.tfvars"
    backend_file="$environment_dir/backend.hcl"
    bucket="$project-$account-terraform-state"
    if [ ! -f "$variables_file" ]; then
      cat > "$variables_file" <<EOF
aws_account_id = "$account"
aws_region     = "$region"
EOF
      printf 'Configuración local creada: %s\n' "$variables_file"
    fi
    if [ ! -f "$backend_file" ]; then
      {
        printf 'bucket       = "%s"\n' "$bucket"
        printf 'key          = "%s/terraform.tfstate"\n' "$config_environment"
        printf 'region       = "%s"\n' "$region"
        printf 'allowed_account_ids = ["%s"]\n' "$account"
        printf 'encrypt      = true\nuse_lockfile = true\n'
        if [ -n "${AWS_PROFILE:-}" ]; then printf 'profile      = "%s"\n' "$AWS_PROFILE"; fi
      } > "$backend_file"
      printf 'Configuración local creada: %s\n' "$backend_file"
    fi
    check_account "$variables_file"
    configured_region=$(read_tfvar aws_region "$variables_file")
    [ "$configured_region" = "$region" ] ||
      fail "$variables_file usa la región $configured_region, pero el perfil/comando selecciona $region."
  done
}

check_account() {
  config_file=$1
  expected=$(read_tfvar aws_account_id "$config_file")
  [ -n "$expected" ] || fail "No se pudo leer aws_account_id de $config_file."
  actual=$(active_account)
  [ "$actual" = "$expected" ] ||
    fail "La sesión activa apunta a la cuenta $actual, pero $config_file configura $expected."
  printf 'Cuenta AWS verificada: %s\n' "$actual"
}

confirm_plan() {
  phrase=$1
  printf '\nRevisa el plan anterior y los costes. Escribe "%s" para continuar: ' "$phrase"
  IFS= read -r answer
  [ "$answer" = "$phrase" ] || fail "Aplicación cancelada."
}

temporary_plan_dir() {
  mktemp -d "${TMPDIR:-/tmp}/family-planner-aws-plan.XXXXXX"
}

check_environment() {
  environment=$1
  environment_dir="$ROOT/infra/environments/$environment"
  variables_file="$environment_dir/terraform.tfvars"
  backend_file="$environment_dir/backend.hcl"

  require_file "$BOOTSTRAP_VARS"
  require_file "$backend_file"
  require_file "$variables_file"
  check_account "$variables_file"

  state_bucket=$(terraform -chdir="$BOOTSTRAP_DIR" output -raw state_bucket)
  backend_bucket=$(read_tfvar bucket "$backend_file")
  backend_key=$(read_tfvar key "$backend_file")
  backend_region=$(read_tfvar region "$backend_file")
  configured_region=$(read_tfvar aws_region "$variables_file")
  [ "$backend_bucket" = "$state_bucket" ] ||
    fail "El bucket de $backend_file no coincide con el bucket de estado del bootstrap ($state_bucket)."
  [ "$backend_key" = "$environment/terraform.tfstate" ] ||
    fail "Usa la clave de estado $environment/terraform.tfstate en $backend_file."
  [ -n "$backend_region" ] && [ "$backend_region" = "$configured_region" ] ||
    fail "La región de $backend_file debe coincidir con aws_region en $variables_file."
}

ensure_bootstrap() {
  prepare_config
  check_account "$BOOTSTRAP_VARS"
  plan_dir=$(temporary_plan_dir)
  trap 'rm -rf "$plan_dir"' 0 HUP INT TERM
  if [ ! -f "$BOOTSTRAP_DIR/terraform.tfstate" ]; then
    project=$(read_tfvar project "$BOOTSTRAP_VARS")
    project=${project:-family-planner}
    bucket="$project-$(read_tfvar aws_account_id "$BOOTSTRAP_VARS")-terraform-state"
    if aws s3api head-bucket --bucket "$bucket" >/dev/null 2>&1; then
      fail "El bucket de estado $bucket ya existe, pero falta el estado local $BOOTSTRAP_DIR/terraform.tfstate. Restaura el estado antes de continuar; no se importará ni recreará automáticamente."
    fi
  fi
  terraform -chdir="$BOOTSTRAP_DIR" init -input=false
  set +e
  terraform -chdir="$BOOTSTRAP_DIR" plan -input=false -detailed-exitcode -out="$plan_dir/bootstrap.tfplan"
  status=$?
  set -e
  [ "$status" -le 2 ] || fail "Falló el plan de bootstrap."
  if [ "$status" -eq 2 ]; then
    terraform -chdir="$BOOTSTRAP_DIR" show -no-color "$plan_dir/bootstrap.tfplan"
    confirm_plan 'APPLY bootstrap'
    terraform -chdir="$BOOTSTRAP_DIR" apply -input=false "$plan_dir/bootstrap.tfplan"
  fi
  trap - 0 HUP INT TERM
  rm -rf "$plan_dir"
}

build_artifacts() {
  AWS_BUILD_DIR="$ROOT/build/aws" sh "$ROOT/scripts/build_aws.sh"
  [ "$API_ZIP" = "$ROOT/build/aws/api-compatible.zip" ] || cp "$ROOT/build/aws/api-compatible.zip" "$API_ZIP"
  if [ "$FRONTEND_DIST" != "$ROOT/build/aws/frontend-compatible/dist" ]; then
    rm -rf "$FRONTEND_DIST"
    mkdir -p "$(dirname "$FRONTEND_DIST")"
    cp -R "$ROOT/build/aws/frontend-compatible/dist" "$FRONTEND_DIST"
  fi
  require_file "$API_ZIP"
  require_file "$FRONTEND_DIST/index.html"
}

upload_lambda() {
  environment=$1
  artifact_buckets=$(terraform -chdir="$BOOTSTRAP_DIR" output -json artifact_buckets)
  artifact_bucket=$(printf '%s' "$artifact_buckets" | python3 -c \
    'import json,sys; print(json.load(sys.stdin)[sys.argv[1]])' "$environment")
  printf 'Subiendo el paquete Lambda versionado a %s/%s/...\n' "$artifact_bucket" "$environment"
  commit=$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || date -u +%Y%m%dT%H%M%SZ)
  artifact_key="$environment/$commit-$(basename "$API_ZIP")"
  artifact_version=$(aws s3api put-object --bucket "$artifact_bucket" --key "$artifact_key" --body "$API_ZIP" --query VersionId --output text)
  case "$artifact_version" in ''|None|null) fail "S3 no devolvió VersionId; comprueba que el bucket tenga versionado habilitado." ;; esac
  artifact_sha256=$(openssl dgst -sha256 -binary "$API_ZIP" | openssl base64 -A)
}

plan() {
  [ "$#" -eq 1 ] || { usage >&2; exit 2; }
  environment=$1
  case "$environment" in
    preview|production) ;;
    *) usage >&2; exit 2 ;;
  esac

  require_tools
  build_artifacts
  ensure_bootstrap
  prepare_config
  check_environment "$environment"
  upload_lambda "$environment"

  environment_dir="$ROOT/infra/environments/$environment"
  plan_dir=$(temporary_plan_dir)
  trap 'rm -rf "$plan_dir"' 0 HUP INT TERM
  terraform -chdir="$environment_dir" init -input=false -backend-config=backend.hcl
  terraform -chdir="$environment_dir" plan -input=false -out="$plan_dir/$environment.tfplan" \
    -var="lambda_artifact_bucket=$artifact_bucket" \
    -var="lambda_artifact_key=$artifact_key" \
    -var="lambda_artifact_version=$artifact_version" \
    -var="lambda_artifact_sha256=$artifact_sha256"
  terraform -chdir="$environment_dir" show -no-color "$plan_dir/$environment.tfplan"
  printf '\nPlan de %s mostrado; no se aplicaron cambios.\n' "$environment"
}

bootstrap() {
  require_tools
  ensure_bootstrap
  terraform -chdir="$BOOTSTRAP_DIR" output
}

deploy() {
  [ "$#" -eq 1 ] || { usage >&2; exit 2; }
  environment=$1
  case "$environment" in
    preview|production) ;;
    *) usage >&2; exit 2 ;;
  esac

  require_tools
  build_artifacts
  ensure_bootstrap
  prepare_config

  environment_dir="$ROOT/infra/environments/$environment"
  check_environment "$environment"

  upload_lambda "$environment"

  plan_dir=$(temporary_plan_dir)
  trap 'rm -rf "$plan_dir"' 0 HUP INT TERM
  terraform -chdir="$environment_dir" init -input=false -backend-config=backend.hcl
  terraform -chdir="$environment_dir" plan -input=false -out="$plan_dir/$environment.tfplan" \
    -var="lambda_artifact_bucket=$artifact_bucket" \
    -var="lambda_artifact_key=$artifact_key" \
    -var="lambda_artifact_version=$artifact_version" \
    -var="lambda_artifact_sha256=$artifact_sha256"
  terraform -chdir="$environment_dir" show -no-color "$plan_dir/$environment.tfplan"
  confirm_plan "APPLY $environment"
  terraform -chdir="$environment_dir" apply -input=false "$plan_dir/$environment.tfplan"

  frontend_bucket=$(terraform -chdir="$environment_dir" output -raw frontend_bucket)
  distribution_id=$(terraform -chdir="$environment_dir" output -raw cloudfront_distribution_id)
  aws cloudfront wait distribution-deployed --id "$distribution_id"
  aws s3 sync "$FRONTEND_DIST/" "s3://$frontend_bucket/" \
    --exclude index.html \
    --cache-control 'public,max-age=31536000,immutable'
  aws s3 cp "$FRONTEND_DIST/index.html" "s3://$frontend_bucket/index.html" \
    --content-type text/html \
    --cache-control 'no-cache'
  aws cloudfront create-invalidation \
    --distribution-id "$distribution_id" \
    --paths '/*'
  printf '\nDespliegue %s terminado: ' "$environment"
  terraform -chdir="$environment_dir" output -raw site_url
}

case "${1:-}" in
  bootstrap)
    [ "$#" -eq 1 ] || { usage >&2; exit 2; }
    bootstrap
    ;;
  deploy)
    shift
    deploy "$@"
    ;;
  plan)
    shift
    plan "$@"
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac
