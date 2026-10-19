#!/usr/bin/env bash
# Build SIP-0113's evaluator image (A2, #2416): headless Chromium, Lighthouse and axe, which the
# sandbox service's scenario runner launches beside the app it measures.
#
# The tag is read from its one pinned reference (EVALUATOR_IMAGE in
# src/squadops/sandbox/environment.py), so it cannot drift from what the runner launches.
set -euo pipefail
cd "$(dirname "$0")/../.."

PYTHON="${PYTHON:-}"
if [ -z "$PYTHON" ]; then
  if [ -x .venv/bin/python ]; then PYTHON=.venv/bin/python; else PYTHON=python3; fi
fi
TAG="$(PYTHONPATH=src "$PYTHON" -c 'from squadops.sandbox.environment import EVALUATOR_IMAGE; print(EVALUATOR_IMAGE)')"
docker build -t "$TAG" infra/evaluator
echo "Built $TAG"
