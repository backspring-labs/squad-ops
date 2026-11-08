"""#2973: a listing by project, cycle, run, type or promotion status walked every metadata file under
its directory (group_run's ~54,000, about 2 s a page; a listing by cycle alone walked the whole
vault). It reads each run's listing summary instead, a cache of its artifacts' metadata whose every
entry is checked against the metadata file it was read from, and the page's records from their
metadata. The walk is kept as ``_walk_listing``, the oracle these tests compare against."""

from __future__ import annotations

import importlib.util
import itertools
import json
import logging
import os
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from adapters.cycles import filesystem_artifact_vault as fav
from adapters.cycles.filesystem_artifact_vault import (
    LISTING_SUMMARY,
    FilesystemArtifactVault,
    _Filters,
    _identity,
)
from squadops.cycles.models import ArtifactRef

T0 = datetime(2026, 11, 8, 12, 0, tzinfo=UTC)
_READ_ONLY = Path(__file__).resolve().parents[3] / "scripts" / "dev" / "read_only_vault.py"


def _ref(aid: str, cycle: str | None = "cyc_1", run: str | None = "run_1", **kw) -> ArtifactRef:
    fields = dict(
        artifact_id=aid,
        project_id="proj",
        artifact_type="code",
        filename=f"{aid}.py",
        content_hash="",
        size_bytes=0,
        media_type="text/plain",
        created_at=T0,
        cycle_id=cycle,
        run_id=run,
    )
    fields.update(kw)
    return ArtifactRef(**fields)


def _summaries(base: Path) -> dict[Path, bytes]:
    return {p: p.read_bytes() for p in base.rglob(LISTING_SUMMARY)}


