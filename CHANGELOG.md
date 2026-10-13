# Changelog

All versions follow Semantic Versioning. The canonical package version is `1.8.0` (backend `__version__`, `APP_VERSION`, frontend-react, and mobile are aligned).

## [1.8.0] — 2026-10-14

### Fixed / Hardened for Release
- **Observability**: implemented real Prometheus endpoint `GET /metrics` (`erp_http_requests_total`, request-latency histogram, in-flight gauge, DB pool gauge) with path-template labels; wired into app factory and middleware stack.
- **Monitoring deployable**: added root `prometheus.yml` scrape config and pinned `prom/prometheus:v2.53.4` service + volume to `docker-compose.prod.yml`.
- **Kubernetes manifests corrected against actual images**: container port/probes/Prometheus annotation moved from 3000 → 8000 (Service keeps 3000→targetPort 8000); added hidden `/health/live`, `/health/startup`, `/health/ready` alias endpoints so probe paths exist; frontend probes switched to `/healthz` backed by a new nginx location returning 200.
- **Mobile dependency set rebuilt** to a coherent Expo SDK 50 / React Native 0.73.6 baseline (previous manifest listed impossible/fabricated versions); `mobile/README.md` corrected.
- **Docs drift eliminated**: `/metrics` claims in README and production docs now true; `PRODUCTION_SETUP.md` updated from "not implemented" to documented endpoint.
- **Repo hygiene**: removed orphan root `package-lock.json` and added ignore rule; pytest plugin crash fixed via `-p no:libtmux` in `pytest.ini` (full suite green: 289 backend + 105 frontend tests).
- **Version alignment**: unified all package version strings on `1.8.0` (was drifting 2.2.0 / 1.8.0 / 1.8.0 / 2.5.0).

## [1.0.0] — 2026-06-19

### Initial Release
- 12 production modules extracted and organized
- 274 tracked files at tag `v1.0.0` (`git ls-tree -r v1.0.0 --name-only | wc -l`)
- Multi-version backend (v1.8, v2.1, v2.2)
- React Native mobile application
- BI Dashboard, POS, MRP, E-commerce frontend modules
- Kubernetes deployment manifests
- CI/CD pipeline (GitHub Actions)
- Docker Compose setup
- Full documentation

### Modules
| Module | Version | Status |
|--------|---------|--------|
| DevOps & CI/CD | — | ✅ |
| BI Dashboard | v3.2 | ✅ |
| Core System | v2.2 | ✅ |
| Core System | v2.1 | ✅ |
| Core System | v1.8 | ✅ |
| Retail POS | v2.9 | ✅ |
| Manufacturing/MRP | v2.7 | ✅ |
| Mobile App | v2.5 | ✅ |
| Knowledge System | — | ✅ |
| Kubernetes Deployment | v3.1 | ✅ |
| Integration Guide | — | ✅ |
| E-commerce Storefront | v3.0 | ✅ |
