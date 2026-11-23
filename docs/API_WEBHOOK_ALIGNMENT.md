# API, Webhook, and Frontend Contract Alignment

Status: source audit / staging preparation. This document does not change runtime behavior.

## Canonical source examined

- Repository: `nyeinpyaesone-ui/ERP`
- Branch examined: `main`
- Application entry point: `backend/app/main.py`
- API inventory: `docs/API_SUMMARY.md`
- Frontend: `backend/frontend-react`
- Shared HTTP client: `backend/frontend-react/src/api/axios.js`
- Authentication provider/hook: `backend/frontend-react/src/contexts/AuthContext.jsx`

The API summary describes 102 OpenAPI paths and identifies the router registry in `backend/app/main.py` as the source of truth. Regenerate/verify this inventory from the live app OpenAPI document after route changes; do not maintain a second hand-written route registry.

## Frontend request contract

- The frontend must use the shared Axios instance from `src/api/axios.js`.
- The configured API base is `VITE_API_URL`, defaulting to same-origin `/api/v1`.
- The client reads the access token from localStorage key `token` and sends it as a Bearer token.
- HTTP 401 responses clear that same token key and redirect to `/login`.
- `AuthContext.jsx` exports `useAuth()`; it is the current custom React hook. There is no separate `src/hooks` abstraction in the inspected frontend.
- Login submits OAuth2 form fields `username` and `password`; registration submits JSON and then performs login.

Do not configure Render with `VITE_API_BASE_URL` unless the frontend client is changed in the same reviewed commit. The currently inspected client reads `VITE_API_URL`.

## Webhook and related endpoint inventory

All paths below are mounted beneath the `/api/v1` prefix unless stated otherwise.

| Method | Path | Contract |
|---|---|---|
| GET, POST | `/integrations/integrations` | List / create integrations |
| GET, POST | `/integrations/webhooks` | List / create outbound webhook definitions |
| POST | `/integrations/webhooks/{webhook_id}/test` | Send a test event to a configured destination |
| GET | `/integrations/webhooks/{webhook_id}/deliveries` | Read delivery history |
| POST | `/payments/webhook` | Receive and verify Stripe webhook events |
| POST | `/jev/intercept` | Opt-in Jev interception collector |
| GET | `/jev/intercept/status` | Interception state and event-file status |
| WS | `/ws/{client_id}` | Authenticated WebSocket connection |
| POST | `/ws/broadcast` | HTTP broadcast trigger |
| GET | `/health`, `/ready` | Root liveness/readiness |
| GET | `/health`, `/ready` | Versioned health/readiness at `/api/v1/health` and `/api/v1/ready` |

The Stripe receiver validates the Stripe signature. The Jev collector is disabled unless `JEV_INTERCEPT=1` and its endpoints use the `jev_intercept:read/create` permissions.

## Confirmed alignment gaps

1. **Webhook UI has an inert delete control.** `Integrations.jsx` renders a trash button without an onClick handler. No DELETE webhook route is registered in `integrations.py` or listed in `docs/API_SUMMARY.md`.
2. **Webhook UI does not expose the existing delivery-history endpoint.** The backend has a deliveries GET route, but the inspected page does not call it.
3. **Webhook create flow is not present in the inspected page.** The backend supports POST create; the page imports a Plus icon but does not render a create action.
4. **Webhook destination security needs remediation before exposure.** The create schema accepts a caller-supplied URL and the test action makes an outbound HTTP request to it. Add strict URL/host validation and network egress controls to prevent SSRF, including redirects and DNS/IP rebinding considerations.
5. **Webhook secret response handling needs review.** The ORM model contains a `secret` field, while create/list handlers return ORM objects directly. Use explicit response schemas that never serialize the secret; treat it as write-only.
6. **Sync SQLAlchemy session is moved between worker threads in the async test route.** The test-delivery route performs database operations through separate `asyncio.to_thread` calls. Keep one session's complete DB transaction on one worker thread or migrate that path to an async session.
7. **Stripe delivery idempotency is missing.** The current Stripe handler documents that repeated events are not deduplicated. Persist Stripe event IDs under a unique constraint before applying payment side effects.
8. **WebSocket token is supplied in the query string.** Review proxy/access-log exposure; prefer an authenticated handshake mechanism that does not place bearer credentials in URLs.
9. **Jev interception writes JSONL to a local file.** Render's ephemeral filesystem is not a durable audit store. Keep interception disabled in hosted staging until storage, retention, access, and redaction policies are explicitly designed.

## CI/CD source-of-truth review

The active `.github/workflows/ci.yml` uses full commit-SHA pins and matches the current `backend/` and `backend/frontend-react/` layout. The repository also has a pinned `.github/workflows/codeql.yml`.

The separate `.github/workflows/ci-cd-enhanced.yml` is stale: its job logs show GitHub rejecting `actions/checkout@v4` and `github/codeql-action/*@v3` because repository policy requires full SHA pins. Its frontend jobs still point at a root `frontend/` directory, use `|| true` around lint/build/test commands, and its deploy jobs are placeholder echo commands. It must not remain a competing push/PR/scheduled pipeline. The branch version is therefore archived as manual-only; use `ci.yml` as the canonical quality/deployment workflow and `codeql.yml` for CodeQL.

## Required final verification

- [ ] Import the FastAPI app and generate `/openapi.json`.
- [ ] Assert every router mount is unique and every documented route exists.
- [ ] Compare generated OpenAPI paths/methods with `docs/API_SUMMARY.md`.
- [ ] Test auth token persistence, refresh/logout behavior, 401 handling, and RBAC.
- [ ] Test webhook create/list/test/delivery history and permissions.
- [ ] Add tests for secret non-disclosure, URL allow/deny rules, redirect handling, and network failures.
- [ ] Add Stripe duplicate-event tests and database uniqueness.
- [ ] Test WebSocket authentication and avoid query-string credentials.
- [ ] Keep Jev interception off in Render until durable protected storage is available.
- [ ] Run backend tests, frontend lint/tests/build, secret scan, dependency scan, and container scan.
- [ ] Configure Render's frontend build variable as `VITE_API_URL`; verify the backend CORS allowlist contains the exact staging frontend origin.
- [ ] Deploy only to an isolated staging database; do not import or mutate production ERP data during verification.

## Cross-platform source-of-truth note

The separately inspected GitLab project `nyeinpyaesone-ui/erp` and its `staging/render-foundation` branch are not yet verified as a synchronized mirror of this GitHub repository. Its previous Render Blueprint must not be reused for this GitHub codebase without reconciling repository identity, root directories, build commands, environment variable names, and commit lineage.
