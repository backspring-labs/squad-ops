#!/usr/bin/env bash
# The cluster-level objects SquadOps needs: the service roles and databases, and the one
# grant that keeps the integration-test role out of the deployment database (#1180).
#
# Idempotent, because it runs twice over: docker-entrypoint-initdb.d runs it at initdb
# (alphabetically before init.sql) — on a FRESH volume only — and an existing deployment
# gets it from scripts/dev/ops/ensure_test_database.sh, which pipes this file into the
# postgres container on every bootstrap and deploy. Uses psql directly (no dblink).
#
# Environment (the postgres container's): POSTGRES_USER, POSTGRES_DB — the deployment
# database — and POSTGRES_TEST_PASSWORD, the test role's password, which the helper passes
# from .env. Without it the role is not created here and only the grant is applied (it
# needs no password), so a plain `docker compose up` on a fresh volume still closes the
# hole and the bootstrap/deploy path supplies the role. No password is written in here.

set -e

have_test_password=0
if [[ -n "${POSTGRES_TEST_PASSWORD:-}" ]]; then
    have_test_password=1
fi

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
     -v deployment_db="$POSTGRES_DB" \
     -v have_test_password="$have_test_password" \
     -v test_password="${POSTGRES_TEST_PASSWORD:-}" <<-EOSQL
    -- Keycloak database and role (SIP-0062)
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'keycloak') THEN
            CREATE USER keycloak WITH PASSWORD 'keycloak';
        END IF;
    END
    \$\$;
    SELECT 'CREATE DATABASE keycloak OWNER keycloak'
        WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'keycloak')\gexec

    -- LangFuse database and role (SIP-0061)
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'langfuse') THEN
            CREATE USER langfuse WITH PASSWORD 'langfuse';
        END IF;
    END
    \$\$;
    SELECT 'CREATE DATABASE langfuse OWNER langfuse'
        WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'langfuse')\gexec

    -- Integration-test isolation (#1180).
    -- Postgres grants CONNECT on every new database to PUBLIC, so any role with LOGIN can
    -- reach the deployment database — that default is the hole, and revoking it from
    -- PUBLIC is what makes the test role's refusal a server decision. The database owner
    -- and superusers are unaffected, and every SquadOps service connects as the owner.
    -- (Revoking from squadops_test by name would be a no-op: a privilege held only via
    -- PUBLIC is not held by the role, so there is nothing to revoke from it.)
    REVOKE CONNECT ON DATABASE :"deployment_db" FROM PUBLIC;

    \if :have_test_password
        -- The role: create if missing, then set the password every run so .env is the truth.
        SELECT format('CREATE ROLE squadops_test LOGIN PASSWORD %L', :'test_password')
            WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'squadops_test')\gexec
        SELECT format('ALTER ROLE squadops_test PASSWORD %L', :'test_password')\gexec

        -- The database: create it owned by the role, or hand an existing one over (the
        -- #1099 conftest created it owned by squadops). A database's owner owns its
        -- public schema (PG15), which the migrations the suite applies need.
        SELECT 'CREATE DATABASE squadops_test OWNER squadops_test'
            WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'squadops_test')\gexec
        SELECT 'ALTER DATABASE squadops_test OWNER TO squadops_test'
            FROM pg_database
            WHERE datname = 'squadops_test' AND pg_get_userbyid(datdba) <> 'squadops_test'\gexec

        -- Whatever a previous owner left inside it: TRUNCATE and CREATE TABLE IF NOT
        -- EXISTS need ownership, so the tables (indexes and constraints follow) and any
        -- sequences or views go to the role as well.
        \c squadops_test
        DO \$\$
        DECLARE r record;
        BEGIN
            FOR r IN
                SELECT c.relkind, c.relname
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public'
                  AND c.relkind IN ('r', 'p', 'S', 'v', 'm')
                  AND pg_get_userbyid(c.relowner) <> 'squadops_test'
            LOOP
                EXECUTE format(
                    'ALTER %s public.%I OWNER TO squadops_test',
                    CASE r.relkind
                        WHEN 'S' THEN 'SEQUENCE'
                        WHEN 'v' THEN 'VIEW'
                        WHEN 'm' THEN 'MATERIALIZED VIEW'
                        ELSE 'TABLE'
                    END,
                    r.relname
                );
            END LOOP;
        END
        \$\$;
    \else
        \echo 'POSTGRES_TEST_PASSWORD not set: squadops_test role not created here — the bootstrap/deploy path supplies it (scripts/dev/ops/ensure_test_database.sh)'
    \endif
EOSQL
