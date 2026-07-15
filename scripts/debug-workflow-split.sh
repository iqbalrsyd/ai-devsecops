#!/bin/bash
# Debug why the 2-file split is not appearing in the FE.
# Shows the key fields from the pipeline response that determine
# whether the custom (2nd) file is generated.

set -e

cd /opt/ai-devsecops 2>/dev/null || cd "$(dirname "$0")/.."

# Reuse the same test setup as test-pipeline-via-backend.sh
GITHUB_TOKEN="${GITHUB_TOKEN:-}"
if [ -z "$GITHUB_TOKEN" ]; then
    GITHUB_TOKEN=$(grep "^GITHUB_TOKEN=" .env 2>/dev/null | cut -d= -f2-)
fi
if [ -z "$GITHUB_TOKEN" ]; then
    echo "ERROR: GITHUB_TOKEN not set and not in .env"
    exit 1
fi

PG_CONTAINER=$(docker ps --format '{{.Names}}' | grep -E 'postgres' | head -1)
USER_EMAIL=$(docker exec "$PG_CONTAINER" psql -U postgres -d ai_devsecops -t -c \
    "SELECT email FROM users LIMIT 1;" 2>/dev/null | tr -d ' ' | head -1)
if [ -z "$USER_EMAIL" ]; then
    echo "ERROR: No user in DB."
    exit 1
fi

NEW_HASH=$(python3 -c "
import bcrypt
print(bcrypt.hashpw(b'TestPass123!', bcrypt.gensalt(rounds=10)).decode())
" 2>/dev/null)

if [ -n "$NEW_HASH" ]; then
    docker exec "$PG_CONTAINER" psql -U postgres -d ai_devsecops -c \
        "UPDATE users SET password_hash='$NEW_HASH' WHERE email='$USER_EMAIL';" >/dev/null
fi

LOGIN=$(curl -sk -X POST http://localhost:8080/api/auth/login \
    -H 'Content-Type: application/json' \
    -d "{\"email\":\"$USER_EMAIL\",\"password\":\"TestPass123!\"}")
TOKEN=$(echo "$LOGIN" | python3 -c "import sys,json;print(json.load(sys.stdin).get('access_token',''))")
if [ -z "$TOKEN" ]; then
    echo "ERROR: login failed. Response: $LOGIN"
    exit 1
fi

# Run the pipeline against the same repo you tested in the UI
# (replace REPO with the full_name you used in the UI)
REPO="${REPO:-iqbalrsyd/ai-devsecops}"
RESP=$(curl -sk -X POST http://localhost:8080/api/pipeline/generate \
    -H "Authorization: Bearer $TOKEN" \
    -H 'Content-Type: application/json' \
    -d "{\"repository_full_name\":\"$REPO\",\"github_token\":\"$GITHUB_TOKEN\"}")

echo "$RESP" | python3 -c "
import sys, json
r = json.load(sys.stdin)
print('=== CVSS-driven jobs node output ===')
print('cvss_driven_jobs_count :', r.get('cvss_driven_jobs_count'))
print('cvss_driven_jobs_reasoning:')
print('  ', (r.get('cvss_driven_jobs_reasoning') or '<empty>')[:400])
print()
print('=== Split output (workflow files) ===')
wf = r.get('workflow_files') or []
print(f'workflow_files count   : {len(wf)}')
for f in wf:
    print(f'  - {f.get(\"name\")} (kind={f.get(\"kind\")}) jobs={f.get(\"jobs\")}')
print()
has_generic = bool(r.get('workflow_yaml_generic'))
has_custom  = bool(r.get('workflow_yaml_custom'))
print(f'workflow_yaml_generic  : {\"present (\" + str(len(r.get(\"workflow_yaml_generic\",\"\"))) + \" chars)\" if has_generic else \"EMPTY\"}')
print(f'workflow_yaml_custom   : {\"present (\" + str(len(r.get(\"workflow_yaml_custom\",\"\"))) + \" chars)\" if has_custom else \"EMPTY\"}')
print()
print('=== Diagnosis ===')
if not wf:
    print('NO workflow_files at all — split builder failed (check ai-service logs).')
elif len(wf) < 2:
    print('Only 1 file in workflow_files — cvss_driven_jobs is empty.')
    print('This means the CVSS node did not produce jobs for this repo.')
    print('Common causes:')
    print('  1. coverage_gap is empty (all applicable coverage already served)')
    print('  2. gap_with_findings is empty (no top CVSS findings in the gap)')
    print('  3. LLM call returned no valid jobs AND deterministic fallback')
    print('     also returned [] (no high-priority coverage matched)')
    print('Next: check ai-service logs:')
    print('  docker compose logs ai-service --tail 200 | grep cvss')
else:
    print('2 files present — split is working. Re-check the FE tab buttons.')
    print('  In the FE, look for two pill buttons: ai-devsecops.yml + ai-devsecops-custom.yml')
"
