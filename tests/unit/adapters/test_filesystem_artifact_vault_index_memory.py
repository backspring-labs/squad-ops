"""The vault's index in memory, and its file IO off the event loop (#3218).

On the Spark the index held 92,000 entries (8 MB). Every store, promote and retrieve parsed it on
the event loop, and every store rewrote it, so a run's checkout seeding and a gate's promotion held
the runtime API for 18 to 41 s.
"""

from __future__ import annotations

import asyncio
import threading
import time
from datetime import UTC, datetime, timedelta

import pytest

from adapters.cycles.filesystem_artifact_vault import FilesystemArtifactVault
from squadops.cycles.gate_promotion import promote_run_artifacts
from squadops.cycles.models import ArtifactRef

T0 = datetime(2026, 11, 19, 12, 0, tzinfo=UTC)


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


async def test_lookups_read_the_index_file_once(tmp_path, monkeypatch):
    """Bug caught: a retrieve, a metadata read or a promotion parsing the index file each time
    (the 8 MB parse per artifact that #3218's seeding and promotion spans were made of)."""
    writer = FilesystemArtifactVault(base_dir=tmp_path)
    for n in range(3):
        await writer.store(_ref(n), b"x")
    vault = FilesystemArtifactVault(base_dir=tmp_path)
    loads = []
    load = vault._load_index
    monkeypatch.setattr(vault, "_load_index", lambda: loads.append(1) or load())

    for n in range(3):
        assert (await vault.retrieve(_ref(n).artifact_id))[1] == b"x"
    await vault.get_metadata(_ref(0).artifact_id)
    await vault.promote_artifact(_ref(1).artifact_id)

    assert len(loads) == 1


async def test_concurrent_stores_share_an_index_write_and_none_is_lost(tmp_path, monkeypatch):
    """Bug caught: two stores in worker threads each reading, changing and writing the index, so
    one's entry is lost; or every store writing the whole index once (the write the stores
    waiting behind it should share)."""
    vault = FilesystemArtifactVault(base_dir=tmp_path)
    await vault.store(_ref(0), b"x")  # loads the index, so the stores below only add to it
    stores = 4  # within the smallest default thread pool (5), so every store reaches a thread
    saves: list[int] = []
    save = vault._save_index
    others_added = threading.Event()

    def held_save(index):
        saves.append(len(index))
        if len(saves) == 1:  # the first concurrent store's write: hold it until the rest add
            others_added.wait(timeout=5)
        save(index)

    monkeypatch.setattr(vault, "_save_index", held_save)

    async def watch():
        while vault._index_version < 1 + stores:
            await asyncio.sleep(0.01)
        others_added.set()

    await asyncio.gather(
        watch(), *(vault.store(_ref(n), f"c{n}".encode()) for n in range(1, 1 + stores))
    )

    assert len(saves) == 2  # the held write, and one for every store waiting behind it
    fresh = FilesystemArtifactVault(base_dir=tmp_path)
    for n in range(1 + stores):
        assert (await fresh.retrieve(_ref(n).artifact_id))[0].artifact_id == _ref(n).artifact_id


async def test_an_index_another_vault_replaced_is_read_again_and_kept(tmp_path):
    """Bug caught: the index read once and never again, so an artifact a host script's vault
    stored is "not found" here, and this vault's next write drops that script's entry."""
    vault = FilesystemArtifactVault(base_dir=tmp_path)
    await vault.store(_ref(0), b"x")
    await FilesystemArtifactVault(base_dir=tmp_path).store(_ref(1), b"y")

    assert (await vault.retrieve(_ref(1).artifact_id))[1] == b"y"
    await vault.store(_ref(2), b"z")
    fresh = FilesystemArtifactVault(base_dir=tmp_path)
    assert [(await fresh.retrieve(_ref(n).artifact_id))[1] for n in range(3)] == [b"x", b"y", b"z"]


@pytest.mark.parametrize("path", ["gate promotion", "checkout seeding"])
async def test_a_slow_vault_write_leaves_other_requests_served(tmp_path, monkeypatch, path):
    """Bug caught: a gate's promotion or a run's seeding writing the vault on the event loop, so
    a worker's millisecond request waits for it (#3218's 18.5 s and 40.9 s spans). Entered at the
    gate's own caller, ``promote_run_artifacts``, and at the store a seeding makes."""
    vault = FilesystemArtifactVault(base_dir=tmp_path)
    await vault.store(_ref(0), b"x")
    write = vault._write_metadata

    def slow_write(meta_path, ref):
        time.sleep(0.2)  # an fsync on a busy disk, made slow
        write(meta_path, ref)

    monkeypatch.setattr(vault, "_write_metadata", slow_write)
    order: list[str] = []

    async def vault_work():
        if path == "gate promotion":
            assert await promote_run_artifacts(vault, "run_1") == 1
        else:
            await vault.store(_ref(1), b"y")
        order.append("vault")

    async def quick_request():
        await asyncio.sleep(0.05)
        order.append("quick")

    await asyncio.gather(vault_work(), quick_request())

    assert order == ["quick", "vault"]
