"""#2931: a power loss left empty artifact metadata, and one empty file failed a re-attached run's
listing, though the listing was for a different, completed run. The vault's write order makes an
artifact exist only once its content and metadata are both durable, a corrupt record is a typed
error to the read that needs it, and a listing skips it and names it."""

from __future__ import annotations

import fcntl
import importlib.util
import logging
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from adapters.cycles import filesystem_artifact_vault as fav
from adapters.cycles.filesystem_artifact_vault import FilesystemArtifactVault
from squadops.api.routes.cycles.errors import cycle_error_envelope
from squadops.cycles.models import ArtifactNotFoundError, ArtifactRef, ArtifactUnreadableError

T0 = datetime(2026, 11, 8, 12, 0, tzinfo=UTC)
_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "dev" / "vault_integrity.py"


def _ref(n: int, run: str = "run_1", *, aid: str | None = None) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=aid or f"art_{n:012d}",
        project_id="proj",
        artifact_type="code",
        filename=f"f{n}.py",
        content_hash="",
        size_bytes=0,
        media_type="text/plain",
        created_at=T0 + timedelta(minutes=n),
        cycle_id="cyc_1",
        run_id=run,
    )


def _path_of(fd: int) -> Path:
    """The path an open descriptor names: ``/proc/self/fd`` on Linux, ``F_GETPATH`` on macOS,
    which has no ``/proc`` (#2976)."""
    if sys.platform == "darwin":
        return Path(os.fsdecode(fcntl.fcntl(fd, fcntl.F_GETPATH, bytes(1024)).split(b"\0", 1)[0]))
    return Path(os.readlink(f"/proc/self/fd/{fd}"))


def _meta(vault: FilesystemArtifactVault, ref: ArtifactRef) -> Path:
    return vault._artifact_dir_for_ref(ref) / "metadata.json"


async def test_a_crash_before_the_metadata_leaves_no_artifact(tmp_path, monkeypatch):
    """The commit point. Bug caught: content written and indexed before its metadata, so a crash
    between them leaves an id that resolves to nothing readable, or a listing that reads a record
    the disk never finished."""
    vault = FilesystemArtifactVault(base_dir=tmp_path)
    real = fav._write_atomically

    def crash_at_metadata(path, data, mode):
        if path.name == "metadata.json":
            raise OSError("power lost")
        real(path, data, mode)

    monkeypatch.setattr(fav, "_write_atomically", crash_at_metadata)
    with pytest.raises(OSError, match="power lost"):
        await vault.store(_ref(1), b"print(1)\n")
    monkeypatch.undo()

    assert (vault._artifact_dir_for_ref(_ref(1)) / "f1.py").read_bytes() == b"print(1)\n"
    assert await vault.list_artifacts(project_id="proj") == []
    with pytest.raises(ArtifactNotFoundError):
        await vault.retrieve(_ref(1).artifact_id)
    assert list(vault._artifact_dir_for_ref(_ref(1)).glob("*.tmp")) == []


async def test_each_write_is_fsynced_and_renamed_in_order(tmp_path, monkeypatch):
    """Bug caught: a rename with no fsync, which a power loss can undo or leave empty; or the index,
    or the listing summary (#2973), made durable before the metadata it points at."""
    vault = FilesystemArtifactVault(base_dir=tmp_path)
    synced: list[str] = []
    real_fsync = os.fsync

    def recording_fsync(fd):
        target = _path_of(fd)
        synced.append(target.name if target.is_dir() else target.suffix)
        real_fsync(fd)

    monkeypatch.setattr(fav.os, "fsync", recording_fsync)
    await vault.store(_ref(1), b"x")

    art = vault._artifact_dir_for_ref(_ref(1)).name
    # content's temp file, its directory; metadata's, its directory; the index's, the vault's; the
    # run's listing summary's, the run's
    assert synced == [".tmp", art, ".tmp", art, ".tmp", tmp_path.name, ".tmp", "run_1"]


