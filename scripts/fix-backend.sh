#!/bin/bash
set -e

cd /opt/ai-devsecops

echo "=== Fix Backend: pull + sync .env + force rebuild ==="

# 1. Pull latest
echo "[1/7] Pull latest from origin..."
git fetch origin
git reset --hard origin/fix/ai-devsecops-custom-needs

# 2. Verify Dockerfile fixed
echo "[2/7] Verify backend/Dockerfile has CMD..."
if grep -q 'CMD \["./main"\]' backend/Dockerfile; then
    echo "  OK - CMD found"
else
    echo "  ERROR: CMD not found!"
    exit 1
fi

# 3. Verify compose target removed
echo "[3/7] Verify docker-compose.prod.yml (no target: builder)..."
if grep -q "target: builder" docker-compose.prod.yml; then
    echo "  ERROR: target: builder still present!"
    exit 1
else
    echo "  OK - target: builder removed"
fi

# 4. Sync .env DB config to match compose
echo "[4/7] Sync .env DB config to match compose..."
if [ ! -f .env ]; then
    echo "  .env missing, copying from template..."
    cp .env.production.example .env
    chmod 600 .env
    echo "  WARNING: .env created from template. You need to fill in API keys!"
else
    # Use sed to update only DB-related fields to match compose
    sed -i 's/^DATABASE_USER=.*/DATABASE_USER=postgres/' .env
    sed -i 's/^DATABASE_PASSWORD=.*/DATABASE_PASSWORD=postgres/' .env
    sed -i 's/^DATABASE_NAME=.*/DATABASE_NAME=ai_devsecops/' .env
    sed -i 's/^DATABASE_HOST=.*/DATABASE_HOST=postgres/' .env
    sed -i 's/^DATABASE_PORT=.*/DATABASE_PORT=5432/' .env
    sed -i 's/^DATABASE_SSLMODE=.*/DATABASE_SSLMODE=disable/' .env
    sed -i 's/^REDIS_HOST=.*/REDIS_HOST=redis/' .env
    sed -i 's/^REDIS_PORT=.*/REDIS_PORT=6379/' .env
    echo "  OK - .env DB fields synced"
    echo "  Current DB config:"
    grep -E "^DATABASE_" .env
fi

# 5. Restart postgres to ensure data is clean
echo "[5/7] Restart postgres (to ensure user/db created with new config)..."
docker compose -f docker-compose.prod.yml restart postgres
sleep 5

# 6. Force rebuild backend
echo "[6/7] Force rebuild backend (no cache)..."
docker compose -f docker-compose.prod.yml build --no-cache backend
docker compose -f docker-compose.prod.yml up -d --force-recreate --no-deps backend

# 7. Wait & verify
echo "[7/7] Wait & verify..."
sleep 20
echo "--- STATUS ---"
docker compose -f docker-compose.prod.yml ps
echo ""
echo "--- BACKEND LOG ---"
docker logs ai-devsecops-backend-1 --tail=15
echo ""
echo "--- TEST FROM NGINX ---"
docker exec ai-devsecops-nginx-1 wget -qO- http://backend:8080/api/v1/health 2>&1 | head -5
echo ""
echo "--- TEST LOGIN ---"
curl -sIk -X POST https://app.iqbalhidayatrasyad.blog/api/v1/auth/login \
    -H "Content-Type: application/json" -d '{}' 2>&1 | head -5
