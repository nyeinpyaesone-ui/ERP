#!/usr/bin/env bash
# Wrapper for the @modelcontextprotocol/server-postgres MCP server.
#
# The server takes its DSN as a positional argument and has no environment
# variable equivalent, so opencode config cannot inject one without embedding
# the credential in a tracked file. This keeps POSTGRES_MCP_URL external.
#
# Usage (for local shells):
#   export POSTGRES_MCP_URL='postgresql://erp:erp_secret@localhost:5432/erp_solution'
set -euo pipefail

if [ -z "${POSTGRES_MCP_URL:-}" ]; then
  echo "mcp-postgres: POSTGRES_MCP_URL is not set." >&2
  echo "  export POSTGRES_MCP_URL='postgresql://erp:erp_secret@localhost:5432/erp_solution'" >&2
  exit 1
fi

exec npx -y @modelcontextprotocol/server-postgres "$POSTGRES_MCP_URL"