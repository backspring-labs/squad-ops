"""Persistence adapters package.

Holds the asyncpg runtime ports (`adapters.persistence.runtime.*`) and the
chat repository/cache adapters. The legacy sqlalchemy backend
(`DbRuntime`/`PostgresRuntime`/`get_db_runtime`) was removed in #234 — it had
no production callers; every active persistence path is asyncpg.
"""
