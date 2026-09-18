# Backup & Restore Guide

This guide covers backup procedures, scheduling, and disaster recovery for ERP SOLUTION.

---

## Backup Strategy Overview

| Component | Method | Frequency | Retention |
|-----------|--------|-----------|-----------|
| PostgreSQL | `pg_dump` (custom format) | Daily (2 AM) | 30 days |
| Redis | RDB snapshot + AOF | Daily | 7 days |
| Application Config | File copy (`.env.production`) | On change | Indefinite |
| User Uploads | Volume snapshot / rsync | Daily | 30 days |
| SSL Certificates | File copy | On renewal | Indefinite |

---

## Automated Backup Script

The `scripts/backup.sh` script handles all backup operations.

### Usage
```bash
# Full backup (default: production environment)
./scripts/backup.sh

# Backup to custom directory
./scripts/backup.sh /mnt/backups/erp

# Backup staging environment
./scripts/backup.sh /opt/erp-solution/backups staging
```

### What It Backs Up
```
backup_<env>_<timestamp>/
├── source_code.tar.gz        # Full repo (excludes .git, node_modules, venv)
├── database.sql              # PostgreSQL dump (if DB running)
├── env.production            # Production environment config
└── manifest.txt              # Metadata: date, git commit, version
```

### Example Output
```
==========================================
  ERP SOLUTION Backup (production)
==========================================
  Destination: /opt/erp-solution/backups/erp_backup_production_20240115_020000
==========================================
[1/4] Backing up source code...
  ✓ Source code backed up
[2/4] Backing up database...
  ✓ Database backed up
[3/4] Backing up environment files...
  ✓ Environment files backed up
[4/4] Creating backup manifest...
  ✓ Manifest created
==========================================
  Backup Complete!
  Location: /opt/erp-solution/backups/erp_backup_production_20240115_020000
==========================================
```

---

## Scheduling Automated Backups

### Cron Job (Daily at 2 AM)
```bash
# Edit crontab for root
sudo crontab -e

# Add:
0 2 * * * /opt/erp-solution/ERP/scripts/backup.sh /opt/erp-solution/backups production >> /opt/erp-solution/logs/backup-$(date +\%Y\%m\%d).log 2>&1
```

### Systemd Timer (More Robust)
```bash
# Create service file
sudo tee /etc/systemd/system/erp-backup.service > /dev/null <<'EOF'
[Unit]
Description=ERP Solution Daily Backup
After=docker.service

[Service]
Type=oneshot
WorkingDirectory=/opt/erp-solution/ERP
ExecStart=/opt/erp-solution/ERP/scripts/backup.sh /opt/erp-solution/backups production
StandardOutput=journal
StandardError=journal
EOF

# Create timer file
sudo tee /etc/systemd/system/erp-backup.timer > /dev/null <<'EOF'
[Unit]
Description=Run ERP backup daily at 2 AM

[Timer]
OnCalendar=*-*-* 02:00:00
Persistent=true
RandomizedDelaySec=15min

[Install]
WantedBy=timers.target
EOF

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable --now erp-backup.timer

# Verify
systemctl list-timers --all | grep erp-backup
```

---

## Manual Backup Commands

### Database Only
```bash
# Using docker-compose (production-blue project)
docker-compose -p production-blue -f docker-compose.prod.yml exec -T postgres \
  pg_dump -U erp -Fc erp_solution > backup_$(date +%Y%m%d_%H%M%S).dump

# Or using backup script's internal method
docker-compose -p production-blue -f docker-compose.prod.yml exec -T postgres \
  pg_dump -U erp erp_solution > backup_$(date +%Y%m%d).sql
```

### Compressed Custom Format (Recommended)
```bash
# Custom format allows parallel restore and selective table restore
docker-compose -p production-blue -f docker-compose.prod.yml exec -T postgres \
  pg_dump -U erp -Fc -Z9 erp_solution > erp_backup_$(date +%Y%m%d).dump
```

