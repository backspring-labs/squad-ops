"""#2921: listing a project's artifacts walks every metadata file under it, about 3 s for group_run's
~54,000. On the event loop that held every other request of the runtime API for as long, so the
console's Home waited seconds on calls that take milliseconds. The walk runs in a worker thread,
and metadata is written whole and renamed into place so the walk never reads a partial file."""

from __future__ import annotations

import asyncio
import json
import time
from datetime import UTC, datetime, timedelta

import pytest

from adapters.cycles import filesystem_artifact_vault as fav
from adapters.cycles.filesystem_artifact_vault import FilesystemArtifactVault
from squadops.cycles.models import ArtifactRef

T0 = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)


def _ref(n: int) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=f"art_{n:012d}",
        project_id="proj",
        artifact_type="code",
        filename=f"f{n}.py",
        content_hash="",
        size_bytes=0,
        media_type="text/plain",
        created_at=T0 + timedelta(minutes=n),
        cycle_id="cyc_1",
        run_id="run_1",
    )


@pytest.fixture
async def vault(tmp_path):
    v = FilesystemArtifactVault(base_dir=tmp_path)
    for n in range(3):
        await v.store(_ref(n), b"x")
    return v


async def test_a_slow_listing_leaves_other_requests_served(vault, monkeypatch):
    """Bug caught: the walk on the event loop, so a request that takes milliseconds waits for it."""
    load = vault._load_metadata

    def slow_load(path):
        time.sleep(0.2)  # a file read on a big tree, made slow
        return load(path)

    monkeypatch.setattr(vault, "_load_metadata", slow_load)
    order: list[str] = []

    async def listing():
        await vault.list_artifacts(project_id="proj")
        order.append("listing")

    async def quick_request():
        await asyncio.sleep(0.05)
        order.append("quick")

    await asyncio.gather(listing(), quick_request())

    assert order == ["quick", "listing"]


async def test_a_page_is_still_the_newest_first(vault):
    """The walk moved; what it returns didn't: newest first, then the page."""
    page = await vault.list_artifacts(project_id="proj", limit=2, offset=0)
    rest = await vault.list_artifacts(project_id="proj", limit=2, offset=2)

    assert [r.artifact_id for r in page] == ["art_000000000002", "art_000000000001"]
    assert [r.artifact_id for r in rest] == ["art_000000000000"]


async def test_a_promotion_rewrites_metadata_whole(vault, tmp_path):
    promoted = await vault.promote_artifact("art_000000000001")

    listed = {r.artifact_id: r for r in await vault.list_artifacts(project_id="proj")}
    assert promoted.promotion_status == "promoted"
    assert listed["art_000000000001"].promotion_status == "promoted"
    assert list(tmp_path.rglob("*.tmp")) == []


def test_a_failed_write_leaves_the_old_file_and_no_temporary(tmp_path):
    """Bug caught: a write that dies part-way leaving a truncated file a reader then fails on."""
    path = tmp_path / "metadata.json"
    path.write_text(json.dumps({"artifact_id": "art_old"}))

    with pytest.raises(TypeError):
        fav._write_json_atomically(path, {"bad": object()})

    assert json.loads(path.read_text()) == {"artifact_id": "art_old"}
    assert list(tmp_path.glob("*.tmp")) == []