@pytest.mark.parametrize(
    "damage",
    [b"", b"{not json", b"[]", b'{"artifact_id": "x"}'],
    ids=["empty-after-power-loss", "truncated", "not-an-object", "missing-fields"],
)
async def test_a_listing_skips_a_corrupt_record_and_names_it(tmp_path, damage, caplog):
    """#2931's outage. Bug caught: one unreadable metadata file raising out of the walk, so every
    listing that passes it fails, a different run's included; or the record skipped silently."""
    vault = FilesystemArtifactVault(base_dir=tmp_path)
    for n in range(3):
        await vault.store(_ref(n), b"x")
    await vault.store(_ref(9, run="run_2"), b"y")
    _meta(vault, _ref(1)).write_bytes(damage)

    with caplog.at_level(logging.WARNING, logger=fav.__name__):
        cycle_wide = await vault.list_artifacts(project_id="proj", cycle_id="cyc_1")
    other_run = await vault.list_artifacts(project_id="proj", cycle_id="cyc_1", run_id="run_2")

    assert [r.artifact_id for r in cycle_wide] == [
        _ref(9).artifact_id, _ref(2).artifact_id, _ref(0).artifact_id
    ]  # fmt: skip
    assert [r.artifact_id for r in other_run] == [_ref(9).artifact_id]
    [warning] = [r for r in caplog.records if r.getMessage() == "artifact_record_unreadable"]
    assert warning.path == f"proj/cyc_1/run_1/{_ref(1).artifact_id}/metadata.json"


async def test_a_read_that_needs_a_corrupt_record_refuses_with_a_typed_error(tmp_path):
    """Bug caught: a damaged record read as absent (a baseline resolved to None, a checkpoint's
    artifact skipped) or raised as a bare JSONDecodeError no caller handles."""
    vault = FilesystemArtifactVault(base_dir=tmp_path)
    ref = await vault.store(_ref(1), b"x")
    await vault.set_baseline("proj", "code", ref.artifact_id)
    _meta(vault, ref).write_bytes(b"")

    for read in (vault.retrieve, vault.get_metadata):
        with pytest.raises(ArtifactUnreadableError, match=f"{ref.artifact_id} is unreadable"):
            await read(ref.artifact_id)
    with pytest.raises(ArtifactUnreadableError):
        await vault.get_baseline("proj", "code")
    assert not issubclass(ArtifactUnreadableError, ArtifactNotFoundError)
    assert cycle_error_envelope(ArtifactUnreadableError("x"))[0] == 500


@pytest.mark.parametrize(
    ("change", "why"),
    [("delete", "is missing"), ("truncate", "doesn't match"), ("same-size", "doesn't match")],
)
async def test_content_that_isnt_what_its_metadata_records_is_unreadable(tmp_path, change, why):
    """Bug caught: a retrieve returning content a power loss emptied, or another file's bytes, as
    if they were the artifact."""
    vault = FilesystemArtifactVault(base_dir=tmp_path)
    ref = await vault.store(_ref(1), b"print('hello')\n")
    content = vault._artifact_dir_for_ref(ref) / ref.filename
    if change == "delete":
        content.unlink()
    elif change == "truncate":
        content.write_bytes(b"")
    else:
        content.write_bytes(b"print('HELLO')\n")

    with pytest.raises(ArtifactUnreadableError, match=why):
        await vault.retrieve(ref.artifact_id)


async def test_an_unreadable_index_is_rebuilt_and_an_unreadable_baselines_file_refuses(tmp_path):
    """Bug caught: an empty index after a power loss failing every lookup, though the tree holds
    every id; or an empty baselines file read as "no baseline"."""
    vault = FilesystemArtifactVault(base_dir=tmp_path)
    ref = await vault.store(_ref(1), b"x")
    await vault.set_baseline("proj", "code", ref.artifact_id)
    (tmp_path / "_index.json").write_bytes(b"")

    assert (await vault.retrieve(ref.artifact_id))[1] == b"x"

    (tmp_path / "proj" / ".baselines.json").write_bytes(b"")
    with pytest.raises(ArtifactUnreadableError, match="baselines record"):
        await vault.list_baselines("proj")


