#!/bin/bash
set -e

# Sync OpenCode API key from a known-good source to VPS .env
# and force-restart ai-service + verify LLM call works

cd /opt/ai-devsecops

KEY_NAME="${KEY_NAME:-OPENCODE_API_KEY}"
NEW_KEY="${1:-}"

# If no key provided, read from local .env (if present) or use known-good
if [ -z "$NEW_KEY" ]; then
    if [ -f /opt/ai-devsecops/.env ]; then
        NEW_KEY=$(grep "^${KEY_NAME}=" /opt/ai-devsecops/.env | cut -d= -f2-)
    fi
    if [ -z "$NEW_KEY" ] || [ "$NEW_KEY" = "sk" ]; then
        echo "ERROR: No key provided and no valid key in .env"
        echo ""
        echo "Usage: KEY_NAME=OPENCODE_API_KEY bash $0 <API_KEY>"
        echo "  or:  bash $0 <API_KEY>"
        echo ""
        echo "Get OpenCode key from: https://opencode.ai"
        exit 1
    fi
fi

# Validate key length
if [ ${#NEW_KEY} -lt 30 ]; then
    echo "WARNING: Key length is only ${#NEW_KEY} chars (expected 50+)"
    echo "  Key: ${NEW_KEY:0:10}..."
    echo "  This might be a placeholder, not a real key"
fi

echo "=== Sync $KEY_NAME ==="

# 1. Backup
cp .env .env.bak.$(date +%Y%m%d_%H%M%S)
echo "[1/5] Backed up .env"

# 2. Update or append
if grep -q "^${KEY_NAME}=" .env; then
    sed -i "s|^${KEY_NAME}=.*|${KEY_NAME}=${NEW_KEY}|" .env
    echo "[2/5] Updated existing $KEY_NAME"
else
    echo "${KEY_NAME}=${NEW_KEY}" >> .env
    echo "[2/5] Appended new $KEY_NAME"
fi

# 3. Set related vars to OpenCode provider
echo "[3/5] Setting LLM provider to OpenCode..."
sed -i 's|^LLM_PROVIDER=.*|LLM_PROVIDER=opencode|' .env
if ! grep -q "^LLM_PROVIDER=" .env; then
    echo "LLM_PROVIDER=opencode" >> .env
fi
# Default model
if ! grep -q "^LLM_MODEL=" .env; then
    echo "LLM_MODEL=minimax-m3" >> .env
fi

# 4. Recreate ai-service
echo "[4/5] Force recreate ai-service..."
docker compose -f docker-compose.prod.yml up -d --force-recreate --no-deps ai-service
sleep 10

# 5. Verify
echo "[5/5] Verify key in container..."
docker exec ai-devsecops-ai-service-1 python3 -c "
from app.config import settings
key = settings.${KEY_NAME}
print('${KEY_NAME} length:', len(key))
print('${KEY_NAME} first 10:', key[:10])
print('${KEY_NAME} last 5:', key[-5:])
print('LLM_PROVIDER:', settings.LLM_PROVIDER)
print('LLM_MODEL:', settings.LLM_MODEL)
print('OPENCODE_BASE_URL:', settings.OPENCODE_BASE_URL)

# Real LLM call test
try:
    from app.services.llm_service import get_llm
    llm = get_llm()
    response = llm.invoke('Reply with just the word: WORKING')
    print()
    print('LLM call: SUCCESS')
    print('  Response:', repr(response.content[:100]))
except Exception as e:
    print()
    print('LLM call: FAILED')
    print('  Error:', type(e).__name__, str(e)[:300])
" 2>&1
