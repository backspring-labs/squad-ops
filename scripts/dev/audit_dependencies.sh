#!/usr/bin/env bash
# Dependency vulnerability audit (#1205): pip-audit against the lock files the images
# actually install — requirements/*.lock, compiled from ci-constraints.txt (#1203) — never
# against the dev venv or ci-constraints.txt itself (the #1041 lesson: audit what ships).
#
# Fails on any advisory not listed in requirements/audit-ignore.txt, where every ignored
# id carries its reason and the issue that retires it. CI runs this same script
# (.github/workflows/ci.yml, `dependency audit`), so the local and the CI answer are one.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

if ! command -v pip-audit >/dev/null 2>&1; then
  echo "ERROR: pip-audit not found — pip install pip-audit (it is in tests/requirements.txt)" >&2
  exit 2
fi

IGNORES=()
while IFS= read -r line; do
  line="${line%%#*}"; line="${line//[[:space:]]/}"
  [ -n "$line" ] && IGNORES+=(--ignore-vuln "$line")
done < requirements/audit-ignore.txt

status=0
for lock in requirements/base.lock requirements/api.lock requirements/agent.lock; do
  echo "== $lock"
  pip-audit -r "$lock" --progress-spinner off "${IGNORES[@]}" || status=1
done
# The evaluator image's npm lock (SIP-0113 A2; #2455): the same rule, its own ignore list.
echo "== infra/evaluator/package-lock.json"
if command -v npm >/dev/null 2>&1; then
  npm_audit=(npm audit --package-lock-only --omit=dev --json)
  report="$(cd infra/evaluator && "${npm_audit[@]}" || true)"
elif command -v docker >/dev/null 2>&1; then
  report="$(docker run --rm -v "$REPO_ROOT/infra/evaluator:/w:ro" -w /w node:20-bookworm-slim \
    npm audit --package-lock-only --omit=dev --json || true)"
else
  echo "ERROR: neither npm nor docker found: the evaluator's npm lock can't be audited" >&2
  exit 2
fi
NPM_AUDIT_REPORT="$report" python3 - infra/evaluator/audit-ignore.txt <<'PY' || status=1
import json, os, sys
ignored = {line.split("#")[0].strip() for line in open(sys.argv[1]) if line.split("#")[0].strip()}
report = json.loads(os.environ["NPM_AUDIT_REPORT"])
found = {
    via["url"].rsplit("/", 1)[-1]: f"{via['name']} ({via['severity']}): {via['title']}"
    for vuln in report.get("vulnerabilities", {}).values()
    for via in vuln.get("via", [])
    if isinstance(via, dict)
}
new = {k: v for k, v in found.items() if k not in ignored}
for advisory, what in sorted(found.items()):
    print(f"{'ACCEPTED' if advisory in ignored else 'NEW     '} {advisory} {what}")
stale = sorted(ignored - set(found))
if stale:
    print(f"no longer reported, so delete from audit-ignore.txt: {stale}")
sys.exit(1 if new or stale else 0)
PY

if [ "$status" -ne 0 ]; then
  echo "dependency audit FAILED: an advisory above is not fixed and not accepted in requirements/audit-ignore.txt or infra/evaluator/audit-ignore.txt" >&2
fi
exit "$status"
