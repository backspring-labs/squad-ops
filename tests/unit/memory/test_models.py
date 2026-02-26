"""Unit tests for Memory domain models."""

import pytest

from squadops.memory.models import MemoryEntry, MemoryQuery, MemoryResult


class TestMemoryEntry:
    """Tests for MemoryEntry dataclass."""

    def test_minimal_entry(self):
        entry = MemoryEntry(content="test content")
        assert entry.content == "test content"
        assert entry.namespace == "role"
        assert entry.agent_id is None
        assert entry.cycle_id is None
        assert entry.tags == ()
        assert entry.importance == 0.7
        assert entry.metadata == ()

    def test_full_entry(self):
        entry = MemoryEntry(
            content="test content",
            namespace="custom",
            agent_id="agent-1",
            cycle_id="cycle-1",
            tags=("tag1", "tag2"),
            importance=0.9,
            metadata=(("key", "value"),),
        )
        assert entry.namespace == "custom"
        assert entry.agent_id == "agent-1"
        assert entry.cycle_id == "cycle-1"
        assert entry.tags == ("tag1", "tag2")
        assert entry.importance == 0.9
        assert entry.metadata == (("key", "value"),)

    def test_entry_is_frozen(self):
        entry = MemoryEntry(content="test")
        with pytest.raises(AttributeError):
            entry.content = "modified"  # type: ignore


class TestMemoryQuery:
    """Tests for MemoryQuery dataclass."""

    def test_minimal_query(self):
        query = MemoryQuery(text="search text")
        assert query.text == "search text"
        assert query.limit == 8
        assert query.threshold == 0.7
        assert query.namespace is None
        assert query.tags == ()

    def test_full_query(self):
        query = MemoryQuery(
            text="search text",
            limit=10,
            threshold=0.8,
            namespace="custom",
            tags=("tag1",),
        )
        assert query.limit == 10
        assert query.threshold == 0.8
        assert query.namespace == "custom"
        assert query.tags == ("tag1",)

    def test_query_is_frozen(self):
        query = MemoryQuery(text="test")
        with pytest.raises(AttributeError):
            query.text = "modified"  # type: ignore


class TestMemoryResult:
    """Tests for MemoryResult dataclass."""

    def test_result(self):
        entry = MemoryEntry(content="test")
        result = MemoryResult(entry=entry, memory_id="mem-1", score=0.95)
        assert result.entry == entry
        assert result.memory_id == "mem-1"
        assert result.score == 0.95

    def test_result_is_frozen(self):
        entry = MemoryEntry(content="test")
        result = MemoryResult(entry=entry, memory_id="mem-1", score=0.95)
        with pytest.raises(AttributeError):
            result.score = 0.5  # type: ignore
