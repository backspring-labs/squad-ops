#!/bin/bash
# Run the regression test suite.
#
# All unit tests that must always pass. Includes a test quality lint
# step that fails on tautological or weak tests.
#
# #1316: the gated population is the tree, not a list. Until 1.7.3 this script
# enumerated the directories to run, and the list drifted four times (#200, #220,
# #207, #1316 — nine directories and 437 tests ungated at the last count), each
# fix appending to the array and the next new directory missing it. One fact,
# "which tests are gated", had two authors: the array and the filesystem. Now
# pytest and the lint run `tests/unit` whole and EXCLUDED_DIRS names what is
# deliberately left out, each entry with its reason; a new directory is gated
# the day it is created. tests/unit/scripts/test_regression_gate_coverage.py
# guards the shape.
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

# The population the gate runs. Everything under it is gated unless named below.
UNIT_TESTS="tests/unit"

# Directories under tests/unit deliberately NOT gated. Each entry carries its
# reason on the same line; the coverage guard fails an entry without one, an
# entry that no longer exists, and any return to an include list. Empty today:
# nothing under tests/unit is slow, flaky or legacy — the nine directories the
# old list omitted were omitted by drift, not by decision (#1316).
EXCLUDED_DIRS=(
)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Running ruff lint + format check (fail-stop)..."
ruff check .
ruff format --check .
echo ""

echo "Running test quality lint..."
# The lint and pytest read the same exclusions, so a directory left out of the
# suite is left out of the lint too — never one without the other.
# (The ${arr[@]+"${arr[@]}"} form is for bash 3.2 under set -u, where an empty
# array expanded as "${arr[@]}" is an unbound-variable error — the dev-mac shell.)
LINT_EXCLUDES=()
PYTEST_IGNORES=()
for _dir in ${EXCLUDED_DIRS[@]+"${EXCLUDED_DIRS[@]}"}; do
  LINT_EXCLUDES+=("--exclude" "$_dir")
  PYTEST_IGNORES+=("--ignore=$_dir")
done

python "$SCRIPT_DIR/lint_test_quality.py" ${LINT_EXCLUDES[@]+"${LINT_EXCLUDES[@]}"} "$UNIT_TESTS"
echo ""

echo "Running regression tests..."
echo "Population: $UNIT_TESTS (excluded: ${EXCLUDED_DIRS[*]:-none})"
echo ""

# Run pytest across the regression directories.
# #216: -n auto parallelizes across CPU cores (pytest-xdist). The suite is
# isolation-clean under parallel workers (verified ~4460 tests green). Pass
# `-n 0` via "$@" to force serial when debugging a single test.
pytest -n auto ${PYTEST_IGNORES[@]+"${PYTEST_IGNORES[@]}"} "$UNIT_TESTS" "$@"

# #972: positive completion evidence — pipes can mask exit codes at the caller,
# but a MISSING final line is visible in any scrollback. Printed only when every
# gate above actually ran and passed (set -e guarantees we cannot reach here
# otherwise).
echo ""
echo "ALL GATES PASSED (ruff check, ruff format, test-quality lint, pytest)"
