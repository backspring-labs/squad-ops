"""The one asyncpg pool factory (#577).

Pool creation was scattered — the runtime API (bounded), the SQL and Prefect task
adapters (unbounded, lazily imported) — and none registered a JSON codec, which is why
every postgres-backed adapter carried its own ``parse_jsonb`` and ``or {}`` around every
JSONB read, and ``json.dumps`` around every JSONB write. Every pool now comes from here
with the ``jsonb``/``json`` codecs registered on each connection: a JSONB column reads
back as the Python value and takes a Python value on write. Raw asyncpg stays — no ORM.

The architecture test refuses any ``asyncpg.create_pool`` outside this module, so a pool
without the codec cannot appear again.
"""

from __future__ import annotations

import json
from typing import Any

import asyncpg

#: The runtime API's sizing before #577, kept as the default so a caller that names
#: nothing gets what the API had; the task adapters had no bounds at all.
DEFAULT_MIN_SIZE = 1
DEFAULT_MAX_SIZE = 10


async def register_json_codecs(conn: asyncpg.Connection) -> None:
    """``jsonb`` and ``json`` travel as Python values on this connection."""
    for typename in ("jsonb", "json"):
        await conn.set_type_codec(
            typename, encoder=json.dumps, decoder=json.loads, schema="pg_catalog"
        )


async def create_pool(
    dsn: str,
    *,
    min_size: int = DEFAULT_MIN_SIZE,
    max_size: int = DEFAULT_MAX_SIZE,
    **kwargs: Any,
) -> asyncpg.Pool:
    """An asyncpg pool with the JSON codecs registered on every connection."""
    return await asyncpg.create_pool(
        dsn, min_size=min_size, max_size=max_size, init=register_json_codecs, **kwargs
    )
