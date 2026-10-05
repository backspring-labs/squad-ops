#!/usr/bin/env bash
# Shared credential provisioning.
#
# Sourced (never executed) by both the bootstrap path
# (scripts/bootstrap/lib/docker_setup.sh) and the rebuild/deploy path
# (scripts/dev/ops/rebuild_and_deploy.sh). Before #371 only bootstrap created
# the agent client secret, so "git pull && rebuild_and_deploy.sh" on an
# already-bootstrapped box left agents unable to start. One function for both
# paths keeps them from drifting.
#
# #2006: every credential is the deploy's own. infra/deploy_credentials.json names
# them, .env holds each one, and the secrets/ files are derived from .env. A new
# deploy generates each value; one that predates #2006 adopts the value it already
# runs with (rotating it is docs/ops/credential_rotation.md). This used to write the
# committed "squadops-agent-secret" into secrets/agent_client_secret.txt, the same
# on every deploy.

_OPS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_REPO_DIR="$(cd "$_OPS_DIR/../../.." && pwd)"
_DEPLOY_CREDENTIALS_PY="$_OPS_DIR/deploy_credentials.py"

# Give .env every credential and derive secrets/ from it, before any `docker compose`
# call: compose refuses to resolve without them. DRY_RUN=1 prints what it would do.
ensure_deploy_credentials() {
    local args=(ensure)
    [[ "${DRY_RUN:-0}" == "1" ]] && args+=(--dry-run)
    python3 "$_DEPLOY_CREDENTIALS_PY" "${args[@]}"
}

# Re-sync the realm exports into Keycloak (#372) and set each client's secret from .env
# (#2006), once Keycloak is healthy. Both paths need it: a realm the export just created
# holds the export's seed secret until this runs, and the agents present the deploy's own.
sync_keycloak_realms() {
    if [[ "${DRY_RUN:-0}" == "1" ]]; then
        echo "[dry-run] keycloak realm sync and client secrets from .env"
        return 0
    fi
    (cd "$_REPO_DIR" && docker compose up -d --wait squadops-keycloak) && \
        python3 "$_OPS_DIR/keycloak_realm_sync.py" \
            --password-file "$_REPO_DIR/secrets/keycloak_admin_password.txt" \
            "$_REPO_DIR/infra/auth/squadops-realm.json" "$_REPO_DIR/infra/auth/squadops-realm-local.json"
}
