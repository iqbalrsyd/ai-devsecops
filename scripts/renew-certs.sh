#!/bin/bash
set -e

LOG_FILE="/var/log/le-renew.log"
LOCK_FILE="/var/run/le-renew.lock"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Prevent concurrent runs
if [ -f "$LOCK_FILE" ]; then
    log "Renewal already in progress, skipping."
    exit 0
fi
touch "$LOCK_FILE"
trap "rm -f $LOCK_FILE" EXIT

log "Starting certificate renewal check..."

# Renew certificates
certbot renew --quiet

# Check if any certs were renewed
RENEWED=$(find /etc/letsencrypt/live -name "cert.pem" -type f -exec openssl x509 -in {} -noout -dates -subject 2>/dev/null \; | \
    awk -F'serialNumber=' '/notAfter=/{split($1,d,"/"); if(d[2]!="") print d[2]}')

if [ -n "$RENEWED" ]; then
    log "Certificates renewed, reloading nginx..."
    cd /opt/ai-devsecops
    docker compose -f docker-compose.yml -f docker-compose.prod.yml exec nginx nginx -s reload 2>/dev/null || \
        docker compose -f docker-compose.yml -f docker-compose.prod.yml restart nginx
    log "Nginx reloaded successfully"
else
    log "No certificates renewed (not due yet)"
fi

log "Renewal check complete"
