#!/bin/bash
# Trigger pipeline from backend (full HTTP flow) and capture everything
# This mimics what frontend does when clicking "Generate Pipeline"

set -e

cd /opt/ai-devsecops

echo "=== Full Pipeline Test (from backend) ==="

# Get a valid repo ID from DB
echo "[1/5] Get repo from DB..."
REPO_ID=$(docker exec ai-devsecops-postgres-1 psql -U postgres -d ai_devsecops -t -c "SELECT id FROM repositories LIMIT 1;" 2>/dev/null | tr -d ' ' | head -1)
echo "  Repo ID: '$REPO_ID'"

if [ -z "$REPO_ID" ]; then
    echo ""
    echo "  WARNING: No repo in DB. Test with public repo instead."
    echo "  Need to create a repo first via frontend:"
    echo "  1. Login to https://app.iqbalhidayatrasyad.blog"
    echo "  2. Connect a GitHub repo (any public repo for testing)"
    echo "  3. Then run this script again"
    echo ""
    echo "  OR test AI service direct (bypasses backend):"
    echo "  bash scripts/test-pipeline-direct.sh"
    exit 0
fi

# Get JWT_SECRET from .env
JWT_SECRET=$(grep "^JWT_SECRET=" .env | cut -d= -f2-)
echo "[2/5] JWT secret: ${JWT_SECRET:0:20}..."

# Get user ID
USER_ID=$(docker exec ai-devsecops-postgres-1 psql -U postgres -d ai_devsecops -t -c "SELECT id FROM users LIMIT 1;" 2>/dev/null | tr -d ' ' | head -1)
echo "  User ID: $USER_ID"

# Get user email for login
USER_EMAIL=$(docker exec ai-devsecops-postgres-1 psql -U postgres -d ai_devsecops -t -c "SELECT email FROM users LIMIT 1;" 2>/dev/null | tr -d ' ' | head -1)
echo "  User email: $USER_EMAIL"

# Login to get JWT token
echo "[3/5] Login as $USER_EMAIL..."
LOGIN_RESP=$(curl -s -X POST http://localhost/api/v1/auth/login \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$USER_EMAIL\",\"password\":\"test\"}" 2>&1 | head -c 200)
echo "  Login response: $LOGIN_RESP"

# Reset user password to known value
echo "  Resetting password to 'TestPass123!'..."
docker exec ai-devsecops-postgres-1 psql -U postgres -d ai_devsecops -c "
UPDATE users SET password_hash = crypt('TestPass123!', gen_salt('bf')) WHERE email = '$USER_EMAIL';
" 2>&1 | tail -3

# Login again
LOGIN_RESP=$(curl -s -X POST http://localhost/api/v1/auth/login \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$USER_EMAIL\",\"password\":\"TestPass123!\"}" 2>&1)
TOKEN=$(echo "$LOGIN_RESP" | python3 -c "import json,sys; d=json.loads(sys.stdin.read()); print(d.get('access_token',''))" 2>/dev/null)
echo "  Token: ${TOKEN:0:30}..."

if [ -z "$TOKEN" ]; then
    echo "  ERROR: Login failed. Response:"
    echo "$LOGIN_RESP"
    exit 1
fi

# Capture log before
LOG_BEFORE=$(docker logs ai-devsecops-ai-service-1 --tail=0 2>&1 | wc -l)
LOG_BEFORE_BACKEND=$(docker logs ai-devsecops-backend-1 --tail=0 2>&1 | wc -l)

# Call pipeline generate
echo ""
echo "[4/5] Calling POST /api/v1/repositories/$REPO_ID/pipelines/generate..."
RESP=$(curl -s -X POST "http://localhost/api/v1/repositories/$REPO_ID/pipelines/generate" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{"query":"basic CI","language":"python","framework":"","deploy_target":"docker","project_type":"api","security_requirements":[]}' 2>&1)
echo "  Response (first 500 chars):"
echo "$RESP" | head -c 500
echo ""

# Show new logs
sleep 2
echo ""
echo "[5/5] New AI service log lines..."
LOG_AFTER=$(docker logs ai-devsecops-ai-service-1 --tail=0 2>&1 | wc -l)
NEW=$((LOG_AFTER - LOG_BEFORE))
echo "  AI service new lines: $NEW"
if [ $NEW -gt 0 ] && [ $NEW -lt 100 ]; then
    docker logs ai-devsecops-ai-service-1 --tail=$NEW 2>&1
fi

echo ""
echo "  Backend new lines:"
LOG_AFTER_BACKEND=$(docker logs ai-devsecops-backend-1 --tail=0 2>&1 | wc -l)
NEW_BACKEND=$((LOG_AFTER_BACKEND - LOG_BEFORE_BACKEND))
echo "  Backend new lines: $NEW_BACKEND"
if [ $NEW_BACKEND -gt 0 ] && [ $NEW_BACKEND -lt 50 ]; then
    docker logs ai-devsecops-backend-1 --tail=$NEW_BACKEND 2>&1
fi

# Search for errors
echo ""
echo "=== Recent errors in AI service ==="
docker logs ai-devsecops-ai-service-1 --tail=100 2>&1 | grep -iE "error|exception|traceback" | head -10
echo ""
echo "=== Recent errors in Backend ==="
docker logs ai-devsecops-backend-1 --tail=100 2>&1 | grep -iE "error|exception|fatal" | head -10
