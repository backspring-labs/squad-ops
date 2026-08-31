#!/bin/bash
# Regenerate pinned lock files from requirements/*.txt using pip-compile.
#
# Compiled AGAINST ci-constraints.txt (#1041). Every package CI also pins resolves to
# CI's exact version, so the deployed set is a subset of the tested set by construction —
# the locks cannot drift from CI again without this constraint being removed. Before it,
# 42 packages disagreed, including numpy 1.26 vs 2.4 and lancedb 0.8 vs 0.33, and CI's
# greens said nothing about the versions the images installed.
#
# Run with Python 3.12 — the version the images and CI both use (#237). The previous
# locks were compiled with 3.11 and their headers say so.
#
# `--upgrade` is deliberate. Without it pip-compile treats the EXISTING lock as a
# preference and keeps any pin that still satisfies the constraint, which is how the two
# locks drifted from each other while both looked freshly compiled: api.lock sat on
# langfuse 2.36.2 and packaging 23.2 while agent.lock had 2.60.10 and 24.2, and a
# regeneration left both exactly where they were. Nothing blocked the newer client —
# forcing it resolved cleanly. The constraint pins every shared package anyway, so
# `--upgrade` only moves what CI does not pin.
#
# Run this when:
#   - Adding or updating a direct dependency in requirements/*.txt
#   - Periodic security refresh (monthly or on advisory)
#
# Prerequisites:
#   pip install pip-tools
#
# Usage:
#   ./scripts/maintainer/update_deps.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../" && pwd)"
cd "$REPO_ROOT"

# Documented exceptions are filtered OUT of the constraint rather than the constraint
# being abandoned: pip-compile fails hard on an unsatisfiable constraint, so one
# irreducible package would otherwise cost the reconciliation of all the others.
# requirements/constraint-exceptions.txt carries the reason for each, and the drift test
# reads the same file, so an undocumented divergence cannot pass.
EXCEPTIONS="$(grep -vE '^\s*(#|$)' requirements/constraint-exceptions.txt | tr -d ' ')"
CONSTRAINTS="$(mktemp)"
trap 'rm -f "$CONSTRAINTS"' EXIT
if [ -n "$EXCEPTIONS" ]; then
  grep -viE "^($(echo "$EXCEPTIONS" | paste -sd'|'))==" ci-constraints.txt > "$CONSTRAINTS"
  echo "Excluded from the constraint (see requirements/constraint-exceptions.txt):"
  echo "$EXCEPTIONS" | sed 's/^/  /'
else
  cp ci-constraints.txt "$CONSTRAINTS"
fi

echo "Compiling requirements/base.lock ..."
pip-compile requirements/base.txt -o requirements/base.lock \
  -c "$CONSTRAINTS" --upgrade --strip-extras --quiet

echo "Compiling requirements/api.lock ..."
pip-compile requirements/api.txt -o requirements/api.lock \
  -c "$CONSTRAINTS" --upgrade --strip-extras --quiet

echo "Compiling requirements/agent.lock ..."
pip-compile requirements/agent.txt -o requirements/agent.lock \
  -c "$CONSTRAINTS" --upgrade --strip-extras --quiet

echo "Done. Review the diffs and commit the updated lock files."
