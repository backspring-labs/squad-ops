#!/usr/bin/env bash
# Record what is in service now: one deploy record (#1720).
#
#   ./scripts/dev/ops/record_deploy.sh ["<what is recording>"]
#   ./scripts/dev/ops/record_deploy.sh --check
#
# rebuild_and_deploy.sh runs it as its last step. Run it by hand after anything that changes what
# is in service without a deploy, such as `ollama pull` re-pulling a model under the same tag.
#
# --check writes nothing: it exits 1, naming each service, when the latest record does not
# describe the running images (#2193). verify_loaded.py runs it after every rebuild.
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

# #2354: the record is of the deploy that runs, so every compose call here (deploy_facts.py's
# `compose ps` and the one-off container) is made in the project that runs it, as the runtime
# container's own compose labels name it: its project, its directory and its files. A bare
# `docker compose` takes the project from the current directory's name, so from a worktree it was a
# project nobody deployed: it built a stray runtime image, network and database volume, then
# failed on the worktree's missing secrets with a build log line as its reason. With no runtime
# running there is no deploy to read, and the script says so and builds nothing.
RUNTIME_CONTAINER=squadops-runtime-api
labels=$(docker inspect "$RUNTIME_CONTAINER" --format \
    '{{index .Config.Labels "com.docker.compose.project"}}|{{index .Config.Labels "com.docker.compose.project.working_dir"}}|{{index .Config.Labels "com.docker.compose.project.config_files"}}' \
    2>/dev/null) || labels=""
IFS='|' read -r project project_dir config_files <<<"$labels"
if [ -z "$project" ] || [ -z "$project_dir" ] || [ -z "$config_files" ]; then
    echo "record_deploy.sh: $RUNTIME_CONTAINER is not running under compose, so there is no deploy to read; start the deploy first (#2354)" >&2
    exit 1
fi
cd "$project_dir"
export COMPOSE_PROJECT_NAME="$project"
export COMPOSE_FILE="${config_files//,/:}"

if [ "${1:-}" = "--check" ]; then
    facts=$(python3 "$REPO_ROOT/scripts/dev/ops/deploy_facts.py" "record_deploy.sh --check" "")
    printf '%s' "$facts" | docker compose run --rm --no-deps -T runtime-api \
        python -m squadops.api.runtime.deploy_check
    exit
fi

facts=$(python3 "$REPO_ROOT/scripts/dev/ops/deploy_facts.py" "${1:-record_deploy.sh}" "${SOURCE_HASH:-}")
printf '%s' "$facts" | docker compose run --rm --no-deps -T runtime-api \
    python -m squadops.api.runtime.record_deploy
