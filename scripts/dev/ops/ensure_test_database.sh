#!/usr/bin/env bash
# Make the running Postgres match the repo's cluster-level objects: the integration-test
# role and database, and the grant that keeps the test role out of the deployment
# database (#1180). Idempotent, so it runs on every bootstrap and deploy.
#
# On 2026-08-30 `pytest tests/integration` emptied cycle_gate_decisions because the suite
# connected as `squadops`, the deployment database's owner. The fix is a `squadops_test`
# role that Postgres itself refuses at the deployment database (REVOKE CONNECT ... FROM
# PUBLIC) rather than a guard we have to remember. infra/00-create-databases.sh declares
# that; docker-entrypoint-initdb.d runs it only on a FRESH volume, so an existing
# deployment gets it from here — the shape of the #372 Keycloak realm re-sync. Callers:
#   scripts/bootstrap/bootstrap.sh          a fresh environment, once its services are up
#   scripts/dev/ops/rebuild_and_deploy.sh   the existing deployment, every deploy
#   .github/workflows/ci.yml                the integration job's postgres service container
#
# The test role's password is POSTGRES_TEST_PASSWORD: the environment wins, else .env. The
# keycloak and langfuse roles' passwords (KEYCLOAK_DB_PASSWORD, LANGFUSE_DB_PASSWORD, #2006) are
# read the same way and passed when set, so each deploy sets them from .env. Every one is in .env
# because scripts/dev/ops/deploy_credentials.py ensure runs first on both paths; .env.example
# holds no working value to seed from. No password is written in this file.
#
# Env: CONTAINER (squadops-postgres), DRY_RUN (0)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
CONTAINER="${CONTAINER:-squadops-postgres}"
INIT_SCRIPT="$REPO_ROOT/infra/00-create-databases.sh"
ENV_FILE="$REPO_ROOT/.env"
PASSWORD_VAR="POSTGRES_TEST_PASSWORD"

say() { echo "[ensure_test_database] $*" >&2; }
die() { echo "[ensure_test_database] ERROR: $*" >&2; exit 1; }

# --- 1. The passwords: the environment, else .env ---------------------------------------
from_env_or_dotenv() {
    local name="$1" value="${!1:-}"
    if [[ -z "$value" && -f "$ENV_FILE" ]]; then
        value="$(grep "^${name}=" "$ENV_FILE" | tail -1 | cut -d= -f2- || true)"
    fi
    printf '%s' "$value"
}
password="$(from_env_or_dotenv "$PASSWORD_VAR")"
[[ -n "$password" ]] \
    || die "${PASSWORD_VAR} is not set: run scripts/dev/ops/deploy_credentials.py ensure (#2006)"
role_passwords=()
for name in KEYCLOAK_DB_PASSWORD LANGFUSE_DB_PASSWORD; do
    value="$(from_env_or_dotenv "$name")"
    if [[ -n "$value" ]]; then
        role_passwords+=(-e "${name}=${value}")
    fi
done

if [[ "${DRY_RUN:-0}" == "1" ]]; then
    say "[dry-run] docker exec -i -e ${PASSWORD_VAR}=… $CONTAINER bash -s < $INIT_SCRIPT"
    exit 0
fi

# --- 2. Postgres answering on TCP inside the container ---------------------------------
# initdb's temporary server listens on the unix socket only, so a socket probe (the
# compose healthcheck's pg_isready) can say "ready" while the init scripts are still
# running; TCP comes up only with the real server.
# `docker inspect` takes a name (the box) or an ID (CI's service container) alike.
[[ "$(docker inspect -f '{{.State.Running}}' "$CONTAINER" 2>/dev/null)" == "true" ]] \
    || die "$CONTAINER is not running"
for _ in $(seq 1 30); do
    if docker exec "$CONTAINER" sh -c 'pg_isready -q -h 127.0.0.1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' 2>/dev/null; then
        break
    fi
    sleep 2
done
docker exec "$CONTAINER" sh -c 'pg_isready -q -h 127.0.0.1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
    || die "Postgres in $CONTAINER is not accepting TCP connections after 60s"

# --- 3. The init script, the repo's copy, with the password in its environment ----------
# Piped in rather than run from the compose mount, so the checked-out version runs and
# this does not depend on where docker-compose.yml mounts it.
say "applying $INIT_SCRIPT in $CONTAINER"
docker exec -i -e "${PASSWORD_VAR}=${password}" ${role_passwords[@]+"${role_passwords[@]}"} "$CONTAINER" bash -s < "$INIT_SCRIPT"

# --- 4. What the cluster now says ------------------------------------------------------
docker exec -i "$CONTAINER" sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tA' <<'SQL' \
    | sed 's/^/[ensure_test_database]   /' >&2
SELECT 'role squadops_test: '
       || CASE WHEN EXISTS (SELECT FROM pg_roles WHERE rolname = 'squadops_test')
               THEN 'present' ELSE 'MISSING' END
UNION ALL
SELECT 'database ' || datname || ': owner=' || pg_get_userbyid(datdba)
       || ' acl=' || COALESCE(datacl::text, '<default: PUBLIC may connect>')
FROM pg_database
WHERE datname IN ('squadops', 'squadops_test')
ORDER BY 1;
SQL
say "done"
