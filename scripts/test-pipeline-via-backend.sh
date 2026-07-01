#!/bin/bash
# Test pipeline via backend (full flow like frontend does)

set -e

cd /opt/ai-devsecops

# Config
GITHUB_TOKEN="${GITHUB_TOKEN:-}"
if [ -z "$GITHUB_TOKEN" ]; then
    GITHUB_TOKEN=$(grep "^GITHUB_TOKEN=" .env | cut -d= -f2-)
fi

# Get user email from DB
USER_EMAIL=$(docker exec ai-devsecops-postgres-1 psql -U postgres -d ai_devsecops -t -c "SELECT email FROM users LIMIT 1;" 2>/dev/null | tr -d ' ' | head -1)
if [ -z "$USER_EMAIL" ]; then
    echo "ERROR: No user in DB. Register a user via webapp first."
    exit 1
fi
echo "Test user: $USER_EMAIL"

# Reset password using python (crypt() may not be in alpine postgres)
# Use a Go-compatible bcrypt hash
NEW_HASH=$(python3 -c "
import bcrypt
print(bcrypt.hashpw(b'TestPass123!', bcrypt.gensalt(rounds=10)).decode())
" 2>/dev/null || echo "")

if [ -n "$NEW_HASH" ]; then
    docker exec ai-devsecops-postgres-1 psql -U postgres -d ai_devsecops -c "
UPDATE users SET password_hash = '$NEW_HASH' WHERE email = '$USER_EMAIL';" 2>&1 | tail -1
    echo "  Password reset using python bcrypt"
else
    # Fallback: try to use existing password (assume user knows it)
    echo "  WARNING: Could not reset password (bcrypt python not available)"
    echo "  Will use existing password (you need to enter manually)"
    read -s -p "  Enter password for $USER_EMAIL: " USER_PASS
    echo ""
    NEW_HASH=""
fi

# Default password for login attempt
LOGIN_PASS="${USER_PASS:-TestPass123!}"

# Get repo ID from DB
REPO_ID=$(docker exec ai-devsecops-postgres-1 psql -U postgres -d ai_devsecops -t -c "SELECT id FROM repositories LIMIT 1;" 2>/dev/null | tr -d ' ' | head -1)
if [ -z "$REPO_ID" ]; then
    echo "ERROR: No repository in DB. Connect a repo via webapp first."
    exit 1
fi
echo "Test repo: $REPO_ID"

# Login to get JWT
echo ""
echo "[1/5] Login as $USER_EMAIL..."
echo "  (testing nginx -> backend connectivity)..."

# Test 0: RAM check
echo "  RAM available: $(free -m | awk 'NR==2{printf \"%.0f MB\", $7}')"
echo ""

# Test 1: Is nginx listening?
if ! curl -sI --max-time 5 http://localhost 2>&1 | head -1 | grep -q "301\|200\|308"; then
    echo "  ERROR: nginx not responding on http://localhost"
    echo "  Check: docker ps | grep nginx"
    exit 1
fi

# Test 2: Is HTTPS working?
if ! curl -sIk --max-time 5 https://localhost 2>&1 | head -1 | grep -q "200\|301\|308"; then
    echo "  ERROR: nginx not responding on https://localhost"
    echo "  Last 5 nginx log:"
    docker logs ai-devsecops-nginx-1 --tail=5
    exit 1
fi

# Test 2.5: Is backend reachable from nginx container directly? (bypass HTTPS)
echo "  Test: backend reachable from nginx container (direct)?"
DIRECT_RESP=$(docker run --rm --network ai-devsecops_appnet curlimages/curl:latest \
    --max-time 10 -s -X POST http://backend:8080/api/v1/auth/login \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$USER_EMAIL\",\"password\":\"$LOGIN_PASS\"}" 2>&1 | head -c 300)
echo "  Direct (bypass nginx): $DIRECT_RESP"
echo ""

# Test 3: Direct login (HTTPS via nginx)
echo "  Calling POST https://localhost/api/v1/auth/login..."
LOGIN=$(curl -sL --max-time 30 -X POST https://localhost/api/v1/auth/login \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$USER_EMAIL\",\"password\":\"$LOGIN_PASS\"}" 2>&1)
echo "  Raw response (first 200 chars):"
echo "$LOGIN" | head -c 200
echo ""
TOKEN=$(echo "$LOGIN" | python3 -c "import json,sys; print(json.loads(sys.stdin.read()).get('access_token',''))" 2>/dev/null)
if [ -z "$TOKEN" ]; then
    echo "  ERROR: Login failed. Full response:"
    echo "$LOGIN"
    echo ""
    echo "  Backend log:"
    docker logs ai-devsecops-backend-1 --tail=10
    echo ""
    echo "  Nginx log:"
    docker logs ai-devsecops-nginx-1 --tail=5
    exit 1
fi
echo "  Token: ${TOKEN:0:20}..."

# Capture log position
LOG_BEFORE_AI=$(docker logs ai-devsecops-ai-service-1 --tail=0 2>&1 | wc -l)
LOG_BEFORE_BACKEND=$(docker logs ai-devsecops-backend-1 --tail=0 2>&1 | wc -l)

# Trigger pipeline
echo ""
echo "[2/5] Triggering pipeline generation (timeout 300s)..."
RESP=$(curl -s --max-time 300 -X POST \
    "http://localhost/api/v1/repositories/$REPO_ID/pipelines/generate" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{
        "query": "basic CI with security scanning",
        "language": "python",
        "framework": "flask",
        "deploy_target": "docker",
        "project_type": "api",
        "security_requirements": ["sast", "secret-scan", "dependency-scan"]
    }')
echo "  Response size: $(echo -n "$RESP" | wc -c) bytes"
echo "  Response (first 500 chars):"
echo "$RESP" | head -c 500
echo ""

# Parse
echo ""
echo "[3/5] Parse response..."
echo "$RESP" | python3 -c "
import json, sys
try:
    data = json.loads(sys.stdin.read())
    if 'error' in data:
        print('  ERROR:', data['error'])
        sys.exit(1)
    if 'pipeline' in data:
        p = data['pipeline']
        print('  Pipeline ID:', p.get('id', '?')[:8])
        print('  Status:', p.get('status', '?'))
        yaml = p.get('generated_yaml', '') or ''
        print(f'  YAML: {len(yaml)} chars')
        if yaml:
            print('  First 300 chars:', repr(yaml[:300]))
    print('  validation_passed:', data.get('validation_passed'))
    print('  validation_errors:', data.get('validation_errors', []))
    print('  pr_url:', data.get('pr_url'))
except json.JSONDecodeError as e:
    print('  Invalid JSON:', e)
    print('  Raw:', sys.stdin.read()[:500])
" 2>&1

# Get new logs
sleep 3
echo ""
echo "[4/5] New AI service log lines..."
LOG_AFTER_AI=$(docker logs ai-devsecops-ai-service-1 --tail=0 2>&1 | wc -l)
NEW_AI=$((LOG_AFTER_AI - LOG_BEFORE_AI))
echo "  AI service new lines: $NEW_AI"
if [ $NEW_AI -gt 0 ] && [ $NEW_AI -lt 200 ]; then
    docker logs ai-devsecops-ai-service-1 --tail=$NEW_AI 2>&1 | head -80
fi

echo ""
echo "[5/5] Errors in log..."
docker logs ai-devsecops-ai-service-1 --tail=300 2>&1 | grep -iE "error|exception|traceback" | grep -v "GET /api/health" | head -10
docker logs ai-devsecops-backend-1 --tail=200 2>&1 | grep -iE "error|exception|panic" | head -10
