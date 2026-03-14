#!/usr/bin/env bash
# Wrapper that runs init.sql with ON_ERROR_STOP so SQL failures are not silent.
# Mounted into docker-entrypoint-initdb.d/ and runs after 00-create-databases.sh.

set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -f /docker-entrypoint-initdb.d/init.sql
