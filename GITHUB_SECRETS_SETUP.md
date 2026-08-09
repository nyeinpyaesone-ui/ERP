# GitHub Secrets Setup for Docker Push

## Required Secrets

Go to: https://github.com/nyeinpyaesone-ui/ERP/settings/secrets/actions

### 1. Add Repository Variables

| Name | Value |
|------|-------|
| DOCKER_USER | powerrangeranikg |

### 2. Add Repository Secrets

**Important:** Use the same token value for all secrets (your Docker Hub password/PAT)

| Name | Value |
|------|-------|
| DOCKERHUB_PASSWORD | (Your Docker Hub Personal Access Token - starts with dckr_pat_) |

*Note: The workflows now use a single `DOCKERHUB_PASSWORD` secret for all Docker operations.*

### 3. How to Add

1. Click "New repository secret"
2. Enter Name: `DOCKERHUB_PASSWORD`
3. Enter Value: paste your Docker Hub Personal Access Token
4. Click "Add secret"
5. Add the variable `DOCKER_USER` with value `powerrangeranikg` in the Variables tab

## After Setup

Push a tag to trigger build:
```bash
git tag v1.0.0
git push origin v1.0.0
```

GitHub Actions will automatically:
- Build backend image
- Build frontend image
- Push both to Docker Hub

## Verify

Check your Docker Hub:
- https://hub.docker.com/r/powerrangeranikg/erp-solution-backend
- https://hub.docker.com/r/powerrangeranikg/erp-solution-frontend
