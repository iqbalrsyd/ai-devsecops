#!/bin/bash
set -e

BACKUP_DIR="/opt/backups/postgres"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
KEEP_DAYS=7

mkdir -p "$BACKUP_DIR"

COMPOSE_FILE="-f /opt/ai-devsecops/docker-compose.prod.yml"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting Postgres backup..."

$COMPOSE_FILE exec -T postgres \
    pg_dump -U ai_devsecops ai_devsecops | gzip > "$BACKUP_DIR/postgres_${TIMESTAMP}.sql.gz"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Backup created: postgres_${TIMESTAMP}.sql.gz"

# Cleanup old backups
find "$BACKUP_DIR" -name "postgres_*.sql.gz" -mtime +$KEEP_DAYS -delete
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Old backups cleaned (kept last $KEEP_DAYS days)"

# Print backup size
du -h "$BACKUP_DIR/postgres_${TIMESTAMP}.sql.gz"
