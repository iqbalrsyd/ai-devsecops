#!/bin/bash
set -e

cd /opt/ai-devsecops

echo "=== Fix Nginx: pull + force recreate ==="

# 1. Fetch & reset ke remote
echo "[1/5] Fetching latest from origin..."
git fetch origin

echo "[2/5] Force reset to origin/fix/ai-devsecops-custom-needs..."
git reset --hard origin/fix/ai-devsecops-custom-needs

# 2. Verify file updated
echo "[3/5] Verifying prod-nginx.conf (should NOT have 'upstream'):"
if grep -q "upstream backend_upstream" nginx/prod-nginx.conf; then
    echo "  ERROR: file still has 'upstream' block! Force pull may have failed."
    exit 1
else
    echo "  OK - no upstream block found"
fi

# 3. Force recreate nginx
echo "[4/5] Force recreating nginx container..."
docker compose -f docker-compose.prod.yml up -d --force-recreate --no-deps nginx

# 4. Wait & check
sleep 5
echo "[5/5] Nginx log:"
docker logs ai-devsecops-nginx-1 --tail=20

echo ""
echo "=== Testing ==="
echo "--- HTTP (expect 301) ---"
curl -sI http://localhost 2>&1 | head -5
echo "--- HTTPS (expect 200) ---"
curl -sIk https://localhost 2>&1 | head -5
echo "--- HTTPS domain (expect 200) ---"
curl -sIk https://app.iqbalhidayatrasyad.blog 2>&1 | head -5
