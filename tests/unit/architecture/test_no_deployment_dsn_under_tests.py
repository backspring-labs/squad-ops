"""No file under ``tests/`` names the deployment database in a connection string (#1182).

On 2026-08-30 ``pytest tests/integration`` emptied ``cycle_gate_decisions`` — 291 rows,
unrecoverable — because a DSN literal in a test module named the deployment database and
connected as its owner, a superuser in the compose image. #1099 shipped the **run-time**
guard (the integration conftest refuses such a DSN) and #1180 put a server-side layer
under it (a ``squadops_test`` role the deployment database refuses at the wire). This is
the **commit-time** one: nothing stops the next module from writing the literal again, and
the failure mode is silent until it destroys data.

Same shape as the architecture guards beside it — ``test_forbidden_imports`` asserts the
runtime layer does not import adapters; this asserts the test suite cannot address the
deployment database. Cheap, fast, no services: it runs on every PR.

Two properties the issue named as deciding whether this is worth having, both asserted by
the tests at the bottom rather than left to a reader:

* **The scan is broader than the fix it guards.** ``test_config.env``, ``README.md`` and
  any future ``*.yaml`` fixture are scanned too. #1099's stale file literals outranked the
  corrected default, so a Python-only scan would have read green while the hole was open.
* **It matches the database NAME, not one URL.** A different host, port or credential
  spelling is the same danger; matching an exact string would rubber-stamp the known case
  and miss every variant.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from squadops.bootstrap.database_isolation import DEPLOYMENT_DB_NAME, TEST_DB_NAME

pytestmark = [pytest.mark.domain_orchestration]

_REPO = Path(__file__).resolve().parents[3]
_TESTS = _REPO / "tests"

#: A Postgres connection string whose database is the deployment one. The path segment is
#: what is matched — host, port, role and password are free, because a DSN that reaches
#: the deployment database by a different spelling destroys the same rows. Anchored on a
#: terminator so ``squadops_test`` (the database the suite may destroy at will) does not
#: match: `/squadops` followed by end, a query string, or whitespace/quote.
_DEPLOYMENT_DSN = re.compile(
    rf"postgres(?:ql)?(?:\+\w+)?://[^\s\"'`]*/{re.escape(DEPLOYMENT_DB_NAME)}(?=[\s\"'`?]|$)"
)

#: Files that name the deployment database deliberately, each with the reason. An entry
#: here is an argument, not a mute: it says why this file is *about* the boundary rather
#: than crossing it.
_ALLOWLIST: dict[str, str] = {
    # The unit test of the isolation seam itself (#1180). It asserts what
    # `with_database()` produces and that compose/CI spell the deployment database the
    # same way — naming it is the whole point, and it opens no connection.
    "tests/unit/bootstrap/setup/test_checks.py": (
        "tests the database-isolation seam; asserts on DSNs rather than connecting"
    ),
    # This file: the pattern and the counter-examples below are literals by necessity.
    "tests/unit/architecture/test_no_deployment_dsn_under_tests.py": "the guard itself",
}

#: Everything under tests/, not just modules — the extensions are not enumerated, because
#: enumerating them is how the next fixture format slips through.
_SKIP_DIRS = {"__pycache__", ".pytest_cache", "node_modules", ".venv"}


def _scanned_files() -> list[Path]:
    return sorted(
        p
        for p in _TESTS.rglob("*")
        if p.is_file() and not any(part in _SKIP_DIRS for part in p.parts)
    )


def _offences(text: str) -> list[str]:
    return _DEPLOYMENT_DSN.findall(text)


def test_no_test_file_addresses_the_deployment_database():
    """Bug caught: a DSN literal naming the deployment database lands under ``tests/``.

    It is silent until the suite runs against a live deployment and empties a table. The
    sanctioned way to get a DSN is ``squadops.bootstrap.database_isolation`` —
    ``test_role_dsn()`` for the suite's own connection, ``with_database()`` to retarget an
    existing one.
    """
    offences = []
    for path in _scanned_files():
        rel = str(path.relative_to(_REPO))
        if rel in _ALLOWLIST:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue  # a binary fixture cannot carry a DSN a loader would read
        for hit in _offences(text):
            line = text[: text.index(hit)].count("\n") + 1
            offences.append(f"{rel}:{line}  {hit}")

    assert offences == [], (
        f"a file under tests/ names the deployment database {DEPLOYMENT_DB_NAME!r} in a "
        f"connection string. The suite must address {TEST_DB_NAME!r} instead — use "
        f"squadops.bootstrap.database_isolation.test_role_dsn() for the suite's own "
        f"connection, or with_database() to retarget one. This is how 291 rows of "
        f"cycle_gate_decisions were destroyed on 2026-08-30 (#1099, #1180):\n  "
        + "\n  ".join(offences)
    )


class TestTheScanIsWideEnoughToBeWorthHaving:
    """The issue named two ways this check could exist and be useless. Both are pinned
    here, because a guard that only matches the case it was written for is a guard that
    reads green through the next variant."""

    @pytest.mark.parametrize(
        "dsn",
        [
            pytest.param(
                "postgresql://squadops:pw@localhost:5432/squadops", id="the-2026-08-30-one"
            ),
            pytest.param(
                "postgresql://other:pw@db.internal:6543/squadops", id="different-host-port-role"
            ),
            pytest.param("postgres://squadops:pw@localhost/squadops", id="postgres-scheme"),
            pytest.param("postgresql+asyncpg://u:p@h/squadops", id="driver-qualified"),
            pytest.param(
                "postgresql://u:p@h:5432/squadops?sslmode=require", id="with-query-string"
            ),
        ],
    )
    def test_a_deployment_dsn_is_caught_however_it_is_spelled(self, dsn):
        # The match ends at the database name — a query string is not part of the
        # offence, only of the line a reader is sent to.
        assert _offences(f'POSTGRES_URL = "{dsn}"') == [dsn.split("?")[0]]

    @pytest.mark.parametrize(
        "dsn",
        [
            pytest.param(
                "postgresql://squadops_test:pw@localhost:5432/squadops_test", id="the-test-database"
            ),
            pytest.param(
                "postgresql://u:p@h/squadops_test?sslmode=disable", id="test-db-with-query"
            ),
            pytest.param("postgresql://u:p@h/squadopsdev", id="a-longer-name-sharing-the-prefix"),
        ],
    )
    def test_the_test_database_and_its_neighbours_are_not_flagged(self, dsn):
        """A guard that flags ``squadops_test`` fails the whole suite on its own sanctioned
        DSN, and the first fix anyone reaches for is deleting the guard."""
        assert _offences(f'POSTGRES_URL = "{dsn}"') == []

    def test_the_scan_reaches_past_python(self):
        """#1099's stale literals lived in ``test_config.env`` and ``README.md`` and
        outranked the corrected default. A ``*.py``-only scan would have read green."""
        scanned = {p.suffix for p in _scanned_files()}
        assert {".env", ".md"} <= scanned, (
            f"the scan covers only {sorted(scanned)} — the file that started this was a "
            f".env, and enumerating extensions is how the next format slips through"
        )

    def test_every_allowlist_entry_still_names_a_file_that_would_otherwise_fail(self):
        """Bug caught: a mute outliving its subject.

        An entry for a file that no longer carries a deployment DSN is a rule about code
        that is not there — and the next file at that path inherits the exemption silently.
        """
        stale = []
        for rel, reason in _ALLOWLIST.items():
            path = _REPO / rel
            if not path.exists():
                stale.append(f"{rel} (no such file) — {reason}")
            elif not _offences(path.read_text(encoding="utf-8")):
                stale.append(f"{rel} (no deployment DSN in it any more) — {reason}")
        assert stale == [], "allowlist entries that no longer have a subject:\n  " + "\n  ".join(
            stale
        )
