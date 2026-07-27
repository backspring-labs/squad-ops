#!/usr/bin/env bash
# Build the canonical sandbox environment image (SIP-0102 phase 102.2).
#
# The tag matches the environment contract's pinned reference
# (src/squadops/sandbox/environment.py) — keep them in lockstep. The publish
# pipeline (registry vs local-only) is open decision 4 in the SIP-0102 plan.
set -euo pipefail
cd "$(dirname "$0")/../.."

TAG="squadops-sandbox-env:fastapi-react-1.4-dev"
docker build -t "$TAG" -f infra/sandbox/fastapi-react.Dockerfile infra/sandbox
echo "Built $TAG"
