#!/usr/bin/env bash
# Build the canonical sandbox environment image (SIP-0102 phase 102.2), which cycle-create preflight
# requires on the sandbox host. Its tag is SANDBOX_ENV_IMAGE (src/squadops/sandbox/environment.py),
# so it can't drift from what the contracts pin (#1197); --if-absent and the rest are
# build_pinned_image.sh's. The publish pipeline (registry vs local-only) is open decision 4 in the
# SIP-0102 plan.
set -euo pipefail
exec "$(dirname "$0")/build_pinned_image.sh" SANDBOX_ENV_IMAGE infra/sandbox/sandbox-env.Dockerfile infra/sandbox "$@"
