"""
Filesystem artifact vault adapter (SIP-0064).

Stores artifact bytes to local filesystem with JSON sidecar metadata.
Vault enforces integrity (content_hash, vault_uri) but NOT business policy (T6).

Durability (#2931). ``store()`` writes in this order, each step a temp file beside its target that is
fsynced, renamed into place, and followed by an fsync of its directory:

1. the content;
2. the metadata, carrying the content's ``content_hash`` and ``size_bytes``. **Its rename is the
   commit point:** an artifact exists when its metadata is readable and its content matches it;
3. the artifact-id index;
4. the listing summary of the artifact's run (below).

``store()`` returns only then, so a checkpoint in Postgres can never reference an artifact the
disk didn't keep. A crash before step 2 leaves content with no metadata, which is no artifact.
The baselines file and the index are written the same way.

A record that exists but can't be read whole (metadata that doesn't parse; content missing, or not
the size or hash its metadata records) is ``ArtifactUnreadableError`` to a read that needs it: a
retrieve, a metadata read, a baseline's resolution. A listing skips it and names it in a structured
warning (``artifact_record_unreadable``), so one damaged file can't fail a listing for another run.

Listing (#2973). A listing reads, for each directory of artifacts in its scope (a run's, or a
project's unattached ones), that directory's listing summary (``.listing.json``): each artifact's
project, cycle, run, type, promotion status and creation time, and the identity of the metadata file
they were read from (inode, size, mtime). It is a cache of the metadata, never a record of its own:

- an artifact directory the summary doesn't name, or whose metadata isn't the file its entry was
  read from (a rewrite renames a new file into place, so its identity changes), is read from its
  metadata, and an entry whose directory or metadata is gone is dropped. So a crash between the
  metadata's rename and the summary's write, a lost race between a listing's repair and a store,
  or a summary that is missing or doesn't parse, never hides a committed artifact or lists a
  stale one: the summary is behind, and the listing reads the tree where it is;
- a summary a listing found behind is written back, by the same writer;
- the page a listing returns is read from its metadata, so a record damaged since it was summarized
  is skipped and named, as the walk did.

A listing finds an artifact where ``store()`` put it, ``<project>/<cycle>/<run>/`` or
``<project>/_unattached/``, the assumption the walk's narrowing to a project already made.

Layout:
  <base_dir>/
    <project_id>/<cycle_id>/<run_id>/<artifact_id>/metadata.json + <filename>
    <project_id>/<cycle_id>/<run_id>/.listing.json
    <project_id>/.baselines.json
    <project_id>/_unattached/<artifact_id>/metadata.json + <filename>
    <project_id>/_unattached/.listing.json
    _index.json   (artifact_id → relative path)
"""

from __future__ import annotations

import asyncio
import dataclasses
import hashlib
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import NamedTuple

from squadops.cycles.artifact_names import artifact_filename_refusal
from squadops.cycles.models import ArtifactNotFoundError, ArtifactRef, ArtifactUnreadableError
from squadops.ports.cycles.artifact_vault import ArtifactVaultPort

logger = logging.getLogger(__name__)

_DEFAULT_BASE_DIR = Path("data/artifacts")

#: Where a project's artifacts attached to no run live (the layout above).
UNATTACHED = "_unattached"
#: A directory of artifacts' listing summary (#2973): a cache of its artifacts' metadata.
LISTING_SUMMARY = ".listing.json"
#: The summary's format. A summary in another is read as missing, and rebuilt from the tree.
_LISTING_FORMAT = 1


class _Listed(NamedTuple):
    """One artifact as its directory's listing summary holds it: what a listing filters and sorts
    on, with the identity of the metadata file it was read from."""

    artifact_id: str
    project_id: str
    cycle_id: str | None
    run_id: str | None
    artifact_type: str
    promotion_status: str
    #: ``str(created_at)``: the listing's sort key, as the walk computed it.
    created_at: str
    #: The metadata file's (inode, size, mtime_ns) when this entry was read from it.
    metadata_identity: tuple[int, int, int]

    @classmethod
    def of(cls, ref: ArtifactRef, stat: os.stat_result) -> _Listed:
        return cls(
            ref.artifact_id,
            ref.project_id,
            ref.cycle_id,
            ref.run_id,
            ref.artifact_type,
            ref.promotion_status,
            str(ref.created_at),
            _identity(stat),
        )


