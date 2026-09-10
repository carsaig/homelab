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

// 3. Write deterministic, patched openid-client passport.js
const passportPath = "/app/api/node_modules/openid-client/build/passport.js";
if (fs.existsSync(passportPath)) {
  const passportContent = `import * as client from './index.js';
export class Strategy {
    name;
    _config;
    _verify;
    _callbackURL;
    _sessionKey;
    _passReqToCallback;
    _proxy;
    _usePAR;
    _useJAR;
    _DPoP;
    _scope;
    constructor(options, verify) {
        if (!(options?.config instanceof client.Configuration)) {
            throw new TypeError();
        }
        if (typeof verify !== 'function') {
            throw new TypeError();
        }
        const { host } = new URL(options.config.serverMetadata().issuer);
        this.name = options.name ?? host;
        this._sessionKey = options.sessionKey ?? host;
        this._DPoP = options.DPoP;
        this._config = options.config;
        this._scope = options.scope;
        this._useJAR = options.useJAR;
        this._usePAR = options.usePAR;
        this._verify = verify;
        this._callbackURL = options.callbackURL;
        this._passReqToCallback = options.passReqToCallback;
    }
    authorizationRequestParams(req, options) {
        let params = new URLSearchParams();
        if (options?.scope) {
            if (Array.isArray(options?.scope) && options.scope.length) {
                params.set('scope', options.scope.join(' '));
            }
            else if (typeof options?.scope === 'string' && options.scope.length) {
                params.set('scope', options.scope);
            }
        }
        if (options?.prompt) {
            params.set('prompt', options.prompt);
        }
        return params;
    }
    authorizationCodeGrantParameters(req, options) {
        return {};
    }
    async authorizationRequest(req, options) {
        try {
            let redirectTo = client.buildAuthorizationUrl(this._config, new URLSearchParams(this.authorizationRequestParams(req, options)));
            if (redirectTo.searchParams.get('response_type')?.includes('id_token')) {
                redirectTo.searchParams.set('nonce', client.randomNonce());
            }
            const codeVerifier = client.randomPKCECodeVerifier();
            const code_challenge = await client.calculatePKCECodeChallenge(codeVerifier);
            redirectTo.searchParams.set('code_challenge', code_challenge);
            redirectTo.searchParams.set('code_challenge_method', 'S256');
            if (!this._config.serverMetadata().supportsPKCE() &&
                !redirectTo.searchParams.has('nonce')) {
                redirectTo.searchParams.set('state', client.randomState());
            }
            if (this._callbackURL && !redirectTo.searchParams.has('redirect_uri')) {
                redirectTo.searchParams.set('redirect_uri', this._callbackURL);
            }
            if (this._scope && !redirectTo.searchParams.has('scope')) {
                redirectTo.searchParams.set('scope', this._scope);
            }
            const DPoP = await this._DPoP?.(req);
            if (DPoP && !redirectTo.searchParams.has('dpop_jkt')) {
                redirectTo.searchParams.set('dpop_jkt', await DPoP.calculateThumbprint());
            }
            const sessionKey = this._sessionKey;
            const stateData = { code_verifier: codeVerifier };
            let nonce;
            if ((nonce = redirectTo.searchParams.get('nonce'))) {
                stateData.nonce = nonce;
            }
            let state;
            if ((state = redirectTo.searchParams.get('state'))) {
                stateData.state = state;
            }
            let max_age;
            if ((max_age = redirectTo.searchParams.get('max_age'))) {
                stateData.max_age = parseInt(max_age, 10);
            }
            ;
            req.session[sessionKey] = stateData;
            if (req.session && typeof req.session.save === 'function') {
                await new Promise((res) => req.session.save(res));
            }
            if (this._useJAR) {
                let key;
                let modifyAssertion;
                if (Array.isArray(this._useJAR)) {
                    ;
                    [key, modifyAssertion] = this._useJAR;
                }
                else {
                    key = this._useJAR;
                }
                redirectTo = await client.buildAuthorizationUrlWithJAR(this._config, redirectTo.searchParams, key, { [client.modifyAssertion]: modifyAssertion });
            }
            if (this._usePAR) {
                redirectTo = await client.buildAuthorizationUrlWithPAR(this._config, redirectTo.searchParams, { DPoP });
            }
            return this.redirect(redirectTo.href);
        }
        catch (err) {
            return this.error(err);
        }
    }
    async authorizationCodeGrant(req, currentUrl, options) {
        try {
            const sessionKey = this._sessionKey;
            const stateData = req.session?.[sessionKey];
            if (!stateData?.code_verifier) {
                return this.fail({
                    message: 'Unable to verify authorization request state',
                });
            }
            let input = currentUrl;
            if (req.method === 'POST') {
                input = new Request(currentUrl.href, {
                    method: 'POST',
                    headers: Object.entries(req.headersDistinct).reduce((acc, [key, values]) => {
                        for (const value of values) {
                            acc.append(key, value);
                        }
                        return acc;
                    }, new Headers()),
                    body: req,
                    duplex: 'half',
                });
            }
            const tokens = await client.authorizationCodeGrant(this._config, input, {
                pkceCodeVerifier: stateData.code_verifier,
                expectedNonce: stateData.nonce,
                expectedState: stateData.state,
                maxAge: stateData.max_age,
            }, this.authorizationCodeGrantParameters(req, options), { DPoP: await this._DPoP?.(req) });
            const verified = (err, user, info) => {
                if (err)
                    return this.error(err);
                if (!user)
                    return this.fail(info);
                return this.success(user);
            };
            if (options.passReqToCallback ?? this._passReqToCallback) {
                return this._verify(req, tokens, verified);
            }
            return this._verify(tokens, verified);
        }
        catch (err) {
            if (err instanceof client.AuthorizationResponseError &&
                err.error === 'access_denied') {
                return this.fail({
                    message: err.error_description || err.error,
                    ...Object.fromEntries(err.cause.entries()),
                });
            }
            return this.error(err);
        }
    }
    currentUrl(req) {
        return new URL(\`\${req.protocol}://\${req.host}\${req.originalUrl ?? req.url}\`);
    }
    authenticate(req, options) {
        if (!req.session) {
            return this.error(new Error('OAuth 2.0 authentication requires session support. Did you forget to use express-session middleware?'));
        }
        const currentUrl = this.currentUrl(req);
        if ((req.method === 'GET' && currentUrl.searchParams.size === 0) ||
            (currentUrl.searchParams.size === 1 && currentUrl.searchParams.has('iss'))) {
            Strategy.prototype.authorizationRequest.call(this, req, options);
        }
        else {
            Strategy.prototype.authorizationCodeGrant.call(this, req, currentUrl, options);
        }
    }
}
//# sourceMappingURL=passport.js.map\n`;

  fs.writeFileSync(passportPath, passportContent, "utf8");
  console.log("[entrypoint-patch] deterministic passport.js written");
}
NODE_PATCH

exec "$@"
