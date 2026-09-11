import { Glob } from 'bun';
import { join } from 'node:path';
import { readFileSync, writeFileSync, readdirSync, statSync } from 'node:fs';
import {
  metricsResponse,
  httpRequestsTotal,
  httpRequestDurationSeconds,
  normalizeMetricsPath,
} from './src/server/metrics';

const env = process.env;
const BASE_PATH = (env.VITE_BASE_PATH || '/admin').replace(/\/$/, '');
const CLIENT_DIR = join(import.meta.dir, 'dist', 'client');
const SERVER_DIR = join(import.meta.dir, 'dist', 'server');
const SERVER_ENTRY = new URL('./dist/server/server.js', import.meta.url);

// --- 1. PRE-STARTUP DIST PATCHING ---
function patchDistFiles() {
  console.log(`[admin-panel] Patching dist files for BASE_PATH=${BASE_PATH}...`);
  
  // 1. Server router basepaths in dist/server/server.js
  const serverPath = join(SERVER_DIR, 'server.js');
  try {
    let serverCode = readFileSync(serverPath, 'utf8');
    serverCode = serverCode.replaceAll('var ROUTER_BASEPATH = "/";', `var ROUTER_BASEPATH = "${BASE_PATH}";`);
    serverCode = serverCode.replaceAll('var SERVER_FN_BASE = "/_serverFn/";', `var SERVER_FN_BASE = "${BASE_PATH}/_serverFn/";`);
    // Ensure all internal server module imports stay ./assets/
    serverCode = serverCode.replaceAll(`import("./admin/assets/`, `import("./assets/`);
    serverCode = serverCode.replaceAll(`import("${BASE_PATH}/assets/`, `import("./assets/`);
    writeFileSync(serverPath, serverCode);
    console.log('[admin-panel] Patched dist/server/server.js');
  } catch (err) {
    console.error('[admin-panel] Error patching server.js:', err);
  }

  // 2. Normalise the server manifest (_tanstack-start-manifest_*.js). Its entries reach
  // the client router, which resolves them through the asset URL helper — and that helper
  // already prepends the base to a path whose leading slash it strips. The manifest must
  // therefore keep the build's own /assets/ paths: prefixing them here made every preload
  // resolve to ${BASE_PATH}${BASE_PATH}/assets/... and fail.
  try {
    for (const f of readdirSync(join(SERVER_DIR, 'assets'))) {
      if (f.startsWith('_tanstack-start-manifest') && f.endsWith('.js')) {
        const p = join(SERVER_DIR, 'assets', f);
        const code = readFileSync(p, 'utf8');
        const normalised = code.replaceAll(`${BASE_PATH}/assets/`, '/assets/');
        if (normalised !== code) {
          writeFileSync(p, normalised);
          console.log('[admin-panel] Normalised server manifest:', f);
        }
      }
    }
  } catch (err) {
    console.error('[admin-panel] Error normalising server manifest:', err);
  }

  // 3. Patch client assets in dist/client/assets
  const clientAssetsDir = join(CLIENT_DIR, 'assets');
  try {
    for (const f of readdirSync(clientAssetsDir)) {
      if (f.endsWith('.js')) {
        const p = join(clientAssetsDir, f);
        let code = readFileSync(p, 'utf8');
        let changed = false;

        // Replace /assets/ with /admin/assets/
        if (code.includes('/assets/')) {
          code = code.replaceAll(`${BASE_PATH}/assets/`, '/assets/').replaceAll('/assets/', `${BASE_PATH}/assets/`);
          changed = true;
        }

        // server.js gets SERVER_FN_BASE rewritten above, but the client bundles keep
        // their own hardcoded /_serverFn/ prefix. Without this the browser calls the
        // root application instead of the panel and every loader comes back empty.
        if (code.includes('/_serverFn/')) {
          code = code
            .replaceAll(`${BASE_PATH}/_serverFn/`, '/_serverFn/')
            .replaceAll('/_serverFn/', `${BASE_PATH}/_serverFn/`);
          changed = true;
        }

        // Vite's asset URL helper already prepends the base to every dependency
        // (`${BASE_PATH}/` + dep with a leading slash stripped), so __vite__mapDeps
        // entries have to stay relative. Making them absolute yields
        // ${BASE_PATH}${BASE_PATH}/assets/... and every lazily loaded chunk 404s,
        // which leaves route components stuck on their pending state.
        const mapDeps = /(__vite__mapDeps=\(i,m=__vite__mapDeps,d=\(m\.f\|\|\(m\.f=\[)([\s\S]*?)(\]\)\)\))/;
        if (mapDeps.test(code)) {
          const fixed = code.replace(mapDeps, (_all, head, body, tail) =>
            head + body.replaceAll(`"${BASE_PATH}/assets/`, '"assets/') + tail,
          );
          if (fixed !== code) {
            code = fixed;
            changed = true;
          }
        }

        // Basepaths
        if (code.includes('basepath:`/`')) {
          code = code.replaceAll('basepath:`/`', `basepath:\`${BASE_PATH}\``);
          changed = true;
        }
        if (code.includes('basepath:``')) {
          code = code.replaceAll('basepath:``', `basepath:\`${BASE_PATH}\``);
          changed = true;
        }
        if (code.includes('basepath:"/"')) {
          code = code.replaceAll('basepath:"/"', `basepath:"${BASE_PATH}"`);
          changed = true;
        }
        if (code.includes('basepath:""')) {
          code = code.replaceAll('basepath:""', `basepath:"${BASE_PATH}"`);
          changed = true;
        }

        // Modulepreload helper in main-*.js. It receives two kinds of input: the build's
        // own dependency lists, which are relative, and the router manifest entries, which
        // the server already serialises with the base applied. Prepending unconditionally
        // doubles the latter, so only add the base when it is not there yet.
        const preloadHelper = `ua=function(e){var p=e.replace(/^\\//, '');var b='${BASE_PATH}'.replace(/^\\//, '');return p===b||p.startsWith(b+'/')?'/'+p:'${BASE_PATH}/'+p}`;
        for (const variant of [
          'ua=function(e){return`/`+e}',
          `ua=function(e){return\`${BASE_PATH}/\`+e.replace(/^\\//, '')}`,
        ]) {
          if (code.includes(variant) && variant !== preloadHelper) {
            code = code.replaceAll(variant, preloadHelper);
            changed = true;
          }
        }

        // Fix TanStack Start hydration invariant crashes
        if (code.includes('let t=s[1];t||me(),l(t)')) {
          code = code.replaceAll('let t=s[1];t||me(),l(t)', 'let t=s[1]||s[0];t&&l(t)');
          changed = true;
        }
        if (code.includes('let t=s[1]||s[0];if(t),l(t)')) {
          code = code.replaceAll('let t=s[1]||s[0];if(t),l(t)', 'let t=s[1]||s[0];t&&l(t)');
          changed = true;
        }
        if (code.includes('n||me();let r=A(t.stores.loadedAt')) {
          code = code.replaceAll('n||me();let r=A(t.stores.loadedAt', 'if(!n)return null;let r=A(t.stores.loadedAt');
          changed = true;
        }
        if (code.includes('n||me();let r=A(n,e=>e)')) {
          code = code.replaceAll('n||me();let r=A(n,e=>e)', 'if(!n)return null;let r=A(n,e=>e)');
          changed = true;
        }
        if (code.includes('function Se(){throw Error(`Invariant failed`)}')) {
          code = code.replaceAll('function Se(){throw Error(`Invariant failed`)}', 'function Se(){return null;}');
          changed = true;
        }
        if (code.includes('function lE(e,t){if(!e){if(uE)throw Error(dE);var n=typeof t==`function`?t():t,r=n?dE+`: `+n:dE;throw Error(r)}}')) {
          code = code.replaceAll('function lE(e,t){if(!e){if(uE)throw Error(dE);var n=typeof t==`function`?t():t,r=n?dE+`: `+n:dE;throw Error(r)}}', 'function lE(e,t){if(!e){return;}}');
          changed = true;
        }

        if (changed) {
          writeFileSync(p, code);
          console.log(`[admin-panel] Patched client file: ${f}`);
        }
      }
    }
  } catch (err) {
    console.error('[admin-panel] Error patching client assets:', err);
  }
}

