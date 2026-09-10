#!/bin/sh
# Patch LibreChat: Add configMiddleware to agents/chat.js
CHAT_JS="/app/api/server/routes/agents/chat.js"
if [ -f "$CHAT_JS" ] && ! grep -q 'configMiddleware' "$CHAT_JS"; then
  sed -i 's|  buildEndpointOption,|  buildEndpointOption,\n  configMiddleware,|' "$CHAT_JS"
  sed -i 's|router.use(buildEndpointOption);|router.use(configMiddleware);\nrouter.use(buildEndpointOption);|' "$CHAT_JS"
  echo "[entrypoint-patch] configMiddleware added to agents/chat.js"
fi

# Patch socialLogins.js: dedicated cookie name 'openid.sid', saveUninitialized: false, sameSite: 'lax'
SOCIAL_LOGINS_JS="/app/api/server/socialLogins.js"
if [ -f "$SOCIAL_LOGINS_JS" ]; then
  sed -i "s/secret: process.env.OPENID_SESSION_SECRET,/name: 'openid.sid',\n    secret: process.env.OPENID_SESSION_SECRET,/g" "$SOCIAL_LOGINS_JS"
  sed -i 's/resave: true,/resave: false,/g' "$SOCIAL_LOGINS_JS"
  sed -i 's/saveUninitialized: true,/saveUninitialized: false,/g' "$SOCIAL_LOGINS_JS"
  if ! grep -q "sameSite: 'lax'" "$SOCIAL_LOGINS_JS"; then
    sed -i "s/secure: shouldUseSecureCookie(),/secure: shouldUseSecureCookie(),\n      sameSite: 'lax',/g" "$SOCIAL_LOGINS_JS"
  fi
  echo "[entrypoint-patch] OpenID session cookie patched (dedicated openid.sid, saveUninitialized: false, sameSite: lax)"
fi

# Patch openid-client passport.js: await req.session.save before redirect
PASSPORT_JS="/app/api/node_modules/openid-client/build/passport.js"
if [ -f "$PASSPORT_JS" ] && ! grep -q 'req.session.save' "$PASSPORT_JS"; then
  sed -i "s/req.session\[sessionKey\] = stateData;/req.session[sessionKey] = stateData;\n            if (req.session \&\& typeof req.session.save === 'function') { await new Promise((res) => req.session.save(res)); }/g" "$PASSPORT_JS"
  echo "[entrypoint-patch] openid-client passport.js patched to await req.session.save"
fi

# Execute the original entrypoint
exec "$@"
