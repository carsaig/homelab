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

  // 2. Patch server manifest (_tanstack-start-manifest_*.js) so SSR emits /admin/assets/ URLs
  try {
    for (const f of readdirSync(join(SERVER_DIR, 'assets'))) {
      if (f.startsWith('_tanstack-start-manifest') && f.endsWith('.js')) {
        const p = join(SERVER_DIR, 'assets', f);
        let code = readFileSync(p, 'utf8');
        code = code.replaceAll(`${BASE_PATH}/assets/`, '/assets/').replaceAll('/assets/', `${BASE_PATH}/assets/`);
        writeFileSync(p, code);
        console.log('[admin-panel] Patched server manifest:', f);
      }
    }
  } catch (err) {
    console.error('[admin-panel] Error patching server manifest:', err);
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

        // Relative Vite mapDeps in client files
        if (code.includes('"assets/')) {
          code = code.replaceAll('"assets/', `"${BASE_PATH}/assets/`);
          changed = true;
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

        // Modulepreload helper in main-*.js
        if (code.includes('ua=function(e){return`/`+e}')) {
          code = code.replaceAll('ua=function(e){return`/`+e}', `ua=function(e){return\`${BASE_PATH}/\`+e.replace(/^\\//, '')}`);
          changed = true;
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

function getCacheHeaders(filePath: string): Record<string, string> {
  return NO_CACHE;
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
    for (const prefix of ['', BASE_PATH]) {
      const routePath = `${prefix}/${path}`;
      routes[routePath] = (req) =>
        withHttpMetrics(req, routePath, async () => {
          const res = new Response(file, { headers: { 'Content-Type': file.type, ...cache } });
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
      patched.headers.set('Clear-Site-Data', '"cache"');
      applySecurityHeaders(patched.headers);
      return patched;
    },
  },
});

console.log(`Admin panel listening on http://localhost:${server.port}${BASE_PATH}/`);
