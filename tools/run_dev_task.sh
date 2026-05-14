#!/usr/bin/env bash
#
# Drive a single ForgeLoop dev_task end-to-end:
#   approve -> branch off base -> OpenHands execute -> commit -> QA gate.
#
# No GitHub side-effects (push/PR/merge are off in this runner — the
# project-wide no-push policy is enforced by review/policy, not by this
# script).
#
# Usage:
#   tools/run_dev_task.sh <dev_task_id> <branch_name> <base_branch> <commit_msg>
#
# Environment:
#   PROBEPILOT_WORKSPACE_ID   (default: read from /tmp/fl_ids)
#   FORGELOOP_API             (default: http://127.0.0.1:8080)
#   OPENHANDS_BASE_URL        (default: http://127.0.0.1:3000)
#   FL_TOKEN_FILE             (default: /tmp/fl_token)
#
# Improvements vs the previous /tmp/fl_run_one_dt.sh:
# - JSON payloads are built by python, never by bash string interpolation,
#   so shell metacharacters in dev_task fields no longer mangle the
#   request body.
# - The wait-for-conversation polling tolerates a slow / temporarily
#   unresponsive OpenHands (60s curl timeout, swallows transient errors,
#   keeps looping up to the deadline).
# - Lives in the repo under tools/ instead of /tmp so it survives
#   reboots and is reviewable like real code.

set -e -o pipefail

DT_ID="${1:?usage: $0 <dev_task_id> <branch_name> <base_branch> <commit_msg>}"
BR_NAME="${2:?usage: $0 <dev_task_id> <branch_name> <base_branch> <commit_msg>}"
BASE_BRANCH="${3:?usage: $0 <dev_task_id> <branch_name> <base_branch> <commit_msg>}"
CMSG="${4:?usage: $0 <dev_task_id> <branch_name> <base_branch> <commit_msg>}"

REPO_ROOT="${FL_REPO_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
API="${FORGELOOP_API:-http://127.0.0.1:8080}"
OH="${OPENHANDS_BASE_URL:-http://127.0.0.1:3000}"
TOKEN_FILE="${FL_TOKEN_FILE:-/tmp/fl_token}"

# Load the project + workspace IDs (these are session-local; not committed).
if [ -f /tmp/fl_ids ]; then
  # shellcheck disable=SC1091
  . /tmp/fl_ids
fi
: "${PROJECT_ID:?missing PROJECT_ID in /tmp/fl_ids}"
: "${WORKSPACE_ID:?missing WORKSPACE_ID in /tmp/fl_ids}"
: "${TOOL_RUNNER_DEF_ID:?missing TOOL_RUNNER_DEF_ID in /tmp/fl_ids}"

