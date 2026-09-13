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
if [ "$status" -ne 0 ]; then
  echo "dependency audit FAILED: an advisory above is not fixed and not accepted in requirements/audit-ignore.txt" >&2
fi
exit "$status"
