#!/usr/bin/env bash
# SIP-0062 Phase 3b: CI denylist check
# Fail if any NoOp/noop auth patterns appear in adapters/auth/.
set -euo pipefail

DENYLISTED_PATTERNS="NoOpAuth|noop_auth|NoopAuth"

if grep -rE "$DENYLISTED_PATTERNS" adapters/auth/ 2>/dev/null; then
    echo "ERROR: NoOp auth patterns found in adapters/auth/. This violates SIP-0062."
    exit 1
fi

echo "OK: No NoOp auth patterns found in adapters/auth/."
exit 0
