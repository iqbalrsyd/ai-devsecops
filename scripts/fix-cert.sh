#!/bin/bash
set -e

echo "=== Fix Cert: Diagnose & Repair (v2) ==="

CERT_HOST_PATH="/etc/letsencrypt/live/app.iqbalhidayatrasyad.blog"
CERT_DEST="/opt/ai-devsecops/nginx/certs/app.iqbalhidayatrasyad.blog"
LE_DEST="/opt/ai-devsecops/nginx/letsencrypt/app.iqbalhidayatrasyad.blog"

echo ""
echo "[1/6] Verify cert files exist on host..."
if [ ! -f "$CERT_HOST_PATH/fullchain.pem" ]; then
    echo "  ERROR: cert files missing at $CERT_HOST_PATH"
    echo ""
    echo "  Contents of /etc/letsencrypt/live/:"
    ls -la /etc/letsencrypt/live/ 2>&1 || echo "  (directory does not exist)"
    echo ""
    echo "  Re-run: sudo bash scripts/init-letsencrypt.sh app.iqbalhidayatrasyad.blog admin@iqbalhidayatrasyad.blog"
    exit 1
fi
echo "  OK - fullchain.pem and privkey.pem exist"
ls -la "$CERT_HOST_PATH/"

echo ""
echo "[2/6] Recreate symlinks (rm -f file, mkdir -p parent, ln -sfn)..."
sudo rm -f "$CERT_DEST"
sudo rm -f "$LE_DEST"
sudo mkdir -p /opt/ai-devsecops/nginx/certs
sudo mkdir -p /opt/ai-devsecops/nginx/letsencrypt
sudo ln -sfn "$CERT_HOST_PATH" "$CERT_DEST"
sudo ln -sfn "$CERT_HOST_PATH" "$LE_DEST"
echo "  OK - symlinks created"
ls -la /opt/ai-devsecops/nginx/certs/
ls -la /opt/ai-devsecops/nginx/letsencrypt/

echo ""
echo "[3/6] Verify cert readable in container BEFORE recreate..."
# Stop nginx first so it can be restarted with fresh mount
docker stop ai-devsecops-nginx-1 2>/dev/null || true

echo ""
echo "[4/6] Recreate nginx container (fresh volume mount)..."
cd /opt/ai-devsecops
docker compose -f docker-compose.prod.yml up -d --force-recreate --no-deps nginx
sleep 8

echo ""
echo "[5/6] Verify cert is now readable inside container..."
docker exec ai-devsecops-nginx-1 ls -la /etc/letsencrypt/live/app.iqbalhidayatrasyad.blog/ 2>&1 | head -10

echo ""
echo "[6/6] Check nginx log..."
docker logs ai-devsecops-nginx-1 --tail=20

echo ""
echo "=== Testing ==="
echo "--- HTTP (expect 301 to HTTPS) ---"
curl -sI http://localhost 2>&1 | head -5
echo ""
echo "--- HTTPS localhost (expect 200) ---"
curl -sIk https://localhost 2>&1 | head -5
echo ""
echo "--- HTTPS domain (expect 200) ---"
curl -sIk https://app.iqbalhidayatrasyad.blog 2>&1 | head -5
