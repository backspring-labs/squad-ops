"""SIP-0110 §A.4.3 (#2174): the legacy agent store is dormant, and no embedder is built at an
address nobody set."""

from __future__ import annotations

import pytest

from adapters.embeddings.factory import create_embeddings_provider
from adapters.memory.factory import create_memory_provider
from squadops.memory.exceptions import MemoryDormantError
from squadops.memory.models import MemoryEntry, MemoryQuery


@pytest.mark.parametrize(
    ("operation", "call"),
    [
        ("store", lambda port: port.store(MemoryEntry(content="x"))),
        ("search", lambda port: port.search(MemoryQuery(text="x"))),
        ("get", lambda port: port.get("m1")),
        ("delete", lambda port: port.delete("m1")),
    ],
)
async def test_a_call_into_the_dormant_store_is_refused_and_logged_at_warning(
    operation, call, caplog
):
    """Bug caught: #2171's shape. A memory failure swallowed at DEBUG, so a store that can never
    write reads as an empty one."""
    port = create_memory_provider(provider="dormant")

    with caplog.at_level("WARNING", logger="adapters.memory.dormant"):
        with pytest.raises(MemoryDormantError, match=f"{operation} refused"):
            await call(port)

    assert [(r.levelname, r.getMessage()) for r in caplog.records] == [
        ("WARNING", f"legacy agent memory is dormant (SIP-0110 §A.4.3, #2174): {operation} refused")
    ]


@pytest.mark.parametrize(
    "missing", [{"db_path": "/tmp/x"}, {"embeddings": object()}], ids=["no-embedder", "no-path"]
)
def test_the_lancedb_store_is_never_built_on_a_default(missing):
    """Bug caught: the factory building its own embedder at ``localhost:11434`` when the caller
    named none (#2171), or opening a store at a path nobody chose."""
    with pytest.raises(ValueError, match="requires its embeddings and its db_path"):
        create_memory_provider(provider="lancedb", **missing)


@pytest.mark.parametrize(
    "kwargs", [{"model": "nomic-embed-text"}, {"base_url": "http://ollama:11434"}]
)
def test_an_embedder_names_its_server_and_model(kwargs):
    """Bug caught: an embedder built at a defaulted ``localhost`` URL, or for a model nobody
    installed, reached only when the first embedding silently fails (#2171)."""
    with pytest.raises(TypeError):
        create_embeddings_provider("ollama", **kwargs)