class _Filters(NamedTuple):
    """A listing's filters. Each is applied when it is truthy, as the walk applied them."""

    project_id: str | None
    cycle_id: str | None
    run_id: str | None
    artifact_type: str | None
    promotion_status: str | None

    def match(self, record: ArtifactRef | _Listed) -> bool:
        return not (
            (self.project_id and record.project_id != self.project_id)
            or (self.cycle_id and record.cycle_id != self.cycle_id)
            or (self.run_id and record.run_id != self.run_id)
            or (self.artifact_type and record.artifact_type != self.artifact_type)
            or (self.promotion_status and record.promotion_status != self.promotion_status)
        )


def _identity(stat: os.stat_result) -> tuple[int, int, int]:
    return (stat.st_ino, stat.st_size, stat.st_mtime_ns)


class FilesystemArtifactVault(ArtifactVaultPort):
    """Stores artifacts on the local filesystem in a hierarchical layout."""

    def __init__(self, base_dir: str | Path | None = None) -> None:
        self._base_dir = Path(base_dir) if base_dir else _DEFAULT_BASE_DIR
        self._base_dir.mkdir(parents=True, exist_ok=True)
        if not self._index_path.exists():
            self._rebuild_index()

    # --- Index management ---

    @property
    def _index_path(self) -> Path:
        return self._base_dir / "_index.json"

    def _load_index(self) -> dict[str, str]:
        if not self._index_path.exists():
            return {}
        try:
            index = json.loads(self._index_path.read_text())
        except ValueError:
            index = None
        if not isinstance(index, dict):
            # #2931: an index a power loss left empty is rebuilt from the tree, which holds every
            # id it maps, rather than failing every lookup.
            logger.warning(
                "artifact_index_unreadable_rebuilt", extra={"path": str(self._index_path)}
            )
            index = self._index_from_tree()
            self._replace_unreadable_index(index)
        return index

    def _replace_unreadable_index(self, index: dict[str, str]) -> None:
        """Where an index rebuilt from the tree goes: written over the unreadable one."""
        self._save_index(index)

    def _save_index(self, index: dict[str, str]) -> None:
        _write_json_atomically(self._index_path, index)

    def _update_index(self, artifact_id: str, rel_path: str) -> None:
        index = self._load_index()
        index[artifact_id] = rel_path
        self._save_index(index)

    def _rebuild_index(self) -> None:
        self._save_index(self._index_from_tree())

    def _index_from_tree(self) -> dict[str, str]:
        index: dict[str, str] = {}
        for meta_path in self._base_dir.rglob("metadata.json"):
            art_dir = meta_path.parent
            # The artifact_id is the last component of the path
            index[art_dir.name] = str(art_dir.relative_to(self._base_dir))
        return index

    # --- Path helpers ---

    def _contained_content_path(self, art_dir: Path, filename: str) -> Path:
        """Where an artifact's content is written, refused unless it is inside the artifact's own
        directory, and that directory inside the vault. Every caller depends on this: a filename
        or an id that climbs out (``..``, an absolute path) would otherwise be written wherever the
        process can write."""
        refusal = artifact_filename_refusal(filename)
        if refusal is not None:
            raise ValueError(f"artifact filename {filename!r} refused: {refusal}")
        base = self._base_dir.resolve()
        resolved_dir = art_dir.resolve()
        if not resolved_dir.is_relative_to(base):
            raise ValueError(f"artifact directory {art_dir} is outside the vault {base}")
        if not (resolved_dir / filename).resolve().is_relative_to(resolved_dir):
            raise ValueError(f"artifact filename {filename!r} resolves outside its artifact")
        # The checks read resolved paths; the path written, and recorded as ``vault_uri``, keeps
        # the form it always had.
        return art_dir / filename

    def _artifact_dir_for_ref(self, ref: ArtifactRef) -> Path:
        if ref.cycle_id and ref.run_id:
            return self._base_dir / ref.project_id / ref.cycle_id / ref.run_id / ref.artifact_id
        return self._base_dir / ref.project_id / UNATTACHED / ref.artifact_id

    def _baselines_path_for_project(self, project_id: str) -> Path:
        return self._base_dir / project_id / ".baselines.json"

    # --- Port implementation ---

    async def store(self, artifact: ArtifactRef, content: bytes) -> ArtifactRef:
        art_dir = self._artifact_dir_for_ref(artifact)
        content_path = self._contained_content_path(art_dir, artifact.filename)
        art_dir.mkdir(parents=True, exist_ok=True)

        content_hash = hashlib.sha256(content).hexdigest()

        content_path.parent.mkdir(parents=True, exist_ok=True)
        _write_atomically(content_path, content, CONTENT_MODE)

        vault_uri = str(content_path)

        updated = dataclasses.replace(
            artifact,
            content_hash=content_hash,
            size_bytes=len(content),
            vault_uri=vault_uri,
        )

        meta_path = art_dir / "metadata.json"
        self._write_metadata(meta_path, updated)

        rel_path = str(art_dir.relative_to(self._base_dir))
        self._update_index(artifact.artifact_id, rel_path)
        self._record_in_listing(art_dir)

        logger.info("Stored artifact %s at %s", artifact.artifact_id, vault_uri)
        return updated

    async def retrieve(self, artifact_id: str) -> tuple[ArtifactRef, bytes]:
        art_dir = self._resolve_artifact_dir(artifact_id)
        meta_path = art_dir / "metadata.json"
        if not meta_path.exists():
            raise ArtifactNotFoundError(f"Artifact not found: {artifact_id}")

        ref = self._load_metadata(meta_path)
        content_path = art_dir / ref.filename
        try:
            content = content_path.read_bytes()
        except FileNotFoundError:
            raise ArtifactUnreadableError(
                f"Artifact {artifact_id} is unreadable: its content {ref.filename!r} is missing"
            ) from None
        if (ref.size_bytes is not None and len(content) != ref.size_bytes) or (
            ref.content_hash and hashlib.sha256(content).hexdigest() != ref.content_hash
        ):
            raise ArtifactUnreadableError(
                f"Artifact {artifact_id} is unreadable: its content doesn't match the size and "
                "hash its metadata records"
            )
        return ref, content

    async def get_metadata(self, artifact_id: str) -> ArtifactRef:
        art_dir = self._resolve_artifact_dir(artifact_id)
        meta_path = art_dir / "metadata.json"
        if not meta_path.exists():
            raise ArtifactNotFoundError(f"Artifact not found: {artifact_id}")
        return self._load_metadata(meta_path)

    async def promote_artifact(self, artifact_id: str) -> ArtifactRef:
        art_dir = self._resolve_artifact_dir(artifact_id)
        meta_path = art_dir / "metadata.json"
        if not meta_path.exists():
            raise ArtifactNotFoundError(f"Artifact not found: {artifact_id}")

        ref = self._load_metadata(meta_path)
        if ref.promotion_status == "promoted":
            return ref  # Idempotent

        updated = dataclasses.replace(ref, promotion_status="promoted")
        self._write_metadata(meta_path, updated)
        self._record_in_listing(art_dir)
        return updated

    async def list_artifacts(
        self,
        *,
        project_id: str | None = None,
        cycle_id: str | None = None,
        run_id: str | None = None,
        artifact_type: str | None = None,
        promotion_status: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[ArtifactRef]:
        if not self._base_dir.exists():
            return []
        filters = _Filters(project_id, cycle_id, run_id, artifact_type, promotion_status)
        # #2921: a listing reads the disk, so it runs in a worker thread, off the event loop. Every
        # file it reads is written whole and renamed into place (`_write_atomically`), so it never
        # reads one half-written while a store writes.
        return await asyncio.to_thread(self._listing, filters, limit, offset)

    async def set_baseline(self, project_id: str, artifact_type: str, artifact_id: str) -> None:
        # Verify artifact exists via index
        art_dir = self._resolve_artifact_dir(artifact_id)
        if not (art_dir / "metadata.json").exists():
            raise ArtifactNotFoundError(f"Artifact not found: {artifact_id}")

        baselines = self._load_baselines(project_id)
        baselines[artifact_type] = artifact_id
        self._save_baselines(project_id, baselines)

    async def get_baseline(self, project_id: str, artifact_type: str) -> ArtifactRef | None:
        baselines = self._load_baselines(project_id)
        artifact_id = baselines.get(artifact_type)
        if artifact_id is None:
            return None
        try:
            return await self.get_metadata(artifact_id)
        except ArtifactNotFoundError:
            return None

    async def list_baselines(self, project_id: str) -> dict[str, ArtifactRef]:
        baselines = self._load_baselines(project_id)
        result = {}
        for art_type, artifact_id in baselines.items():
            try:
                ref = await self.get_metadata(artifact_id)
                result[art_type] = ref
            except ArtifactNotFoundError:
                continue
        return result

    # --- Internal helpers ---

    def _resolve_artifact_dir(self, artifact_id: str) -> Path:
        """Look up artifact_id in the index and return its directory."""
        index = self._load_index()
        rel_path = index.get(artifact_id)
        if rel_path is None:
            raise ArtifactNotFoundError(f"Artifact not found: {artifact_id}")
        return self._base_dir / rel_path

    def _listing(self, filters: _Filters, limit: int | None, offset: int) -> list[ArtifactRef]:
        """A listing's page (#2973): its scope's listing summaries, brought up to date with the
        tree, filtered and sorted; then the page's records, read from their metadata."""
        groups = self._listing_groups(filters)
        if groups is None:
            return self._walk_listing(filters, limit, offset)
        candidates: list[tuple[Path, str, _Listed]] = []
        for group in groups:
            for name, listed in self._current_listing(group).items():
                if filters.match(listed):
                    candidates.append((group, name, listed))
        # #1976: newest first, then by id, so a page is stable. Timestamps compare as ISO text, as
        # progress sorts them: text never raises on a naive timestamp beside an aware one.
        candidates.sort(key=lambda c: c[2].artifact_id)
        candidates.sort(key=lambda c: c[2].created_at, reverse=True)
        page: list[ArtifactRef] = []
        damaged: dict[Path, list[str]] = {}
        for group, name, _ in candidates[offset:]:
            if limit is not None and len(page) >= limit:
                break
            meta_path = group / name / "metadata.json"
            try:
                ref = self._load_metadata(meta_path)
            except FileNotFoundError:
                continue  # removed since the summary was read
            except ArtifactUnreadableError as e:
                # Damaged in place since it was summarized, its file's identity unchanged (the
                # vault's own writes rename a new file into place). Skipped and named, as the walk
                # skips it, and dropped from its summary, so the next listing's offsets don't
                # count it.
                self._name_unreadable(meta_path, e)
                damaged.setdefault(group, []).append(name)
                continue
            if filters.match(ref):  # rewritten since, by a store the listing raced
                page.append(ref)
        for group, names in damaged.items():
            summary = self._load_listing_summary(group)
            for name in names:
                summary.pop(name, None)
            self._save_listing_summary_or_name_it(group, summary)
        return page

    def _walk_listing(self, filters: _Filters, limit: int | None, offset: int) -> list[ArtifactRef]:
        """A listing by walking every metadata file under its narrowest directory: the listing
        before #2973, kept for a scope the layout can't name (an id spelled ``_unattached``)."""
        if filters.project_id and filters.cycle_id and filters.run_id:
            scan_dir = self._base_dir / filters.project_id / filters.cycle_id / filters.run_id
        elif filters.project_id and filters.cycle_id:
            scan_dir = self._base_dir / filters.project_id / filters.cycle_id
        elif filters.project_id:
            scan_dir = self._base_dir / filters.project_id
        else:
            scan_dir = self._base_dir
        results: list[ArtifactRef] = []
        self._collect_artifacts(scan_dir, results, *filters)
        results.sort(key=lambda r: r.artifact_id)
        results.sort(key=lambda r: str(r.created_at), reverse=True)
        return results[offset:] if limit is None else results[offset : offset + limit]

    def _listing_groups(self, filters: _Filters) -> list[Path] | None:
        """Every directory of artifacts a listing with ``filters`` must read, by the layout: each
        run directory its project, cycle and run filters allow, and each project's unattached
        directory, unless the listing names both a project and a cycle (as the walk scanned only
        that cycle's directory). ``None`` for a scope the layout can't name."""
        if UNATTACHED in (filters.project_id, filters.cycle_id, filters.run_id):
            return None
        projects = (
            [self._base_dir / filters.project_id]
            if filters.project_id
            else _subdirectories(self._base_dir)
        )
        with_unattached = not (filters.project_id and filters.cycle_id)
        groups: list[Path] = []
        for project in projects:
            if with_unattached and (project / UNATTACHED).is_dir():
                groups.append(project / UNATTACHED)
            if filters.cycle_id:
                cycles = [project / filters.cycle_id]
            else:
                cycles = [c for c in _subdirectories(project) if c.name != UNATTACHED]
            for cycle in cycles:
                if filters.run_id:
                    if (cycle / filters.run_id).is_dir():
                        groups.append(cycle / filters.run_id)
                else:
                    groups.extend(_subdirectories(cycle))
        return groups

    def _current_listing(self, group: Path) -> dict[str, _Listed]:
        """``group``'s artifacts, by directory name, from its listing summary where the summary is
        current and from their metadata where it is behind; written back when it was behind."""
        # Strings, not Paths, per artifact: a project holds tens of thousands, and building a Path
        # for each cost a listing more than reading its summaries did.
        directory = str(group)
        names = _subdirectory_names(directory)
        summary = self._load_listing_summary(group)
        current: dict[str, _Listed] = {}
        changed = False
        for name in names:
            meta_path = f"{directory}/{name}/metadata.json"
            listed = summary.get(name)
            try:
                if listed is None or listed.metadata_identity != _identity(os.stat(meta_path)):
                    listed = self._listed_from_metadata(Path(meta_path))
                    changed = True
            except FileNotFoundError:
                continue  # content with no metadata, which is no artifact; or removed since
            except ArtifactUnreadableError as e:
                self._name_unreadable(Path(meta_path), e)
                continue
            current[name] = listed
        if changed or current.keys() != summary.keys():
            self._save_listing_summary_or_name_it(group, current)
        return current

    def _listed_from_metadata(self, meta_path: Path) -> _Listed:
        """``meta_path``'s artifact as a summary entry. The identity is the open file's, so an entry
        never pairs one file's fields with another's identity, however a write races the read."""
        with open(meta_path, "rb") as f:
            stat = os.fstat(f.fileno())
            text = f.read()
        return _Listed.of(self._parsed_metadata(meta_path, text), stat)

    def _record_in_listing(self, art_dir: Path) -> None:
        """The artifact just committed to ``art_dir``, into its directory's listing summary, read
        back from its metadata as a listing would read it. After the commit point the artifact
        exists, and a summary is a cache a listing repairs, so a summary that can't be written is
        named, not raised: the store did not fail."""
        group = art_dir.parent
        try:
            listed = self._listed_from_metadata(art_dir / "metadata.json")
            summary = self._load_listing_summary(group)
            summary[art_dir.name] = listed
            self._save_listing_summary(group, summary)
        except (OSError, ArtifactUnreadableError) as e:
            self._name_unwritten_summary(group, e)

    def _load_listing_summary(self, group: Path) -> dict[str, _Listed]:
        """``group``'s listing summary, or ``{}`` (every entry behind) when it is missing, can't be
        read, doesn't parse or is in another format."""
        path = group / LISTING_SUMMARY
        try:
            data = json.loads(path.read_bytes())
            if data.get("format") != _LISTING_FORMAT:
                return {}
            return {
                name: _Listed._make([*fields[:-1], tuple(fields[-1])])
                for name, fields in data["artifacts"].items()
            }
        except FileNotFoundError:
            return {}
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            logger.warning(
                "artifact_listing_summary_unreadable",
                extra={"path": str(path.relative_to(self._base_dir))},
            )
            return {}

    def _save_listing_summary(self, group: Path, summary: dict[str, _Listed]) -> None:
        data = {
            "format": _LISTING_FORMAT,
            "fields": list(_Listed._fields),
            "artifacts": {name: list(listed) for name, listed in sorted(summary.items())},
        }
        _write_atomically(
            group / LISTING_SUMMARY, json.dumps(data, separators=(",", ":")).encode(), METADATA_MODE
        )

    def _save_listing_summary_or_name_it(self, group: Path, summary: dict[str, _Listed]) -> None:
        """A listing's repair, written back so the next listing reads it. A listing that can't
        write it (a reader without write access to the vault) still answers from the tree."""
        try:
            self._save_listing_summary(group, summary)
        except OSError as e:
            self._name_unwritten_summary(group, e)

    def _name_unwritten_summary(self, group: Path, error: Exception) -> None:
        logger.warning(
            "artifact_listing_summary_unwritten",
            extra={
                "path": str((group / LISTING_SUMMARY).relative_to(self._base_dir)),
                "reason": f"{type(error).__name__}: {error}",
            },
        )

    def _name_unreadable(self, meta_path: Path, error: ArtifactUnreadableError) -> None:
        # #2931: one damaged record failed every listing that walked past it, a completed run's
        # included. It is skipped and named; a read that needs it still refuses.
        logger.warning(
            "artifact_record_unreadable",
            extra={"path": str(meta_path.relative_to(self._base_dir)), "reason": str(error)},
        )

    @staticmethod
    def _write_metadata(meta_path: Path, ref: ArtifactRef) -> None:
        """``ref`` as ``meta_path``'s metadata: the commit point."""
        meta = dataclasses.asdict(ref)
        for key in ("created_at",):
            if meta.get(key) is not None:
                meta[key] = str(meta[key])
        _write_json_atomically(meta_path, meta)

    def _collect_artifacts(
        self,
        scan_dir: Path,
        results: list[ArtifactRef],
        project_id: str | None,
        cycle_id: str | None,
        run_id: str | None,
        artifact_type: str | None,
        promotion_status: str | None = None,
    ) -> None:
        if not scan_dir.exists():
            return
        for meta_path in scan_dir.rglob("metadata.json"):
            try:
                ref = self._load_metadata(meta_path)
            except ArtifactUnreadableError as e:
                self._name_unreadable(meta_path, e)
                continue
            if _Filters(project_id, cycle_id, run_id, artifact_type, promotion_status).match(ref):
                results.append(ref)

    def _load_metadata(self, meta_path: Path) -> ArtifactRef:
        """The record ``meta_path`` holds, or ``ArtifactUnreadableError`` naming the artifact when
        it doesn't parse (an empty file after a power loss, #2931) or doesn't hold an artifact."""
        return self._parsed_metadata(meta_path, meta_path.read_bytes())

    def _parsed_metadata(self, meta_path: Path, text: bytes) -> ArtifactRef:
        try:
            return self._parse_metadata(text)
        except (ValueError, TypeError, KeyError) as e:
            raise ArtifactUnreadableError(
                f"Artifact {meta_path.parent.name} is unreadable: its metadata doesn't parse "
                f"({type(e).__name__})"
            ) from e

    @staticmethod
    def _parse_metadata(text: str | bytes) -> ArtifactRef:
        data = json.loads(text)
        if not isinstance(data, dict):
            raise TypeError("metadata is not an object")
        from datetime import datetime

        if isinstance(data.get("created_at"), str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        # D19: Legacy artifacts without promotion_status default to "working" at read time
        if "promotion_status" not in data:
            data["promotion_status"] = "working"
        # SIP-0084: JSON arrays → tuples for provenance tuple fields
        for key in (
            "system_fragment_ids",
            "system_fragment_versions",
            "capability_supplement_ids",
        ):
            if isinstance(data.get(key), list):
                data[key] = tuple(data[key])
        return ArtifactRef(**data)

    def _load_baselines(self, project_id: str) -> dict:
        path = self._baselines_path_for_project(project_id)
        if not path.exists():
            return {}
        try:
            baselines = json.loads(path.read_text())
        except ValueError:
            baselines = None
        if not isinstance(baselines, dict):
            # Never read as "no baseline": a damaged record refuses the read that needs it (#2931).
            raise ArtifactUnreadableError(f"Project {project_id}'s baselines record doesn't parse")
        return baselines

    def _save_baselines(self, project_id: str, baselines: dict) -> None:
        path = self._baselines_path_for_project(project_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        _write_json_atomically(path, baselines)


#: A metadata file's mode: readable by every reader of the vault, as `write_text` left it (#2921's follow-up).
METADATA_MODE = 0o644
#: A content file's mode: as `write_bytes` left it under the default umask, before #2931.
CONTENT_MODE = 0o644


def _subdirectory_names(directory: str | Path) -> list[str]:
    """The names of ``directory``'s subdirectories, or none when it isn't one."""
    try:
        with os.scandir(directory) as entries:
            return [e.name for e in entries if e.is_dir()]
    except (FileNotFoundError, NotADirectoryError):
        return []


def _subdirectories(directory: Path) -> list[Path]:
    return [directory / name for name in _subdirectory_names(directory)]


def _write_json_atomically(path: Path, data: object) -> None:
    """``data`` as JSON, written by ``_write_atomically``."""
    _write_atomically(path, json.dumps(data, indent=2).encode(), METADATA_MODE)


def _write_atomically(path: Path, data: bytes, mode: int) -> None:
    """Writes ``data`` to a temporary file beside ``path``, fsyncs it, renames it into place, then
    fsyncs the directory, so the rename itself survives a power loss (#2931). A reader sees the old
    file or the new one, never a partial write (#2921: the artifact listing reads metadata files
    from a worker thread while the vault writes them)."""
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with open(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        # mkstemp creates the file 0600. The vault is read by more than the process that writes it:
        # the release capture, the verification-set driver and triage read it from the host as
        # another user.
        Path(tmp).chmod(mode)
        Path(tmp).replace(path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    _fsync_directory(path.parent)


def _fsync_directory(directory: Path) -> None:
    """A rename is durable only once its directory is: fsync the directory's own entry."""
    fd = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
