#!/bin/bash
set -e

echo "=== Fix Cert: Diagnose & Repair ==="

CERT_HOST_PATH="/etc/letsencrypt/live/app.iqbalhidayatrasyad.blog"
CERT_DEST="/opt/ai-devsecops/nginx/certs/app.iqbalhidayatrasyad.blog"
LE_DEST="/opt/ai-devsecops/nginx/letsencrypt/app.iqbalhidayatrasyad.blog"

echo ""
echo "[1/5] Check if cert files exist on host..."
if [ -f "$CERT_HOST_PATH/fullchain.pem" ] && [ -f "$CERT_HOST_PATH/privkey.pem" ]; then
    echo "  OK - cert files exist on host"
else
    echo "  ERROR - cert files missing on host at $CERT_HOST_PATH"
    echo ""
    echo "  Contents of /etc/letsencrypt/live/:"
    ls -la /etc/letsencrypt/live/ 2>&1 || echo "  (directory does not exist)"
    echo ""
    echo "  This means Let's Encrypt cert was never issued, or expired/deleted."
    echo "  Re-run: sudo bash scripts/init-letsencrypt.sh app.iqbalhidayatrasyad.blog admin@iqbalhidayatrasyad.blog"
    exit 1
fi

echo ""
echo "[2/5] Recreate symlinks to cert files..."
sudo rm -f "$CERT_DEST"
sudo rm -f "$LE_DEST"
sudo mkdir -p /opt/ai-devsecops/nginx/certs
sudo mkdir -p /opt/ai-devsecops/nginx/letsencrypt
sudo ln -sfn "$CERT_HOST_PATH" "$CERT_DEST"
sudo ln -sfn "$CERT_HOST_PATH" "$LE_DEST"
echo "  OK - symlinks recreated"
ls -la /opt/ai-devsecops/nginx/certs/
ls -la /opt/ai-devsecops/nginx/letsencrypt/

echo ""
echo "[3/5] Verify cert is readable in container..."
docker exec ai-devsecops-nginx-1 ls -la /etc/letsencrypt/live/app.iqbalhidayatrasyad.blog/ 2>&1 | head -10

echo ""
echo "[4/5] Force recreate nginx to reload volumes..."
cd /opt/ai-devsecops
docker compose -f docker-compose.prod.yml up -d --force-recreate --no-deps nginx
sleep 5

echo ""
echo "[5/5] Check nginx log..."
docker logs ai-devsecops-nginx-1 --tail=15

echo ""
echo "=== Testing ==="
echo "--- HTTP (expect 301) ---"
curl -sI http://localhost 2>&1 | head -5
echo "--- HTTPS (expect 200) ---"
curl -sIk https://localhost 2>&1 | head -5
echo "--- HTTPS domain (expect 200) ---"
curl -sIk https://app.iqbalhidayatrasyad.blog 2>&1 | head -5
