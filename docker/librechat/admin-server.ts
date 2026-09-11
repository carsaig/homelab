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

const NEVER_CACHE = new Set(['manifest.json', 'sw.js', 'robots.txt']);

function getCacheHeaders(filePath: string): Record<string, string> {
  const fileName = filePath.split('/').pop() ?? '';
  if (NEVER_CACHE.has(fileName)) return NO_CACHE;
  if (filePath.startsWith('assets/')) return LONG_CACHE;
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
            if (code.includes('/assets/')) {
              code = code.replaceAll('/admin/assets/', '/assets/').replaceAll('/assets/', `${BASE_PATH}/assets/`);
              body = code;
            }
          }
          const res = new Response(body, { headers: { 'Content-Type': file.type, ...cache } });
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
        text = text.replaceAll('/styles-', `${BASE_PATH}/assets/styles-`);
        body = text;
      }

      const patched = new Response(body, res);
      for (const [k, v] of Object.entries(NO_CACHE)) {
        patched.headers.set(k, v);
      }

      // The session cookie is issued for the mount path, but the bundle is built for the
      // root and therefore calls its server functions at /_serverFn/... . The browser
      // withholds a cookie scoped to the mount path from those requests, so the sign-in
      // exchange never sees the PKCE verifier it stored moments earlier. Widen the scope
      // to cover both.
      const setCookies = patched.headers.getSetCookie?.() ?? [];
      if (setCookies.length > 0) {
        patched.headers.delete('set-cookie');
        for (const cookie of setCookies) {
          patched.headers.append('set-cookie', cookie.replace(/;\s*Path=[^;]*/i, '; Path=/'));
        }
      }

      applySecurityHeaders(patched.headers);
      return patched;
    },
  },
});

console.log(`Admin panel listening on http://localhost:${server.port}${BASE_PATH}/`);