### Redis Backup
```bash
# Trigger BGSAVE (async)
docker exec erp-redis redis-cli BGSAVE

# Copy RDB file
docker cp erp-redis:/data/dump.rdb ./redis_backup_$(date +%Y%m%d).rdb
```

### Configuration Backup
```bash
# Backup .env.production
cp /opt/erp-solution/.env.production /opt/erp-solution/backups/env.production.$(date +%Y%m%d)

# Backup nginx configs
tar -czf nginx_configs_$(date +%Y%m%d).tar.gz /opt/erp-solution/ERP/nginx/
```

---

## Restore Procedures

### 1. Restore Database (Full Restore)

#### From SQL Dump
```bash
# 1. Stop application (keep DB running)
docker-compose -p production-blue -f docker-compose.prod.yml stop backend frontend

# 2. Drop and recreate database
docker-compose -p production-blue -f docker-compose.prod.yml exec -T postgres \
  psql -U erp -c "DROP DATABASE IF EXISTS erp_solution; CREATE DATABASE erp_solution;"

# 3. Restore
cat backup_20240115.sql | docker-compose -p production-blue -f docker-compose.prod.yml exec -T postgres \
  psql -U erp erp_solution

# 4. Run migrations (in case schema differs)
docker-compose -p production-blue -f docker-compose.prod.yml run --rm backend alembic upgrade head

# 5. Restart application
docker-compose -p production-blue -f docker-compose.prod.yml start backend frontend
```

#### From Custom Format Dump (Faster, Parallel)
```bash
# 1. Stop application
docker-compose -p production-blue -f docker-compose.prod.yml stop backend frontend

# 2. Restore with pg_restore (4 parallel jobs)
docker-compose -p production-blue -f docker-compose.prod.yml exec -T postgres \
  pg_restore -U erp -d erp_solution -j4 -c < erp_backup_20240115.dump

# 3. Run migrations
docker-compose -p production-blue -f docker-compose.prod.yml run --rm backend alembic upgrade head

# 4. Restart
docker-compose -p production-blue -f docker-compose.prod.yml start backend frontend
```

### 2. Restore Single Table
```bash
# Restore only 'users' table
docker-compose -p production-blue -f docker-compose.prod.yml exec -T postgres \
  pg_restore -U erp -d erp_solution -t users < erp_backup_20240115.dump
```

### 3. Point-in-Time Recovery (PITR)

**Requires:** WAL archiving configured (see below).

```bash
# 1. Stop application
docker-compose -p production-blue -f docker-compose.prod.yml stop backend frontend

# 2. Restore base backup
pg_basebackup -D /var/lib/postgresql/data -Ft -z -P

# 3. Create recovery.signal and configure restore_command
cat > /var/lib/postgresql/data/recovery.signal <<'EOF'
EOF

cat > /var/lib/postgresql/data/postgresql.auto.conf <<'EOF'
restore_command = 'cp /backups/wal_archives/%f %p'
recovery_target_time = '2024-01-15 14:30:00'
recovery_target_action = 'promote'
EOF

# 4. Start PostgreSQL (will replay WAL to target time)
docker-compose -p production-blue -f docker-compose.prod.yml up -d postgres

# 5. Wait for promotion, then restart app
docker-compose -p production-blue -f docker-compose.prod.yml up -d backend frontend
```

---

## WAL Archiving Setup (For PITR)

### Configure PostgreSQL for WAL Archiving
```bash
# Edit postgresql.conf (inside container or mounted config)
# These settings enable WAL archiving to /backups/wal_archives
cat >> /opt/erp-solution/postgresql.conf <<'EOF'
wal_level = replica
archive_mode = on
archive_command = 'test ! -f /backups/wal_archives/%f && cp %p /backups/wal_archives/%f'
archive_timeout = 300
max_wal_senders = 3
wal_keep_segments = 64
EOF

# Create archive directory
mkdir -p /opt/erp-solution/backups/wal_archives
chown -R 999:999 /opt/erp-solution/backups/wal_archives

# Mount in docker-compose.prod.yml (postgres service)
# volumes:
#   - ./postgresql.conf:/etc/postgresql/postgresql.conf
#   - ./backups/wal_archives:/backups/wal_archives
```

