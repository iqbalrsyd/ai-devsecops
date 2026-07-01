#!/bin/bash
set -e

cd /opt/ai-devsecops

KEY_NAME="${1:-OPENCODE_API_KEY}"
NEW_KEY="$2"

echo "=== Update API Key: $KEY_NAME ==="

# Detect placeholders / empty values
PLACEHOLDERS=("__FILL_IN" "your-api-key" "changeme" "placeholder" "sk-xxx")

is_placeholder() {
    local val="$1"
    [ -z "$val" ] && return 0
    for p in "${PLACEHOLDERS[@]}"; do
        [[ "$val" == *"$p"* ]] && return 0
    done
    return 1
}

if [ -z "$NEW_KEY" ]; then
    echo ""
    echo "Usage: bash scripts/fix-api-key.sh <KEY_NAME> <NEW_VALUE>"
    echo ""
    echo "Examples:"
    echo "  bash scripts/fix-api-key.sh OPENAI_API_KEY sk-new-openai-key"
    echo "  bash scripts/fix-api-key.sh ANTHROPIC_API_KEY sk-ant-new-key"
    echo "  bash scripts/fix-api-key.sh OPENROUTER_API_KEY sk-or-v1-new-key"
    echo "  bash scripts/fix-api-key.sh OPENCODE_API_KEY sk-new-opencode-key"
    echo ""
    echo "Current API key status:"
    for key in OPENAI_API_KEY ANTHROPIC_API_KEY OPENROUTER_API_KEY OPENCODE_API_KEY; do
        val=$(grep "^${key}=" .env | cut -d= -f2-)
        if is_placeholder "$val"; then
            echo "  $key = <empty/placeholder> ❌"
        else
            echo "  $key = ${val:0:10}...${val: -5} (len=${#val}) ✓"
        fi
    done
    echo ""
    echo "Currently active provider: $(grep "^LLM_PROVIDER=" .env | cut -d= -f2-)"
    echo "Currently active model:    $(grep "^LLM_MODEL=" .env | cut -d= -f2-)"
    echo ""
    exit 0
fi

# 1. Backup
cp .env .env.bak.$(date +%Y%m%d_%H%M%S)
echo "[1/5] Backed up .env to .env.bak.<timestamp>"

# 2. Update or append
if grep -q "^${KEY_NAME}=" .env; then
    sed -i "s|^${KEY_NAME}=.*|${KEY_NAME}=${NEW_KEY}|" .env
    echo "[2/5] Updated existing $KEY_NAME in .env"
else
    echo "${KEY_NAME}=${NEW_KEY}" >> .env
    echo "[2/5] Appended new $KEY_NAME to .env"
fi

# 3. Verify
echo "[3/5] Verifying $KEY_NAME..."
NEW_LEN=$(grep "^${KEY_NAME}=" .env | cut -d= -f2- | wc -c)
echo "  Length: $((NEW_LEN - 1)) chars"
if is_placeholder "$NEW_KEY"; then
    echo "  WARNING: Value looks like placeholder/empty!"
    echo "  Pipeline will fail until real key is set."
fi

# 4. Detect which container consumes this key
echo "[4/5] Determining which service to restart..."
case "$KEY_NAME" in
    OPENAI_API_KEY|ANTHROPIC_API_KEY|OPENROUTER_API_KEY|OPENCODE_API_KEY|GOOGLE_API_KEY|LLM_PROVIDER|LLM_MODEL|LLM_REQUEST_TIMEOUT|GITHUB_TOKEN)
        SERVICE="ai-service"
        ;;
    JWT_SECRET|JWT_ACCESS_DURATION|JWT_REFRESH_DURATION|ENCRYPTION_KEY|CORS_ALLOWED_ORIGINS)
        SERVICE="backend"
        ;;
    *)
        SERVICE="ai-service"
        ;;
esac
echo "  $KEY_NAME consumed by: $SERVICE"

# 5. Restart the appropriate service
echo "[5/5] Force recreate $SERVICE container..."
docker compose -f docker-compose.prod.yml up -d --force-recreate --no-deps "$SERVICE"
sleep 8

echo ""
echo "=== Status ==="
docker compose -f docker-compose.prod.yml ps | grep -E "ai-service|backend"
echo ""
echo "=== AI service log (last 5 lines) ==="
docker logs ai-devsecops-ai-service-1 --tail=5
echo ""
echo "=== Test LLM with new key ==="
docker exec ai-devsecops-ai-service-1 python3 -c "
from app.config import settings
key = settings.${KEY_NAME}
print('${KEY_NAME} length:', len(key))
print('${KEY_NAME} first 10:', key[:10] if key else '<empty>')
print('LLM_PROVIDER:', settings.LLM_PROVIDER)
print('LLM_MODEL:', settings.LLM_MODEL)

# Try a real LLM call
try:
    from app.services.llm_service import get_llm
    llm = get_llm()
    response = llm.invoke('Reply with just the word: OK')
    print('LLM call:', 'SUCCESS' if 'OK' in response.content else 'UNEXPECTED')
    print('  Response:', repr(response.content[:100]))
except Exception as e:
    print('LLM call: FAILED')
    print('  Error:', type(e).__name__, str(e)[:300])
" 2>&1
echo ""
echo "=== Done! ==="
echo "API key $KEY_NAME updated. Test pipeline feature in webapp."
