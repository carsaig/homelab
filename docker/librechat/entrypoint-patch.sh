#!/bin/sh
# Patch LibreChat v0.8.4: Add configMiddleware to agents/chat.js
# Without this, the Memory Agent background processor never fires
# because req.config (which contains the memory config) is never set.
# This was fixed in responses.js but missed in chat.js.

CHAT_JS="/app/api/server/routes/agents/chat.js"

if [ -f "$CHAT_JS" ] && ! grep -q 'configMiddleware' "$CHAT_JS"; then
  sed -i 's|  buildEndpointOption,|  buildEndpointOption,\n  configMiddleware,|' "$CHAT_JS"
  sed -i 's|router.use(buildEndpointOption);|router.use(configMiddleware);\nrouter.use(buildEndpointOption);|' "$CHAT_JS"
  echo "[entrypoint-patch] configMiddleware added to agents/chat.js"
else
  echo "[entrypoint-patch] agents/chat.js already patched or not found"
fi

# Execute the original entrypoint
exec "$@"
