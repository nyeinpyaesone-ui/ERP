# API Documentation Summary

> Generated from live OpenAPI (`GET /openapi.json`). **98 paths** total.
> Source of truth: `backend/app/main.py` router registration + `TestClient(app).get('/openapi.json')`.
> All API routes are versioned under `/api/v1`. There is no unversioned `/auth/*` tree.

## Base URLs

- Development: `http://localhost:8000`
- Production: `https://api.yourdomain.com`
- API base path (all routers except root health): `<base>/api/v1`
- Example: auth login is `POST http://localhost:8000/api/v1/auth/login`
  (NOT `POST /auth/login` as older revisions of this doc stated).

## Authentication

- Scheme: **JWT Bearer** via `OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")`
  (see `backend/app/auth.py:14`, OpenAPI `components.securitySchemes.OAuth2PasswordBearer`).
- Login with form fields (`username` + `password`) at `POST /api/v1/auth/login`, then send:
  ```
  Authorization: Bearer <your-jwt-token>
  ```
- Most endpoints require the token; RBAC is enforced via `require_permission()`
  against `backend/app/permissions_catalogue.py`.

## Router table (every prefix registered in `backend/app/main.py`)

| Router module (`app/routers/`) | Prefix | Tag | Paths |
|---|---|---|---|
| `auth` | `/api/v1/auth` | Authentication | 5 |
| `crm` | `/api/v1/crm` | CRM | 8 |
| `hr` | `/api/v1/hr` | HR | 4 |
| `inventory` | `/api/v1/inventory` | Inventory | 4 |
| `finance` | `/api/v1/finance` | Finance | 5 |
| `projects` | `/api/v1/projects` | Projects | 6 |
| `ai` | `/api/v1/ai` | AI | 3 |
| `documents` | `/api/v1/documents` | Documents | 3 |
| `reports` | `/api/v1/reports` | Reports | 4 |
| `workflows` | `/api/v1/workflows` | Workflows | 5 |
| `payments` | `/api/v1/payments` | Payments | 2 |
| `integrations` | `/api/v1/integrations` | Integrations | 4 |
| `analytics` | `/api/v1/analytics` | Analytics | 2 |
| `admin` | `/api/v1/admin` | Admin | 6 |
| `websocket` | `/api/v1/ws` | WebSocket | 1 (`POST /api/v1/ws/broadcast`) |
| `search` | `/api/v1/search` | Search | 7 |
| `permissions` | `/api/v1/permissions` | Permissions | 11 |
| `llm` | `/api/v1/llm` | LLM | 13 |
| `health` | `/api/v1` | Health | 2 (`GET /api/v1/health`, `GET /api/v1/ready`) |
| `health_root` | `` (root) | Health | 2 (`GET /health`, `GET /ready`) |

Root `GET /` returns service info (`name`, `version`, `status`, `features`).

## Health / docs URLs

| Purpose | Dev URL | Prod URL |
|---|---|---|
| Health (versioned) | `http://localhost:8000/api/v1/health` | `https://api.yourdomain.com/api/v1/health` |
| Health (root) | `http://localhost:8000/health` | `https://api.yourdomain.com/health` |
| Readiness (versioned) | `http://localhost:8000/api/v1/ready` | `https://api.yourdomain.com/api/v1/ready` |
| Readiness (root) | `http://localhost:8000/ready` | `https://api.yourdomain.com/ready` |
| Swagger UI | `http://localhost:8000/docs` | `https://api.yourdomain.com/docs` |
| ReDoc | `http://localhost:8000/redoc` | `https://api.yourdomain.com/redoc` |
| OpenAPI JSON | `http://localhost:8000/openapi.json` | `https://api.yourdomain.com/openapi.json` |

## Endpoints by group (live paths)

### Auth — `/api/v1/auth` (5 paths)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/login` | Login (OAuth2 password flow, returns JWT) |
| POST | `/api/v1/auth/register` | User registration |
| GET | `/api/v1/auth/me` | Current user |
| GET | `/api/v1/auth/users` | List users |
| PUT | `/api/v1/auth/users/{user_id}` | Update user |

### CRM — `/api/v1/crm` (8 paths)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET/POST | `/api/v1/crm/companies` | List / create companies |
| GET/PUT/DELETE | `/api/v1/crm/companies/{company_id}` | Get / update / delete company |
| GET/POST | `/api/v1/crm/contacts` | List / create contacts |
| GET/PUT/DELETE | `/api/v1/crm/contacts/{contact_id}` | Get / update / delete contact |
| GET/POST | `/api/v1/crm/deals` | List / create deals |
| GET | `/api/v1/crm/deals/pipeline` | Pipeline view |
| GET/PUT/DELETE | `/api/v1/crm/deals/{deal_id}` | Get / update / delete deal |
| GET | `/api/v1/crm/dashboard` | CRM dashboard |

