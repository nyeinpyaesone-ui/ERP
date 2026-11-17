---
name: jev-intercept
description: Code interception and runtime analysis for ERP system. Intercepts function calls, API requests, and database queries for security audit, performance profiling, and Jev-enhanced decision making.
---

# jev-intercept — Code Interception & Runtime Analysis

## Purpose

* Intercept Python (FastAPI) and JavaScript (React) execution at runtime
* Capture function arguments, return values, execution time, stack traces
* Feed intercepted data into Jev for typed judgments (security, performance, correctness)
* Zero-code instrumentation via sys.settrace / monkey-patching / middleware

## Capabilities

| Layer | Interception Method | Output |
|-------|---------------------|--------|
| Backend (FastAPI) | Pure-ASGI middleware + `sys.settrace` | Request/response, DB queries, auth checks |
| Frontend (React) | Vite dev plugin: runtime `fetch`/XHR hooks | API calls (method, URL, status, duration) |
| Database | SQLAlchemy event listeners | Query SQL, params, duration, row counts |
| Jev Integration | Structured events → Jev questions | Security verdict, performance score, correctness bool |

## Workflow

1. **Instrument**: Enable interception via env var `JEV_INTERCEPT=1`
2. **Collect**: Interceptor emits JSONL events to `.opencode/intercept/events.jsonl`
3. **Judge**: `jev-intercept` reads events, maps to Jev questions (security, perf, correctness)
4. **Decide**: Simulation or real Jev returns typed decisions with `needs_review`
5. **Act**: CI gate, alert, or auto-remediation (with approval)

## Safety

* Read-only interception by default (no mutation)
* PII redaction via configurable rules
* Opt-in per module: `JEV_INTERCEPT_MODULES=app.routers.auth,app.services.payments`
* Audit trail: every interception logged with timestamp, correlation ID
* **Inert unless `JEV_INTERCEPT=1`**: the collector returns `404` when
  interception is off, so a production deployment cannot be used as an
  arbitrary file-append endpoint.

## Integration

* `backend/app/services/jev_intercept.py` — reusable pure-ASGI middleware,
  JSONL writer, optional `sys.settrace`, SQLAlchemy listeners (single
  implementation). Bodies are observed as they stream past: nothing is
  buffered for replay, and streaming responses are never collected.
* `backend/app/routers/jev_intercept.py` — collector at `/api/v1/jev/intercept`
  (inert unless `JEV_INTERCEPT=1`) and `/api/v1/jev/intercept/status`
  (permissions `jev_intercept:create` / `jev_intercept:read`)
* `scripts/interceptor.py` — thin shim importing the backend module
* `scripts/frontend_intercept.js` — Vite dev plugin (runtime `fetch`/XHR hooks,
  no source rewriting)
* `scripts/jev_judge.py` — maps events to Jev questions
* `scripts/run_backend_intercept.sh` — starts uvicorn with `JEV_INTERCEPT=1`

### Activation

```bash
# Backend (from the repository root)
.opencode/skills/jev-intercept/scripts/run_backend_intercept.sh

# Or manually
JEV_INTERCEPT=1 uvicorn app.main:app --reload   # run from backend/
```

Frontend (dev only), in `backend/frontend-react/vite.config.js`:

```js
import { jevInterceptPlugin } from '../../.opencode/skills/jev-intercept/scripts/frontend_intercept.js';

export default defineConfig({ plugins: [react(), jevInterceptPlugin()] });
```

The plugin injects runtime hooks into `index.html`, so no application module is
rewritten. It posts `{method, url, status, duration_ms}` to the collector and
falls back to appending the JSONL file from the dev server when the backend is
not running. Bodies are never captured in the browser. Components can record
their own events with `window.__jevRecord?.({ type: 'component_render' })`.

Events go to `.opencode/intercept/events.jsonl` (override with
`JEV_INTERCEPT_EVENTS_FILE`). `JEV_INTERCEPT_TRACE=1` additionally enables
function tracing for `JEV_INTERCEPT_MODULES`.

Judge the collected events:

```bash
backend/venv/bin/python .opencode/skills/jev-intercept/scripts/jev_judge.py
```

It prints a simulation envelope (`mode: agent_simulation`, `jev_called: false`,
`needs_review: true`) grouped by `request_id`; no key or network call is made.
