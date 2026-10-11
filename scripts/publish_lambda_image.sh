#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
ENVIRONMENT=${1:-}
case "$ENVIRONMENT" in preview|production) ;; *) printf '%s\n' 'Usage: publish_lambda_image.sh preview|production' >&2; exit 2 ;; esac

command -v aws >/dev/null 2>&1 || { printf '%s\n' "Error: aws CLI no está disponible." >&2; exit 1; }
command -v docker >/dev/null 2>&1 || { printf '%s\n' "Error: Docker no está disponible." >&2; exit 1; }
command -v terraform >/dev/null 2>&1 || { printf '%s\n' "Error: Terraform no está disponible." >&2; exit 1; }

docker_config_tmp=
cleanup() {
  if [ -n "${docker_config_tmp:-}" ]; then rm -rf "$docker_config_tmp"; fi
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM
if [ -z "${DOCKER_CONFIG:-}" ]; then
  if [ -z "${DOCKER_HOST:-}" ]; then
    docker_context=${DOCKER_CONTEXT:-$(docker context show)}
    DOCKER_HOST=$(docker context inspect --format '{{.Endpoints.docker.Host}}' "$docker_context")
    export DOCKER_HOST
    unset DOCKER_CONTEXT
  fi
  docker_config_tmp=$(mktemp -d "${TMPDIR:-/tmp}/family-planner-docker.XXXXXX")
  printf '{"auths":{}}\n' > "$docker_config_tmp/config.json"
  DOCKER_CONFIG=$docker_config_tmp
  export DOCKER_CONFIG
fi

repository_uri=$(terraform -chdir="$ROOT/infra/bootstrap" output -json lambda_repositories | python3 -c 'import json,sys; print(json.load(sys.stdin)[sys.argv[1]])' "$ENVIRONMENT")
region=${AWS_REGION:-$(aws configure get region 2>/dev/null || true)}
region=${region:-eu-west-1}
account=${repository_uri%%.dkr.ecr.*}
account=${account##*/}
commit=$(git -C "$ROOT" rev-parse HEAD)
tag="sha-$commit"

local_image=${BACKEND_IMAGE:-family-planner-lambda:local}
docker image inspect "$local_image" >/dev/null 2>&1 || {
  printf 'Error: falta la imagen local %s; ejecuta make build-aws primero.\n' "$local_image" >&2
  exit 1
}
printf 'Etiquetando la imagen Lambda ya construida para ECR...\n' >&2
docker tag "$local_image" "$repository_uri:$tag"
printf 'Autenticando Docker en ECR...\n' >&2
aws ecr get-login-password --region "$region" | docker login --username AWS --password-stdin "$account.dkr.ecr.$region.amazonaws.com"
docker push "$repository_uri:$tag"

if [ "$ENVIRONMENT" = production ]; then
  docker tag "$repository_uri:$tag" "$repository_uri:latest"
  docker push "$repository_uri:latest"
fi

digest=$(aws ecr describe-images --region "$region" --repository-name "${repository_uri##*/}" --image-ids "imageTag=$tag" --query 'imageDetails[0].imageDigest' --output text)
case "$digest" in sha256:????????????????????????????????????????????????????????????????) ;; *) printf 'Error: ECR no devolvió un digest válido (%s).\n' "$digest" >&2; exit 1 ;; esac
printf '%s@%s\n' "$repository_uri" "$digest"