### HR — `/api/v1/hr` (4 paths)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/hr/dashboard` | HR dashboard |
| GET/POST | `/api/v1/hr/departments` | List / create departments |
| GET/POST | `/api/v1/hr/employees` | List / create employees |
| GET/PUT/DELETE | `/api/v1/hr/employees/{employee_id}` | Get / update / delete employee |

### Inventory — `/api/v1/inventory` (4 paths)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/inventory/dashboard` | Inventory dashboard |
| GET/POST | `/api/v1/inventory/products` | List / create products |
| GET/PUT/DELETE | `/api/v1/inventory/products/{product_id}` | Get / update / delete product |
| GET/POST | `/api/v1/inventory/movements` | List / create stock movements |

### Finance — `/api/v1/finance` (5 paths)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/finance/dashboard` | Finance dashboard |
| GET/POST | `/api/v1/finance/invoices` | List / create invoices |
| GET | `/api/v1/finance/invoices/{invoice_id}` | Get invoice |
| PUT | `/api/v1/finance/invoices/{invoice_id}/status` | Update invoice status |
| POST | `/api/v1/finance/payments` | Create payment |

### Projects — `/api/v1/projects` (6 paths)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/projects/dashboard` | Projects dashboard |
| GET/POST | `/api/v1/projects/projects` | List / create projects |
| GET/PUT | `/api/v1/projects/projects/{project_id}` | Get / update project |
| GET | `/api/v1/projects/projects/{project_id}/tasks` | List project tasks |
| POST | `/api/v1/projects/tasks` | Create task |
| PUT | `/api/v1/projects/tasks/{task_id}` | Update task |

### AI — `/api/v1/ai` (3 paths)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/ai/chat` | AI chat |
| GET | `/api/v1/ai/forecast/revenue` | Revenue forecast |
| GET | `/api/v1/ai/insights` | AI insights |

### Documents — `/api/v1/documents` (3 paths)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/documents/upload` | Upload document |
| GET | `/api/v1/documents/documents` | List documents |
| GET/DELETE | `/api/v1/documents/documents/{doc_id}` | Get / delete document |

### Reports — `/api/v1/reports` (4 paths)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/reports/revenue` | Revenue report |
| GET | `/api/v1/reports/chart/revenue` | Revenue chart data |
| GET | `/api/v1/reports/inventory` | Inventory report |
| GET | `/api/v1/reports/pipeline` | Pipeline report |

### Workflows — `/api/v1/workflows` (5 paths)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET/POST | `/api/v1/workflows/workflows` | List / create workflows |
| GET/DELETE | `/api/v1/workflows/workflows/{workflow_id}` | Get / delete workflow |
| POST | `/api/v1/workflows/workflows/{workflow_id}/execute` | Execute workflow |
| PUT | `/api/v1/workflows/workflows/{workflow_id}/toggle` | Enable/disable workflow |
| GET | `/api/v1/workflows/executions` | List executions |

### Payments — `/api/v1/payments` (2 paths)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/payments/create-intent` | Create Stripe payment intent |
| POST | `/api/v1/payments/webhook` | Stripe webhook receiver |

### Integrations — `/api/v1/integrations` (4 paths)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET/POST | `/api/v1/integrations/integrations` | List / create integrations |
| GET/POST | `/api/v1/integrations/webhooks` | List / create webhooks |
| GET | `/api/v1/integrations/webhooks/{webhook_id}/deliveries` | Webhook deliveries |
| POST | `/api/v1/integrations/webhooks/{webhook_id}/test` | Test webhook |

### Analytics — `/api/v1/analytics` (2 paths)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/analytics/dashboard` | Dashboard analytics |
| GET | `/api/v1/analytics/monthly-trends` | Monthly trends |

### Admin — `/api/v1/admin` (6 paths)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/admin/stats` | Admin stats |
| GET | `/api/v1/admin/activity-logs` | Activity logs |
| GET | `/api/v1/admin/notifications` | Notifications |
| PUT | `/api/v1/admin/notifications/{notif_id}/read` | Mark notification read |
| GET/POST | `/api/v1/admin/settings` | Get / create settings |
| DELETE | `/api/v1/admin/settings/{key}` | Delete setting |

### WebSocket — `/api/v1/ws` (1 path)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/ws/broadcast` | Broadcast message (HTTP trigger; live socket upgrades served by the WS router — there is no separate `/ws` route) |

```javascript
// Real-time updates go through the /api/v1/ws router, not /ws.
const ws = new WebSocket('wss://api.yourdomain.com/api/v1/ws/...');
```

### Search — `/api/v1/search` (7 paths)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET/POST | `/api/v1/search/` | Search (GET form + POST body) |
| GET | `/api/v1/search/suggestions` | Query suggestions |
| GET | `/api/v1/search/facets` | Search facets |
| GET | `/api/v1/search/analytics` | Search analytics |
| GET | `/api/v1/search/analytics/popular-queries` | Popular queries |
| POST | `/api/v1/search/index/{entity_type}/{entity_id}` | Index one entity |
| POST | `/api/v1/search/reindex` | Reindex all |

