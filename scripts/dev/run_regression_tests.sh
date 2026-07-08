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
    "tests/unit/agents/"
    "tests/unit/comms/"
    "tests/unit/capabilities/"
    "tests/unit/cycles/"
    "tests/unit/events/"
    "tests/unit/cli/"
    "tests/unit/console/"
    "tests/unit/contracts/"
    "tests/unit/runtime/"        # SIP-0089 runtime modes/assignments/scheduler (#220)
    "tests/unit/architecture/"   # D26 forbidden-imports + future architecture guards (#220)
    "tests/unit/adapters/"       # mocked adapter unit tests (a2a, persistence, queue, chat) (#207)
    "tests/unit/scripts/"        # dev/ops script helpers (derive_binding, #327)
)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Running ruff lint + format check (fail-stop)..."
ruff check .
ruff format --check .
echo ""

echo "Running test quality lint..."
python "$SCRIPT_DIR/lint_test_quality.py" "${REGRESSION_DIRS[@]}"
echo ""

echo "Running regression tests..."
echo "Directories: ${REGRESSION_DIRS[*]}"
echo ""

# Run pytest across the regression directories.
# #216: -n auto parallelizes across CPU cores (pytest-xdist). The suite is
# isolation-clean under parallel workers (verified ~4460 tests green). Pass
# `-n 0` via "$@" to force serial when debugging a single test.
pytest -n auto "${REGRESSION_DIRS[@]}" "$@"
