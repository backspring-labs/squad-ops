"""Persistence adapters package.

`get_db_runtime` / `PostgresRuntime` are resolved lazily (PEP 562). Importing a
sibling asyncpg adapter under `adapters.persistence.runtime.*` must not drag in
the sqlalchemy-based postgres backend (and its optional `sqlalchemy` dependency)
merely to load this package — that eager coupling made the asyncpg adapter unit
tests uncollectable in the minimal CI env (#220). The names stay importable on
demand, so `from adapters.persistence import get_db_runtime` still works.
"""

from typing import TYPE_CHECKING

__all__ = ["get_db_runtime", "PostgresRuntime"]

if TYPE_CHECKING:
    from adapters.persistence.factory import get_db_runtime
    from adapters.persistence.postgres import PostgresRuntime


def __getattr__(name: str):
    if name == "get_db_runtime":
        from adapters.persistence.factory import get_db_runtime

        return get_db_runtime
    if name == "PostgresRuntime":
        from adapters.persistence.postgres import PostgresRuntime

        return PostgresRuntime
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
