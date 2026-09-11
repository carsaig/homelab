import { Glob } from 'bun';
import { join } from 'node:path';
import {
  metricsResponse,
  httpRequestsTotal,
  httpRequestDurationSeconds,
  normalizeMetricsPath,
} from './src/server/metrics';

const CLIENT_DIR = join(import.meta.dir, 'dist', 'client');
const SERVER_ENTRY = new URL('./dist/server/server.js', import.meta.url);

const env = process.env;
const BASE_PATH = (env.VITE_BASE_PATH || '/admin').replace(/\/$/, '');

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

const ONE_DAY = 86400;
const rawMaxAge = Number(env.ADMIN_PANEL_STATIC_CACHE_MAX_AGE ?? env.STATIC_CACHE_MAX_AGE);
const rawSMaxAge = Number(env.ADMIN_PANEL_STATIC_CACHE_S_MAX_AGE ?? env.STATIC_CACHE_S_MAX_AGE);
const maxAge = Number.isNaN(rawMaxAge) ? ONE_DAY * 2 : rawMaxAge;
const sMaxAge = Number.isNaN(rawSMaxAge) ? ONE_DAY : rawSMaxAge;

const NO_CACHE: Record<string, string> = {
  'Cache-Control': 'no-cache, no-store, must-revalidate',
  Pragma: 'no-cache',
  Expires: '0',
};

const LONG_CACHE: Record<string, string> = {
  'Cache-Control': `public, max-age=${maxAge}, s-maxage=${sMaxAge}`,
};

const CACHE_RESET_ID = 'v4';
const CACHE_RESET_COOKIE = 'admin_cache_reset';

const NEVER_CACHE = new Set(['manifest.json', 'sw.js', 'robots.txt']);

// Assets are rewritten as they are served, so their bytes change while the build's
// content hash in the file name does not. Pinning them in browsers hands out a stale
// copy that no request can correct; let them be cached but revalidated against an ETag.
const REVALIDATE: Record<string, string> = {
  'Cache-Control': `public, max-age=0, s-maxage=${sMaxAge}, must-revalidate`,
};

function getCacheHeaders(filePath: string): Record<string, string> {
  const fileName = filePath.split('/').pop() ?? '';
  if (NEVER_CACHE.has(fileName)) return NO_CACHE;
  if (filePath.startsWith('assets/')) return REVALIDATE;
  return {};
}

const CSP_VALUE = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self' data:",
  "connect-src 'self' ",
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
          let body: any = file;
          if (path.endsWith('.js')) {
            let code = await file.text();
            const rewritten = code
              .replaceAll(`${BASE_PATH}/assets/`, '/assets/')
              .replaceAll('/assets/', `${BASE_PATH}/assets/`)
              // Server functions are called at /_serverFn/... because the bundle is built
              // for the root. Keep them inside the panel's path, where its session cookie
              // applies and where the chat application does not answer instead.
              .replaceAll(`${BASE_PATH}/_serverFn/`, '/_serverFn/')
              .replaceAll('/_serverFn/', `${BASE_PATH}/_serverFn/`);
            if (rewritten !== code) {
              body = rewritten;
            }
          }
          const etag =
            typeof body === 'string' ? `"${Bun.hash(body).toString(16)}"` : undefined;
          if (etag && req.headers.get('if-none-match') === etag) {
            return new Response(null, { status: 304, headers: { ...cache, ETag: etag } });
          }
          const res = new Response(body, {
            headers: { 'Content-Type': file.type, ...cache, ...(etag ? { ETag: etag } : {}) },
          });
          applySecurityHeaders(res.headers);
          return res;
        });
    }
  }
  return routes;
}

const server = Bun.serve({
  port: Number(process.env.PORT ?? 3000),
  routes: {
    ...(await buildStaticRoutes()),
    '/metrics': (req) => metricsResponse(req),
    '/health': () => new Response('ok'),
    '/*': async (req) => {
      const url = new URL(req.url);
      const metricsPath = BASE_PATH && url.pathname.startsWith(BASE_PATH)
        ? url.pathname.slice(BASE_PATH.length) || '/'
        : url.pathname;

      let routerUrl = url;
      if (BASE_PATH && url.pathname.startsWith(BASE_PATH)) {
        const subPath = url.pathname.slice(BASE_PATH.length) || '/';
        routerUrl = new URL(subPath + url.search + url.hash, url.origin);
      }
      const routerReq = new Request(routerUrl.href, req);

      const res = await withHttpMetrics(req, metricsPath, () => handler.fetch(routerReq));
      
      let body: any = res.body;
      const contentType = res.headers.get('content-type') || '';
      if (contentType.includes('text/html')) {
        let text = await res.text();
        text = text.replaceAll('/admin/assets/', '/assets/').replaceAll('/assets/', `${BASE_PATH}/assets/`);
        text = text.replaceAll('/admin/favicon.ico', '/favicon.ico').replaceAll('/favicon.ico', `${BASE_PATH}/favicon.ico`);
        text = text.replaceAll('/admin/manifest.json', '/manifest.json').replaceAll('/manifest.json', `${BASE_PATH}/manifest.json`);
        text = text.replaceAll('/admin/librechat-logo.svg', '/librechat-logo.svg').replaceAll('/librechat-logo.svg', `${BASE_PATH}/librechat-logo.svg`);
        // Only rewrite a stylesheet reference that has not been prefixed already, otherwise
        // this rule runs over its own output and yields <base>/assets/<base>/assets/styles-...
        text = text.replace(/(?<!\/assets)\/styles-/g, `${BASE_PATH}/assets/styles-`);
        body = text;
      }

      const patched = new Response(body, res);
      for (const [k, v] of Object.entries(NO_CACHE)) {
        patched.headers.set(k, v);
      }

      // An earlier revision issued the session cookie for the whole origin. Browsers that
      // saw it still hold that copy alongside the correctly scoped one and send both, so
      // the wrong one can win. Expire the origin-wide copy; the panel only ever sets the
      // cookie for its own path now.
      if (BASE_PATH && contentType.includes('text/html')) {
        patched.headers.append(
          'set-cookie',
          'admin-session=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax',
        );

        // Earlier revisions let browsers pin the rewritten assets for two days, so a stale
        // bundle can outlive any correction on the server. Drop the cached copies once per
        // browser and remember that it happened; normal revalidation takes over afterwards.
        const cookies = req.headers.get('cookie') ?? '';
        if (!cookies.includes(`${CACHE_RESET_COOKIE}=${CACHE_RESET_ID}`)) {
          patched.headers.set('Clear-Site-Data', '"cache"');
          patched.headers.append(
            'set-cookie',
            `${CACHE_RESET_COOKIE}=${CACHE_RESET_ID}; Path=${BASE_PATH}; Max-Age=31536000; SameSite=Lax`,
          );
        }
      }

      applySecurityHeaders(patched.headers);
      return patched;
    },
  },
});

console.log(`Admin panel listening on http://localhost:${server.port}${BASE_PATH}/`);
