#!/usr/bin/env bash
# Build the canonical sandbox environment image (SIP-0102 phase 102.2).
#
# The tag is read from the environment contract's one pinned reference
# (SANDBOX_ENV_IMAGE in src/squadops/sandbox/environment.py) so it cannot drift from
# what the contracts pin (#1197). The publish pipeline (registry vs local-only) is open
# decision 4 in the SIP-0102 plan.
set -euo pipefail
cd "$(dirname "$0")/../.."

PYTHON="${PYTHON:-}"
if [ -z "$PYTHON" ]; then
  if [ -x .venv/bin/python ]; then PYTHON=.venv/bin/python; else PYTHON=python3; fi
fi
TAG="$(PYTHONPATH=src "$PYTHON" -c 'from squadops.sandbox.environment import SANDBOX_ENV_IMAGE; print(SANDBOX_ENV_IMAGE)')"
docker build -t "$TAG" -f infra/sandbox/sandbox-env.Dockerfile infra/sandbox
echo "Built $TAG"
