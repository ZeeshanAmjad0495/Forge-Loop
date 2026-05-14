#!/usr/bin/env bash
# ForgeLoop QA gate. Sourceable library + standalone CLI.
#
# Usage as a library:
#   source /tmp/forgeloop_qa_gate.sh
#   forgeloop_qa_gate <dev_task_id> [comment_target_pr_number]
#   # Returns 0 if no blocking+required check failed; 1 otherwise.
#   # Writes a markdown summary to $FL_QA_SUMMARY_FILE (default /tmp/qa_summary.md).
#
# Usage as CLI:
#   /tmp/forgeloop_qa_gate.sh <dev_task_id> [pr_number]
#
# Reads from /tmp/fl_ids: PROJECT_ID, WORKSPACE_ID
# Reads from services/api/.env: AUTH_ADMIN_EMAIL, AUTH_ADMIN_PASSWORD, GITHUB_TOKEN
#
# Every check execution is recorded by ForgeLoop as a check_run; this script
# only orchestrates and summarises.

set -o pipefail

FL_REPO_ROOT="${FL_REPO_ROOT:-/Users/zeeshan.amjad/Documents/ai/incidentpilot}"
FL_API="${FL_API:-http://127.0.0.1:8080}"
FL_QA_SUMMARY_FILE="${FL_QA_SUMMARY_FILE:-/tmp/qa_summary.md}"
FL_GH_OWNER="${FL_GH_OWNER:-ZeeshanAmjad0495}"
FL_GH_REPO="${FL_GH_REPO:-ProbePilot}"

