#!/bin/sh
set -eu

for variable in COOLIFY_BASE_URL COOLIFY_ACCESS_TOKEN MCP_PROXY_BEARER_TOKEN; do
	eval "value=\${${variable}:-}"
	if [ -z "${value}" ]; then
		echo "FATAL: ${variable} is required." >&2
		exit 1
	fi
done

/opt/mcp-proxy/bin/mcp-proxy --host 127.0.0.1 --port 9090 \
	--named-server-config /etc/mcp-proxy/config.json \
	--pass-environment &
proxy_pid=$!

attempt=0
until python3 -c "import socket; s=socket.create_connection(('127.0.0.1',9090),1); s.close()" 2>/dev/null; do
	attempt=$((attempt + 1))
	if ! kill -0 "${proxy_pid}" 2>/dev/null || [ "${attempt}" -ge 30 ]; then
		echo "FATAL: MCP bridge failed to become ready." >&2
		exit 1
	fi
	sleep 1
done

exec caddy run --config /etc/caddy/Caddyfile
