#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
ENVIRONMENT=${1:-}

case "$ENVIRONMENT" in
  preview|production) ;;
  *) printf 'Uso: sync_codex_mcp.sh preview|production\n' >&2; exit 2 ;;
esac

if ! command -v codex >/dev/null 2>&1; then
  printf 'No se encuentra Codex CLI; se omite la sincronización MCP de %s.\n' "$ENVIRONMENT" >&2
  exit 1
fi

ENVIRONMENT_DIR="$ROOT/infra/environments/$ENVIRONMENT"
SERVER_NAME="family-planner-$ENVIRONMENT"
MCP_URL=$(terraform -chdir="$ENVIRONMENT_DIR" output -raw mcp_url) || {
  printf 'No se pudo leer mcp_url de %s.\n' "$ENVIRONMENT" >&2
  exit 1
}
CLIENT_ID=$(terraform -chdir="$ENVIRONMENT_DIR" output -raw mcp_oauth_client_id) || {
  printf 'No se pudo leer mcp_oauth_client_id de %s.\n' "$ENVIRONMENT" >&2
  exit 1
}

if codex mcp get "$SERVER_NAME" --json >/dev/null 2>&1; then
  codex mcp remove "$SERVER_NAME" || {
    printf 'No se pudo quitar la configuración anterior de %s.\n' "$SERVER_NAME" >&2
    exit 1
  }
fi

codex mcp add "$SERVER_NAME" --url "$MCP_URL" --oauth-client-id "$CLIENT_ID" || {
  printf 'No se pudo añadir la configuración MCP actual de %s.\n' "$ENVIRONMENT" >&2
  exit 1
}

printf 'Codex MCP actualizado: %s → %s\n' "$SERVER_NAME" "$MCP_URL"
printf 'Si Codex pide autorización, ejecuta: codex mcp login %s -c mcp_oauth_callback_port=1455\n' "$SERVER_NAME"
