# SSL Certificates Guide

This guide covers Let's Encrypt certificate management for ERP SOLUTION production deployments.

---

## Certificate Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Let's Encrypt CA                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                    ┌─────────┴─────────┐
                    ▼                   ▼
            api.yourdomain.com    app.yourdomain.com
                    │                   │
                    └─────────┬─────────┘
                              ▼
                    ┌─────────────────┐
                    │   certbot       │
                    │  (standalone)   │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
       /etc/letsencrypt/  /opt/erp-solution/  nginx container
       live/domain/       ssl/
       ├─ cert.pem        ├─ cert.pem         Mounted at
       ├─ privkey.pem     ├─ key.pem          /etc/nginx/ssl/
       ├─ chain.pem
       └─ fullchain.pem
```

---

## Initial Certificate Issuance

The `install.sh` script handles this automatically:

```bash
# Run during initial install
sudo ./install.sh yourdomain.com admin@yourdomain.com
```

**What happens:**
1. Stops any service on port 80
2. Runs `certbot certonly --standalone -d api.yourdomain.com -d app.yourdomain.com`
3. Copies certificates to `/opt/erp-solution/ssl/`
4. Configures daily auto-renewal cron job

### Manual Issuance (if needed)
```bash
# Ensure port 80 is free
sudo systemctl stop nginx 2>/dev/null || true
sudo ss -ltnp | grep :80

# Request certificates
sudo certbot certonly --standalone \
  --non-interactive \
  --agree-tos \
  --email admin@yourdomain.com \
  -d api.yourdomain.com -d app.yourdomain.com

