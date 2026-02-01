"""LanceDB memory adapter.

Vector-based memory storage using LanceDB with EmbeddingsPort injection.
Part of SIP-0.8.7 Infrastructure Ports Migration.
Updated in SIP-0.8.8 to use EmbeddingsPort instead of embed_fn seam.
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from squadops.memory.exceptions import MemoryEmbeddingError, MemoryStoreError
from squadops.memory.models import MemoryEntry, MemoryQuery, MemoryResult
from squadops.ports.memory.store import MemoryPort

if TYPE_CHECKING:
    import lancedb

    from squadops.ports.embeddings.provider import EmbeddingsPort


class LanceDBAdapter(MemoryPort):
    """LanceDB-backed memory with EmbeddingsPort injection.

    Supports semantic search via vector embeddings. The embeddings port
    is injectable for testing and to support different embedding providers.
    """

    def __init__(
        self,
        db_path: str,
        embeddings: EmbeddingsPort,
        table_name: str = "memories",
        **config,
    ):
        """Initialize LanceDB adapter.

        Args:
            db_path: Path to LanceDB database directory
            embeddings: EmbeddingsPort for generating vectors
            table_name: Name of the table to use
            **config: Additional configuration
        """
        self._db_path = db_path
        self._embeddings = embeddings
        self._table_name = table_name
        self._embedding_dim = embeddings.dimensions()
        self._db: lancedb.DBConnection | None = None
        self._table: Any = None

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

            # Generate embedding via port
            embedding = await self._embeddings.embed(entry.content)

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

            # Generate query embedding via port
            query_embedding = await self._embeddings.embed(query.text)

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
