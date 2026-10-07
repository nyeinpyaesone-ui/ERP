# Testing Guide

## Testing Strategy

### Backend Unit Tests
Tests live in `backend/app/tests/` (with `app/tests/unit/`). They need no
running services: fixtures use SQLite in-memory engines or mocked sessions, so
PostgreSQL and Redis are not required.
```bash
cd backend
source venv/bin/activate
pytest app/tests/ -v --cov=app --cov-report=html
```

Integration tests that need PostgreSQL are marked `integration`; none exist yet.

### Frontend Tests
Vitest, via the `test` script. This is the only script the package defines for
testing — there is no `test:coverage` or `lint` script.
```bash
cd backend/frontend-react
npm ci
npm test
```

### E2E Tests
No Playwright/Cypress configuration exists yet, so there is nothing to run.

### Mobile Tests
The Expo package defines `start`/`android`/`ios`/`web` only — no `test` script.
```bash
cd mobile
npm run web
```

## Coverage

CI enforces a floor of 58% declared once in `backend/pyproject.toml`
(`[tool.coverage.report] fail_under = 58`). CI does **not** pass
`--cov-fail-under` — the earlier duplicate flag is gone, so the two cannot
drift apart. That number is a ratchet: it is the measured floor, raised as
coverage grows — it was never a goal of 80, which the suite could not reach.
Measured on the current suite: **58.21%**.

| Module | Measured | Aspiration |
|--------|----------|------------|
| Backend API | 58.21% | 85% |
| Frontend Components | (no threshold) | 80% |
| Mobile Screens | (untested) | 75% |

## CI/CD Testing
Tests run automatically on:
- Every push to `main` or `develop`
- Every pull request
- Before release tagging

## Manual Testing Checklist
- [ ] User registration and login
- [ ] Inventory CRUD operations
- [ ] Order creation and processing
- [ ] Report generation
- [ ] Mobile app sync
- [ ] AI chat functionality
- [ ] Multi-tenant isolation
