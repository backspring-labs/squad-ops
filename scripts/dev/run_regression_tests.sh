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

# --- #972: tool preflight — fail LOUDLY with the likely cause, first thing. ---
# A bare "ruff: command not found" buried mid-scroll reads as noise, and a
# caller piping output (| tail) masks the exit code entirely — at the v1.6.0
# cut that combination produced a green-looking run in which no gate executed.
# One clear line, before anything else runs.
for _tool in ruff pytest python; do
  if ! command -v "$_tool" >/dev/null 2>&1; then
    echo "ERROR: '$_tool' not found — activate the virtualenv first: source .venv/bin/activate" >&2
    exit 127
  fi
done

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
    "tests/unit/sandbox/"      # SIP-0102 execution sandbox domain (102.1)
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

# #972: positive completion evidence — pipes can mask exit codes at the caller,
# but a MISSING final line is visible in any scrollback. Printed only when every
# gate above actually ran and passed (set -e guarantees we cannot reach here
# otherwise).
echo ""
echo "ALL GATES PASSED (ruff check, ruff format, test-quality lint, pytest)"
