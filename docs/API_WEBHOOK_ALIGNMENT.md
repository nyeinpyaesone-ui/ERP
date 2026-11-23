# API, Webhook, and Frontend Contract Alignment

Status: repository CI verified on 2026-11-23 (CI run #507); restored-staging validation and deployment remain pending.

## Canonical source

- Repository: `nyeinpyaesone-ui/ERP`
- Review branch: `audit/api-webhook-contract`
- Application entry point: `backend/app/main.py`
- Shared frontend HTTP client: `backend/frontend-react/src/api/axios.js`
- Frontend auth hook: `backend/frontend-react/src/contexts/AuthContext.jsx`
- Webhook page: `backend/frontend-react/src/pages/Integrations.jsx`

The FastAPI router registry in `backend/app/main.py` is authoritative. Generate endpoint inventories from `/openapi.json`; do not keep a second hand-written route registry as runtime configuration.

## Frontend HTTP and authentication contract

- Use the shared Axios client from `src/api/axios.js`.
- API base setting: `VITE_API_URL`, default `/api/v1`.
- Access token storage key: `token`; requests send `Authorization: Bearer <token>`.
- HTTP 401 clears the same key and redirects to `/login`.
- `AuthContext.jsx` exports `useAuth()`; this is the current auth hook.
- Login uses OAuth2 form fields `username` and `password`.

Render frontend configuration must use `VITE_API_URL`, not `VITE_API_BASE_URL`. The backend CORS allowlist must include the exact staging frontend origin.

## Webhook endpoint contract

All paths below are mounted beneath `/api/v1/integrations`.

| Method | Path | Contract |
|---|---|---|
| GET, POST | `/integrations` | List / create integrations |
| GET, POST | `/webhooks` | List / create outbound webhook definitions |
| DELETE | `/webhooks/{webhook_id}` | Soft-disable webhook; preserve delivery history |
| POST | `/webhooks/{webhook_id}/test` | Send guarded test event |
| GET | `/webhooks/{webhook_id}/deliveries` | Return the most recent 100 delivery records |

Implementation changes:
- `WebhookPublic` and `WebhookDeliveryPublic` are explicit response schemas; the write-only webhook secret is not serialized.
- Webhook create and delivery require HTTPS, port 443, no embedded credentials, and an exact host in `WEBHOOK_ALLOWED_HOSTS`.
- Delivery re-validates DNS and rejects non-public IP answers.
- HTTP redirects are disabled, environment proxies are not trusted, and only 2xx responses count as successful delivery.
- Database operations for a test delivery remain on one synchronous request worker/session.
- DELETE deactivates the webhook rather than deleting its record or delivery history.
- The Integrations page now supports create, test, disable, and delivery-history workflows.

Security boundary: exact host allowlisting and DNS checks reduce SSRF exposure, but DNS rebinding cannot be ruled out solely by application-level preflight resolution. Production egress firewall/network policy should also restrict outbound connections to approved destinations.

## Stripe contract

- `POST /api/v1/payments/webhook` verifies the Stripe signature.
- A new `stripe_webhook_events` table stores Stripe event IDs as a primary key.
- Event processing and payment/invoice updates share one transaction.
- Repeated event IDs are acknowledged as duplicates without repeating side effects.
- A second event ID for an already processed PaymentIntent does not add a second payment.
- The worker creates and closes its own SQLAlchemy session, avoiding cross-thread use of a request-scoped session.
- Migration `009` adds the idempotency table.

## WebSocket contract

Path: `WS /api/v1/ws/{client_id}`.

The server no longer reads bearer tokens from query parameters. The client must connect, then send this first frame:

```json
{"type":"authenticate","token":"<access-token>"}
```

Authentication must complete within five seconds. The server binds the connection group to the authenticated user's ID and ignores the caller-supplied path ID. The shared client helper is `backend/frontend-react/src/api/websocket.js`; it rejects `ws://` on HTTPS pages so bearer tokens are only sent over secure WebSocket transport in production.

Do not use `?token=...` in WebSocket URLs; URLs are commonly retained in proxy and access logs.

## Jev interception storage contract

Jev capture remains disabled unless `JEV_INTERCEPT=1`. In production, it also requires:
- `JEV_INTERCEPT_DURABLE=1`
- an absolute `JEV_INTERCEPT_EVENTS_FILE` path on an operator-provisioned persistent volume.

The durable flag is an operator assertion, not an automatic proof that a disk is mounted. Keep Jev interception disabled in Render staging until a persistent disk, access controls, retention, redaction, and backup policy are explicitly configured.

## Alembic history repair

The repository contained two migration files declaring the same revision ID `005`, which makes Alembic revision discovery ambiguous.

The review branch now:
- retains the permission reconciliation migration as revision `005`;
- renames the tenancy migration revision to `005_tenancy`, parent `005`;
- adds additive permission reconciliation revision `005_permissions_reconcile`;
- links revision `006` to `005_permissions_reconcile`;
- keeps the subsequent `007`, `008`, and new `009` chain intact.

The tenancy migration checks for existing tables, columns, indexes, and constraints before adding them; its downgrade is intentionally a no-op to preserve tenant and ERP records. Tests assert unique revision IDs and a single head revision (`009`). A PostgreSQL integration regression test also creates disposable schemas for both legacy `005` interpretations, upgrades to head twice, checks permission reconciliation, and confirms an existing synthetic tenant row survives.

Before running this on any existing database, take and verify a backup. The migration is designed to be additive/idempotent, but staging must validate it against a restored copy of the actual schema before production use.

## CI/CD source of truth

- `.github/workflows/ci.yml`: canonical tests, quality checks, image builds, and approved deployment flow.
- `.github/workflows/codeql.yml`: CodeQL.
- `.github/workflows/ci-cd-enhanced.yml`: manual-only archive; it is not a competing automatic pipeline.
- Backend PostgreSQL URLs are normalized to the installed `psycopg2` driver; the frontend CI/Docker build uses Node 22 for the current jsdom/undici runtime.
- The final backend runtime image removes `pip`, `setuptools`, and `wheel` after copying application dependencies; these build/install tools remain outside the shipped runtime image.
- Ruff and Black are blocking on changed backend Python files. Full-repository lint debt predates this patch and remains a separate cleanup task.

The archived workflow had unpinned actions, stale frontend paths, non-blocking checks, and placeholder deployment steps.

## Verification gates

- [x] GitHub Actions passes backend tests, migration graph and legacy PostgreSQL migration tests, frontend lint/tests/build, Gitleaks, both image builds, and the blocking Trivy vulnerability gate (run #507).
- [ ] OpenAPI route inventory is regenerated and compared to `docs/API_SUMMARY.md`.
- [ ] Webhook response schema is confirmed not to expose secrets.
- [ ] URL allowlist, private DNS rejection, redirects, and delivery error cases are tested.
- [ ] Stripe duplicate event and same-PaymentIntent duplicate tests pass against PostgreSQL.
- [ ] WebSocket valid/invalid first-frame authentication tests pass; production connections use `wss://`.
- [ ] Jev production storage gate tests pass; Jev remains off in staging until durable storage is provisioned.
- [ ] Restore a backup to an isolated staging database and run `alembic upgrade head`.
- [ ] Configure Render frontend `VITE_API_URL` and backend `CORS_ORIGINS`.
- [ ] Configure `WEBHOOK_ALLOWED_HOSTS` only with approved destinations; leave blank to disable outbound webhook creation/delivery.
- [ ] Deploy only to a separate staging database; do not import or mutate production ERP data.

## Cross-platform source-of-truth note

The separate GitLab project `nyeinpyaesone-ui/erp` has not been verified as a synchronized mirror of this GitHub repository. Do not reuse its Render Blueprint without reconciling repository identity, root directories, environment names, build commands, and commit lineage.
