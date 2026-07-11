#!/usr/bin/env bash
# Shared secret-provisioning helpers.
#
# Sourced (never executed) by both the bootstrap path
# (scripts/bootstrap/lib/docker_setup.sh) and the rebuild/deploy path
# (scripts/dev/ops/rebuild_and_deploy.sh). Before #371 only bootstrap created
# the agent client secret, so "git pull && rebuild_and_deploy.sh" on an
# already-bootstrapped box left agents unable to start. Single-sourcing the
# filename and default value here keeps the two paths from drifting.

# squadops-agent Keycloak client secret (#326). docker-compose mounts this file
# into every agent container (SQUADOPS__AUTH__AGENT_CLIENT__CLIENT_SECRET=
# secret://agent_client_secret). The value MUST match the client secret in the
# Keycloak realm export, or agents fail client-credentials auth at startup.
AGENT_CLIENT_SECRET_FILE="secrets/agent_client_secret.txt"
AGENT_CLIENT_SECRET_DEFAULT="squadops-agent-secret"

# Idempotently create the agent client secret file if it is absent.
#   - returns 0 (no output) when the file already exists
#   - returns 0 when it creates the file — the caller prints its own message,
#     so it can match its surrounding logging style (success() vs colored echo)
#   - returns non-zero if the directory or file cannot be created
ensure_agent_client_secret() {
    [[ -f "$AGENT_CLIENT_SECRET_FILE" ]] && return 0
    mkdir -p "$(dirname "$AGENT_CLIENT_SECRET_FILE")" || return 1
    printf '%s' "$AGENT_CLIENT_SECRET_DEFAULT" > "$AGENT_CLIENT_SECRET_FILE"
}
