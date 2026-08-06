#!/bin/sh
set -eu

# Render the service configuration from required deployment variables.

: "${PROXMOX_HOST:?PROXMOX_HOST is required}"
: "${PROXMOX_PORT:?PROXMOX_PORT is required}"
: "${PROXMOX_VERIFY_SSL:?PROXMOX_VERIFY_SSL is required}"
: "${SECURITY_DEV_MODE:?SECURITY_DEV_MODE is required}"
: "${PROXMOX_TOKEN_ID:?PROXMOX_TOKEN_ID is required}"
: "${PROXMOX_TOKEN_SECRET:?PROXMOX_TOKEN_SECRET is required}"

CONFIG_PATH="${PROXMOX_MCP_CONFIG:-/app/proxmox-config/config.json}"

PVE_USER="${PROXMOX_TOKEN_ID%%!*}"
PVE_TOKEN_NAME="${PROXMOX_TOKEN_ID##*!}"
if [ "$PVE_USER" = "$PROXMOX_TOKEN_ID" ]; then
  echo "FATAL: PROXMOX_TOKEN_ID is invalid" >&2
  exit 1
fi


mkdir -p "$(dirname "$CONFIG_PATH")"
cat > "$CONFIG_PATH" <<EOF
{
  "proxmox": {
    "host": "${PROXMOX_HOST}",
    "port": ${PROXMOX_PORT},
    "verify_ssl": ${PROXMOX_VERIFY_SSL},
    "service": "PVE"
  },
  "auth": {
    "user": "${PVE_USER}",
    "token_name": "${PVE_TOKEN_NAME}",
    "token_value": "${PROXMOX_TOKEN_SECRET}"
  },
  "mcp": {
    "host": "127.0.0.1",
    "port": 8000,
    "transport": "STREAMABLE_HTTP",
    "dns_rebinding_protection": true,
    "allowed_hosts": ["127.0.0.1", "127.0.0.1:8000"],
    "allowed_origins": []
  },
  "security": { "dev_mode": ${SECURITY_DEV_MODE} },
  "command_policy": {
    "mode": "deny_all",
    "allow_patterns": [],
    "deny_patterns": ["(^|\\\\s)rm\\\\s+-rf(\\\\s|$)", ":\\\\(\\\\)\\\\{:\\\\|:\\\\&\\\\};:"],
    "require_approval_token": false,
    "approval_token": null
  },
  "jobs": { "sqlite_path": "/tmp/proxmox-jobs.sqlite3" },
  "logging": {
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "file": "/tmp/proxmox_mcp.log"
  }
}
EOF

export PROXMOX_MCP_MODE="mcp-http"
export PROXMOX_MCP_CONFIG="$CONFIG_PATH"
export MCP_HOST="127.0.0.1"
export MCP_PORT="8000"
export MCP_TRANSPORT="STREAMABLE_HTTP"

# MCP server on loopback (reachable only by Caddy inside this container)
python -m proxmox_mcp.docker_entrypoint &

# Give it a moment to bind before Caddy starts proxying to it
sleep 2

# Caddy enforces the Bearer check and is the only exposed listener (:8080)
exec caddy run --config /etc/caddy/Caddyfile
