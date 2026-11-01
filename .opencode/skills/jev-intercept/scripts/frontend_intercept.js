/**
 * Frontend interceptor for React/Vite (Jev-Intercept skill).
 *
 * Dev-only (`apply: 'serve'`). It does two things:
 *
 *  1. injects a small runtime hook into index.html that wraps `window.fetch`
 *     and `XMLHttpRequest` and POSTs `{method, url, status, duration_ms}` to
 *     the backend collector at `/api/v1/jev/intercept`;
 *  2. registers a dev-server middleware on the same path that appends events
 *     straight to the JSONL file when the backend is not running.
 *
 * No source code is rewritten: the previous version used regex `transform()`
 * hooks that injected calls to an undefined `sendEvent` and could break
 * `npm run dev` on any file that used `fetch`/`axios`. Runtime patching gives
 * the same visibility without touching application modules.
 *
 * Bodies are never captured in the browser — only method, URL, status and
 * duration — so credentials and PII cannot leak into the event stream.
 *
 * Usage in `backend/frontend-react/vite.config.js`:
 *
 *   import { jevInterceptPlugin } from '../../.opencode/skills/jev-intercept/scripts/frontend_intercept.js';
 *   export default defineConfig({ plugins: [react(), jevInterceptPlugin()] });
 *
 * Manual component instrumentation:
 *
 *   window.__jevRecord?.({ type: 'component_render', component: 'InvoiceList' });
 */
import fs from 'node:fs';
import path from 'node:path';

// Same-origin path: the Vite/nginx proxy forwards /api to the backend, which
// mounts the collector router at /api/v1/jev.
const COLLECTOR_URL = '/api/v1/jev/intercept';

const SECRET_PARAMS = ['token', 'access_token', 'refresh_token', 'api_key', 'key'];

/** Mask credential-looking query parameters before the URL leaves the page. */
export function scrubUrl(url) {
  try {
    const parsed = new URL(url, 'http://localhost');
    for (const name of SECRET_PARAMS) {
      if (parsed.searchParams.has(name)) parsed.searchParams.set(name, '***');
    }
    return parsed.pathname + (parsed.search ? parsed.search : '');
  } catch {
    return String(url).split('?')[0];
  }
}

function eventsFile() {
  return (
    process.env.JEV_INTERCEPT_EVENTS_FILE ||
    path.resolve(process.cwd(), '.opencode/intercept/events.jsonl')
  );
}

/**
 * Browser-side hook, injected into index.html in dev.
 *
 * Kept as a string because it must run in the page, not in the Vite process.
 * It is deliberately defensive: instrumentation must never break the app, so
 * every hook is wrapped and every failure is swallowed.
 */
function runtimeHook(collectorUrl) {
  return `(function () {
  if (window.__jevInterceptInstalled) return;
  window.__jevInterceptInstalled = true;
  var SECRET = ${JSON.stringify(SECRET_PARAMS)};
  var COLLECTOR = ${JSON.stringify(collectorUrl)};

  function scrub(url) {
    try {
      var parsed = new URL(url, window.location.origin);
      SECRET.forEach(function (name) {
        if (parsed.searchParams.has(name)) parsed.searchParams.set(name, '***');
      });
      return parsed.pathname + parsed.search;
    } catch (err) {
      return String(url).split('?')[0];
    }
  }

  function post(event) {
    try {
      event.timestamp = Date.now();
      event.request_id = window.__JEV_REQUEST_ID__ || 'unknown';
      var token = null;
      try { token = localStorage.getItem('token'); } catch (err) { token = null; }
      var headers = { 'Content-Type': 'application/json' };
      if (token) headers.Authorization = 'Bearer ' + token;
      fetch(COLLECTOR, {
        method: 'POST',
        headers: headers,
        body: JSON.stringify(event),
        keepalive: true,
      }).catch(function () {});
    } catch (err) {
      /* never break the page */
    }
  }

  window.__JEV_REQUEST_ID__ = Math.random().toString(36).slice(2, 10);
  window.__jevRecord = post;

  var originalFetch = window.fetch;
  if (originalFetch) {
    window.fetch = function (input, init) {
      var start = performance.now();
      var url = typeof input === 'string' ? input : (input && input.url) || '';
      var method = (init && init.method) || (input && input.method) || 'GET';
      return originalFetch.apply(this, arguments).then(
        function (response) {
          post({ type: 'fetch', method: method, url: scrub(url), status: response.status, duration_ms: performance.now() - start });
          return response;
        },
        function (error) {
          post({ type: 'fetch', method: method, url: scrub(url), error: String(error), duration_ms: performance.now() - start });
          throw error;
        }
      );
    };
  }

  var originalOpen = XMLHttpRequest.prototype.open;
  var originalSend = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function (method, url) {
    this.__jev = { method: method, url: scrub(url), start: 0 };
    return originalOpen.apply(this, arguments);
  };
  XMLHttpRequest.prototype.send = function () {
    var record = this.__jev || { method: 'GET', url: '', start: 0 };
    record.start = performance.now();
    var xhr = this;
    this.addEventListener('loadend', function () {
      post({ type: 'xhr', method: record.method, url: record.url, status: xhr.status, duration_ms: performance.now() - record.start });
    });
    return originalSend.apply(this, arguments);
  };
})();`;
}

// --- Vite Plugin ---
export function jevInterceptPlugin(options = {}) {
  const collectorUrl = options.collectorUrl || COLLECTOR_URL;

  return {
    name: 'jev-intercept',
    apply: 'serve',
    transformIndexHtml() {
      return [
        {
          tag: 'script',
          children: runtimeHook(collectorUrl),
          injectTo: 'head-prepend',
        },
      ];
    },
    configureServer(server) {
      // Fallback sink used when the backend collector is unreachable.
      server.middlewares.use(collectorUrl, (req, res) => {
        if (req.method !== 'POST') {
          res.writeHead(405, { 'Content-Type': 'application/json' });
          res.end('{"error":"method not allowed"}');
          return;
        }
        let body = '';
        req.on('data', (chunk) => {
          body += chunk;
        });
        req.on('end', () => {
          try {
            const event = JSON.parse(body);
            const target = eventsFile();
            fs.mkdirSync(path.dirname(target), { recursive: true });
            fs.appendFileSync(
              target,
              JSON.stringify({ ...event, source: 'frontend' }) + '\n'
            );
            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end('{"ok":true}');
          } catch {
            res.writeHead(400, { 'Content-Type': 'application/json' });
            res.end('{"error":"invalid json"}');
          }
        });
      });
    },
  };
}

export default jevInterceptPlugin;
