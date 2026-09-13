#!/usr/bin/env bash
# The prose lane: the unit tests a prose-only diff can break, run instead of the whole
# suite when scripts/dev/classify_ci_diff.sh says `code=false`.
#
# Selection is by what a test names, so a new test that reads a plan, a SIP, a site page
# or a root document joins the lane the day it is written: every test file that mentions
# docs/, sips/, site/ or an upper-case root markdown file. That over-selects on purpose — a
# mention in a comment costs seconds; a guard left out lets a broken document merge.
#
# The floor is the ground truth: the test files that actually OPEN prose while the whole
# unit suite runs, traced with an audit hook on 2026-09-13 (#1444's CI follow-up). If the
# selection ever drops one, the lane fails by name instead of passing without it.
#
# Usage: run_prose_lane.sh [--list] [pytest args...]
set -euo pipefail
cd "$(dirname "$0")/../.."

FLOOR=(
  tests/unit/api/test_route_lanes.py
  tests/unit/architecture/test_docs_version_sync.py
  tests/unit/architecture/test_sip_registry_audit.py
  tests/unit/architecture/test_site_sip_links.py
  tests/unit/cycles/test_check_governance.py
  tests/unit/cycles/test_verification_set_driver.py
  tests/unit/maintainer/test_release_notes.py
)

mapfile -t selected < <(
  grep -rlE --include='test_*.py' '"docs"|"sips"|"site"|docs/|sips/|site/|[A-Z]+\.md' tests/unit | sort
)

missing=()
for must in "${FLOOR[@]}"; do
  printf '%s\n' "${selected[@]}" | grep -qxF "$must" || missing+=("$must")
done
if [ "${#missing[@]}" -gt 0 ]; then
  echo "ERROR: the prose lane no longer selects a test that reads prose: ${missing[*]}" >&2
  exit 1
fi

if [ "${1:-}" = "--list" ]; then
  printf '%s\n' "${selected[@]}"
  exit 0
fi

echo "Prose lane: ${#selected[@]} test files (floor of ${#FLOOR[@]} held)"
pytest -n auto "${selected[@]}" "$@"
echo ""
echo "PROSE LANE PASSED"
