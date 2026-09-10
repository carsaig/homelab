#!/bin/sh
set -e

node - << "NODE_PATCH"
const fs = require("fs");

// 1. Patch agents/chat.js (configMiddleware)
const chatPath = "/app/api/server/routes/agents/chat.js";
if (fs.existsSync(chatPath)) {
  let content = fs.readFileSync(chatPath, "utf8");
  if (!content.includes("configMiddleware")) {
    content = content.replace(
      "  buildEndpointOption,",
      "  buildEndpointOption,\n  configMiddleware,"
    );
    content = content.replace(
      "router.use(buildEndpointOption);",
      "router.use(configMiddleware);\nrouter.use(buildEndpointOption);"
    );
    fs.writeFileSync(chatPath, content, "utf8");
    console.log("[entrypoint-patch] configMiddleware added to agents/chat.js");
  }
}

// 2. Patch socialLogins.js (dedicated openid.sid cookie, saveUninitialized: false, sameSite: lax)
const socialLoginsPath = "/app/api/server/socialLogins.js";
if (fs.existsSync(socialLoginsPath)) {
  let content = fs.readFileSync(socialLoginsPath, "utf8");
  if (!content.includes("name: 'openid.sid'")) {
    content = content.replace(
      "secret: process.env.OPENID_SESSION_SECRET,",
      "name: 'openid.sid',\n    secret: process.env.OPENID_SESSION_SECRET,"
    );
  }
  content = content.replace(/resave: true,/g, "resave: false,");
  content = content.replace(/saveUninitialized: true,/g, "saveUninitialized: false,");
  if (!content.includes("sameSite: 'lax'")) {
    content = content.replace(
      "secure: shouldUseSecureCookie(),",
      "secure: shouldUseSecureCookie(),\n      sameSite: 'lax',"
    );
  }
  fs.writeFileSync(socialLoginsPath, content, "utf8");
  console.log("[entrypoint-patch] socialLogins.js patched cleanly");
}

// 3. Patch openid-client passport.js (await req.session.save before redirect, keep req.session[sessionKey] intact)
const passportPath = "/app/api/node_modules/openid-client/build/passport.js";
if (fs.existsSync(passportPath)) {
  let content = fs.readFileSync(passportPath, "utf8");
  const target = "req.session[sessionKey] = stateData;";
  const replacement = "req.session[sessionKey] = stateData;\n            if (req.session && typeof req.session.save === \"function\") { await new Promise((res) => req.session.save(res)); }";
  if (!content.includes("req.session.save") && content.includes(target)) {
    content = content.replace(target, replacement);
    fs.writeFileSync(passportPath, content, "utf8");
    console.log("[entrypoint-patch] passport.js patched cleanly");
  }
}
NODE_PATCH

exec "$@"