async def _layout(vault: FilesystemArtifactVault, seed: int) -> list[ArtifactRef]:
    """A vault of a random shape: projects, cycles and runs that share ids across each other (a
    run id under two cycles, a cycle id under two projects), unattached artifacts with a cycle, a
    run or neither, creation times that tie (the id breaks it), and some artifacts promoted."""
    rng = random.Random(seed)
    stored: list[ArtifactRef] = []
    n = 0

    async def store(project: str, cycle: str | None, run: str | None) -> None:
        nonlocal n
        n += 1
        ref = _ref(
            f"art_{seed}_{n:04d}",
            cycle,
            run,
            project_id=project,
            artifact_type=rng.choice(["code", "document", "test_report"]),
            created_at=T0 + timedelta(minutes=rng.randint(0, 6)),
        )
        stored.append(await vault.store(ref, b"x" * rng.randint(0, 3)))

    for project in ["proj_a", "proj_b"][: rng.randint(1, 2)]:
        for cycle, run in itertools.product(range(rng.randint(1, 3)), range(rng.randint(1, 2))):
            for _ in range(rng.randint(0, 4)):
                await store(project, f"cyc_{cycle}", f"run_{run}")
        for cycle, run in [("cyc_0", None), (None, "run_0"), (None, None)]:
            for _ in range(rng.randint(0, 2)):
                await store(project, cycle, run)
    for ref in rng.sample(stored, k=len(stored) // 3):
        await vault.promote_artifact(ref.artifact_id)
    return stored


_FILTERS = list(
    itertools.product(
        [None, "proj_a", "proj_b", "proj_none"],
        [None, "cyc_0", "cyc_1", "cyc_none"],
        [None, "run_0", "run_1"],
        [None, "code", "document"],
        [None, "working", "promoted"],
    )
)
_PAGES = [(None, 0), (2, 0), (2, 3), (500, 1), (None, 7)]


async def _assert_every_listing_is_the_walks(vault: FilesystemArtifactVault, seed: int) -> None:
    rng = random.Random(seed)
    for filters in _FILTERS:
        for limit, offset in rng.sample(_PAGES, k=2):
            f = _Filters(*filters)
            listed = await vault.list_artifacts(**f._asdict(), limit=limit, offset=offset)
            assert listed == vault._walk_listing(f, limit, offset), (filters, limit, offset)


@pytest.mark.parametrize("seed", [1, 2, 3])
async def test_every_listing_matches_the_walk_in_the_same_order(tmp_path, seed):
    """The done-when. Bug caught: a listing that drops, adds or reorders an artifact the walk
    returns, for some filter combination or page: an unattached artifact missed by a cycle listing,
    a run id matched under the wrong cycle, a tie on creation time broken differently, an offset
    counted over a different list, a promotion the summary didn't see; and it must stay so when the
    summaries are missing (a vault from before #2973) or behind (a crash, a lost race)."""
    vault = FilesystemArtifactVault(base_dir=tmp_path)
    stored = await _layout(vault, seed)
    assert len(stored) > 5 and list(tmp_path.rglob(LISTING_SUMMARY))

    await _assert_every_listing_is_the_walks(vault, seed)

    for summary in tmp_path.rglob(LISTING_SUMMARY):  # a vault from before #2973
        summary.unlink()
    await _assert_every_listing_is_the_walks(vault, seed)

    # Behind in every way at once: summaries from before more stores and promotions put back (a
    # crash after each metadata commit), one emptied by a power loss, a damaged record, and content
    # whose metadata never landed.
    earlier = _summaries(tmp_path)
    more = await _layout(vault, seed + 100)
    for ref in more[:3]:
        await vault.promote_artifact(ref.artifact_id)
    for path, data in earlier.items():
        path.write_bytes(data)
    next(iter(earlier)).write_bytes(b"")
    (vault._artifact_dir_for_ref(stored[0]) / "metadata.json").write_bytes(b"{")
    orphan = vault._artifact_dir_for_ref(stored[1]).parent / "art_orphan"
    orphan.mkdir()
    (orphan / "f.py").write_bytes(b"x")
    await _assert_every_listing_is_the_walks(vault, seed)


@pytest.mark.parametrize(
    "behind",
    [
        "store crashed before the summary",
        "promotion crashed before the summary",
        "a listing's stale repair renamed over the store's",
        "summary missing",
        "summary emptied by a power loss",
        "summary in another format",
    ],
)
async def test_a_summary_behind_the_tree_never_hides_or_misstates_a_committed_artifact(
    tmp_path, monkeypatch, behind
):
    """How "behind" is defined. Bug caught: a summary trusted over the tree, so a crash between the
    metadata's rename and the summary's write hides the artifact from every listing, or lists a
    promoted one as working (the gate-promotion and increment-tree reads filter on it)."""
    vault = FilesystemArtifactVault(base_dir=tmp_path)
    await vault.store(_ref("art_kept"), b"x")
    summary = vault._artifact_dir_for_ref(_ref("art_kept")).parent / LISTING_SUMMARY
    before = summary.read_bytes()
    real = fav._write_atomically

    def crash_at_summary(path, data, mode):
        if path.name == LISTING_SUMMARY:
            raise SystemExit("power lost")  # the process dies; nothing after it runs
        real(path, data, mode)

    if behind == "store crashed before the summary":
        monkeypatch.setattr(fav, "_write_atomically", crash_at_summary)
        with pytest.raises(SystemExit):
            await vault.store(_ref("art_new", created_at=T0 + timedelta(minutes=1)), b"y")
        monkeypatch.undo()
    else:
        await vault.store(_ref("art_new", created_at=T0 + timedelta(minutes=1)), b"y")
    if behind == "promotion crashed before the summary":
        monkeypatch.setattr(fav, "_write_atomically", crash_at_summary)
        with pytest.raises(SystemExit):
            await vault.promote_artifact("art_kept")
        monkeypatch.undo()
    else:
        await vault.promote_artifact("art_kept")
    if behind == "a listing's stale repair renamed over the store's":
        summary.write_bytes(before)
    elif behind == "summary missing":
        summary.unlink()
    elif behind == "summary emptied by a power loss":
        summary.write_bytes(b"")
    elif behind == "summary in another format":
        summary.write_text(json.dumps({"format": 0, "artifacts": {}}))

    listed = await vault.list_artifacts(project_id="proj", cycle_id="cyc_1", run_id="run_1")
    promoted = await vault.list_artifacts(run_id="run_1", promotion_status="promoted")

    assert [(r.artifact_id, r.promotion_status) for r in listed] == [
        ("art_new", "working"),
        ("art_kept", "promoted"),
    ]
    assert [r.artifact_id for r in promoted] == ["art_kept"]
    # The listing wrote back what it read, so the next one reads it from the summary.
    entries = json.loads(summary.read_bytes())["artifacts"]
    assert {name: fields[5] for name, fields in entries.items()} == {
        "art_kept": "promoted",
        "art_new": "working",
    }


async def test_a_listing_reads_the_summaries_and_only_its_pages_metadata(tmp_path, monkeypatch):
    """The wiring, entering at ``list_artifacts`` (the port method the artifact routes call). Bug
    caught: a listing that still reads every metadata file in its scope, the 2 s a page #2973 is
    about, or that reads the summaries but no longer returns the records' full metadata."""
    vault = FilesystemArtifactVault(base_dir=tmp_path)
    for n in range(12):
        ref = _ref(
            f"art_{n:02d}",
            run=f"run_{n % 3}",
            created_at=T0 + timedelta(minutes=n),
            metadata={"note": f"n{n}"},
        )
        await vault.store(ref, b"x")
    read: list[str] = []
    real_read_bytes = Path.read_bytes

    def recording_read_bytes(path):
        read.append(path.name)
        return real_read_bytes(path)

    def recording_open(path, *args, **kwargs):
        read.append(Path(path).name)
        return open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_bytes", recording_read_bytes)
    monkeypatch.setattr(fav, "open", recording_open, raising=False)
    page = await vault.list_artifacts(project_id="proj", limit=2, offset=1)

    assert [(r.artifact_id, r.metadata) for r in page] == [
        ("art_10", {"note": "n10"}),
        ("art_09", {"note": "n9"}),
    ]
    assert sorted(read) == [LISTING_SUMMARY] * 3 + ["metadata.json"] * 2


@pytest.mark.parametrize("damage", ["emptied", "rotted in place"])
async def test_a_record_damaged_behind_the_summary_is_skipped_and_named(tmp_path, caplog, damage):
    """#2931's containment, through the summary. Bug caught: a summary entry read as the artifact
    after its metadata was damaged, so a listing returns a record nothing can read; or the damaged
    record counted towards an offset, shifting a page against the walk. "Rotted in place" keeps
    the file's inode, size and mtime, so only the page's read of the metadata can see it."""
    vault = FilesystemArtifactVault(base_dir=tmp_path)
    for n in range(4):
        await vault.store(_ref(f"art_{n}", created_at=T0 + timedelta(minutes=n)), b"x")
    meta = vault._artifact_dir_for_ref(_ref("art_3")) / "metadata.json"
    if damage == "emptied":
        meta.write_bytes(b"")
    else:
        before = meta.stat()
        with open(meta, "r+b") as f:
            f.write(b"\x00" * before.st_size)
        os.utime(meta, ns=(before.st_atime_ns, before.st_mtime_ns))
        assert _identity(meta.stat()) == _identity(before)

    with caplog.at_level(logging.WARNING, logger=fav.__name__):
        page = await vault.list_artifacts(project_id="proj", limit=2, offset=0)
        again = await vault.list_artifacts(project_id="proj", limit=2, offset=1)
    named = [r.path for r in caplog.records if r.getMessage() == "artifact_record_unreadable"]

    assert [r.artifact_id for r in page] == ["art_2", "art_1"]
    assert again == vault._walk_listing(_Filters("proj", None, None, None, None), 2, 1)
    assert [r.artifact_id for r in again] == ["art_1", "art_0"]
    assert named == ["proj/cyc_1/run_1/art_3/metadata.json"] * 2  # every listing names it


def _read_only_vault(base: Path):
    spec = importlib.util.spec_from_file_location("read_only_vault", _READ_ONLY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.ReadOnlyVault(base_dir=base)


def _tree(base: Path) -> dict[str, tuple[int, int]]:
    return {
        str(p.relative_to(base)): (p.stat().st_ino, p.stat().st_mtime_ns) for p in base.rglob("*")
    }


async def test_a_read_only_vault_rebuilds_summaries_in_memory_and_never_writes(tmp_path):
    """The host's read-only scripts. Bug caught: a listing's repair writing the deploy's vault
    through the subclass that must never write; or the summary it keeps in memory read stale after
    the deploy promotes an artifact."""
    deploy = FilesystemArtifactVault(base_dir=tmp_path)
    for n in range(3):
        await deploy.store(_ref(f"art_{n}", created_at=T0 + timedelta(minutes=n)), b"x")
    for summary in tmp_path.rglob(LISTING_SUMMARY):
        summary.unlink()  # a vault the deploy wrote before #2973
    tree = _tree(tmp_path)
    read_only = _read_only_vault(tmp_path)

    first = await read_only.list_artifacts(project_id="proj")
    assert _tree(tmp_path) == tree
    await deploy.promote_artifact("art_0")
    promoted = await read_only.list_artifacts(project_id="proj", promotion_status="promoted")

    assert [r.artifact_id for r in first] == ["art_2", "art_1", "art_0"]
    assert [r.artifact_id for r in promoted] == ["art_0"]
    assert not list(tmp_path.rglob("*.tmp"))


async def test_a_summary_that_cannot_be_written_fails_neither_the_store_nor_the_listing(
    tmp_path, monkeypatch, caplog
):
    """Bug caught: a committed artifact reported as a failed store because its cache couldn't be
    written (the caller retries an artifact that exists), or a listing failing on a reader that
    can't write the vault. Either is named."""
    vault = FilesystemArtifactVault(base_dir=tmp_path)
    real = fav._write_atomically

    def disk_full_at_summary(path, data, mode):
        if path.name == LISTING_SUMMARY:
            raise OSError(28, "No space left on device")
        real(path, data, mode)

    monkeypatch.setattr(fav, "_write_atomically", disk_full_at_summary)
    with caplog.at_level(logging.WARNING, logger=fav.__name__):
        stored = await vault.store(_ref("art_1"), b"x")
        listed = await vault.list_artifacts(project_id="proj")

    assert listed == [stored]
    unwritten = [
        r for r in caplog.records if r.getMessage() == "artifact_listing_summary_unwritten"
    ]
    assert [r.path for r in unwritten] == [f"proj/cyc_1/run_1/{LISTING_SUMMARY}"] * 2