patchDistFiles();

const MIN_SESSION_SECRET_LENGTH = 32;
const secret = env.SESSION_SECRET || env.ADMIN_PANEL_SESSION_SECRET;
if (env.NODE_ENV !== 'development') {
  if (!secret || secret.length < MIN_SESSION_SECRET_LENGTH) {
    console.error(
      `[admin-panel] SESSION_SECRET must be set to at least ${MIN_SESSION_SECRET_LENGTH} characters.`,
    );
    process.exit(1);
  }
}

const NO_CACHE: Record<string, string> = {
  'Cache-Control': 'no-cache, no-store, must-revalidate',
  Pragma: 'no-cache',
  Expires: '0',
};

// Build output under assets/ is content-hashed, but patchDistFiles() rewrites those
// files in place afterwards, so the hash in the name no longer describes the bytes we
// serve. Marking them immutable would pin a pre-patch copy in browsers indefinitely.
// Let them be cached and revalidated against an ETag of the patched content instead:
// unchanged assets cost a 304 rather than a full download.
// A previous revision served the hashed assets as immutable. Those files are rewritten
// after the build, so a browser can hold a copy that no longer matches what we send and,
// being immutable, will never revalidate it. Purge the origin's cache once per browser
// and remember that we did so; afterwards normal caching applies.
const CACHE_RESET_ID = 'v2';
const CACHE_RESET_COOKIE = 'admin_cache_reset';

