#!/bin/bash
# Run tests affected by changes
# Usage:
#   ./run_affected_tests.sh           # Staged changes (pre-commit)
#   ./run_affected_tests.sh --staged  # Staged changes explicitly
#   ./run_affected_tests.sh --branch  # All changes vs main (pre-push)
#   ./run_affected_tests.sh --all     # Staged + unstaged (working dir)
#
# Environment:
#   BASE_REF - Base branch for --branch mode (default: origin/main)
#
# Part of SIP-0.8.9 Test Suite Modernization.

set -euo pipefail

MODE="${1:---staged}"
BASE_REF="${BASE_REF:-origin/main}"

case "$MODE" in
    --staged)
        CHANGED_FILES=$(git diff --cached --name-only)
        shift || true  # Consume the mode arg
        ;;
    --branch)
        CHANGED_FILES=$(git diff --name-only "${BASE_REF}...HEAD")
        shift || true
        ;;
    --all)
        CHANGED_FILES=$(git diff --name-only HEAD)
        shift || true
        ;;
    -*)
        # Unknown flag - assume --staged and DON'T shift (pass flag through to pytest)
        MODE="--staged"  # Set for accurate "Mode:" output
        CHANGED_FILES=$(git diff --cached --name-only)
        ;;
    *)
        # No mode specified, default to staged
        MODE="--staged"
        CHANGED_FILES=$(git diff --cached --name-only)
        ;;
esac

if [ -z "$CHANGED_FILES" ]; then
    echo "No changes detected"
    exit 0
fi

echo "Mode: $MODE"
echo "Changed files:"
echo "$CHANGED_FILES" | head -10
if [ $(echo "$CHANGED_FILES" | wc -l) -gt 10 ]; then
    echo "... and $(( $(echo "$CHANGED_FILES" | wc -l) - 10 )) more"
fi
echo ""

# Map changed files to test directories
TEST_DIRS=""

for file in $CHANGED_FILES; do
    case "$file" in
        src/squadops/agents/*)
            TEST_DIRS="$TEST_DIRS tests/unit/agents/ tests/unit/agent_foundation/"
            ;;
        src/squadops/capabilities/*)
            TEST_DIRS="$TEST_DIRS tests/unit/capabilities/"
            ;;
        src/squadops/api/*)
            TEST_DIRS="$TEST_DIRS tests/unit/api/"
            ;;
        src/squadops/ports/memory/*|adapters/memory/*)
            TEST_DIRS="$TEST_DIRS tests/unit/memory/"
            ;;
        src/squadops/config/*)
            TEST_DIRS="$TEST_DIRS tests/unit/config/"
            ;;
        src/squadops/tasks/*)
            TEST_DIRS="$TEST_DIRS tests/unit/tasks/"
            ;;
        src/squadops/llm/*)
            TEST_DIRS="$TEST_DIRS tests/unit/llm/"
            ;;
        src/squadops/telemetry/*)
            TEST_DIRS="$TEST_DIRS tests/unit/telemetry/"
            ;;
        src/squadops/prompts/*)
            TEST_DIRS="$TEST_DIRS tests/unit/prompts/"
            ;;
        src/squadops/tools/*)
            TEST_DIRS="$TEST_DIRS tests/unit/tools/"
            ;;
        src/squadops/embeddings/*)
            TEST_DIRS="$TEST_DIRS tests/unit/embeddings/"
            ;;
        src/squadops/cycles/*|adapters/cycles/*)
            TEST_DIRS="$TEST_DIRS tests/unit/cycles/"
            ;;
        src/squadops/auth/*|adapters/auth/*)
            TEST_DIRS="$TEST_DIRS tests/unit/auth/"
            ;;
        src/squadops/orchestration/*)
            TEST_DIRS="$TEST_DIRS tests/unit/agent_foundation/orchestration/"
            ;;
        src/squadops/cli/*)
            TEST_DIRS="$TEST_DIRS tests/unit/cli/"
            ;;
        src/squadops/contracts/*)
            TEST_DIRS="$TEST_DIRS tests/unit/contracts/"
            ;;
        adapters/*)
            TEST_DIRS="$TEST_DIRS tests/unit/adapters/"
            ;;
        tests/*)
            # Test file changed - run it directly
            if [ -f "$file" ]; then
                TEST_DIRS="$TEST_DIRS $file"
            fi
            ;;
    esac
done

# Deduplicate and sort test directories
TEST_DIRS=$(echo "$TEST_DIRS" | tr ' ' '\n' | sort -u | tr '\n' ' ')

if [ -z "$TEST_DIRS" ]; then
    echo "No matching test directories for changed files"
    echo "Run full unit tests with: pytest tests/unit/ -v"
    exit 0
fi

echo "Running tests for: $TEST_DIRS"
echo ""

# Run pytest with any remaining args passed through
# shellcheck disable=SC2086
pytest $TEST_DIRS "$@" -v
