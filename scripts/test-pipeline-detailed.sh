#!/bin/bash
# Direct test of pipeline generate with full error capture
# Identifies which node fails

set -e

cd /opt/ai-devsecops

echo "=== Pipeline Generate Direct Test ==="

# Get log line count before
LOG_BEFORE=$(docker logs ai-devsecops-ai-service-1 --tail=0 2>&1 | wc -l)

# Call pipeline/generate (long timeout for 18+ LLM calls)
echo ""
echo "[1/4] Calling /pipeline/generate (timeout 300s)..."
RESP=$(docker run --rm --network ai-devsecops_appnet curlimages/curl:latest \
    --max-time 300 \
    -s -X POST http://ai-service:8000/pipeline/generate \
    -H "Content-Type: application/json" \
    -d '{"repository_full_name":"octocat/Hello-World","github_token":"","query":"basic CI","language":"python","framework":"","deploy_target":"docker","project_type":"api","security_requirements":[]}' 2>&1)

echo "Response size: $(echo -n "$RESP" | wc -c) bytes"
echo ""
echo "Response (first 800 chars):"
echo "$RESP" | head -c 800
echo ""
echo "..."

# Parse JSON
echo ""
echo "[2/4] Parse response..."
echo "$RESP" | python3 -c "
import json, sys
try:
    data = json.loads(sys.stdin.read())
    print('  Valid JSON')
    print('  Status:', data.get('status', '?'))
    print('  Errors:', data.get('errors', [])[:3])
    print('  Stages:', len(data.get('generated_stages', [])))
    if 'generated_workflow' in data:
        wf = data['generated_workflow'] or ''
        print(f'  Workflow: {len(wf)} chars')
    if 'node_io' in data:
        print()
        print('  Node I/O trace:')
        for n in data['node_io'][-10:]:
            err = n.get('error', '')
            status = n.get('status', '?')
            print(f\"    [{status:7}] {n.get('node', '?'):30} ({n.get('duration_ms', 0)}ms){' - ERROR: ' + err[:80] if err else ''}\")
except json.JSONDecodeError as e:
    print('  Invalid JSON:', e)
    print('  Raw:', sys.stdin.read()[:500])
except Exception as e:
    print('  Error:', type(e).__name__, e)
" 2>&1

# Show new log lines
echo ""
echo "[3/4] New AI service log lines..."
sleep 3
LOG_AFTER=$(docker logs ai-devsecops-ai-service-1 --tail=0 2>&1 | wc -l)
NEW=$((LOG_AFTER - LOG_BEFORE))
echo "  New log lines: $NEW"
if [ $NEW -gt 0 ]; then
    docker logs ai-devsecops-ai-service-1 --tail=$NEW 2>&1 | head -80
fi

# Search for tracebacks
echo ""
echo "[4/4] Search for errors in full log..."
docker logs ai-devsecops-ai-service-1 --tail=300 2>&1 | grep -iE "error|exception|traceback|failed" | grep -v "GET /api/health" | head -20
