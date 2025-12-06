#!/bin/bash
# Generic Python Script Runner
# Auto-activates venv and executes any Python script with venv dependencies

set -e

# Get repository root (script is in scripts/dev/, so go up two levels)
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

# Auto-activate virtual environment if it exists and not already activated
if [ -d ".venv" ] && [ -z "$VIRTUAL_ENV" ]; then
    source .venv/bin/activate
fi

# Validate script path provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 <python_script> [args...]"
    echo ""
    echo "Examples:"
    echo "  $0 scripts/dev/generate_sip_uid.py"
    echo "  $0 scripts/maintainer/update_sip_status.py --help"
    exit 1
fi

SCRIPT_ARG="$1"
shift  # Remove script path from arguments

# Resolve script path using realpath for normalization
# This handles relative paths, absolute paths, and resolves symlinks
if [[ "$SCRIPT_ARG" == /* ]]; then
    # Absolute path - normalize it
    SCRIPT_PATH="$(realpath "$SCRIPT_ARG" 2>/dev/null || echo "$SCRIPT_ARG")"
else
    # Relative path - try multiple resolution strategies
    # 1. Try as-is relative to repo root
    if [ -f "$REPO_ROOT/$SCRIPT_ARG" ]; then
        SCRIPT_PATH="$(realpath "$REPO_ROOT/$SCRIPT_ARG")"
    # 2. Try as script name in common directories
    elif [ -f "$REPO_ROOT/scripts/dev/$SCRIPT_ARG" ]; then
        SCRIPT_PATH="$(realpath "$REPO_ROOT/scripts/dev/$SCRIPT_ARG")"
    elif [ -f "$REPO_ROOT/scripts/maintainer/$SCRIPT_ARG" ]; then
        SCRIPT_PATH="$(realpath "$REPO_ROOT/scripts/maintainer/$SCRIPT_ARG")"
    # 3. Try with .py extension if not provided
    elif [ -f "$REPO_ROOT/$SCRIPT_ARG.py" ]; then
        SCRIPT_PATH="$(realpath "$REPO_ROOT/$SCRIPT_ARG.py")"
    elif [ -f "$REPO_ROOT/scripts/dev/$SCRIPT_ARG.py" ]; then
        SCRIPT_PATH="$(realpath "$REPO_ROOT/scripts/dev/$SCRIPT_ARG.py")"
    elif [ -f "$REPO_ROOT/scripts/maintainer/$SCRIPT_ARG.py" ]; then
        SCRIPT_PATH="$(realpath "$REPO_ROOT/scripts/maintainer/$SCRIPT_ARG.py")"
    else
        SCRIPT_PATH="$REPO_ROOT/$SCRIPT_ARG"
    fi
fi

# Validate script exists
if [ ! -f "$SCRIPT_PATH" ]; then
    echo "Error: Script not found: $SCRIPT_ARG"
    echo ""
    echo "Tried:"
    echo "  - $REPO_ROOT/$SCRIPT_ARG"
    echo "  - $REPO_ROOT/scripts/dev/$SCRIPT_ARG"
    echo "  - $REPO_ROOT/scripts/maintainer/$SCRIPT_ARG"
    echo "  - $REPO_ROOT/$SCRIPT_ARG.py"
    echo "  - $REPO_ROOT/scripts/dev/$SCRIPT_ARG.py"
    echo "  - $REPO_ROOT/scripts/maintainer/$SCRIPT_ARG.py"
    exit 1
fi

# Execute the Python script with remaining arguments
# Use 'python' (not 'python3') since venv activation ensures correct interpreter
exec python "$SCRIPT_PATH" "$@"

