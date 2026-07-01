#!/bin/bash
set -e

cd /opt/ai-devsecops

echo "=== Fix Nginx: pull + fix cert + force recreate ==="

# 1. Fetch & reset
echo "[1/7] Fetching latest from origin..."
git fetch origin
echo "[2/7] Force reset to origin/fix/ai-devsecops-custom-needs..."
git reset --hard origin/fix/ai-devsecops-custom-needs

# 2. Verify nginx config updated
echo "[3/7] Verifying prod-nginx.conf..."
if grep -q "upstream backend_upstream" nginx/prod-nginx.conf; then
    echo "  ERROR: still has 'upstream' block! Force pull failed."
    exit 1
else
    echo "  OK - no upstream block (resolver-via-variable pattern)"
fi

# 3. Check cert exists
echo "[4/7] Check cert files..."
CERT_PATH="/etc/letsencrypt/live/app.iqbalhidayatrasyad.blog"
if [ ! -f "$CERT_PATH/fullchain.pem" ]; then
    echo "  ERROR: cert files missing at $CERT_PATH"
    echo "  Run: sudo bash scripts/init-letsencrypt.sh app.iqbalhidayatrasyad.blog admin@iqbalhidayatrasyad.blog"
    exit 1
fi
echo "  OK - cert files exist"

# 4. Recreate symlinks
echo "[5/7] Recreate cert symlinks..."
sudo rm -f /opt/ai-devsecops/nginx/certs/app.iqbalhidayatrasyad.blog
sudo rm -f /opt/ai-devsecops/nginx/letsencrypt/app.iqbalhidayatrasyad.blog
sudo ln -sfn "$CERT_PATH" /opt/ai-devsecops/nginx/certs/app.iqbalhidayatrasyad.blog
sudo ln -sfn "$CERT_PATH" /opt/ai-devsecops/nginx/letsencrypt/app.iqbalhidayatrasyad.blog
ls -la /opt/ai-devsecops/nginx/certs/

# 5. Force recreate nginx
echo "[6/7] Force recreating nginx container..."
docker compose -f docker-compose.prod.yml up -d --force-recreate --no-deps nginx
sleep 5

# 6. Check
echo "[7/7] Nginx log:"
docker logs ai-devsecops-nginx-1 --tail=15

echo ""
echo "=== Testing ==="
echo "--- HTTP (expect 301) ---"
curl -sI http://localhost 2>&1 | head -5
echo "--- HTTPS (expect 200) ---"
curl -sIk https://localhost 2>&1 | head -5
echo "--- HTTPS domain (expect 200) ---"
curl -sIk https://app.iqbalhidayatrasyad.blog 2>&1 | head -5
