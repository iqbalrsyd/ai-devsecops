#!/bin/bash
# Debug pipeline generation failure
# Usage: bash scripts/debug-pipeline.sh

set -e

cd /opt/ai-devsecops

echo "=== Debug Pipeline Generation ==="

# 1. Check all services
echo ""
echo "[1/7] All container status..."
docker compose -f docker-compose.prod.yml ps

# 2. Test connectivity ai-service from backend
echo ""
echo "[2/7] Test ai-service reachable from backend..."
docker exec ai-devsecops-backend-1 wget -qO- http://ai-service:8000/api/health 2>&1 | head -5
echo ""

# 3. Test ai-service direct
echo ""
echo "[3/7] Test ai-service direct (from container)..."
docker exec ai-devsecops-ai-service-1 python3 -c "
from app.config import settings
print('LLM_PROVIDER:', repr(settings.LLM_PROVIDER))
print('LLM_MODEL:', repr(settings.LLM_MODEL))
print('OPENCODE_API_KEY set:', bool(settings.OPENCODE_API_KEY))
print('OPENCODE_API_KEY length:', len(settings.OPENCODE_API_KEY))
print('OPENCODE_BASE_URL:', repr(settings.OPENCODE_BASE_URL))
" 2>&1

# 4. Test LLM connection
echo ""
echo "[4/7] Test LLM API call..."
docker exec ai-devsecops-ai-service-1 python3 -c "
from app.services.llm_service import get_llm
try:
    llm = get_llm()
    response = llm.invoke('Reply with just the word: OK')
    print('LLM response:', repr(response.content))
except Exception as e:
    print('LLM ERROR:', type(e).__name__, str(e)[:300])
" 2>&1

# 5. Try pipeline via direct AI service call
echo ""
echo "[5/7] Test pipeline API direct..."
curl -s -X POST http://ai-service:8000/pipeline/generate \
    -H "Content-Type: application/json" \
    -d '{"repository_id":"test/repo","github_token":"","project_id":"","query":"basic CI","language":"python","framework":"","deploy_target":"docker","project_type":"api","security_requirements":[]}' 2>&1 | head -50

# 6. Check ai-service log for any recent errors
echo ""
echo "[6/7] AI service log (last 30 lines)..."
docker logs ai-devsecops-ai-service-1 --tail=30

# 7. Check backend log
echo ""
echo "[7/7] Backend log (last 20 lines)..."
docker logs ai-devsecops-backend-1 --tail=20
