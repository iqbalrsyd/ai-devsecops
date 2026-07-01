#!/bin/bash
set -e

# Sync OpenCode API key + ensure correct model + verify LLM call

cd /opt/ai-devsecops

KEY_NAME="${KEY_NAME:-OPENCODE_API_KEY}"
NEW_KEY="${1:-}"

# If no key provided, read from .env
if [ -z "$NEW_KEY" ]; then
    if [ -f /opt/ai-devsecops/.env ]; then
        NEW_KEY=$(grep "^${KEY_NAME}=" /opt/ai-devsecops/.env | cut -d= -f2-)
    fi
    if [ -z "$NEW_KEY" ] || [ "$NEW_KEY" = "sk" ]; then
        echo "ERROR: No valid key in .env"
        echo "Usage: bash $0 <API_KEY>"
        echo "  Get key from: https://opencode.ai"
        exit 1
    fi
fi

# Validate key length
if [ ${#NEW_KEY} -lt 30 ]; then
    echo "WARNING: Key length only ${#NEW_KEY} chars (expected 50+)"
    echo "  Key: ${NEW_KEY:0:10}..."
    echo "  This may be a placeholder"
fi

echo "=== Sync $KEY_NAME + fix model ==="

# 1. Backup
cp .env .env.bak.$(date +%Y%m%d_%H%M%S)
echo "[1/6] Backed up .env"

# 2. Update or append OPENCODE_API_KEY
if grep -q "^${KEY_NAME}=" .env; then
    sed -i "s|^${KEY_NAME}=.*|${KEY_NAME}=${NEW_KEY}|" .env
    echo "[2/6] Updated $KEY_NAME"
else
    echo "${KEY_NAME}=${NEW_KEY}" >> .env
    echo "[2/6] Appended $KEY_NAME"
fi

# 3. Set LLM_PROVIDER=opencode
sed -i 's|^LLM_PROVIDER=.*|LLM_PROVIDER=opencode|' .env
if ! grep -q "^LLM_PROVIDER=" .env; then
    echo "LLM_PROVIDER=opencode" >> .env
fi
echo "[3/6] LLM_PROVIDER=opencode"

# 4. Set LLM_MODEL=minimax-m3 (the only known-working model for this OpenCode key)
sed -i 's|^LLM_MODEL=.*|LLM_MODEL=minimax-m3|' .env
if ! grep -q "^LLM_MODEL=" .env; then
    echo "LLM_MODEL=minimax-m3" >> .env
fi
echo "[4/6] LLM_MODEL=minimax-m3 (set to known-working model)"

# 5. Force recreate ai-service
echo "[5/6] Force recreate ai-service..."
docker compose -f docker-compose.prod.yml up -d --force-recreate --no-deps ai-service
sleep 10

# 6. Verify
echo "[6/6] Verify..."
docker exec ai-devsecops-ai-service-1 python3 -c "
from app.config import settings
key = settings.${KEY_NAME}
print('${KEY_NAME} length:', len(key))
print('${KEY_NAME} first 10:', key[:10])
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
