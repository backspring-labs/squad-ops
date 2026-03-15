#!/usr/bin/env bash
# Creates additional databases and roles needed by SquadOps services.
# Runs before init.sql via docker-entrypoint-initdb.d alphabetical ordering.
# Uses psql directly (no dblink extension required).

set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Keycloak database and role (SIP-0062)
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'keycloak') THEN
            CREATE USER keycloak WITH PASSWORD 'keycloak';
        END IF;
    END
    \$\$;
    CREATE DATABASE keycloak OWNER keycloak;

    -- LangFuse database and role (SIP-0061)
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'langfuse') THEN
            CREATE USER langfuse WITH PASSWORD 'langfuse';
        END IF;
    END
    \$\$;
    CREATE DATABASE langfuse OWNER langfuse;
EOSQL
