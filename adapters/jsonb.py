"""Shared helper for decoding JSONB column values from asyncpg.

asyncpg returns JSONB columns as a JSON ``str`` by default (no custom codec is
registered), but in tests — or with a custom codec — they may already be
decoded. Every postgres-backed adapter decodes the same way through this single
helper, so the behavior can't drift between adapters (#156).
"""

from __future__ import annotations

import json
from typing import Any


def parse_jsonb(value: Any) -> Any:
    """Decode a JSONB column value.

    asyncpg returns JSONB as a JSON ``str`` by default; decode it. If it was
    already decoded — a ``dict``/``list``, or ``None`` for SQL NULL (e.g. in
    tests or with a custom codec) — return it unchanged.

    Callers that need ``None`` coerced to ``{}`` (e.g. a nullable metadata
    column) should apply ``or {}`` at the call site.
    """
    if isinstance(value, str):
        return json.loads(value)
    return value
