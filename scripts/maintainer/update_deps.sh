#!/bin/bash
# Regenerate pinned lock files from requirements/*.txt using pip-compile.
#
# Run this when:
#   - Adding or updating a direct dependency in requirements/*.txt
#   - Periodic security refresh (monthly or on advisory)
#
# Prerequisites:
#   pip install pip-tools
#
# Usage:
#   ./scripts/maintainer/update_deps.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../" && pwd)"
cd "$REPO_ROOT"

echo "Compiling requirements/base.lock ..."
pip-compile requirements/base.txt -o requirements/base.lock --strip-extras --quiet

echo "Compiling requirements/api.lock ..."
pip-compile requirements/api.txt -o requirements/api.lock --strip-extras --quiet

echo "Compiling requirements/agent.lock ..."
pip-compile requirements/agent.txt -o requirements/agent.lock --strip-extras --quiet

echo "Done. Review the diffs and commit the updated lock files."
