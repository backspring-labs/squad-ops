#!/usr/bin/env bash
# Build SIP-0113's evaluator image (A2, #2416): headless Chromium, Lighthouse and axe, which the
# sandbox service's scenario runner launches beside the app it measures.
#
# The tag is read from its one pinned reference (EVALUATOR_IMAGE in
# src/squadops/sandbox/environment.py), so it cannot drift from what the runner launches.
#
# A deploy's sandbox step runs this (#2580): with --if-absent it builds only when the pinned tag
# isn't on the box. Any other argument goes to `docker build` (--no-cache, by hand).
set -euo pipefail
cd "$(dirname "$0")/../.."

IF_ABSENT=false
BUILD_ARGS=()
for arg in "$@"; do
  if [ "$arg" = --if-absent ]; then IF_ABSENT=true; else BUILD_ARGS+=("$arg"); fi
done

PYTHON="${PYTHON:-}"
if [ -z "$PYTHON" ]; then
  if [ -x .venv/bin/python ]; then PYTHON=.venv/bin/python; else PYTHON=python3; fi
fi
# Parsed from the source, never imported: the import chain needs Python 3.10+, and a deploy from a
# checkout with no .venv may only have an older system python3, Apple's 3.9 among them (#2581).
TAG="$("$PYTHON" - <<'PY'
import ast
import sys

tree = ast.parse(open("src/squadops/sandbox/environment.py", encoding="utf-8").read())
for node in tree.body:
    targets = node.targets if isinstance(node, ast.Assign) else [getattr(node, "target", None)]
    if any(getattr(t, "id", None) == "EVALUATOR_IMAGE" for t in targets):
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            print(node.value.value)
            sys.exit(0)
sys.exit("EVALUATOR_IMAGE is not a string literal in src/squadops/sandbox/environment.py")
PY
)"
if [ "$IF_ABSENT" = true ] && docker image inspect "$TAG" >/dev/null 2>&1; then
  echo "$TAG is on the box"
  exit 0
fi
# The empty-array form stays safe under `set -u` on bash 3.2, the Mac's.
docker build ${BUILD_ARGS[@]+"${BUILD_ARGS[@]}"} -t "$TAG" infra/evaluator
echo "Built $TAG"
