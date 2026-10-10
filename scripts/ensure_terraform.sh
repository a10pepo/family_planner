#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
VERSION=${1:-${TERRAFORM_VERSION:-1.16.5}}
CACHE_ROOT=${TERRAFORM_CACHE_DIR:-"$ROOT/build/tools/terraform"}
DEST="$CACHE_ROOT/$VERSION"
BINARY="$DEST/terraform"

fail() {
  printf 'Error: %s\n' "$1" >&2
  exit 1
}

case "$VERSION" in
  *[!0-9.]*|*.*.*.*|.*|*.) fail "Versión Terraform no válida: $VERSION." ;;
esac

if [ -x "$BINARY" ]; then
  installed_version=$("$BINARY" version | sed -n '1s/^Terraform v//p')
  if [ "$installed_version" = "$VERSION" ]; then
    printf '%s\n' "$BINARY"
    exit 0
  fi
  rm -f "$BINARY"
fi

case "$(uname -s)" in
  Darwin) os=darwin ;;
  Linux) os=linux ;;
  *) fail "Sistema no compatible con la descarga automática de Terraform." ;;
esac
case "$(uname -m)" in
  arm64|aarch64) arch=arm64 ;;
  x86_64|amd64) arch=amd64 ;;
  *) fail "Arquitectura no compatible con Terraform: $(uname -m)." ;;
esac

for tool in curl awk unzip install; do
  command -v "$tool" >/dev/null 2>&1 || fail "No se encuentra '$tool', necesario para preparar Terraform $VERSION."
done
if command -v shasum >/dev/null 2>&1; then
  checksum_tool=shasum
elif command -v sha256sum >/dev/null 2>&1; then
  checksum_tool=sha256sum
else
  fail "No se encuentra shasum ni sha256sum para verificar la descarga de Terraform."
fi

mkdir -p "$CACHE_ROOT"
tmp=$(mktemp -d "${TMPDIR:-/tmp}/family-planner-terraform.XXXXXX")
trap 'rm -rf "$tmp"' EXIT
trap 'exit 1' HUP INT TERM
archive="terraform_${VERSION}_${os}_${arch}.zip"
base_url="https://releases.hashicorp.com/terraform/$VERSION"
curl -fsSL "$base_url/$archive" -o "$tmp/$archive"
curl -fsSL "$base_url/terraform_${VERSION}_SHA256SUMS" -o "$tmp/SHA256SUMS"
expected_checksum=$(awk -v file="$archive" '$2 == file || $2 == "*" file {print $1; exit}' "$tmp/SHA256SUMS")
[ -n "$expected_checksum" ] || fail "HashiCorp no publicó el checksum esperado para $archive."
if [ "$checksum_tool" = shasum ]; then
  printf '%s  %s\n' "$expected_checksum" "$tmp/$archive" | shasum -a 256 -c - >/dev/null ||
    fail "El checksum de Terraform no coincide; se canceló la instalación."
else
  printf '%s  %s\n' "$expected_checksum" "$tmp/$archive" | sha256sum -c - >/dev/null ||
    fail "El checksum de Terraform no coincide; se canceló la instalación."
fi
mkdir "$tmp/extracted"
unzip -q "$tmp/$archive" -d "$tmp/extracted"
mkdir -p "$DEST"
install -m 0755 "$tmp/extracted/terraform" "$BINARY"
printf 'Terraform %s preparado en caché local.\n' "$VERSION" >&2
printf '%s\n' "$BINARY"
