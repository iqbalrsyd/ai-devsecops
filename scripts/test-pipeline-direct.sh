#!/bin/bash
# Direct pipeline test - bypass debug-pipeline-v2.sh
# This calls the AI service /pipeline/generate with proper network access

set -e

cd /opt/ai-devsecops

echo "=== Direct Pipeline Test ==="

# 1. Get current log line count
LOG_BEFORE=$(docker logs ai-devsecops-ai-service-1 --tail=0 2>&1 | wc -l)
echo "Log lines before: $LOG_BEFORE"

# 2. Call pipeline/generate (timeout 60s)
echo ""
echo "[1/4] Calling POST /pipeline/generate on ai-service (timeout 60s)..."
RESP=$(docker run --rm --network ai-devsecops_appnet curlimages/curl:latest \
    --max-time 60 \
    -s -X POST http://ai-service:8000/pipeline/generate \
    -H "Content-Type: application/json" \
    -d '{"repository_full_name":"octocat/Hello-World","github_token":"","query":"basic CI","language":"python","framework":"","deploy_target":"docker","project_type":"api","security_requirements":[]}' 2>&1)

echo "Response (first 500 chars):"
echo "$RESP" | head -c 500
echo ""
echo "..."
echo ""
echo "Response size: $(echo -n "$RESP" | wc -c) bytes"

# 3. Check if it's JSON
echo ""
echo "[2/4] Is response valid JSON?"
if echo "$RESP" | python3 -c "import json,sys; json.loads(sys.stdin.read())" 2>/dev/null; then
    echo "  YES - valid JSON"
    echo "$RESP" | python3 -c "
import json, sys
data = json.loads(sys.stdin.read())
print('Keys:', list(data.keys())[:20])
if 'errors' in data:
    print('Errors:', data['errors'][:3])
if 'status' in data:
    print('Status:', data['status'])
if 'generated_workflow' in data:
    wf = data['generated_workflow']
    print(f'Workflow: {len(wf)} chars, starts with: {wf[:80]!r}')
"
else
    echo "  NO - response is not JSON"
    echo "  Raw: $(echo "$RESP" | head -c 200)"
fi

# 4. Get new log lines
sleep 2
echo ""
echo "[3/4] AI service log (new lines)..."
LOG_AFTER=$(docker logs ai-devsecops-ai-service-1 --tail=0 2>&1 | wc -l)
NEW_LINES=$((LOG_AFTER - LOG_BEFORE))
echo "New log lines: $NEW_LINES"
docker logs ai-devsecops-ai-service-1 --tail=$NEW_LINES 2>&1 | head -50

# 5. Check for stack traces
echo ""
echo "[4/4] Search for errors in log..."
docker logs ai-devsecops-ai-service-1 --tail=200 2>&1 | grep -iE "error|exception|traceback" | head -20
