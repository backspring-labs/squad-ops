#!/bin/bash
# Run new architecture tests only (SIP-0.8.9)
#
# These tests are part of the new hexagonal architecture and don't depend
# on legacy imports. They should always pass.
#
# Usage:
#   ./run_new_arch_tests.sh           # Run all new arch tests
#   ./run_new_arch_tests.sh -v        # Verbose output
#   ./run_new_arch_tests.sh --cov     # With coverage
#
# Part of SIP-0.8.9 Test Suite Modernization.

set -euo pipefail

# New architecture test directories (no legacy imports)
NEW_ARCH_DIRS=(
    "tests/unit/api/"
    "tests/unit/tasks/"
    "tests/unit/llm/"
    "tests/unit/telemetry/"
    "tests/unit/embeddings/"
    "tests/unit/prompts/"
    "tests/unit/tools/"
    "tests/unit/agent_foundation/"
    "tests/unit/capabilities/"
    "tests/unit/cycles/"
    "tests/unit/events/"
    "tests/unit/cli/"
    "tests/unit/console/"
    "tests/unit/contracts/"
)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Running test quality lint..."
python "$SCRIPT_DIR/lint_test_quality.py" "${NEW_ARCH_DIRS[@]}" || echo "⚠ Test quality violations found (non-blocking — fix separately)"
echo ""

echo "Running new architecture tests (SIP-0.8.9)..."
echo "Directories: ${NEW_ARCH_DIRS[*]}"
echo ""

# Run pytest with the new arch directories
pytest "${NEW_ARCH_DIRS[@]}" "$@"