const REVALIDATE: Record<string, string> = {
  'Cache-Control': 'public, max-age=60, must-revalidate',
};

const HASHED_ASSET = /(?:^|\/)assets\/.+-[A-Za-z0-9_-]{8,}\.[A-Za-z0-9]+$/;

function getCacheHeaders(filePath: string): Record<string, string> {
  return HASHED_ASSET.test(filePath) ? REVALIDATE : NO_CACHE;
}

const CSP_VALUE = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self' data:",
  "connect-src 'self'",
  "object-src 'none'",
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
].join('; ');

function applySecurityHeaders(headers: Headers): void {
  const contentType = headers.get('Content-Type') ?? '';
  if (!contentType.toLowerCase().startsWith('text/html')) return;
  headers.set('Content-Security-Policy-Report-Only', CSP_VALUE);
  headers.set('X-Content-Type-Options', 'nosniff');
  headers.set('Referrer-Policy', 'strict-origin-when-cross-origin');
  headers.set('X-Frame-Options', 'DENY');
  if (process.env.NODE_ENV === 'production') {
    headers.set('Strict-Transport-Security', 'max-age=31536000; includeSubDomains');
  }
}

type Handler = { default: { fetch: (req: Request) => Promise<Response> } };
const { default: handler } = (await import(SERVER_ENTRY.href)) as Handler;

async function withHttpMetrics(
  req: Request,
  pathname: string,
  getResponse: () => Response | Promise<Response>,
): Promise<Response> {
  const path = normalizeMetricsPath(pathname);
  const end = httpRequestDurationSeconds.startTimer({ method: req.method, path });
  const res = await getResponse();
  const statusCode = String(res.status);
  httpRequestsTotal.inc({ method: req.method, path, status_code: statusCode });
  end({ status_code: statusCode });
  return res;
}