def _integrity():
    spec = importlib.util.spec_from_file_location("vault_integrity", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def test_the_integrity_pass_names_each_kind_of_corrupt_record(tmp_path):
    """The cut's pass (2.7 plan §4.6). Bug caught: a kind of damage the pass doesn't see, so the cut
    record reads clean over a damaged vault; or an artifact id it misses because it isn't art_."""
    vault = FilesystemArtifactVault(base_dir=tmp_path)
    refs = [await vault.store(_ref(n, aid=aid), b"x") for n, aid in enumerate(
        ["art_000000000001", "delta_aaaaaaaaaaaa", "term_-qa.test_01", "art_000000000004"]
    )]  # fmt: skip
    _meta(vault, refs[0]).write_bytes(b"")
    (vault._artifact_dir_for_ref(refs[1]) / refs[1].filename).unlink()
    (vault._artifact_dir_for_ref(refs[2]) / refs[2].filename).write_bytes(b"xy")
    orphan = tmp_path / "proj" / "cyc_1" / "run_1" / "art_orphan"
    orphan.mkdir()
    (orphan / "f.py").write_bytes(b"x")
    (vault._artifact_dir_for_ref(refs[3]) / "metadata.json.abc.tmp").write_bytes(b"{")

    found = _integrity().check(tmp_path)

    run = "proj/cyc_1/run_1"
    assert found == {
        "metadata_unreadable": [f"{run}/art_000000000001/metadata.json"],
        "content_missing": [f"{run}/delta_aaaaaaaaaaaa/f1.py"],
        "content_mismatch": [f"{run}/term_-qa.test_01/f2.py"],
        "content_without_metadata": [f"{run}/art_orphan"],
        "stray_temp_files": [f"{run}/art_000000000004/metadata.json.abc.tmp"],
    }
    assert _integrity().main([str(tmp_path / "proj" / "nothing")]) == 0


async def test_the_integrity_pass_reads_a_whole_vault_clean_and_scopes_to_a_subtree(tmp_path):
    """Bug caught: the pass reporting a clean vault as corrupt (it would be ignored at the cut), or
    ``--under`` reading outside its subtree."""
    vault = FilesystemArtifactVault(base_dir=tmp_path)
    await vault.store(_ref(1), b"x")
    bad = await vault.store(_ref(2, run="run_2"), b"x")
    _meta(vault, bad).write_bytes(b"")
    module = _integrity()
    assert len(list(tmp_path.rglob(".listing.json"))) == 2  # #2973's summaries: not records

    assert sum(map(len, module.check(tmp_path, "proj/cyc_1/run_1").values())) == 0
    assert module.check(tmp_path, "proj/cyc_1/run_2")["metadata_unreadable"] == [
        f"proj/cyc_1/run_2/{bad.artifact_id}/metadata.json"
    ]
    assert module.main([str(tmp_path)]) == 1


async def test_a_read_only_vault_rebuilds_an_unreadable_index_in_memory_and_never_writes(tmp_path):
    """Bug caught: the rebuild of an unreadable index writing it, through the subclass the host's
    read-only scripts use, which refuses every index write and would then raise on every lookup."""
    spec = importlib.util.spec_from_file_location(
        "read_only_vault", _SCRIPT.parent / "read_only_vault.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    ref = await FilesystemArtifactVault(base_dir=tmp_path).store(_ref(1), b"x")
    (tmp_path / "_index.json").write_bytes(b"")

    read_only = module.ReadOnlyVault(base_dir=tmp_path)

    assert (await read_only.retrieve(ref.artifact_id))[1] == b"x"
    assert (tmp_path / "_index.json").read_bytes() == b""
