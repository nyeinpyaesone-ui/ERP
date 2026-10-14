---
name: ERP Frontend
description: Canonical Vite+React PWA at backend/frontend-react - single-API-client rule, env contract, test/lint/build commands with expected results, endpoint-calling conventions, and npm-wrapper pitfalls
---

# ERP Frontend (`backend/frontend-react/`)

The ONLY real frontend (D-001). Root `/frontend` is deleted/broken — never create or build it.

## Stack & layout

- Vite 6.4.4 + React 18 (JSX, no TypeScript config — no tsconfig, no tsc step) + vite-plugin-pwa (generateSW).
- **Tailwind CSS v4** (2026-10-15 migration, T-009): `@tailwindcss/vite` plugin in
  `vite.config.js` (NOT the postcss route — `postcss.config.js` keeps only autoprefixer),
  `src/index.css` starts with `@import "tailwindcss";` (never the v3 `@tailwind` directives),
  and **there is no `tailwind.config.js`** (auto content detection; the unused `primary`
  palette extension and the unused `tailwind-merge` dep were pruned in the same commit).
  v3→v4 parity renames already applied: `flex-shrink-0`→`shrink-0`, `shadow-sm`→`shadow-xs`,
  `outline-none`→`outline-hidden` — if styling "loses" a utility after a future edit,
  check for v3-era class names first.
- Deps of note: vitest **5.x** (jsdom, `vitest.config.ts`), react-router-dom **7.x**
  (v7 = `react-router` re-export; v6 patterns like `BrowserRouter/Routes/Route/Link` unchanged).
  `npm audit` = **0 vulnerabilities** (2026-10-15) — keep it that way; install with semver majors only after running the full battery.
- Tests: Vitest (`vitest.config.ts`), 105 tests / 7 files. Lint: ESLint 10 flat config (`eslint.config.js`), currently 0 errors / 127 warnings — CI enforces errors fail.
- `src/api/axios` is the ONLY API client (D-008). Pages/contexts must import it; tokens + 401 refresh live in the interceptor. Enforced by `src/**/single-client.test.js` — direct `axios`/`fetch` calls to the API fail the suite.

## Env contract

- Only `VITE_API_URL` is read (default `/api/v1`, relative — nginx proxies `/api` to the backend). See `.env.example`. Nothing else is consumed; do not add VITE_-vars without wiring them.

## Commands (from `backend/frontend-react/`)

```sh
npm test          # vitest run -> 105/105 (~35s)
npm run lint      # eslint src -> must stay 0 errors
npm run build     # vite build + PWA sw: 6 precache entries, ~838 KiB
npm run dev       # vite --host
```

Use `npm` from PATH (10.9.2 at ~/.local/bin). `/home/admin/.local/bin/npm` is a SHELL wrapper — never invoke it as `node <path>` (parses as JS and crashes). The Makefile `NPM` var handles the /tmp fallback automatically.

## Endpoint-calling convention

All calls target backend prefixes under `/api/v1/` (auth, crm, hr, inventory, finance, projects, ai, documents, reports, workflows, payments, integrations, analytics, admin, search, permissions, llm) — the 57-call matrix is tested to match the 98 backend routes exactly. After adding a backend route, update calls AND keep the matrix test green. WebSocket: `/api/v1/ws` (single WS endpoint).

## Pitfalls

- Build/test never need a running backend (mock via the axios instance, not fetch).
- PWA service worker regenerates on build; don't hand-edit `dist/sw.js`.
- `node_modules` was npm-ci'd from the lockfile; use `npm ci` (not install) for reproducibility — the Dockerfile does the same.
