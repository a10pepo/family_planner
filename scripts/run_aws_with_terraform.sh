#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
VERSION=${TERRAFORM_VERSION:-1.16.5}
TERRAFORM_BIN=$(sh "$ROOT/scripts/ensure_terraform.sh" "$VERSION")
PATH="$(dirname "$TERRAFORM_BIN"):$PATH"
export PATH TERRAFORM_VERSION="$VERSION"
exec sh "$ROOT/scripts/deploy_aws.sh" "$@"
