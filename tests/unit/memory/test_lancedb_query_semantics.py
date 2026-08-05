"""#571 — LanceDB query semantics against a REAL store (no mocks).

The two defects were invisible to mock-based tests by construction: post-limit
filtering starves results only when a real ANN query returns real neighbors,
and the L2-vs-cosine mismatch only shows in real ``_distance`` values. These
tests run against an actual LanceDB table in tmp_path with deterministic
vectors, so they fail on the pre-#571 adapter and on any regression to either
behavior.
"""

from __future__ import annotations

import math

import pytest

from squadops.memory.models import MemoryEntry, MemoryQuery
from squadops.ports.embeddings.provider import EmbeddingsPort

pytestmark = [pytest.mark.domain_memory]

_DIM = 4


class VectorMapEmbeddings(EmbeddingsPort):
    """Deterministic text→vector map so distances are designed, not learned."""

    def __init__(self, mapping: dict[str, list[float]]):
        self._mapping = mapping

    async def embed(self, text: str) -> list[float]:
        return list(self._mapping[text])

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [await self.embed(t) for t in texts]

    def dimensions(self) -> int:
        return _DIM

    async def health(self) -> dict:
        return {"healthy": True}


def _unit(theta: float) -> list[float]:
    """A unit vector at angle theta in the first two dims."""
    return [math.cos(theta), math.sin(theta), 0.0, 0.0]


def _adapter(tmp_path, mapping):
    from adapters.memory.lancedb import LanceDBAdapter

    return LanceDBAdapter(db_path=str(tmp_path / "db"), embeddings=VectorMapEmbeddings(mapping))


async def test_namespace_prefilter_defeats_limit_starvation(tmp_path):
    """The #571 headline: N out-of-namespace rows sit NEARER the query than
    every in-namespace row. Post-limit filtering returns ZERO results here;
    the prefiltered query must return the in-namespace matches."""
    mapping = {"query": _unit(0.0)}
    for i in range(5):
        mapping[f"noise-{i}"] = _unit(0.01 * (i + 1))  # nearest 5: wrong namespace
    for i in range(3):
        mapping[f"role-{i}"] = _unit(0.3 + 0.01 * i)  # farther, right namespace

    adapter = _adapter(tmp_path, mapping)
    for i in range(5):
        await adapter.store(MemoryEntry(content=f"noise-{i}", namespace="cycle"))
    for i in range(3):
        await adapter.store(MemoryEntry(content=f"role-{i}", namespace="role"))

    results = await adapter.search(
        MemoryQuery(text="query", limit=3, threshold=0.0, namespace="role")
    )

    assert len(results) == 3
    assert {r.entry.content for r in results} == {"role-0", "role-1", "role-2"}


async def test_tag_prefilter_defeats_limit_starvation(tmp_path):
    mapping = {"query": _unit(0.0)}
    for i in range(4):
        mapping[f"untagged-{i}"] = _unit(0.01 * (i + 1))
    mapping["tagged"] = _unit(0.4)

    adapter = _adapter(tmp_path, mapping)
    for i in range(4):
        await adapter.store(MemoryEntry(content=f"untagged-{i}", namespace="role"))
    await adapter.store(MemoryEntry(content="tagged", namespace="role", tags=("lesson",)))

    results = await adapter.search(
        MemoryQuery(text="query", limit=2, threshold=0.0, namespace="role", tags=("lesson",))
    )

    assert [r.entry.content for r in results] == ["tagged"]


async def test_score_is_cosine_not_l2(tmp_path):
    """A vector pointing the SAME direction at a different magnitude has
    cosine distance ~0 (score ~1.0). Under the default L2 metric its distance
    would be large and the score meaningless — this pins the explicit metric."""
    mapping = {
        "query": [1.0, 0.0, 0.0, 0.0],
        "same-direction-scaled": [10.0, 0.0, 0.0, 0.0],
    }
    adapter = _adapter(tmp_path, mapping)
    await adapter.store(MemoryEntry(content="same-direction-scaled", namespace="role"))

    results = await adapter.search(MemoryQuery(text="query", limit=1, threshold=0.0))

    assert len(results) == 1
    assert results[0].score == pytest.approx(1.0, abs=1e-5)


async def test_threshold_remains_a_quality_floor(tmp_path):
    """An orthogonal vector (cosine score ~0) must drop below a 0.5 threshold —
    the post-filter that legitimately returns fewer than limit."""
    mapping = {
        "query": [1.0, 0.0, 0.0, 0.0],
        "aligned": [1.0, 0.1, 0.0, 0.0],
        "orthogonal": [0.0, 0.0, 1.0, 0.0],
    }
    adapter = _adapter(tmp_path, mapping)
    await adapter.store(MemoryEntry(content="aligned", namespace="role"))
    await adapter.store(MemoryEntry(content="orthogonal", namespace="role"))

    results = await adapter.search(MemoryQuery(text="query", limit=5, threshold=0.5))

    assert [r.entry.content for r in results] == ["aligned"]
