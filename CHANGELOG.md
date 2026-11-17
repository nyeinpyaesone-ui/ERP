# Changelog

## [1.1.0] — 2026-10-14

### Multi-platform Linux (amd64 + arm64) stabilization
- Backend Dockerfile: `pip install --prefix=/install` replaces the fragile
  `--user` + `/root/.local` copy (the copied site-packages were only found via
  a non-root HOME side effect); added `libc6-dev` for source builds on archs
  without prebuilt wheels; documented buildx multi-platform usage.
- Frontend Dockerfile: documented amd64/arm64 manifest coverage of
  node:20-alpine / nginx:alpine bases.
- CI (`ci.yml`): docker-backend and docker-frontend now publish
  `linux/amd64,linux/arm64` manifest lists when pushing, with SLSA provenance
  (`mode=min`) and SBOM attestations attached to every pushed image. Local
  no-push builds stay single-arch (`--load` cannot represent a manifest list).
- `docker-build.sh`: `--push` without `--platform` now defaults to
  `linux/amd64,linux/arm64` so manual pushes can't silently overwrite the
  multi-arch tag with a single-arch image; multi-arch without `--push` exports
  to cache instead of hard-failing; QEMU/binfmt availability is pre-checked;
  detected host platform values are validated before use.
- Compose files: `ollama/ollama:latest` pinned to `0.9.6` (reproducible pulls;
  upstream ships amd64 + arm64 manifests).

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
