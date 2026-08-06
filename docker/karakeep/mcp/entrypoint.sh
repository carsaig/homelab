#!/bin/sh
set -e

mcp-proxy --host 127.0.0.1 --port 9090 --named-server-config /etc/mcp-proxy/config.json --pass-environment &

# Give mcp-proxy a moment to bind before Caddy starts proxying to it
sleep 2

exec caddy run --config /etc/caddy/Caddyfile
