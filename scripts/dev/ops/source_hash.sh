#!/usr/bin/env bash
# The commit a deploy's images are built from, as rebuild_and_deploy.sh passes it (#80).
#
# Prints `git rev-parse --short HEAD`, with `-dirty` appended when anything the images copy
# has uncommitted or untracked changes, and `unknown` outside a git checkout. The runtime-api
# image records the value on every cycle it creates (SQUADOPS_GIT_SHA), so a build from a
# modified tree must not claim the clean commit. Changes outside the copied paths (docs,
# plans, SIPs) do not mark it: they are not in any image.
#
# Run from the repository root.
set -uo pipefail

hash=$(git rev-parse --short HEAD 2>/dev/null) || { echo "unknown"; exit 0; }
if [ -n "$(git status --porcelain -- \
    src adapters agents config examples infra requirements pyproject.toml 2>/dev/null)" ]; then
    hash="${hash}-dirty"
fi
echo "$hash"
