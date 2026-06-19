# Docker Hub Setup Guide

## Your Docker Hub Configuration

| Setting | Value |
|---------|-------|
| **Username** | `powerrangeranikg` |
| **Image Name** | `erp-solution` |
| **Backend Image** | `powerrangeranikg/erp-solution-backend` |
| **Frontend Image** | `powerrangeranikg/erp-solution-frontend` |

## Step 1: Create Docker Hub Access Token

1. Go to https://hub.docker.com
2. Sign in as **powerrangeranikg**
3. Click **Account Settings** → **Security**
4. Click **New Access Token**
5. Description: `ERP SOLUTION GitHub Actions`
6. Permissions: **Read, Write, Delete**
7. Click **Generate** and **COPY THE TOKEN**

## Step 2: Add GitHub Secrets

Go to https://github.com/nyeinpyaesone-ui/ERP/settings/secrets/actions

Add these secrets:

| Secret Name | Value |
|-------------|-------|
| `DOCKER_USERNAME` | `powerrangeranikg` |
| `DOCKER_PASSWORD` | *(Paste your Docker Hub access token)* |

## Step 3: Create Docker Hub Repositories

1. Go to https://hub.docker.com
2. Click **Create Repository**
3. Create these two:
   - `powerrangeranikg/erp-solution-backend`
   - `powerrangeranikg/erp-solution-frontend`

## Step 4: Manual Push (Test)

```bash
# Build images
docker build -t powerrangeranikg/erp-solution-backend:latest ./backend
docker build -t powerrangeranikg/erp-solution-frontend:latest ./frontend

# Login to Docker Hub
docker login -u powerrangeranikg
# Enter your password or access token

# Push images
docker push powerrangeranikg/erp-solution-backend:latest
docker push powerrangeranikg/erp-solution-frontend:latest
```

## Step 5: Verify GitHub Actions

1. Go to https://github.com/nyeinpyaesone-ui/ERP/actions
2. Push a new tag: `git tag v1.1.0 && git push origin v1.1.0`
3. Watch the workflow run
4. Check Docker Hub for pushed images

## Image URLs

After successful push, your images will be at:

- `docker.io/powerrangeranikg/erp-solution-backend:v1.1.0`
- `docker.io/powerrangeranikg/erp-solution-frontend:v1.1.0`

## Pull and Run

```bash
# Pull images
docker pull powerrangeranikg/erp-solution-backend:latest
docker pull powerrangeranikg/erp-solution-frontend:latest

# Run
docker run -d -p 8000:8000 powerrangeranikg/erp-solution-backend:latest
docker run -d -p 3000:3000 powerrangeranikg/erp-solution-frontend:latest
```

## Troubleshooting

### "Access Denied" Error
- Check `DOCKER_USERNAME` secret is `powerrangeranikg`
- Check `DOCKER_PASSWORD` is the **access token**, not your password
- Verify repository exists on Docker Hub

### "Repository Not Found"
- Create the repository manually on Docker Hub first
- Or enable "Auto-create repositories" in Docker Hub settings
