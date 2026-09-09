"""The integration suite's role is refused by the deployment database — at the server (#1180).

#1099's session guard refuses a DSN that NAMES the deployment database. This asserts the
layer under it: the role the suite connects as cannot reach ``squadops`` even when asked
to, because ``REVOKE CONNECT ON DATABASE squadops FROM PUBLIC`` is in place and the role
holds no grant of its own. A guard is a program that can be wrong; a grant is enforced
by Postgres. The same credentials connecting to the test database first is the paired
control — without it, "refused" could be a role that does not exist.

Skips when nothing answers on the DSN's host:port (a laptop with no stack up); in CI,
``SQUADOPS_REQUIRE_SERVICES=1`` turns that into a failure, and the job provisions the
role with the deploy-path helper before the suite runs, so the grant is proven on every
push. A reachable server that refuses the role for any reason OTHER than the grant —
role missing, wrong password — fails: that is what the provisioning owes, not a skip.
"""

from __future__ import annotations

import socket
from urllib.parse import urlsplit

import asyncpg
import pytest

from squadops.bootstrap.database_isolation import (
    DEPLOYMENT_DB_NAME,
    SQLSTATE_INSUFFICIENT_PRIVILEGE,
    with_database,
)
from tests.integration.conftest import _missing_service, integration_postgres_dsn

pytestmark = [pytest.mark.database, pytest.mark.docker]


def _reachable(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=2):
            return True
    except OSError:
        return False


async def test_suite_role_is_refused_by_the_deployment_database():
    dsn = integration_postgres_dsn()  # never names the deployment DB (#1099)
    parts = urlsplit(dsn)
    host, port, role = parts.hostname or "localhost", parts.port or 5432, parts.username
    if not _reachable(host, port):
        _missing_service(f"Postgres not reachable on {host}:{port}")

    # Paired control: the same credentials are accepted by the suite's own database.
    try:
        own = await asyncpg.connect(dsn, timeout=5)
    except asyncpg.PostgresError as exc:
        pytest.fail(
            f"the suite's role {role!r} cannot connect to its own database ({exc.sqlstate}: "
            f"{exc}) — the role is not provisioned; bootstrap and rebuild_and_deploy.sh run "
            f"scripts/dev/ops/ensure_test_database.sh (#1180)"
        )
    await own.close()

    # The negative: the deployment database refuses the role, with the permission error.
    try:
        live = await asyncpg.connect(with_database(dsn, DEPLOYMENT_DB_NAME), timeout=5)
    except asyncpg.InsufficientPrivilegeError as exc:
        assert exc.sqlstate == SQLSTATE_INSUFFICIENT_PRIVILEGE
        assert "permission denied for database" in str(exc)
        return
    except asyncpg.PostgresError as exc:
        pytest.fail(
            f"{DEPLOYMENT_DB_NAME!r} refused {role!r} with {exc.sqlstate} ({exc}) — a refusal "
            f"for any reason other than the grant is not isolation"
        )
    await live.close()
    pytest.fail(
        f"the suite's role {role!r} CAN connect to the deployment database "
        f"{DEPLOYMENT_DB_NAME!r}: REVOKE CONNECT ON DATABASE {DEPLOYMENT_DB_NAME} FROM PUBLIC "
        f"is not in place, and these fixtures TRUNCATE cycle tables (#1180, #1099)"
    )
