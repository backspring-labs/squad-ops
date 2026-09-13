"""The isolation contract between the deployment database and the integration-test
database (#1180).

On 2026-08-30 ``pytest tests/integration`` emptied ``cycle_gate_decisions`` (291 rows,
unrecoverable) because the suite connected as ``squadops`` — the deployment database's
owner and, in the compose image, a superuser. #1099 put a guard in the test conftest that
refuses a DSN naming the deployment database. This module names the layer UNDER that
guard, the one Postgres enforces: a dedicated ``squadops_test`` role that owns a
``squadops_test`` database and is refused by the deployment database at the server,
because ``REVOKE CONNECT ON DATABASE squadops FROM PUBLIC`` removed the default grant
that let any LOGIN role reach it.

Three readers share these names so they cannot drift: the doctor check
(``bootstrap/setup/checks.py``), the integration conftest, and the unit test that holds
the shell provisioning (``infra/00-create-databases.sh``, the deploy-path helper, CI) to
the same spelling. The password itself never lives in code: it is
``POSTGRES_TEST_PASSWORD`` in ``.env``, seeded from ``.env.example`` the way
``POSTGRES_PASSWORD`` is.
"""

from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

#: The deployment database — ``POSTGRES_DB`` in docker-compose.yml. Live cycle history
#: lives here; nothing under ``tests/`` may connect to it.
DEPLOYMENT_DB_NAME = "squadops"

#: The role the integration suite connects as. LOGIN, no CREATEDB, no superuser; owner of
#: the test database and nothing else.
TEST_DB_ROLE = "squadops_test"

#: The database the integration suite may destroy at will.
TEST_DB_NAME = "squadops_test"

#: The environment variable (and ``.env`` key) carrying the test role's password.
TEST_DB_PASSWORD_ENV = "POSTGRES_TEST_PASSWORD"

#: SQLSTATE the server answers with when a role may authenticate but not connect to the
#: database it asked for — the one refusal that IS evidence of the grant.
SQLSTATE_INSUFFICIENT_PRIVILEGE = "42501"


def test_role_dsn(
    password: str,
    *,
    host: str = "localhost",
    port: int = 5432,
    database: str = TEST_DB_NAME,
) -> str:
    """A DSN for the test role — the only role a test-side DSN should ever name."""
    return f"postgresql://{TEST_DB_ROLE}:{password}@{host}:{port}/{database}"


def database_name_of(dsn: str) -> str:
    """Database name from a DSN, ignoring any ``?query`` suffix."""
    return dsn.rsplit("/", 1)[-1].split("?", 1)[0]


def with_database(dsn: str, database: str) -> str:
    """The same DSN — same role, password, host and port — pointed at ``database``."""
    parts = urlsplit(dsn)
    return urlunsplit(parts._replace(path=f"/{database}"))
