# Archived workflow fragments

These files were found misplaced inside `.github/workflows/` (a nested
`.github/`, a mobile Expo build, tool configs, and TS sources). GitHub only
loads `*.yml` files at the top of `.github/workflows/`, so these never ran.
They are kept here for reference until the mobile app is ready to ship:

- `build.yml` — Expo/EAS mobile build+submit pipeline; requires an `EXPO_TOKEN`
  secret and a real `eas.json` under `mobile/` before it can be activated.
- `ci.yml` — older CI variant (superseded by `../ci.yml`).
- `eas.json`, `critical-flow.yaml`, `env.ts`, `sentry.ts`,
  `package.json.devops-snippet.json`, lint/format configs, PR template —
  mobile/frontend fragments from a mis-scoped code generation run.
