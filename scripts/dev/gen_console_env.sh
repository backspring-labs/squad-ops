#!/usr/bin/env bash
# gen_console_env.sh — Parse console/continuum.lock and generate .env.console for Docker build args.
# Usage: ./scripts/dev/gen_console_env.sh
# Output: .env.console in repo root (loaded by docker-compose.yml)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
LOCK_FILE="${REPO_ROOT}/console/continuum.lock"
ENV_FILE="${REPO_ROOT}/.env.console"

if [ ! -f "${LOCK_FILE}" ]; then
    echo "ERROR: console/continuum.lock not found at ${LOCK_FILE}" >&2
    exit 1
fi

# Parse YAML fields (simple grep/sed — no yq dependency)
# Use [[:space:]]* instead of \s* for macOS sed compatibility
GIT_URL=$(grep 'git_url:' "${LOCK_FILE}" | sed 's/.*git_url:[[:space:]]*//' | tr -d '"' | tr -d "'" | xargs)
REF=$(grep '  ref:' "${LOCK_FILE}" | sed 's/.*ref:[[:space:]]*//' | tr -d '"' | tr -d "'" | xargs)

if [ -z "${GIT_URL}" ] || [ -z "${REF}" ]; then
    echo "ERROR: Could not parse git_url or ref from ${LOCK_FILE}" >&2
    exit 1
fi

cat > "${ENV_FILE}" <<EOF
# Auto-generated from console/continuum.lock — do not edit manually.
# Regenerate: ./scripts/dev/gen_console_env.sh
CONTINUUM_GIT_URL=${GIT_URL}
CONTINUUM_REF=${REF}
EOF

echo "Generated ${ENV_FILE}:"
echo "  CONTINUUM_GIT_URL=${GIT_URL}"
echo "  CONTINUUM_REF=${REF}"
