#!/usr/bin/env bash
# PostToolUse hook: lint test files for quality anti-patterns after Write/Edit.
# Reads Claude Code tool input JSON from stdin, extracts file_path,
# skips non-test files, runs AST linter on test files.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

# Read tool input from stdin
INPUT=$(cat)

# Extract file_path from JSON — try top-level, then nested input
FILE_PATH=$(echo "$INPUT" | jq -r '.file_path // .input.file_path // empty' 2>/dev/null)

if [ -z "$FILE_PATH" ]; then
    exit 0
fi

# Skip non-test files (handle both absolute and relative paths)
case "$FILE_PATH" in
    */tests/*/test_*.py | tests/*/test_*.py) ;;
    *) exit 0 ;;
esac

# Run the AST linter
exec python "$REPO_ROOT/scripts/dev/lint_test_quality.py" "$FILE_PATH"