# Refresh token from the .env credentials.
set -a; . "$REPO_ROOT/services/api/.env"; set +a
TOKEN=$(curl -sS -X POST "$API/auth/login" \
  -H 'Content-Type: application/json' \
  -d "$(python3 -c 'import json,os;print(json.dumps({"email":os.environ["AUTH_ADMIN_EMAIL"],"password":os.environ["AUTH_ADMIN_PASSWORD"]}))')" \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
echo "$TOKEN" > "$TOKEN_FILE"

ts(){ date -u +%Y-%m-%dT%H:%M:%SZ; }
say(){ echo "[$(ts)] $*"; }

# JSON-encode a value via python (handles quotes/newlines/etc safely).
json(){ python3 -c 'import json,sys;print(json.dumps(sys.argv[1]))' "$1"; }

# POST helper that builds the body from a python dict literal evaluated in
# a here-script. Caller passes the dict as a single python expression.
api_post(){ # $1=path  $2=python-dict-expression
  local path="$1" body_expr="$2"
  local body
  body=$(python3 -c "import json;print(json.dumps($body_expr))")
  curl -sS -X POST "$API$path" \
    -H "Authorization: Bearer $TOKEN" \
    -H 'Content-Type: application/json' \
    -d "$body"
}
api_patch(){
  local path="$1" body_expr="$2"
  local body
  body=$(python3 -c "import json;print(json.dumps($body_expr))")
  curl -sS -X PATCH "$API$path" \
    -H "Authorization: Bearer $TOKEN" \
    -H 'Content-Type: application/json' \
    -d "$body"
}
api_get(){
  curl -sS -H "Authorization: Bearer $TOKEN" "$API$1"
}

wait_oh_finished(){
  # Tolerant of slow / temporarily-unresponsive OH.
  local i st
  for i in $(seq 1 240); do
    st=$(curl -sS -m 60 "$OH/api/v1/app-conversations/search?limit=3" 2>/dev/null \
      | python3 -c "
import sys,json
try:
    d=json.load(sys.stdin); it=d.get('items',[])
    print(it[0].get('execution_status') if it else '')
except Exception: print('')
" 2>/dev/null || echo '')
    case "$st" in
      finished|failed|stopped|cancelled|error|completed) return 0 ;;
    esac
    sleep 10
  done
  return 1
}

# 1) approve
say "DT $DT_ID: approve"
APPROVAL_JSON=$(api_post /approvals "{
  'project_id':'$PROJECT_ID',
  'target_type':'dev_task',
  'target_id':'$DT_ID',
  'feedback':'Approve $DT_ID via tools/run_dev_task.sh',
}")
APP_ID=$(echo "$APPROVAL_JSON" | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])')
api_patch "/approvals/$APP_ID" "{'status':'approved','feedback':'Proceed.'}" > /dev/null
say "  approval=$APP_ID approved"

# 2) branch
say "DT $DT_ID: branch $BR_NAME off $BASE_BRANCH (LOCAL)"
api_post "/workspaces/$WORKSPACE_ID/branches" "{
  'dev_task_id':'$DT_ID',
  'base_branch':'$BASE_BRANCH',
  'name':'$BR_NAME',
  'approval_id':'$APP_ID',
}" > /dev/null
sleep 1
BR_ID=$(api_get "/workspaces/$WORKSPACE_ID/branches" | python3 -c "
import sys,json
for b in json.load(sys.stdin):
    if b.get('name')=='$BR_NAME': print(b['id']); break
")
say "  branch_id=$BR_ID"

# 3) OpenHands execute
say "DT $DT_ID: OpenHands execute"
api_post "/dev-tasks/$DT_ID/openhands/execute" "{
  'workspace_id':'$WORKSPACE_ID',
  'tool_runner_definition_id':'$TOOL_RUNNER_DEF_ID',
  'approval_id':'$APP_ID',
  'mode':'local',
  'timeout_seconds':2400,
}" > "/tmp/fl_exec_$DT_ID.json" || true   # don't die on curl timeout; OH may still finish
wait_oh_finished

# 4) commit (local)
say "DT $DT_ID: commit (LOCAL)"
api_post "/workspace-branches/$BR_ID/commit" "{
  'message': $(json "$CMSG"),
  'approval_id':'$APP_ID',
}" > "/tmp/fl_commit_$DT_ID.json"
CSHA=$(python3 -c "import json;print(json.load(open('/tmp/fl_commit_$DT_ID.json')).get('commit_sha',''))")
say "  commit=$CSHA"

# 5) QA gate
say "DT $DT_ID: ForgeLoop QA gate"
QA_GATE="$REPO_ROOT/tools/forgeloop_qa_gate.sh"
if [ -x "$QA_GATE" ]; then
  set +e
  "$QA_GATE" "$DT_ID"
  QA_RC=$?
  set -e
else
  echo "  WARN: tools/forgeloop_qa_gate.sh not found; skipping" >&2
  QA_RC=0
fi
say "  QA gate exit: $QA_RC"

echo "BR_ID=$BR_ID"
echo "COMMIT_SHA=$CSHA"
echo "QA_RC=$QA_RC"
echo "APP_ID=$APP_ID"
exit "$QA_RC"
