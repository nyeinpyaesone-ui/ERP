#!/bin/bash
# Database backup script
# Usage: ./backup-db.sh [backup_dir]

set -e

BACKUP_DIR="${1:-/backups/postgres}"
DATE=$(date +%Y%m%d_%H%M%S)
DB_NAME="${POSTGRES_DB:-erp_production}"

echo "Starting database backup..."
echo "Database: $DB_NAME"
echo "Backup Directory: $BACKUP_DIR"

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Create backup
BACKUP_FILE="$BACKUP_DIR/db_$DATE.sql"
pg_dump "$DB_NAME" > "$BACKUP_FILE"

# Compress backup
gzip "$BACKUP_FILE"
COMPRESSED_FILE="${BACKUP_FILE}.gz"

echo "Backup created: $COMPRESSED_FILE"

# Upload to cloud storage (if configured)
if [ -n "$AWS_S3_BUCKET" ]; then
    echo "Uploading to S3..."
    aws s3 cp "$COMPRESSED_FILE" "s3://$AWS_S3_BUCKET/postgres/"
fi

# Clean up old backups (keep last 30 days)
echo "Cleaning up old backups..."
find "$BACKUP_DIR" -name "db_*.sql.gz" -mtime +30 -delete

echo "Backup completed successfully!"
echo "File: $COMPRESSED_FILE"
du -h "$COMPRESSED_FILE"