---

## Backup Verification

### Test Restore (Monthly)
```bash
# 1. Create test database
docker run --rm -d --name test-postgres \
  -e POSTGRES_USER=erp -e POSTGRES_PASSWORD=test -e POSTGRES_DB=test_restore \
  postgres:15-alpine

# 2. Wait for ready
sleep 5

# 3. Restore backup
cat backup_20240115.sql | docker exec -i test-postgres psql -U erp test_restore

# 4. Verify data
docker exec test-postgres psql -U erp test_restore -c "SELECT COUNT(*) FROM users;"

# 5. Cleanup
docker stop test-postgres
```

### Verify Backup Integrity
```bash
# Check SQL dump is valid
head -5 backup_20240115.sql
# Should start with: -- PostgreSQL database dump

# Check custom dump
pg_restore -l erp_backup_20240115.dump | head -20
# Lists tables in dump
```

---

## Offsite Backup (S3/MinIO)

### Upload to S3
```bash
# Install awscli
pip install awscli

# Configure
aws configure
# AWS Access Key ID: ***
# AWS Secret Access Key: ***
# Default region: us-east-1
# Default output: json

# Upload daily
aws s3 cp /opt/erp-solution/backups/erp_backup_production_$(date +%Y%m%d)_*.tar.gz \
  s3://your-bucket/erp-backups/production/ --storage-class STANDARD_IA

# Lifecycle policy: Move to Glacier after 30 days, delete after 365 days
```

### Using MinIO (Self-Hosted S3)
```bash
# Install mc (MinIO client)
curl -O https://dl.min.io/client/mc/release/linux-amd64/mc
chmod +x mc && sudo mv mc /usr/local/bin/

# Configure
mc alias set myminio http://minio:9000 admin password

# Mirror backups
mc mirror /opt/erp-solution/backups/ myminio/erp-backups/production/
```

---

## Disaster Recovery Scenarios

| Scenario | RTO | RPO | Procedure |
|----------|-----|-----|-----------|
| Single table corruption | <15 min | <24h | Restore single table from dump |
| Database server failure | <30 min | <24h | Restore full DB on new server |
| Full server loss | <2 hours | <24h | Provision new server → run install.sh → restore DB |
| Ransomware/encryption | <4 hours | <24h | Wipe → reinstall → restore from offsite |
| Region outage | <1 hour | <1h | Failover to standby region (requires setup) |

---

## Backup Checklist

- [ ] Daily automated backup configured (cron or systemd timer)
- [ ] Backups stored offsite (S3, MinIO, remote server)
- [ ] Monthly test restore performed and documented
- [ ] WAL archiving enabled for PITR capability
- [ ] Backup encryption at rest (S3 SSE or GPG)
- [ ] Backup retention policy enforced (auto-delete old)
- [ ] Alert on backup failure (check cron logs / systemd status)
- [ ] `.env.production` backed up separately (encrypted)
- [ ] SSL certificates backed up

---

## Quick Reference

| Command | Description |
|---------|-------------|
| `./scripts/backup.sh` | Full automated backup |
| `docker-compose exec postgres pg_dump -U erp -Fc erp_solution > backup.dump` | Manual DB backup |
| `docker-compose exec -T postgres psql -U erp erp_solution < backup.sql` | Restore from SQL |
| `docker-compose exec -T postgres pg_restore -U erp -d erp_solution -j4 < backup.dump` | Restore from custom format |
| `aws s3 sync /opt/erp-solution/backups/ s3://bucket/erp-backups/` | Upload to S3 |