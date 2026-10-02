#!/usr/bin/env bash
# Record what is in service now: one deploy record (#1720).
#
#   ./scripts/dev/ops/record_deploy.sh ["<what is recording>"]
#
# rebuild_and_deploy.sh runs it as its last step. Run it by hand after anything that changes what
# is in service without a deploy, such as `ollama pull` re-pulling a model under the same tag.
#
# The host reads each running service's image and revision label (deploy_facts.py); the runtime
# image's recorder adds the model digests and writes the record through its own port, as a
# one-off container on the runtime's configuration and database: the trust boundary the
# migrations use, with no credential and no route.
#
# source_revision is the checkout a deploy built from, and only a deploy knows it: it is taken
# from SOURCE_HASH when rebuild_and_deploy.sh exported one, and recorded as unknown otherwise.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$REPO_ROOT"

facts=$(python3 "$REPO_ROOT/scripts/dev/ops/deploy_facts.py" "${1:-record_deploy.sh}" "${SOURCE_HASH:-}")
printf '%s' "$facts" | docker compose run --rm --no-deps -T runtime-api \
    python -m squadops.api.runtime.record_deploy
