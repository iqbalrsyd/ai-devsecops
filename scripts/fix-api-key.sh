#!/bin/bash
set -e

cd /opt/ai-devsecops

KEY_NAME="${1:-OPENCODE_API_KEY}"
NEW_KEY="$2"

echo "=== Update API Key: $KEY_NAME ==="

if [ -z "$NEW_KEY" ]; then
    echo ""
    echo "Usage: bash scripts/fix-api-key.sh <KEY_NAME> <NEW_VALUE>"
    echo ""
    echo "Examples:"
    echo "  bash scripts/fix-api-key.sh OPENCODE_API_KEY sk-new-key-here"
    echo "  bash scripts/fix-api-key.sh OPENAI_API_KEY sk-new-openai-key"
    echo "  bash scripts/fix-api-key.sh OPENROUTER_API_KEY sk-or-v1-new-key"
    echo "  bash scripts/fix-api-key.sh ANTHROPIC_API_KEY sk-ant-new-key"
    echo ""
    echo "Current values in .env:"
    grep -E "^(OPENAI|ANTHROPIC|OPENROUTER|OPENCODE)_API_KEY=" .env | sed 's/=.*$/=<hidden>/' || echo "  (no API keys found)"
    exit 0
fi

# 1. Backup
cp .env .env.bak.$(date +%Y%m%d_%H%M%S)
echo "[1/4] Backed up .env to .env.bak.<timestamp>"

# 2. Update or append
if grep -q "^${KEY_NAME}=" .env; then
    sed -i "s|^${KEY_NAME}=.*|${KEY_NAME}=${NEW_KEY}|" .env
    echo "[2/4] Updated existing $KEY_NAME in .env"
else
    echo "${KEY_NAME}=${NEW_KEY}" >> .env
    echo "[2/4] Appended new $KEY_NAME to .env"
fi

# 3. Verify
echo "[3/4] Verifying .env..."
grep "^${KEY_NAME}=" .env | sed 's/=.\{20\}/=<hidden-after-20-chars>/'

# 4. Restart services
echo "[4/4] Restarting services..."
# Restart both backend and ai-service (in case one needs it)
docker compose -f docker-compose.prod.yml up -d --force-recreate --no-deps backend ai-service
sleep 10

echo ""
echo "=== Status ==="
docker compose -f docker-compose.prod.yml ps | grep -E "backend|ai-service"
echo ""
echo "=== Backend log (last 10 lines) ==="
docker logs ai-devsecops-backend-1 --tail=10
echo ""
echo "=== AI service log (last 10 lines) ==="
docker logs ai-devsecops-ai-service-1 --tail=10
echo ""
echo "=== Done! ==="
echo "API key $KEY_NAME updated. Test login or AI feature to verify."
