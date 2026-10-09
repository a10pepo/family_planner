#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
OUT=${AWS_BUILD_DIR:-"$ROOT/build/aws"}
LAMBDA_OUT="$OUT/lambda"
FRONTEND_OUT="$OUT/frontend-compatible/dist"

command -v python3 >/dev/null 2>&1 || { printf '%s\n' "Error: Python 3 y pip no están disponibles." >&2; exit 1; }
command -v npm >/dev/null 2>&1 || { printf '%s\n' "Error: npm no está disponible." >&2; exit 1; }

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

npm --prefix "$ROOT/frontend" ci
npm --prefix "$ROOT/frontend" run build
mkdir -p "$(dirname "$FRONTEND_OUT")"
rm -rf "$FRONTEND_OUT"
cp -R "$ROOT/frontend/dist" "$FRONTEND_OUT"
printf 'Artefactos listos:\n  %s\n  %s\n' "$OUT/api-compatible.zip" "$FRONTEND_OUT/index.html"