async function buildStaticRoutes(): Promise<Record<string, (req: Request) => Promise<Response>>> {
  const routes: Record<string, (req: Request) => Promise<Response>> = {};
  for await (const path of new Glob('**/*').scan(CLIENT_DIR)) {
    const file = Bun.file(`${CLIENT_DIR}/${path}`);
    const cache = getCacheHeaders(path);
    // Hashed assets are served from the patched bytes, so derive the validator from them.
    const etag =
      cache === REVALIDATE ? `"${Bun.hash(await file.arrayBuffer()).toString(16)}"` : undefined;
    for (const prefix of ['', BASE_PATH]) {
      const routePath = `${prefix}/${path}`;
      routes[routePath] = (req) =>
        withHttpMetrics(req, routePath, async () => {
          if (etag && req.headers.get('if-none-match') === etag) {
            return new Response(null, { status: 304, headers: { ...cache, ETag: etag } });
          }
          const res = new Response(file, {
            headers: { 'Content-Type': file.type, ...cache, ...(etag ? { ETag: etag } : {}) },
          });
          applySecurityHeaders(res.headers);
          return res;
        });
    }
  }
  return routes;
}

function fixHtmlUrls(html: string): string {
  let text = html;
  text = text.replaceAll(`${BASE_PATH}/assets/`, '/assets/').replaceAll('/assets/', `${BASE_PATH}/assets/`);
  text = text.replaceAll(`${BASE_PATH}/favicon.ico`, '/favicon.ico').replaceAll('/favicon.ico', `${BASE_PATH}/favicon.ico`);
  text = text.replaceAll(`${BASE_PATH}/manifest.json`, '/manifest.json').replaceAll('/manifest.json', `${BASE_PATH}/manifest.json`);
  text = text.replaceAll(`${BASE_PATH}/librechat-logo.svg`, '/librechat-logo.svg').replaceAll('/librechat-logo.svg', `${BASE_PATH}/librechat-logo.svg`);
  
  // Clean double prefix if any
  text = text.replaceAll(`${BASE_PATH}${BASE_PATH}`, BASE_PATH);
  return text;
}

const server = Bun.serve({
  port: Number(process.env.PORT ?? 3000),
  routes: {
    ...(await buildStaticRoutes()),
    '/metrics': (req) => metricsResponse(req),
    '/health': () => new Response('ok'),
    '/*': async (req) => {
      const url = new URL(req.url);
      
      // Ensure routerReq maintains the BASE_PATH since ROUTER_BASEPATH is set to BASE_PATH in server.js
      let routerUrl = url;
      if (BASE_PATH && !url.pathname.startsWith(BASE_PATH)) {
        routerUrl = new URL(`${BASE_PATH}${url.pathname === '/' ? '' : url.pathname}${url.search}${url.hash}`, url.origin);
      }
      const routerReq = new Request(routerUrl.href, req);

      const res = await withHttpMetrics(req, url.pathname, () => handler.fetch(routerReq));
      
      let body: any = res.body;
      const contentType = res.headers.get('content-type') || '';
      if (contentType.includes('text/html')) {
        let text = await res.text();
        body = fixHtmlUrls(text);
      }

      const patched = new Response(body, res);
      for (const [k, v] of Object.entries(NO_CACHE)) {
        patched.headers.set(k, v);
      }
      const alreadyReset = (req.headers.get('cookie') ?? '').includes(
        `${CACHE_RESET_COOKIE}=${CACHE_RESET_ID}`,
      );
      if (contentType.includes('text/html') && !alreadyReset) {
        patched.headers.set('Clear-Site-Data', '"cache"');
        patched.headers.append(
          'Set-Cookie',
          `${CACHE_RESET_COOKIE}=${CACHE_RESET_ID}; Path=${BASE_PATH || '/'}; Max-Age=31536000; SameSite=Lax`,
        );
      }
      applySecurityHeaders(patched.headers);
      return patched;
    },
  },
});

console.log(`Admin panel listening on http://localhost:${server.port}${BASE_PATH}/`);
