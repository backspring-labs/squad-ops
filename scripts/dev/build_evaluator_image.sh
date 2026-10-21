#!/usr/bin/env bash
# Build SIP-0113's evaluator image (A2, #2416): headless Chromium, Lighthouse and axe, which the
# sandbox service's scenario runner launches beside the app it measures. Its tag is EVALUATOR_IMAGE
# (src/squadops/sandbox/environment.py); --if-absent and the rest are build_pinned_image.sh's.
set -euo pipefail
exec "$(dirname "$0")/build_pinned_image.sh" EVALUATOR_IMAGE infra/evaluator/Dockerfile infra/evaluator "$@"
