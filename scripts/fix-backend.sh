#!/bin/bash
set -e

cd /opt/ai-devsecops

echo "=== Fix Backend: pull + force rebuild ==="

# 1. Pull latest
echo "[1/5] Pull latest from origin..."
git fetch origin
git reset --hard origin/fix/ai-devsecops-custom-needs

# 2. Verify Dockerfile fixed
echo "[2/5] Verify backend/Dockerfile has CMD..."
if grep -q 'CMD \["./main"\]' backend/Dockerfile; then
    echo "  OK - CMD found"
else
    echo "  ERROR: CMD not found, file not updated!"
    exit 1
fi

# 3. Verify compose target removed
echo "[3/5] Verify docker-compose.prod.yml (no target: builder)..."
if grep -q "target: builder" docker-compose.prod.yml; then
    echo "  ERROR: target: builder still present!"
    exit 1
else
    echo "  OK - target: builder removed"
fi

# 4. Force rebuild backend
echo "[4/5] Force rebuild backend image (no cache)..."
docker compose -f docker-compose.prod.yml build --no-cache backend
docker compose -f docker-compose.prod.yml up -d --force-recreate --no-deps backend

# 5. Wait & verify
echo "[5/5] Wait & verify..."
sleep 15
echo "--- STATUS ---"
docker compose -f docker-compose.prod.yml ps | grep backend
echo ""
echo "--- BACKEND LOG ---"
docker logs ai-devsecops-backend-1 --tail=20
echo ""
echo "--- TEST FROM NGINX ---"
docker exec ai-devsecops-nginx-1 wget -qO- http://backend:8080/api/v1/health 2>&1 | head -5
echo ""
echo "--- TEST LOGIN ---"
curl -sIk -X POST https://app.iqbalhidayatrasyad.blog/api/v1/auth/login \
    -H "Content-Type: application/json" -d '{}' 2>&1 | head -5
