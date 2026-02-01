"""LanceDB memory adapter.

Vector-based memory storage using LanceDB with pluggable async embeddings.
Part of SIP-0.8.7 Infrastructure Ports Migration.
"""
from __future__ import annotations

import asyncio
import uuid
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from squadops.memory.exceptions import MemoryEmbeddingError, MemoryStoreError
from squadops.memory.models import MemoryEntry, MemoryQuery, MemoryResult
from squadops.ports.memory.store import MemoryPort

if TYPE_CHECKING:
    import lancedb

# Type alias for async embedding function
EmbedFn = Callable[[str], Awaitable[list[float]]]


class LanceDBAdapter(MemoryPort):
    """LanceDB-backed memory with pluggable async embedding function.

    Supports semantic search via vector embeddings. The embedding function
    is injectable for testing and to support different embedding providers.
    """

    def __init__(
        self,
        db_path: str,
        embed_fn: EmbedFn | None = None,
        table_name: str = "memories",
        embedding_dim: int = 384,
        **config,
    ):
        """Initialize LanceDB adapter.

        Args:
            db_path: Path to LanceDB database directory
            embed_fn: Async embedding function. If None, uses default Ollama embeddings.
            table_name: Name of the table to use
            embedding_dim: Dimension of embedding vectors
            **config: Additional configuration
        """
        self._db_path = db_path
        self._embed_fn = embed_fn or self._default_ollama_embed_async
        self._table_name = table_name
        self._embedding_dim = embedding_dim
        self._db: lancedb.DBConnection | None = None
        self._table: Any = None

    async def _default_ollama_embed_async(self, text: str) -> list[float]:
        """Legacy Ollama embedding call wrapped for async.

        Preserved for backward compatibility. Wraps sync HTTP call
        via asyncio.to_thread() to avoid blocking the event loop.
        """
        return await asyncio.to_thread(self._ollama_embed_sync, text)

    def _ollama_embed_sync(self, text: str) -> list[float]:
        """Sync Ollama HTTP call (runs in thread pool).

        Copied from legacy implementation for backward compatibility.
        """
        import httpx

        try:
            response = httpx.post(
                "http://localhost:11434/api/embeddings",
                json={"model": "nomic-embed-text", "prompt": text},
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("embedding", [])
        except Exception as e:
            raise MemoryEmbeddingError(f"Failed to generate embedding: {e}") from e

    def _ensure_db(self) -> None:
        """Ensure database connection is established."""
        if self._db is None:
            import lancedb

            self._db = lancedb.connect(self._db_path)

    def _ensure_table(self) -> None:
        """Ensure table exists."""
        self._ensure_db()
        if self._table is None:
            import pyarrow as pa

            try:
                self._table = self._db.open_table(self._table_name)
            except Exception:
                # Create table with schema if it doesn't exist
                schema = pa.schema([
                    pa.field("id", pa.string()),
                    pa.field("content", pa.string()),
                    pa.field("namespace", pa.string()),
                    pa.field("agent_id", pa.string()),
                    pa.field("cycle_id", pa.string()),
                    pa.field("tags", pa.list_(pa.string())),
                    pa.field("importance", pa.float32()),
                    pa.field("metadata", pa.string()),  # JSON serialized
                    pa.field("vector", pa.list_(pa.float32(), self._embedding_dim)),
                ])
                self._table = self._db.create_table(self._table_name, schema=schema)

    async def store(self, entry: MemoryEntry) -> str:
        """Store a memory entry with embedding."""
        import json

        try:
            self._ensure_table()

            # Generate embedding
            embedding = await self._embed_fn(entry.content)

            # Generate ID
            memory_id = str(uuid.uuid4())

            # Prepare record
            record = {
                "id": memory_id,
                "content": entry.content,
                "namespace": entry.namespace,
                "agent_id": entry.agent_id or "",
                "cycle_id": entry.cycle_id or "",
                "tags": list(entry.tags),
                "importance": entry.importance,
                "metadata": json.dumps(dict(entry.metadata)),
                "vector": embedding,
            }

            # Insert
            self._table.add([record])

            return memory_id
        except MemoryEmbeddingError:
            raise
        except Exception as e:
            raise MemoryStoreError(f"Failed to store memory: {e}") from e

    async def search(self, query: MemoryQuery) -> list[MemoryResult]:
        """Search for relevant memories."""
        import json

        try:
            self._ensure_table()

            # Generate query embedding
            query_embedding = await self._embed_fn(query.text)

            # Search
            results = (
                self._table.search(query_embedding)
                .limit(query.limit)
                .to_list()
            )

            # Convert to MemoryResult
            memory_results = []
            for row in results:
                # Filter by threshold
                score = 1.0 - row.get("_distance", 0.0)  # LanceDB uses distance
                if score < query.threshold:
                    continue

                # Filter by namespace if specified
                if query.namespace and row.get("namespace") != query.namespace:
                    continue

                # Filter by tags if specified
                if query.tags:
                    row_tags = set(row.get("tags", []))
                    if not all(t in row_tags for t in query.tags):
                        continue

                entry = MemoryEntry(
                    content=row.get("content", ""),
                    namespace=row.get("namespace", "role"),
                    agent_id=row.get("agent_id") or None,
                    cycle_id=row.get("cycle_id") or None,
                    tags=tuple(row.get("tags", [])),
                    importance=row.get("importance", 0.7),
                    metadata=tuple(json.loads(row.get("metadata", "{}")).items()),
                )

                memory_results.append(MemoryResult(
                    entry=entry,
                    memory_id=row.get("id", ""),
                    score=score,
                ))

            return memory_results
        except MemoryEmbeddingError:
            raise
        except Exception as e:
            raise MemoryStoreError(f"Failed to search memories: {e}") from e

    async def get(self, memory_id: str) -> MemoryEntry | None:
        """Get a specific memory entry by ID."""
        import json

        try:
            self._ensure_table()

            results = self._table.search().where(f"id = '{memory_id}'").limit(1).to_list()

            if not results:
                return None

            row = results[0]
            return MemoryEntry(
                content=row.get("content", ""),
                namespace=row.get("namespace", "role"),
                agent_id=row.get("agent_id") or None,
                cycle_id=row.get("cycle_id") or None,
                tags=tuple(row.get("tags", [])),
                importance=row.get("importance", 0.7),
                metadata=tuple(json.loads(row.get("metadata", "{}")).items()),
            )
        except Exception:
            return None

    async def delete(self, memory_id: str) -> bool:
        """Delete a memory entry."""
        try:
            self._ensure_table()

            # Check if exists
            results = self._table.search().where(f"id = '{memory_id}'").limit(1).to_list()
            if not results:
                return False

            # Delete
            self._table.delete(f"id = '{memory_id}'")
            return True
        except Exception:
            return False
