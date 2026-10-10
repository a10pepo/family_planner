#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
OUT=${AWS_BUILD_DIR:-"$ROOT/build/aws"}
LAMBDA_OUT="$OUT/lambda"
FRONTEND_OUT="$OUT/frontend-compatible/dist"
FRONTEND_BUILDER_IMAGE=${FRONTEND_BUILDER_IMAGE:-family-planner-aws-frontend-builder:node24}

command -v python3 >/dev/null 2>&1 || { printf '%s\n' "Error: Python 3 y pip no están disponibles." >&2; exit 1; }
command -v docker >/dev/null 2>&1 || { printf '%s\n' "Error: Docker no está disponible para compilar el frontend con Node 24." >&2; exit 1; }

rm -rf "$LAMBDA_OUT"
mkdir -p "$LAMBDA_OUT"
python3 -m pip install --disable-pip-version-check --no-cache-dir \
  --platform manylinux2014_x86_64 \
  --python-version 3.12 \
  --implementation cp \
  --abi cp312 \
  --only-binary=:all: \
  --target "$LAMBDA_OUT" \
  -r "$ROOT/backend/requirements-lambda.txt"
cp -R "$ROOT/backend/app" "$LAMBDA_OUT/app"
(
  cd "$LAMBDA_OUT"
  python3 -m zipfile -c "$OUT/api-compatible.zip" .
)
rm -rf "$LAMBDA_OUT"

docker build --target build -f "$ROOT/frontend/Dockerfile" \
  -t "$FRONTEND_BUILDER_IMAGE" "$ROOT"
frontend_container=$(docker create "$FRONTEND_BUILDER_IMAGE")
cleanup() {
  if [ -n "${frontend_container:-}" ]; then docker rm -f "$frontend_container" >/dev/null 2>&1 || true; fi
}
trap cleanup EXIT HUP INT TERM
rm -rf "$FRONTEND_OUT"
mkdir -p "$FRONTEND_OUT"
docker cp "$frontend_container:/app/dist/." "$FRONTEND_OUT"
cleanup
frontend_container=
trap - EXIT HUP INT TERM
printf 'Artefactos listos:\n  %s\n  %s\n' "$OUT/api-compatible.zip" "$FRONTEND_OUT/index.html"
