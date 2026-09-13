"""Every asyncpg pool comes from ``adapters.persistence.pool`` (#577).

A pool created anywhere else has no JSON codec: its JSONB columns read back as strings
and take strings on write, and the adapters — which no longer decode or encode by hand —
would corrupt or crash on it. The factory is the only place ``asyncpg.create_pool`` may
be called, in the source trees and in the tests that stand up real pools.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
FACTORY = REPO / "adapters" / "persistence" / "pool.py"
_CALL = re.compile(r"asyncpg\.create_pool\(")


def _python_files():
    for root in ("src", "adapters", "tests", "scripts"):
        yield from (REPO / root).rglob("*.py")


def test_asyncpg_create_pool_is_called_only_by_the_factory():
    offenders = sorted(
        str(path.relative_to(REPO))
        for path in _python_files()
        if path != FACTORY and _CALL.search(path.read_text(encoding="utf-8"))
    )
    assert offenders == [], (
        f"asyncpg.create_pool called outside adapters/persistence/pool.py — a pool without "
        f"the JSON codec (#577): {offenders}"
    )


def test_the_factory_registers_the_codecs_on_every_connection():
    text = FACTORY.read_text(encoding="utf-8")
    assert "init=register_json_codecs" in text
    assert "set_type_codec(" in text and '"jsonb"' in text
