#!/bin/bash
# Run the regression test suite.
#
# All unit tests that must always pass. Includes a test quality lint
# step that fails on tautological or weak tests.
#
# Usage:
#   ./run_regression_tests.sh           # Run all regression tests
#   ./run_regression_tests.sh -v        # Verbose output
#   ./run_regression_tests.sh --cov     # With coverage

set -euo pipefail

REGRESSION_DIRS=(
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
python "$SCRIPT_DIR/lint_test_quality.py" "${REGRESSION_DIRS[@]}"
echo ""

echo "Running regression tests..."
echo "Directories: ${REGRESSION_DIRS[*]}"
echo ""

# Run pytest with the new arch directories
pytest "${REGRESSION_DIRS[@]}" "$@"
