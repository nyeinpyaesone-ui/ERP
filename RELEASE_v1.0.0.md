# Release v1.0.0 — ERP SOLUTION

**Release Date:** 2026-06-19
**Status:** Production Ready

## What's Included

### 12 Production Modules (274 Files)
| Module | Version | Files | Status |
|--------|---------|-------|--------|
| Core System | v2.2 | 91 | ✅ |
| BI Dashboard | v3.2 | 20 | ✅ |
| Retail POS | v2.9 | 9 | ✅ |
| Manufacturing/MRP | v2.7 | 10 | ✅ |
| E-commerce | v3.0 | 12 | ✅ |
| Mobile App | v2.5 | 17 | ✅ |
| Kubernetes | v3.1 | 22 | ✅ |
| DevOps/CI/CD | — | 10 | ✅ |
| Knowledge System | — | 21 | ✅ |
| Integration | — | 7 | ✅ |
| Legacy v2.1 | v2.1 | 31 | ✅ |
| Legacy v1.8 | v1.8 | 29 | ✅ |

### Infrastructure & Tooling
- ✅ Docker Compose full stack
- ✅ Kubernetes deployment manifests
- ✅ GitHub Actions CI/CD (test, build, release)
- ✅ Makefile for common commands
- ✅ Environment setup script
- ✅ GitHub repository manager

### Documentation
- ✅ README with badges and architecture
- ✅ Production deployment guide
- ✅ API documentation summary
- ✅ GitHub secrets setup guide
- ✅ Contributing guidelines
- ✅ Changelog
- ✅ MIT License

## Quick Start

```bash
git clone https://github.com/nyeinpyaesone-ui/ERP.git
cd ERP
./scripts/setup.sh
docker-compose up -d
```

## Deployment

### Docker Compose (Single Server)
```bash
docker-compose up -d
```

### Kubernetes (Production)
```bash
kubectl apply -f infra/k8s/
```

## API Access

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- Health Check: `http://localhost:8000/health`

## Support

- GitHub Issues: https://github.com/nyeinpyaesone-ui/ERP/issues
- Documentation: See `docs/` directory
- Status: `./scripts/gh-manager.sh status`

---

**Full Changelog**: https://github.com/nyeinpyaesone-ui/ERP/commits/v1.0.0

---

## Appendix A — v1.0.0 snapshot vs HEAD (informational, added post-release)

> This release note describes tag `v1.0.0`. It is a frozen snapshot.
> Current development (`HEAD`, branch `main`) has diverged. Do not read module
> paths below as current.

- **Counts at tag:** `git ls-tree -r v1.0.0 --name-only | wc -l` = **274** tracked files.
- **Counts at HEAD (2026-10-03):** `git ls-tree -r HEAD` = **259** files; `git rev-list --count HEAD` = **64** commits.
- **Module-table erratum:** the table in "What's Included" sums to **279** (91+20+9+10+12+17+22+10+21+7+31+29), not the `274` in its heading. `274` is the total tracked-file count at the tag, not the module-file sum.
- **Removed since v1.0.0** (absent from `HEAD` and worktree): `frontend/` — 51 files deleted (canonical frontend is now `backend/frontend-react/`); `backend-v2.1/` — 31 files; `backend-v1.8/` — 29 files; `docker/` — 4 files (superseded by root `nginx.conf`, `nginx/` and `docker-compose*.yml`).
- **Added since v1.0.0** (selected): `RELEASE_v1.0.0.md`, `STATUS_CHECKLIST.md`, `AGENTS.md`, `docker-compose.prod.yml`, `nginx/`, `scripts/deploy-blue-green.sh`, `scripts/backup.sh`.
