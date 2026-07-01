#!/bin/bash
# Debug pipeline generation - more detailed
# Usage: bash scripts/debug-pipeline-v2.sh

set -e

cd /opt/ai-devsecops

echo "=== Debug Pipeline v2 (with proper network access) ==="

# 1. AI service direct (from inside network)
echo ""
echo "[1/8] Test ai-service /pipeline/generate from inside network..."
docker run --rm --network ai-devsecops_appnet curlimages/curl:latest \
    -s -X POST http://ai-service:8000/pipeline/generate \
    -H "Content-Type: application/json" \
    -d '{"repository_full_name":"test/repo","github_token":"","query":"basic CI","language":"python","deploy_target":"docker","project_type":"api","security_requirements":[]}' 2>&1 | head -80

# 2. Backend generate endpoint (from inside)
echo ""
echo "[2/8] Test backend /api/v1/repositories/.../pipelines/generate..."
# Get first repo ID from DB
REPO_ID=$(docker exec ai-devsecops-postgres-1 psql -U postgres -d ai_devsecops -t -c "SELECT id FROM repositories LIMIT 1;" 2>/dev/null | tr -d ' ' | head -1)
echo "Repo ID: $REPO_ID"

# Get a valid JWT token from DB
USER_ID=$(docker exec ai-devsecops-postgres-1 psql -U postgres -d ai_devsecops -t -c "SELECT id FROM users LIMIT 1;" 2>/dev/null | tr -d ' ' | head -1)
echo "User ID: $USER_ID"

# 3. Check if there's a stored JWT
echo ""
echo "[3/8] Database content (truncated)..."
docker exec ai-devsecops-postgres-1 psql -U postgres -d ai_devsecops -c "
SELECT 'repositories' as tbl, COUNT(*) FROM repositories
UNION ALL
SELECT 'pipelines', COUNT(*) FROM pipelines
UNION ALL
SELECT 'users', COUNT(*) FROM users
UNION ALL
SELECT 'insights', COUNT(*) FROM repository_insights;
" 2>&1

# 4. Try to call backend with valid repo + query
echo ""
echo "[4/8] Call backend generate endpoint..."
if [ -n "$REPO_ID" ]; then
    # Get user's stored refresh token (if any) or use first user
    echo "Need JWT for user. Skipping if complex."
    echo "Manual test needed via frontend login."
else
    echo "No repo in DB - need to create one via frontend first"
fi

# 5. AI service full log
echo ""
echo "[5/8] AI service log (full)..."
docker logs ai-devsecops-ai-service-1 --tail=50

# 6. Check if github_service can reach github (when generate is called)
echo ""
echo "[6/8] Test GitHub connectivity from ai-service..."
docker exec ai-devsecops-ai-service-1 python3 -c "
import urllib.request
import urllib.error
try:
    req = urllib.request.Request('https://api.github.com', headers={'User-Agent': 'test'})
    resp = urllib.request.urlopen(req, timeout=10)
    print('GitHub reachable:', resp.status)
except urllib.error.URLError as e:
    print('GitHub UNREACHABLE:', e.reason)
except Exception as e:
    print('GitHub ERROR:', type(e).__name__, str(e)[:200])
" 2>&1

# 7. Test repo_connection node
echo ""
echo "[7/8] Test repository_connection node in isolation..."
docker exec ai-devsecops-ai-service-1 python3 -c "
import asyncio
from app.agents.nodes.repository_connection_node import repository_connection_node

async def test():
    state = {
        'repository_full_name': 'octocat/Hello-World',  # public test repo
        'github_token': '',
        'errors': [],
    }
    result = await repository_connection_node(state)
    print('Status:', result.get('connection_status', 'unknown'))
    print('Errors:', result.get('errors', []))
    print('URL:', result.get('repository_url', 'none'))

asyncio.run(test())
" 2>&1 | head -30

# 8. Full LLM call test with structured output
echo ""
echo "[8/8] Test LLM with structured output (Pydantic schema)..."
docker exec ai-devsecops-ai-service-1 python3 -c "
from pydantic import BaseModel
from app.services.llm_service import analyze_structured

class TestSchema(BaseModel):
    name: str
    value: int

try:
    result = analyze_structured('Reply with name=hello value=42', TestSchema)
    print('Structured result:', result.model_dump())
except Exception as e:
    print('Structured ERROR:', type(e).__name__, str(e)[:300])
" 2>&1 | head -20
