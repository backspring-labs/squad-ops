"""
LanceDBAdapter - LanceDB-based memory provider for agent-level semantic memory
Implements MemoryProvider interface for Role layer memory (agent-specific)
Uses local LanceDB tables with local embeddings (Ollama/SentenceTransformers)
"""

import hashlib
import json
import logging
import os
from datetime import datetime
from typing import Any

from agents.memory.base import MemoryProvider
import os

from infra.config.loader import load_config

logger = logging.getLogger(__name__)

try:
    import lancedb
    import pandas as pd
    import pyarrow as pa

    LANCEDB_AVAILABLE = True
except ImportError:
    LANCEDB_AVAILABLE = False
    logger.warning("LanceDB not available - install with: pip install lancedb pyarrow")


class LanceDBAdapter(MemoryProvider):
    """
    Adapter for LanceDB memory system.
    Handles Role layer memory (agent-specific semantic memory).
    Uses local LanceDB tables with columnar storage.
    """

    def __init__(self, agent_name: str, db_path: str | None = None):
        """
        Initialize LanceDBAdapter for an agent.

        Args:
            agent_name: Name of the agent
            db_path: Optional path to LanceDB database (default: /app/data/memory_db)
        """
        self.agent_name = agent_name
        self.db_path = db_path or "/app/data/memory_db"

        # Ensure database directory exists
        os.makedirs(self.db_path, exist_ok=True)

        # Initialize LanceDB connection
        self._db = None
        self._table = None
        self._table_name = f"{agent_name.lower()}_memories"

        # Embedding configuration - Use centralized config
        strict_mode = os.getenv("SQUADOPS_STRICT_CONFIG", "false").lower() == "true"
        config = load_config(strict=strict_mode)
        self._ollama_url = config.llm.url
        self._embedding_model = None  # SentenceTransformers fallback

        # Initialize connection and table
        self._initialize_lancedb()

    def _initialize_lancedb(self):
        """Initialize LanceDB connection and create/access table"""
        if not LANCEDB_AVAILABLE:
            logger.warning(f"{self.agent_name}: LanceDB not available, memory operations will fail")
            return

        try:
            # Connect to LanceDB database
            self._db = lancedb.connect(self.db_path)

            # Check if table exists, create if not
            try:
                self._table = self._db.open_table(self._table_name)
                logger.info(f"{self.agent_name}: Opened existing LanceDB table: {self._table_name}")
            except Exception as e:
                # Table doesn't exist, create it (expected on first startup)
                logger.debug(
                    f"{self.agent_name}: Table doesn't exist, creating new LanceDB table: {self._table_name}"
                )
                self._create_table()
                # Verify table was created
                if self._table is None:
                    raise RuntimeError(f"Failed to create LanceDB table {self._table_name}") from e
                logger.info(
                    f"{self.agent_name}: Successfully created LanceDB table: {self._table_name}"
                )

        except Exception as e:
            logger.error(f"{self.agent_name}: Failed to initialize LanceDB: {e}")
            logger.debug(f"{self.agent_name}: LanceDB init error details:", exc_info=True)

    def _create_table(self):
        """Create LanceDB table with schema"""
        try:
            # Define schema for memory table
            schema = pa.schema(
                [
                    pa.field("id", pa.string()),
                    pa.field("ns", pa.string()),
                    pa.field("agent", pa.string()),
                    pa.field("pid", pa.string()),
                    pa.field("cycle_id", pa.string()),
                    pa.field("tags", pa.list_(pa.string())),
                    pa.field("importance", pa.float32()),
                    pa.field("content", pa.string()),  # JSON string
                    pa.field("created_at", pa.string()),  # ISO format timestamp
                    pa.field(
                        "vector", pa.list_(pa.float32(), 768)
                    ),  # Embedding vector (768 for Ollama)
                ]
            )

            # Create empty table with explicit schema using PyArrow Table
            # PyArrow requires non-empty arrays to infer list types, so create minimal data
            empty_data = {
                "id": [""],  # Empty string for string fields
                "ns": [""],
                "agent": [""],
                "pid": [""],
                "cycle_id": [""],
                "tags": [[]],  # Empty list for list field
                "importance": [0.0],
                "content": [""],
                "created_at": [""],
                "vector": [[0.0] * 768],  # Empty vector matching schema
            }

            # Create PyArrow Table with explicit schema
            arrow_table = pa.Table.from_pydict(empty_data, schema=schema)
            self._table = self._db.create_table(self._table_name, arrow_table, mode="overwrite")
            logger.info(f"{self.agent_name}: Created LanceDB table: {self._table_name}")
            if self._table is None:
                raise RuntimeError(f"Table creation returned None for {self._table_name}")
        except Exception as e:
            logger.error(f"{self.agent_name}: Failed to create LanceDB table: {e}")
            logger.debug(f"{self.agent_name}: Table creation error details:", exc_info=True)
            self._table = None  # Ensure it's None on failure
            raise  # Re-raise to let _initialize_lancedb handle it

    def _generate_embedding(self, text: str) -> list[float]:
        """
        Generate embedding for text using Ollama (primary) or SentenceTransformers (fallback).

        Args:
            text: Text to embed

        Returns:
            List of floats representing the embedding vector
        """
        # Try Ollama first
        try:
            import requests

            resp = requests.post(
                f"{self._ollama_url}/api/embeddings",
                json={"model": "nomic-embed-text:latest", "prompt": text},
                timeout=30,
            )
            resp.raise_for_status()
            embedding = resp.json()["embedding"]

            # Ensure it's 768 dimensions (Ollama nomic-embed-text)
            if len(embedding) == 768:
                return embedding
            else:
                logger.warning(
                    f"{self.agent_name}: Ollama returned {len(embedding)} dims, expected 768, using fallback"
                )
                raise ValueError(f"Unexpected embedding dimension: {len(embedding)}")

        except Exception as e:
            logger.debug(
                f"{self.agent_name}: Ollama embedding failed: {e}, trying SentenceTransformers"
            )

            # Fallback to SentenceTransformers
            try:
                if self._embedding_model is None:
                    from sentence_transformers import SentenceTransformer

                    self._embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

                embedding = self._embedding_model.encode(text).tolist()

                # SentenceTransformers returns 384 dimensions, pad to 768 to match schema
                if len(embedding) == 384:
                    # Pad with zeros to match Ollama dimension
                    embedding = embedding + [0.0] * (768 - 384)
                    logger.debug(
                        f"{self.agent_name}: Using SentenceTransformers (384d) padded to 768d"
                    )
                else:
                    logger.warning(
                        f"{self.agent_name}: SentenceTransformers returned unexpected dimension: {len(embedding)}"
                    )

                return embedding

            except Exception as e:
                logger.error(f"{self.agent_name}: Failed to generate embedding: {e}")
                raise

    def _extract_content_text(self, content: Any) -> str:
        """Extract searchable text from content dict"""
        if isinstance(content, dict):
            # Extract key fields for embedding
            action = content.get("action", "memory")
            result = content.get("result", {})
            if isinstance(result, dict):
                result_str = json.dumps(result, separators=(",", ":"))[:200]
                return f"{action}: {result_str}"
            return str(action)
        return str(content)

    async def put(self, item: dict) -> str:
        """
        Store a memory item in LanceDB.

        Args:
            item: Dictionary with ns, agent, tags, content, importance, pid, cycle_id

        Returns:
            Memory ID as string
        """
        if self._table is None:
            logger.error(f"{self.agent_name}: LanceDB table not initialized")
            raise RuntimeError("LanceDB table not initialized")

        try:
            # Extract required fields
            ns = item.get("ns", "role")
            agent = item.get("agent", self.agent_name)
            tags = item.get("tags", [])
            content = item.get("content", {})
            importance = item.get("importance", 0.7)
            pid = item.get("pid", "")
            cycle_id = item.get("cycle_id", "")

            # Generate memory ID
            content_str = json.dumps(content, sort_keys=True)
            mem_id = hashlib.sha256(f"{agent}:{ns}:{content_str}".encode()).hexdigest()[:16]

            # Extract text for embedding
            content_text = self._extract_content_text(content)

            # Generate embedding
            embedding = self._generate_embedding(content_text)

            # Insert into LanceDB table
            # Convert to PyArrow Table to ensure schema consistency
            # PyArrow requires dict of lists, not dict of scalars
            memory_record_lists = {
                "id": [mem_id],
                "ns": [ns],
                "agent": [agent],
                "pid": [pid],
                "cycle_id": [cycle_id],
                "tags": [tags],
                "importance": [float(importance)],
                "content": [json.dumps(content)],
                "created_at": [datetime.utcnow().isoformat()],
                "vector": [embedding],
            }
            arrow_table = pa.Table.from_pydict(memory_record_lists, schema=self._table.schema)
            self._table.add(arrow_table)

            logger.info(
                f"{self.agent_name}: Stored memory {mem_id} in LanceDB table {self._table_name}"
            )
            return mem_id

        except Exception as e:
            logger.error(f"{self.agent_name}: Failed to store memory: {e}")
            raise

    async def put_if_not_exists(self, item: dict) -> str | None:
        """
        Store a memory item only if it doesn't already exist.

        Generates deterministic ID and checks for existence before storing.
        """
        if self._table is None:
            logger.error(f"{self.agent_name}: LanceDB table not initialized")
            raise RuntimeError("LanceDB table not initialized")

        try:
            # Generate deterministic ID (same logic as put())
            ns = item.get("ns", "role")
            agent = item.get("agent", self.agent_name)
            content = item.get("content", {})
            content_str = json.dumps(content, sort_keys=True)
            mem_id = hashlib.sha256(f"{agent}:{ns}:{content_str}".encode()).hexdigest()[:16]

            # Check if memory with this ID already exists
            existing = await self.get("", k=1, mem_ids=[mem_id])
            if existing:
                logger.debug(f"{self.agent_name}: Memory {mem_id} already exists, skipping storage")
                return None

            # Memory doesn't exist - store it using existing put() logic
            return await self.put(item)

        except Exception as e:
            logger.error(f"{self.agent_name}: Failed to put_if_not_exists: {e}")
            raise

    async def count(self, **kw) -> int:
        """
        Count memories in LanceDB table.

        Args:
            **kw: Optional filters:
                - tags: List of tags to filter by
                - ns: Namespace filter
                - agent: Agent name filter

        Returns:
            Number of memories matching filters
        """
        if self._table is None:
            logger.warning(
                f"{self.agent_name}: LanceDB table not initialized, cannot count memories."
            )
            return 0

        try:
            # Build metadata filters
            filters = []
            ns_filter = kw.get("ns")
            agent_filter = kw.get("agent")
            tags_filter = kw.get("tags", [])

            if ns_filter is not None:
                filters.append(f"ns == '{ns_filter}'")
            if agent_filter is not None:
                filters.append(f"agent == '{agent_filter}'")
            if tags_filter and isinstance(tags_filter, (list, tuple)) and len(tags_filter) > 0:
                tag_conditions = " OR ".join([f"'{tag}' IN tags" for tag in tags_filter])
                if tag_conditions:
                    filters.append(f"({tag_conditions})")

            # Build where clause
            where_clause = " AND ".join(filters) if len(filters) > 0 else None

            # Get all records (with filters if any) and count
            if where_clause:
                # Use search with empty vector and filter to count
                # Create a dummy embedding for search
                dummy_embedding = [0.0] * 768
                results_df = (
                    self._table.search(dummy_embedding).where(where_clause).limit(10000).to_pandas()
                )
                return len(results_df)
            else:
                # No filters - count all records
                # LanceDB doesn't have a direct count method, so we need to read all
                # For efficiency, we'll use a limit and count
                # In practice, this should be fast enough for agent memory counts
                results_df = self._table.to_pandas()
                return len(results_df)

        except Exception as e:
            logger.error(f"{self.agent_name}: Failed to count memories: {e}")
            logger.debug(f"{self.agent_name}: Count error details:", exc_info=True)
            return 0

    async def get(self, query: str, k: int = 8, **kw) -> list[dict]:
        """
        Retrieve memories matching query using LanceDB semantic search.

        Args:
            query: Search query string (empty string uses default "memory search")
            k: Maximum number of results
            **kw: Additional parameters:
                - tags: List of tags to filter by
                - ns: Namespace filter
                - agent: Agent name filter
                - mem_ids: List of memory IDs for direct lookup (more efficient than semantic search)

        Returns:
            List of memory dictionaries
        """
        if self._table is None:
            logger.warning(
                f"{self.agent_name}: LanceDB table not initialized, cannot retrieve memories."
            )
            return []

        try:
            # Step 1: Generate query embedding
            # Use default query if empty (Ollama returns 0 dims for empty strings)
            if not query or not query.strip():
                query = "memory search"
                logger.debug(f"{self.agent_name}: Empty query provided, using default: '{query}'")

            logger.debug(f"{self.agent_name}: Generating embedding for query: '{query}'")
            query_embedding = self._generate_embedding(query)
            logger.debug(
                f"{self.agent_name}: Embedding generated successfully, dimension: {len(query_embedding)}"
            )

            # Step 2: Build metadata filters
            filters = []
            ns_filter = kw.get("ns")
            agent_filter = kw.get("agent")
            tags_filter = kw.get("tags", [])
            mem_ids_filter = kw.get("mem_ids", [])

            # Filter by memory IDs (for direct lookup)
            if (
                mem_ids_filter
                and isinstance(mem_ids_filter, (list, tuple))
                and len(mem_ids_filter) > 0
            ):
                # Convert to list of strings for comparison
                mem_id_list = [str(mid) for mid in mem_ids_filter]
                if len(mem_id_list) == 1:
                    filters.append(f"id == '{mem_id_list[0]}'")
                else:
                    # Multiple IDs: use IN clause
                    id_conditions = " OR ".join([f"id == '{mid}'" for mid in mem_id_list])
                    filters.append(f"({id_conditions})")

            if ns_filter is not None:
                filters.append(f"ns == '{ns_filter}'")
            if agent_filter is not None:
                filters.append(f"agent == '{agent_filter}'")
            if tags_filter and isinstance(tags_filter, (list, tuple)) and len(tags_filter) > 0:
                # For tags, check if any tag in the list matches
                tag_conditions = " OR ".join([f"'{tag}' IN tags" for tag in tags_filter])
                if tag_conditions:
                    filters.append(f"({tag_conditions})")

            # Step 3: Build where clause - use len() check to avoid array ambiguity
            where_clause = " AND ".join(filters) if len(filters) > 0 else None
            logger.debug(f"{self.agent_name}: Filters: {filters}, where_clause: {where_clause}")

            # Step 4: Execute vector search
            search_builder = self._table.search(query_embedding).limit(k)

            if where_clause:
                search_builder = search_builder.where(where_clause)

            results_df = search_builder.to_pandas()
            logger.debug(f"{self.agent_name}: Vector search returned {len(results_df)} results")

            # Step 5: Convert to list of dicts
            results = []
            if len(results_df) == 0:
                logger.debug(f"{self.agent_name}: No results found for query '{query}'")
                return []

            for _, row in results_df.iterrows():
                # Parse content from JSON string back to dict
                content = row["content"]
                if isinstance(content, str):
                    try:
                        content = json.loads(content) if content else {}
                    except json.JSONDecodeError:
                        logger.warning(
                            f"{self.agent_name}: Failed to parse content as JSON: {content[:50]}"
                        )
                        content = {}

                # Handle tags conversion - explicit type checking to avoid array ambiguity
                tags_value = row.get("tags")
                if isinstance(tags_value, (list, tuple)):
                    tags_list = list(tags_value) if tags_value else []
                elif hasattr(tags_value, "__iter__") and not isinstance(tags_value, str):
                    # Handle numpy arrays, pandas Series, etc.
                    try:
                        tags_list = list(tags_value)
                    except (TypeError, ValueError):
                        tags_list = []
                else:
                    tags_list = []

                memory_dict = {
                    "id": str(row["id"]),
                    "ns": str(row["ns"]),
                    "agent": str(row["agent"]),
                    "pid": str(row.get("pid", "")) if pd.notna(row.get("pid", "")) else "",
                    "cycle_id": str(row.get("cycle_id", ""))
                    if pd.notna(row.get("cycle_id", ""))
                    else "",
                    "tags": tags_list,
                    "importance": float(row["importance"]),
                    "content": content,
                    "created_at": str(row.get("created_at", ""))
                    if pd.notna(row.get("created_at"))
                    else "",
                }

                # Include distance score if available (LanceDB search returns _distance column)
                if "_distance" in row and pd.notna(row["_distance"]):
                    memory_dict["_distance"] = float(row["_distance"])

                results.append(memory_dict)

            # Sort by importance (descending)
            results.sort(key=lambda x: x.get("importance", 0), reverse=True)

            logger.info(f"{self.agent_name}: Retrieved {len(results)} memories for query '{query}'")
            return results

        except Exception as e:
            logger.error(f"{self.agent_name}: Failed to retrieve memories: {e}")
            logger.debug(f"{self.agent_name}: Search error details:", exc_info=True)
            return []

    async def promote(self, mem_id: str, validator: str, to_ns: str = "squad") -> str:
        """
        Promote a memory to a higher namespace.
        Note: Actual promotion is handled by SqlAdapter, this just marks it.

        Args:
            mem_id: Memory ID to promote
            validator: Agent performing promotion
            to_ns: Target namespace

        Returns:
            Original memory ID (promotion creates new record in SqlAdapter)
        """
        # LanceDBAdapter doesn't handle promotion - that's SqlAdapter's job
        # This method exists for interface compliance
        logger.debug(f"{self.agent_name}: Promotion request for {mem_id} (handled by SqlAdapter)")
        return mem_id