### Permissions — `/api/v1/permissions` (11 paths)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/permissions/me` | My permissions |
| GET | `/api/v1/permissions/permissions` | List permissions |
| GET/POST | `/api/v1/permissions/roles` | List / create roles |
| GET/PUT/DELETE | `/api/v1/permissions/roles/{role_id}` | Get / update / delete role |
| POST | `/api/v1/permissions/roles/{role_id}/permissions` | Assign permissions to role |
| GET/POST | `/api/v1/permissions/users/{user_id}/roles` | Get / assign user roles |
| GET/POST | `/api/v1/permissions/data-policies` | List / create data policies |
| DELETE | `/api/v1/permissions/data-policies/{policy_id}` | Delete data policy |
| PUT | `/api/v1/permissions/data-policies/{policy_id}/toggle` | Toggle data policy |
| GET/POST | `/api/v1/permissions/field-permissions` | List / create field permissions |
| DELETE | `/api/v1/permissions/field-permissions/{fp_id}` | Delete field permission |

### LLM — `/api/v1/llm` (13 paths)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/llm/chat` | Chat completion |
| POST | `/api/v1/llm/chat/stream` | Streaming chat |
| GET/POST | `/api/v1/llm/conversations` | List / create conversations |
| GET/DELETE | `/api/v1/llm/conversations/{conversation_id}` | Get / delete conversation |
| PUT | `/api/v1/llm/conversations/{conversation_id}/archive` | Archive conversation |
| GET | `/api/v1/llm/models` | List models |
| GET/PUT/DELETE | `/api/v1/llm/models/{model_id}` | Get / update / delete model |
| POST | `/api/v1/llm/models/{model_id}/pull` | Pull model |
| GET/POST | `/api/v1/llm/templates` | List / create prompt templates |
| GET | `/api/v1/llm/templates/{template_name}` | Get template by name |
| DELETE | `/api/v1/llm/templates/{template_id}` | Delete template |
| GET | `/api/v1/llm/analytics/usage` | LLM usage analytics |
| GET | `/api/v1/llm/analytics/conversations` | Conversation analytics |

### Health — `/api/v1` + root (4 paths)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/health` | Health check (versioned) |
| GET | `/api/v1/ready` | Readiness check (versioned) |
| GET | `/health` | Health check (root) |
| GET | `/ready` | Readiness check (root) |

## Removed / phantom endpoints (do NOT exist)

These appeared in older revisions of this doc but have **no route in `main.py`
and no path in live `/openapi.json`** — do not call them:

- `/auth/login`, `/auth/register`, `/auth/refresh`, `/auth/logout`
  → use `/api/v1/auth/login`, `/api/v1/auth/register` (+ `/api/v1/auth/me`).
  There is no `/api/v1/auth/refresh` or `/api/v1/auth/logout`.
- `/api/v1/orders` (GET/POST) → does not exist.
- `/api/v1/customers` → does not exist (CRM uses `/api/v1/crm/contacts` + `/api/v1/crm/companies`).
- `/api/v1/reports/sales` → does not exist (reports are `/api/v1/reports/revenue`, `/api/v1/reports/chart/revenue`, `/api/v1/reports/inventory`, `/api/v1/reports/pipeline`).
- `/ai/forecast`, `/ai/chat`, `/ai/rag/query`, `/ai/agents/status`
  → AI lives under `/api/v1/ai/*` (`/api/v1/ai/chat`, `/api/v1/ai/forecast/revenue`, `/api/v1/ai/insights`); there is no RAG or agents-status route.
- `/ws` → does not exist; WebSocket router is mounted at `/api/v1/ws` (`POST /api/v1/ws/broadcast`).

## Multi-tenant

All endpoints support tenant isolation via:
- Header: `X-Tenant-ID: tenant-123`
- JWT claim: `tenant_id`

## Rate limits

- Anonymous: 100 requests/hour
- Authenticated: 1000 requests/hour
- Premium: 10000 requests/hour

## Error codes

| Code | Meaning |
|------|---------|
| 400 | Bad Request |
| 401 | Unauthorized |
| 403 | Forbidden (tenant access) |
| 404 | Not Found |
| 429 | Rate Limited |
| 500 | Internal Server Error |

## Regenerating this doc

From `backend/`:
```bash
venv/bin/python -c "from fastapi.testclient import TestClient; from app.main import app; import json; c=TestClient(app, raise_server_exceptions=False); paths=c.get('/openapi.json').json()['paths']; print(len(paths)); [print(k) for k in sorted(paths)[:10]]"
grep -c "api/v1" docs/API_SUMMARY.md
```
