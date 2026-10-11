# End-User Production Installation Guide

This guide walks you through installing ERP SOLUTION on a production server using the automated `install.sh` script.

---

## Prerequisites

### Server Requirements
| Resource | Minimum | Recommended |
|----------|---------|-------------|
| OS | Ubuntu 22.04 LTS | Ubuntu 24.04 LTS |
| RAM | 4 GB | 8 GB+ |
| CPU | 2 vCPU | 4 vCPU+ |
| Storage | 50 GB SSD | 100 GB+ SSD |
| Network | Public IPv4 | Static IP + IPv6 |

### Domain & DNS
You need a registered domain (e.g., `yourcompany.com`) with **two A records** pointing to your server's public IP:

| Subdomain | Type | Value | Purpose |
|-----------|------|-------|---------|
| `api.yourcompany.com` | A | `YOUR_SERVER_IP` | Backend API (FastAPI) |
| `app.yourcompany.com` | A | `YOUR_SERVER_IP` | Frontend Web App (React) |

> **Note:** DNS propagation can take 5–60 minutes. Run the installer only after DNS resolves.

### Firewall Ports
Ensure these ports are open **before** running the installer:

| Port | Protocol | Purpose |
|------|----------|---------|
| 22 | TCP | SSH (your access) |
| 80 | TCP | HTTP → HTTPS redirect (Let's Encrypt validation) |
| 443 | TCP | HTTPS (API + Frontend) |

```bash
# Ubuntu UFW example
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

### Email Address
A valid email for Let's Encrypt certificate notifications (expiry alerts, renewal failures).

---

## One-Command Installation

```bash
# 1. Clone the repository
git clone https://github.com/nyeinpyaesone-ui/ERP.git
cd ERP

# 2. Run installer as root (sudo required for system packages, Docker, certbot)
sudo ./install.sh yourcompany.com admin@yourcompany.com
```

**That's it.** The script handles everything:
- Preconfigures the host: missing packages, Docker Engine, the compose plugin,
  and a started daemon (a report of anything missing is printed as it goes)
- Warns about ports 80/443 already in use and about low disk, before either
  turns into a confusing failure later
- Creates the directory structure the compose file bind-mounts
- Generates a secure `.env.production` with random passwords (mode 600)
- Validates the compose configuration and refuses blank or placeholder secrets
- Pulls the published images, or builds them locally if the registry has no
  matching tag yet
- Runs database migrations, then starts the stack and waits for real health
- Obtains Let's Encrypt certificates when both subdomains already resolve here
- Verifies the health endpoints through the proxy

To see what the host is missing **without changing anything**, run:

```bash
sudo ./install.sh --preflight
```

---

## Interactive Mode

If you prefer to be prompted:

```bash
sudo ./install.sh
```

You'll be asked for:
```
Enter your domain (e.g., erp.example.com): yourcompany.com
Enter email for SSL certificates: admin@yourcompany.com
```

---

## What the Installer Does (Step-by-Step)

### 1. Host Preconfiguration
Auto-detected and idempotent, so re-running is safe:
- Installs missing required packages: `curl`, `ca-certificates`, `openssl`
- Installs the optional ones when available: `gnupg`, `rsync`, `certbot`
  (a missing `certbot` disables TLS, it does not abort the install)
- Installs Docker Engine if the binary is absent, then **starts** the daemon if
  it is installed but not running
- Installs the `docker compose` v2 plugin, falling back to the standalone binary
- Warns if another process already holds port 80 or 443, and if the filesystem
  holding the install has less than 2 GB free

Use `--skip-deps` to skip provisioning; the script still asserts that
`openssl` and a running daemon are present, so the failure names the real gap.

### 2. Directory Structure
Creates the directories `docker-compose.prod.yml` bind-mounts, in the
directory that holds the compose file (the checkout by default; override with
`--dir=/opt/erp-solution`):
```
<install>/
├── .env.production          # Generated secrets (mode 600)
├── .active_color            # Blue-green state (blue/green)
├── .previous_version        # Rollback version tracking
├── ssl/live/<domain>/       # fullchain.pem + privkey.pem
├── logs/nginx/              # Nginx access/error logs
├── backups/                 # Database + config backups
└── backend/uploads/         # User file uploads (bind-mounted to /app/uploads)
```

The certificate layout matters: the compose file mounts `./ssl` at
`/etc/nginx/ssl`, and the generated nginx block reads
`/etc/nginx/ssl/live/<domain>/fullchain.pem`. `scripts/setup-ssl.sh` writes the
same layout, so a certificate from either script works with the other.

### 3. Secure Environment File
Generates `/opt/erp-solution/.env.production` with **cryptographically random** secrets:

```env
# Database
DB_USER=erp
DB_PASSWORD=<32-char-random>
DB_NAME=erp_solution

# Redis
REDIS_PASSWORD=<32-char-random>

# Security
SECRET_KEY=<64-hex-random>
ALGORITHM=HS256
ENVIRONMENT=prod

# Domains (your input)
CORS_ORIGINS=https://app.yourcompany.com

# External services
OLLAMA_BASE_URL=http://ollama:11434
DOCKER_USER=powerrangeranikg
VERSION=<detected from the latest git tag>
```

`ENVIRONMENT` is `prod`, not `production`: `Settings` declares it as a
`Literal["dev","test","prod"]`, and a `production` value raises at import so
the container never starts.

`install.sh` also verifies before deploying that `DB_PASSWORD`, `REDIS_PASSWORD`,
`SECRET_KEY` and `CORS_ORIGINS` are set and are not template placeholders.
Compose otherwise substitutes blank strings, and the backend then fails closed
at boot with an error that does not mention the missing variable.

> **⚠️ Save these credentials immediately.** They are displayed once at the end of installation and stored in `.env.production` (mode 600).

### 4. Nginx Configuration
- Seeds `nginx/upstream-active.conf` from `upstream-blue.conf` when absent, so
  the `include` in `nginx.conf` resolves
- Writes the TLS server block to `nginx/ssl.conf` for `api.<yourdomain>`
- Certificates are referenced by their in-container path, matching the mount

### 5. SSL Certificates (Let's Encrypt)
- Requires that `api.<domain>` and `app.<domain>` already resolve to this host
- Stops `erp-nginx` for the duration of the ACME challenge (it owns port 80 in
  this stack, so the host's own service has nothing to stop), then restarts it
- Writes to `ssl/live/api.<domain>/`, and reuses an existing certificate rather
  than re-requesting one
- Schedules renewal daily at 03:00 with a deploy hook that copies the renewed
  files into the mounted layout and reloads nginx
- On failure it continues on HTTP only and tells you how to retry:
  `./scripts/setup-ssl.sh api.yourdomain you@example.com`
- `--skip-ssl` skips this entirely

### 6. Initial Blue Deployment
- Pulls the `backend` and `frontend` images; if that fails (no network, or the
  tag was never published) it **builds them locally** instead, so a fresh server
  can still come up
- Starts PostgreSQL, Redis and Ollama, then waits for PostgreSQL readiness
- Runs **Alembic migrations** (`entrypoint.sh` runs them again on every start;
  the explicit pass surfaces schema errors in the installer log first)
- Starts nginx, frontend and backend
- Polls the container healthcheck rather than sleeping a fixed interval, since
  the backend entrypoint waits for Postgres/Redis and migrates before serving

### 7. Health Verification
Probes through the proxy, falling back to localhost:
- `https://api.yourcompany.com/health`, then `/ready`
- `http://127.0.0.1/health`

If nothing answers it prints the `compose ps` and `docker logs` commands to run
by hand, because on a host with no DNS or a firewall this is expected rather
than a failure.

---

## Post-Installation Verification

### 1. Check Containers
```bash
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```
Expected (blue environment):
| Container Name | Status | Ports |
|----------------|--------|-------|
| erp-postgres | Up (healthy) | 5432 |
| erp-redis | Up (healthy) | 6379 |
| erp-ollama | Up | 11434 |
| erp-blue-backend | Up (healthy) | 8000 |
| erp-blue-frontend | Up | 3000 |
| erp-nginx | Up | 80, 443 |

### 2. Test API Endpoints
```bash
# Liveness check
curl -s https://api.yourcompany.com/api/v1/health
# {"status":"healthy"}

# Readiness check (verifies DB + Redis)
curl -s https://api.yourcompany.com/api/v1/ready
# {"status":"ready","checks":{"database":"ok","redis":"ok"}}

# OpenAPI docs (Swagger UI)
open https://api.yourcompany.com/docs

# ReDoc
open https://api.yourcompany.com/redoc
```

### 3. Test Frontend
```bash
open https://app.yourcompany.com
```
You should see the ERP login page.

### 4. First User Registration
**There is no default admin user.** The system uses self-registration via API:

```bash
# Register first user (becomes first admin manually via DB or API)
curl -X POST https://api.yourcompany.com/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@yourcompany.com",
    "password": "your-secure-password",
    "full_name": "System Admin",
    "role": "superadmin"
  }'

# Then login
curl -X POST https://api.yourcompany.com/api/v1/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@yourcompany.com&password=your-secure-password"
```

> **⚠️ The first registered user should be assigned `superadmin` role** via database or by an existing admin. The `role` field in registration accepts: `superadmin`, `admin`, `manager`, `user`, `viewer`.

---

## Credentials Reference

All credentials are saved in **`/opt/erp-solution/.env.production`** (mode 600, root-only).

```bash
# View credentials (requires sudo)
sudo cat /opt/erp-solution/.env.production
```

| Credential | Location | Use Case |
|------------|----------|----------|
| `DB_PASSWORD` | `.env.production` | Direct DB access, backups |
| `REDIS_PASSWORD` | `.env.production` | Cache debugging |
| `SECRET_KEY` | `.env.production` | JWT signing, encryption |
| SSL cert/key | `/opt/erp-solution/ssl/` | Manual nginx config, debugging |

**Backup this file** to a secure location (password manager, encrypted USB).

---

## Default System Settings (from seed)

After installation, these settings are pre-configured:

| Key | Default Value | Category | Description |
|-----|--------------|----------|-------------|
| `company_name` | ERP SOLUTION | general | Company display name |
| `timezone` | UTC | general | Default timezone |
| `date_format` | YYYY-MM-DD | general | Default date format |
| `currency` | USD | finance | Default currency |
| `invoice_prefix` | INV | finance | Invoice number prefix |
| `max_upload_size` | 52428800 (50MB) | system | Max upload size |
| `session_timeout` | 86400 (24h) | security | Session timeout |
| `password_min_length` | 8 | security | Minimum password length |
| `enable_registration` | false | security | Allow self-registration |
| `ollama_model` | llama3.1 | ai | Default Ollama model |
| `ai_temperature` | 0.7 | ai | Default AI temperature |

> **Note:** `enable_registration: false` means only admins can create users via API. Set to `true` to allow public signup.

---

## DNS Configuration Checklist

After installation, verify DNS:

```bash
# Should resolve to your server IP
dig +short api.yourcompany.com
dig +short app.yourcompany.com

# Should show valid TLS cert
curl -I https://api.yourcompany.com/api/v1/health
curl -I https://app.yourcompany.com
```

If using **Cloudflare**:
1. Proxy status: **DNS Only** (gray cloud) for initial cert issuance
2. After certs issued: switch to **Proxied** (orange cloud)
3. SSL/TLS mode: **Full (Strict)**
4. Enable: Auto Minify, Brotli, HTTP/2, HTTP/3

---

## Management Commands

| Task | Command |
|------|---------|
| View logs (all) | `docker-compose -f docker-compose.prod.yml logs -f` |
| View backend logs | `docker-compose -f docker-compose.prod.yml logs -f backend` |
| Deploy update | `./scripts/deploy-blue-green.sh production v1.2.3` |
| Rollback | `./scripts/deploy-blue-green.sh production v1.2.3 --rollback` |
| Backup database | `./scripts/backup.sh` |
| Scale backend | `docker-compose -f docker-compose.prod.yml up -d --scale backend=2` |
| Restart all | `docker-compose -f docker-compose.prod.yml restart` |
| Stop all | `docker-compose -f docker-compose.prod.yml down` |
| Run migrations | `docker-compose -f docker-compose.prod.yml run --rm backend alembic upgrade head` |
| Create admin user | `docker-compose -f docker-compose.prod.yml run --rm backend python -c "..."` |

---

## Common Issues & Fixes

### SSL Certificate Failed
```bash
# Check DNS resolves
dig +short api.yourcompany.com

# Port 80 blocked? (required for standalone validation)
sudo ufw status
sudo ss -ltnp | grep :80

# Manual retry
sudo certbot certonly --standalone -d api.yourcompany.com -d app.yourcompany.com
```

### Database Migration Failed
```bash
# Check logs
docker-compose -f docker-compose.prod.yml logs backend

# Re-run migration manually
docker-compose -f docker-compose.prod.yml run --rm backend alembic upgrade head
```

### Backend Unhealthy
```bash
# Check backend logs
docker logs erp-blue-backend --tail 100

# Common causes:
# - DATABASE_URL wrong in .env.production
# - PostgreSQL not ready (wait longer)
# - Missing SECRET_KEY
# - Redis connection failed (check REDIS_URL)
```

### Frontend Shows Blank Page
```bash
# Check frontend container logs
docker logs erp-blue-frontend --tail 50

# Verify API URL in frontend env
docker exec erp-blue-frontend printenv REACT_APP_API_URL
# Should be: https://api.yourcompany.com
```

### Port 80/443 Already in Use
```bash
# Stop host nginx/apache
sudo systemctl stop nginx
sudo systemctl disable nginx

# Or stop apache
sudo systemctl stop apache2
sudo systemctl disable apache2
```

---

## Uninstall / Cleanup

To completely remove ERP SOLUTION:

```bash
# 1. Stop and remove containers, networks, volumes
cd /path/to/ERP
docker-compose -f docker-compose.prod.yml down -v

# 2. Remove Docker images (optional)
docker rmi $(docker images 'powerrangeranikg/erp-solution-*' -q)

# 3. Remove installation directory
sudo rm -rf /opt/erp-solution

# 4. Remove SSL certs from Let's Encrypt (optional)
sudo certbot delete --cert-name api.yourcompany.com

# 5. Remove cron job
sudo rm /etc/cron.d/erp-certbot-renewal
```

---

## Support

| Channel | Details |
|---------|---------|
| GitHub Issues | https://github.com/nyeinpyaesone-ui/ERP/issues |
| Email | nyeinpyaesone273@gmail.com |
| Documentation | `/docs` in repository |
| API Docs | `https://api.yourcompany.com/docs` |

---

## Next Steps After Install

1. **Register first superadmin user** via `/api/v1/auth/register`
2. **Configure email/SMTP** in Settings → Integrations for notifications
3. **Set up monitoring** (see `docs/MONITORING_ALERTING.md`)
4. **Schedule backups** (see `docs/BACKUP_RESTORE.md`)
5. **Review security hardening** (see `docs/SECURITY_HARDENING.md`)
6. **Deploy updates** via blue-green (see `docs/BLUE_GREEN_DEPLOYMENT.md`)
7. **Configure ERP modules** (CRM, HR, Inventory, Finance, etc.)