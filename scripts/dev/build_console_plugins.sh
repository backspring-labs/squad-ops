#!/usr/bin/env bash
# build_console_plugins.sh — Build all SquadOps Continuum plugin UIs locally.
# Usage: ./scripts/dev/build_console_plugins.sh
#
# Iterates continuum-plugins/squadops.*/ui/ and runs npm ci && npm run build for each.
# Plugin bundles are written to continuum-plugins/squadops.*/dist/plugin.js.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PLUGINS_DIR="${REPO_ROOT}/continuum-plugins"

if [ ! -d "${PLUGINS_DIR}" ]; then
    echo "ERROR: ${PLUGINS_DIR} not found" >&2
    exit 1
fi

built=0
failed=0

for plugin_dir in "${PLUGINS_DIR}"/squadops.*/ui; do
    if [ ! -d "${plugin_dir}" ]; then
        continue
    fi

    plugin_name=$(basename "$(dirname "${plugin_dir}")")
    echo "━━━ Building ${plugin_name} ━━━"

    if [ ! -f "${plugin_dir}/package.json" ]; then
        echo "  SKIP: no package.json"
        continue
    fi

    cd "${plugin_dir}"

    if ! npm ci; then
        echo "  FAILED: npm ci"
        failed=$((failed + 1))
        continue
    fi

    if ! npm run build; then
        echo "  FAILED: npm run build"
        failed=$((failed + 1))
        continue
    fi

    echo "  OK: ${plugin_name}/dist/plugin.js"
    built=$((built + 1))
done

echo ""
echo "Built: ${built}, Failed: ${failed}"

if [ "${failed}" -gt 0 ]; then
    exit 1
fi
