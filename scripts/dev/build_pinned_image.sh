#!/usr/bin/env bash
# Build one of the sandbox's pinned images by the constant that pins its tag (#2580, #2582):
#
#   build_pinned_image.sh <CONSTANT> <dockerfile> <context> [--if-absent] [docker build args...]
#
# <CONSTANT> names a string literal in src/squadops/sandbox/environment.py (EVALUATOR_IMAGE,
# SANDBOX_ENV_IMAGE), so the tag can't drift from what the runtime launches. With --if-absent it
# builds only when that tag isn't on the box, which is how a deploy's sandbox step calls it; a
# deploy never rebuilds under a tag, since a tag is the image's version (#2581's second read). Any
# other argument goes to `docker build` (--no-cache, by hand).
set -euo pipefail
cd "$(dirname "$0")/../.."

CONSTANT="${1:?the constant that pins the tag}"
DOCKERFILE="${2:?the Dockerfile}"
CONTEXT="${3:?the build context}"
shift 3

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
TAG="$("$PYTHON" - "$CONSTANT" <<'PY'
import ast
import sys

name = sys.argv[1]
tree = ast.parse(open("src/squadops/sandbox/environment.py", encoding="utf-8").read())
for node in tree.body:
    targets = node.targets if isinstance(node, ast.Assign) else [getattr(node, "target", None)]
    if any(getattr(t, "id", None) == name for t in targets):
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            print(node.value.value)
            sys.exit(0)
sys.exit(f"{name} is not a string literal in src/squadops/sandbox/environment.py")
PY
)"
if [ "$IF_ABSENT" = true ] && docker image inspect "$TAG" >/dev/null 2>&1; then
  echo "$TAG is on the box"
  exit 0
fi
# The empty-array form stays safe under `set -u` on bash 3.2, the Mac's.
docker build ${BUILD_ARGS[@]+"${BUILD_ARGS[@]}"} -t "$TAG" -f "$DOCKERFILE" "$CONTEXT"
echo "Built $TAG"