# Copy to ERP directory
sudo cp /etc/letsencrypt/live/api.yourdomain.com/fullchain.pem /opt/erp-solution/ssl/cert.pem
sudo cp /etc/letsencrypt/live/api.yourdomain.com/privkey.pem /opt/erp-solution/ssl/key.pem
sudo chown $USER:$USER /opt/erp-solution/ssl/*.pem
```

---

## Nginx SSL Configuration

The `nginx.conf` references certificates at `/etc/nginx/ssl/`:

```nginx
# In docker-compose.prod.yml, nginx service mounts:
volumes:
  - ./ssl:/etc/nginx/ssl:ro

# nginx.conf:
server {
    listen 443 ssl http2;
    server_name api.yourdomain.com;

    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
    
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    
    # HSTS (1 year)
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    ...
}
```

---

## Auto-Renewal

### Cron Job (Created by install.sh)
```bash
# /etc/cron.d/erp-certbot-renewal
0 3 * * * root certbot renew --quiet \
  --post-hook "cp /etc/letsencrypt/live/api.yourdomain.com/fullchain.pem /opt/erp-solution/ssl/cert.pem \
               && cp /etc/letsencrypt/live/api.yourdomain.com/privkey.pem /opt/erp-solution/ssl/key.pem \
               && docker exec erp-nginx nginx -s reload"
```

**Runs daily at 3 AM.** Only renews certificates within 30 days of expiry.

### Systemd Timer Alternative (More Reliable)
```bash
sudo tee /etc/systemd/system/erp-certbot-renewal.service > /dev/null <<'EOF'
[Unit]
Description=Renew Let's Encrypt certificates for ERP
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/bin/certbot renew --quiet \
  --post-hook "cp /etc/letsencrypt/live/api.yourdomain.com/fullchain.pem /opt/erp-solution/ssl/cert.pem && cp /etc/letsencrypt/live/api.yourdomain.com/privkey.pem /opt/erp-solution/ssl/key.pem && docker exec erp-nginx nginx -s reload"
StandardOutput=journal
StandardError=journal
EOF

sudo tee /etc/systemd/system/erp-certbot-renewal.timer > /dev/null <<'EOF'
[Unit]
Description=Daily certificate renewal check

[Timer]
OnCalendar=*-*-* 03:00:00
Persistent=true
RandomizedDelaySec=1h

[Install]
WantedBy=timers.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now erp-certbot-renewal.timer
```

---

## Verification & Testing

### Check Certificate Details
```bash
# View certificate info
openssl x509 -in /opt/erp-solution/ssl/cert.pem -text -noout | grep -E "Subject:|Issuer:|Not Before:|Not After:|DNS:"

# Check expiry
openssl x509 -in /opt/erp-solution/ssl/cert.pem -noout -enddate

# Test TLS connection
openssl s_client -connect api.yourdomain.com:443 -servername api.yourdomain.com </dev/null 2>/dev/null | openssl x509 -noout -dates
```

### Test Renewal (Dry Run)
```bash
# Test renewal without actually renewing
sudo certbot renew --dry-run

# Check what would be renewed
sudo certbot renew --dry-run 2>&1 | grep -E "cert|renew"
```

### Force Renewal
```bash
# Force renew even if not near expiry
sudo certbot renew --force-renewal \
  --post-hook "cp /etc/letsencrypt/live/api.yourdomain.com/fullchain.pem /opt/erp-solution/ssl/cert.pem && cp /etc/letsencrypt/live/api.yourdomain.com/privkey.pem /opt/erp-solution/ssl/key.pem && docker exec erp-nginx nginx -s reload"
```

---

## Staging vs Production

### Staging Environment (Testing)
```bash
# Use Let's Encrypt staging (not trusted by browsers)
sudo certbot certonly --standalone \
  --staging \
  --non-interactive \
  --agree-tos \
  --email admin@yourdomain.com \
  -d api.yourdomain.com -d app.yourdomain.com
```

**Use for:** Testing certificate automation, CI/CD pipelines.

### Production Environment
```bash
# Default (no --staging flag)
sudo certbot certonly --standalone \
  --non-interactive \
  --agree-tos \
  --email admin@yourdomain.com \
  -d api.yourdomain.com -d app.yourdomain.com
```

---

## Cloudflare Integration

If using Cloudflare as DNS proxy:

### Option 1: DNS-01 Challenge (Recommended for Cloudflare)
```bash
# Install Cloudflare DNS plugin
pip install certbot-dns-cloudflare

# Create credentials file
cat > /root/.cloudflare.ini <<'EOF'
dns_cloudflare_email = your@email.com
dns_cloudflare_api_key = YOUR_GLOBAL_API_KEY
EOF
chmod 600 /root/.cloudflare.ini

# Issue with DNS challenge (no port 80 needed)
sudo certbot certonly --dns-cloudflare \
  --dns-cloudflare-credentials /root/.cloudflare.ini \
  --non-interactive --agree-tos \
  --email admin@yourdomain.com \
  -d api.yourdomain.com -d app.yourdomain.com \
  -d *.yourdomain.com  # Wildcard support
```

### Option 2: HTTP-01 with Cloudflare Proxy
```bash
# Cloudflare settings required:
# 1. SSL/TLS mode: Full (Strict)
# 2. Always Use HTTPS: On
# 3. Automatic HTTPS Rewrites: On
# 4. Minimum TLS Version: TLS 1.2

# Certbot still works with HTTP-01 if:
# - Proxy status: DNS Only (gray cloud) during issuance
# - After issuance: switch to Proxied (orange cloud)
```

---

## Troubleshooting

### Certificate Expired
```bash
# Check expiry
openssl x509 -in /opt/erp-solution/ssl/cert.pem -noout -enddate

# Force renew
sudo certbot renew --force-renewal

# Reload nginx
docker exec erp-nginx nginx -s reload
```

### Renewal Fails
```bash
# Check certbot logs
sudo tail -50 /var/log/letsencrypt/letsencrypt.log

# Common issues:
# - Port 80 blocked (firewall, another service)
# - DNS not resolving to server IP
# - Rate limited (max 5 certs/week per domain)

# Check rate limit status
sudo certbot certificates
```

### Port 80 Already in Use
```bash
# Find what's using port 80
sudo ss -ltnp | grep :80

# Stop conflicting service
sudo systemctl stop nginx
sudo systemctl disable nginx

# Or if using apache
sudo systemctl stop apache2
sudo systemctl disable apache2
```

### Nginx Fails to Reload After Renewal
```bash
# Test nginx config
docker exec erp-nginx nginx -t

# Check nginx error log
docker exec erp-nginx tail -20 /var/log/nginx/error.log

# Manual reload
docker exec erp-nginx nginx -s reload
```

### Certificate/Key Mismatch
```bash
# Verify cert and key match
openssl x509 -noout -modulus -in /opt/erp-solution/ssl/cert.pem | openssl md5
openssl rsa -noout -modulus -in /opt/erp-solution/ssl/key.pem | openssl md5
# Both MD5 hashes must be identical
```

---

## Monitoring & Alerting

### Check Certificate Expiry (Prometheus)
```yaml
# Add to prometheus.yml scrape configs
- job_name: 'ssl-cert-check'
  static_configs:
    - targets: ['localhost:9115']  # node-exporter with ssl_cert_exporter
```

### Simple Expiry Check Script
```bash
#!/bin/bash
# /opt/erp-solution/scripts/check-ssl-expiry.sh

CERT_FILE="/opt/erp-solution/ssl/cert.pem"
WARN_DAYS=30
CRIT_DAYS=7

EXPIRY=$(openssl x509 -in "$CERT_FILE" -noout -enddate | cut -d= -f2)
EXPIRY_EPOCH=$(date -d "$EXPIRY" +%s)
NOW_EPOCH=$(date +%s)
DAYS_LEFT=$(( (EXPIRY_EPOCH - NOW_EPOCH) / 86400 ))

if [ $DAYS_LEFT -le $CRIT_DAYS ]; then
    echo "CRITICAL: SSL certificate expires in $DAYS_LEFT days"
    exit 2
elif [ $DAYS_LEFT -le $WARN_DAYS ]; then
    echo "WARNING: SSL certificate expires in $DAYS_LEFT days"
    exit 1
else
    echo "OK: SSL certificate valid for $DAYS_LEFT days"
    exit 0
fi
```

### Add to Monitoring
```bash
# Cron check every 6 hours
0 */6 * * * /opt/erp-solution/scripts/check-ssl-expiry.sh >> /opt/erp-solution/logs/ssl-check.log 2>&1
```

---

## Certificate Files Reference

| File | Path | Purpose | Permissions |
|------|------|---------|-------------|
| Full Chain | `/opt/erp-solution/ssl/cert.pem` | Server cert + intermediate CA | 644 |
| Private Key | `/opt/erp-solution/ssl/key.pem` | Private key (KEEP SECRET) | 600 |
| Let's Encrypt Live | `/etc/letsencrypt/live/api.yourdomain.com/` | Source of truth | root:root 700 |

---

## Security Best Practices

- [ ] Private key permissions: `600` (readable only by root/owner)
- [ ] Certificate permissions: `644`
- [ ] HSTS header enabled (1 year, includeSubDomains)
- [ ] TLS 1.2+ only (disable TLS 1.0, 1.1)
- [ ] Strong cipher suites (HIGH:!aNULL:!MD5)
- [ ] OCSP Stapling enabled (add to nginx.conf)
- [ ] Certificate Transparency monitoring
- [ ] Rate limit monitoring for certbot

---

## Related Documentation

| Document | Link |
|----------|------|
| End-User Install | `docs/END_USER_INSTALL.md` |
| Blue-Green Deployment | `docs/BLUE_GREEN_DEPLOYMENT.md` |
| Backup & Restore | `docs/BACKUP_RESTORE.md` |
| Operations Runbook | `docs/OPERATIONS_RUNBOOK.md` |