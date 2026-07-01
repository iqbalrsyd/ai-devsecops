#!/bin/bash
set -e

# Robust cert mount fix: copy cert files to project directory,
# mount that directory to container, restart nginx

cd /opt/ai-devsecops

CERT_LIVE="/etc/letsencrypt/live/app.iqbalhidayatrasyad.blog"
CERT_FLAT="./nginx/cert-files"

echo "=== Fix Cert Mount (v2 - copy to project dir) ==="

# 1. Verify source cert exists
echo "[1/6] Check source cert..."
if [ ! -f "$CERT_LIVE/fullchain.pem" ]; then
    echo "  ERROR: $CERT_LIVE/fullchain.pem missing"
    echo "  Re-run: sudo bash scripts/init-letsencrypt.sh"
    exit 1
fi
ls -la "$CERT_LIVE/"

# 2. Copy cert files to project dir (resolve symlinks with cp -L)
echo "[2/6] Copy cert files to ./nginx/cert-files/..."
mkdir -p "$CERT_FLAT"
cp -L "$CERT_LIVE/fullchain.pem" "$CERT_FLAT/fullchain.pem"
cp -L "$CERT_LIVE/privkey.pem" "$CERT_FLAT/privkey.pem"
cp -L "$CERT_LIVE/chain.pem" "$CERT_FLAT/chain.pem" 2>/dev/null || true
cp -L "$CERT_LIVE/cert.pem" "$CERT_FLAT/cert.pem" 2>/dev/null || true
chmod 644 "$CERT_FLAT"/*.pem
ls -la "$CERT_FLAT/"

# 3. Update docker-compose.prod.yml to mount from project dir
echo "[3/6] Update docker-compose.prod.yml mount path..."
if grep -q "/etc/letsencrypt/live/app.iqbalhidayatrasyad.blog:/etc/letsencrypt/live/app.iqbalhidayatrasyad.blog" docker-compose.prod.yml; then
    sed -i "s|- /etc/letsencrypt/live/app.iqbalhidayatrasyad.blog:/etc/letsencrypt/live/app.iqbalhidayatrasyad.blog:ro|- ./nginx/cert-files:/etc/letsencrypt/live/app.iqbalhidayatrasyad.blog:ro|" docker-compose.prod.yml
    echo "  OK - mount path updated to ./nginx/cert-files"
else
    echo "  Already updated or different format - check manually"
fi
grep -A3 "volumes:" docker-compose.prod.yml | grep "cert-files\|letsencrypt" || echo "  WARNING: not found in compose"

# 4. Stop & recreate nginx
echo "[4/6] Stop & recreate nginx..."
docker compose -f docker-compose.prod.yml up -d --force-recreate --no-deps nginx
sleep 8

# 5. Verify
echo "[5/6] Verify cert in container..."
docker exec ai-devsecops-nginx-1 ls -la /etc/letsencrypt/live/app.iqbalhidayatrasyad.blog/ 2>&1 | head -10

# 6. Test
echo "[6/6] Test HTTPS..."
docker logs ai-devsecops-nginx-1 --tail=10
echo ""
echo "--- HTTP ---"
curl -sI http://localhost 2>&1 | head -3
echo "--- HTTPS ---"
curl -sIk https://localhost 2>&1 | head -5
echo "--- HTTPS domain ---"
curl -sIk https://app.iqbalhidayatrasyad.blog 2>&1 | head -5
