#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
OUT=${AWS_BUILD_DIR:-"$ROOT/build/aws"}
FRONTEND_OUT="$OUT/frontend-compatible/dist"
BACKEND_IMAGE=${BACKEND_IMAGE:-family-planner-lambda:local}
FRONTEND_BUILDER_IMAGE=${FRONTEND_BUILDER_IMAGE:-family-planner-aws-frontend-builder:node24}

command -v docker >/dev/null 2>&1 || { printf '%s\n' "Error: Docker no está disponible para construir las imágenes." >&2; exit 1; }
lambda_context=$(mktemp -d "${TMPDIR:-/tmp}/family-planner-lambda-context.XXXXXX")
frontend_container=
docker_config_tmp=
cleanup() {
  if [ -n "${frontend_container:-}" ]; then docker rm -f "$frontend_container" >/dev/null 2>&1 || true; fi
  if [ -n "${docker_config_tmp:-}" ]; then rm -rf "$docker_config_tmp"; fi
  if [ -n "${lambda_context:-}" ]; then rm -rf "$lambda_context"; fi
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

mkdir -p "$lambda_context/backend" "$lambda_context/docs"
cp "$ROOT/backend/Dockerfile.lambda" "$lambda_context/Dockerfile"
cp "$ROOT/backend/requirements-lambda.txt" "$lambda_context/backend/requirements-lambda.txt"
cp -R "$ROOT/backend/app" "$lambda_context/backend/app"
cp "$ROOT/docs/openapi.json" "$lambda_context/docs/openapi.json"
printf 'Construyendo imagen Lambda (linux/amd64)...\n'
docker build --progress=plain --platform linux/amd64 -f "$lambda_context/Dockerfile" -t "$BACKEND_IMAGE" "$lambda_context"
printf 'Construyendo frontend con Node 24 dentro de Docker...\n'
docker build --progress=plain --target build -f "$ROOT/frontend/Dockerfile" -t "$FRONTEND_BUILDER_IMAGE" "$ROOT"
frontend_container=$(docker create "$FRONTEND_BUILDER_IMAGE")
rm -rf "$FRONTEND_OUT"
mkdir -p "$FRONTEND_OUT"
docker cp "$frontend_container:/app/dist/." "$FRONTEND_OUT"
cleanup
frontend_container=
docker_config_tmp=
trap - EXIT HUP INT TERM
printf 'Artefactos listos:\n  Imagen Lambda %s\n  %s\n' "$BACKEND_IMAGE" "$FRONTEND_OUT/index.html"