_fl_log(){ echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*"; }

_fl_login(){
  cd "$FL_REPO_ROOT"
  set +u; . services/api/.env; set -u
  . /tmp/fl_ids
  FL_TOKEN=$(curl -sS -X POST "$FL_API/auth/login" -H 'Content-Type: application/json' \
    -d "{\"email\":\"$AUTH_ADMIN_EMAIL\",\"password\":\"$AUTH_ADMIN_PASSWORD\"}" \
    | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
  echo "$FL_TOKEN" > /tmp/fl_token
}

forgeloop_qa_gate(){
  local DT_ID="$1"
  local PR_NUM="${2:-}"
  _fl_login

  local H_AUTH="-H Authorization:Bearer\ $FL_TOKEN"
  curl -sS -H "Authorization: Bearer $FL_TOKEN" \
    "$FL_API/projects/$PROJECT_ID/check-definitions" -o /tmp/qa_defs.json

  python3 - "$FL_TOKEN" "$FL_API" "$DT_ID" "$WORKSPACE_ID" "$FL_QA_SUMMARY_FILE" <<'PY'
import json, os, sys, time, urllib.request

token, api, dt_id, ws_id, summary_path = sys.argv[1:6]
defs = json.load(open('/tmp/qa_defs.json'))
defs = [d for d in defs if d.get('enabled')]
# Run blocking/required first so we fail fast in summary order.
defs.sort(key=lambda d: (0 if (d.get('severity')=='blocking' and d.get('required')) else 1, d.get('name','')))

def post_json(url, body, timeout=600):
    req = urllib.request.Request(url,
        data=json.dumps(body).encode(),
        headers={"Content-Type":"application/json","Authorization":f"Bearer {token}"},
        method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())

results = []
for cd in defs:
    cid = cd['id']; name = cd['name']; sev = cd.get('severity','info'); req = bool(cd.get('required'))
    print(f"  run check: {name} ({sev}/{'required' if req else 'optional'})", flush=True)
    try:
        resp = post_json(
            f"{api}/check-definitions/{cid}/execute",
            {"workspace_id": ws_id, "target_type": "dev_task", "target_id": dt_id, "timeout_seconds": 400},
            timeout=900,
        )
        cr = resp.get('check_run', {})
        co = resp.get('command_run', {}) or {}
        status = cr.get('status'); conclusion = cr.get('conclusion'); summary = cr.get('summary') or ''
        stdout = (co.get('stdout') or '')[-400:]
        stderr = (co.get('stderr') or '')[-400:]
        check_run_id = cr.get('id')
    except Exception as e:
        status, conclusion, summary = 'error', 'failure', str(e)
        stdout = stderr = ''
        check_run_id = None

    results.append({
        'name': name, 'severity': sev, 'required': req,
        'check_definition_id': cid, 'check_run_id': check_run_id,
        'status': status, 'conclusion': conclusion,
        'summary': summary, 'stdout_tail': stdout, 'stderr_tail': stderr,
    })

# Verdict: blocking + required + non-success ⇒ block.
blocking_failed = [r for r in results
                   if r['severity']=='blocking' and r['required'] and r['conclusion']!='success']
warning_failed  = [r for r in results
                   if (r['severity'] != 'blocking' or not r['required']) and r['conclusion']!='success']
passed = [r for r in results if r['conclusion']=='success']

icon = {'success':'✓','failure':'✗','error':'!','timeout':'⏱'}
lines = []
lines.append('## ForgeLoop QA gate')
lines.append('')
lines.append(f"**Verdict: {'BLOCKING FAILURES' if blocking_failed else 'PASS' + (' (with warnings)' if warning_failed else '')}**")
lines.append('')
lines.append('| Check | Severity | Required | Conclusion | check_run_id |')
lines.append('|---|---|---|---|---|')
for r in results:
    mark = icon.get(r['conclusion'],'?')
    lines.append(f"| {r['name']} | {r['severity']} | {'yes' if r['required'] else 'no'} | {mark} {r['conclusion']} | `{r['check_run_id']}` |")
lines.append('')

if blocking_failed:
    lines.append('### Blocking failures')
    for r in blocking_failed:
        tail = (r['stderr_tail'] or r['stdout_tail'] or r['summary'] or '').strip()
        lines.append(f"- **{r['name']}**")
        if tail:
            lines.append('  ```')
            lines.extend('  ' + l for l in tail.splitlines()[-15:])
            lines.append('  ```')
if warning_failed:
    lines.append('### Non-blocking failures (informational)')
    for r in warning_failed:
        tail = (r['stderr_tail'] or r['stdout_tail'] or r['summary'] or '').strip()
        lines.append(f"- {r['name']} ({r['severity']}): {tail.splitlines()[-1] if tail else 'no output'}")

open(summary_path, 'w').write('\n'.join(lines) + '\n')
print('  summary written to', summary_path, flush=True)
sys.exit(1 if blocking_failed else 0)
PY
  local rc=$?
  return $rc
}

# CLI entrypoint
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  DT_ID="${1:-}"
  PR_NUM="${2:-}"
  if [ -z "$DT_ID" ]; then
    echo "usage: $0 <dev_task_id> [pr_number]" >&2
    exit 2
  fi
  forgeloop_qa_gate "$DT_ID" "$PR_NUM"
  rc=$?
  echo
  echo "--- summary ($FL_QA_SUMMARY_FILE) ---"
  cat "$FL_QA_SUMMARY_FILE"
  if [ -n "$PR_NUM" ] && [ -n "${GITHUB_TOKEN:-}" ]; then
    echo
    echo "--- posting summary to PR #$PR_NUM ---"
    python3 - "$GITHUB_TOKEN" "$FL_GH_OWNER" "$FL_GH_REPO" "$PR_NUM" "$FL_QA_SUMMARY_FILE" <<'PY'
import sys, json, urllib.request
token, owner, repo, num, path = sys.argv[1:6]
body = open(path).read()
req = urllib.request.Request(
    f"https://api.github.com/repos/{owner}/{repo}/issues/{num}/comments",
    data=json.dumps({"body": body}).encode(),
    headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "Content-Type":"application/json"},
    method="POST",
)
with urllib.request.urlopen(req, timeout=15) as r:
    d = json.loads(r.read())
    print("comment posted:", d.get("html_url"))
PY
  fi
  exit $rc
fi
