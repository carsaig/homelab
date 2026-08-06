#!/bin/sh
set -e

# Fail closed: an empty token would make Caddy's "Bearer {$TOKEN}" matcher
# accept the literal header "Bearer " — i.e. no real auth. Refuse to start.
if [ -z "${CODEMUNCH_BEARER_TOKEN}" ]; then
	echo "FATAL: CODEMUNCH_BEARER_TOKEN is empty — refusing to start unauthenticated." >&2
	exit 1
fi

# Pin codemunch's tool surface to "full" BEFORE it starts, so Bifrost/the LLM
# sees every code tool directly. Without this, a fresh volume reads as a
# first-ever install and codemunch defaults to the token-lean "counter" front
# door (menu/order/route only). Written only if absent — never clobbers a
# hand-edited config; repo_manager preserves this file across clears. Flip
# tool_surface to "counter" here if you prefer codemunch's dispatch front door.
CONFIG="${CODE_INDEX_PATH:-/data/code-index}/config.jsonc"
if [ ! -f "${CONFIG}" ]; then
	mkdir -p "$(dirname "${CONFIG}")"
	printf '{\n  "tool_surface": "full",\n  "tool_profile": "full"\n}\n' > "${CONFIG}"
fi

# mcp-proxy holds BOTH stdio servers warm behind one HTTP surface on :9090:
#   codemunch       -> jcodemunch-mcp serve   (index stays hot between calls)
#   codemunch-repo  -> python /app/repo_manager.py
# --pass-environment forwards CODE_INDEX_PATH / JCODEMUNCH_* / model path etc.
mcp-proxy --host 127.0.0.1 --port 9090 \
	--named-server-config /etc/mcp-proxy/config.json \
	--pass-environment &

# Give mcp-proxy a moment to bind before Caddy starts proxying to it.
sleep 2

# Caddy is the external bearer gate on :8080.
exec caddy run --config /etc/caddy/Caddyfile
