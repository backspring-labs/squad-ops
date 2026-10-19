"""Disk-backed cycle workspace store (SIP-0102 §4.6 — phase 102.1 slice b).

Implements the confirmed storage decision: one bind-mountable directory per
cycle holding the live tree, plus content-hash revision manifests. The live
tree is the single content instance; revisions pin it by hash (a full
content-addressed store is the open-question-2 upgrade path and changes the
capture mechanism, never these semantics).

All state is on disk — a store constructed over the same root after a service
restart sees every revision, head pointer, and lease (§7 item 12). Timestamps
and clocks are caller-supplied.

Layout per cycle::

    <root>/<cycle_id>/workspace/            the live tree
    <root>/<cycle_id>/revisions/<id>.json   revision metadata + file-hash manifest
    <root>/<cycle_id>/revisions/HEAD        latest revision id
    <root>/<cycle_id>/lease.json            {"expires_at": <epoch seconds>}
    <root>/<cycle_id>/copies/<id>/          a disposable copy, while a declared command runs

The operation journal shares the cycle's directory (``evidence/``, SIP-0102 §7 item 11) and is
not the store's: removing a workspace removes the entries above and keeps it (#2473).
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import stat
import uuid
from collections.abc import Collection, Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path

from squadops.sandbox.models import (
    FileContent,
    RevisionOrigin,
    WorkspaceRevision,
    compute_revision_id,
    content_bytes,
)

_CYCLE_ID_RE = re.compile(r"[A-Za-z0-9_\-]+")

# Derived/dependency state is NOT revision content (§4.6/§4.7): per-cycle
# installs land inside the sandbox (venv, node_modules, the lockfile npm
# install generates) and builds emit outputs (dist) — all of it lives in the
# workspace but never in the pin, or the first install would break every
# stale-base check and pin verification (live-smoke-proven: npm install
# writes frontend/package-lock.json). Promotion into revision content —
# including lockfile-as-evidence capture (§4.7) — is an explicit §4.6
# boundary, never implicit inclusion.
_EXCLUDED_SEGMENTS = frozenset(
    {
        ".sandbox-venv",
        "node_modules",
        "dist",
        # `next build`'s output, stack #2's equivalent of `dist` (measured 2026-08-15
        # auditing SIP-0104 window roll 1): omitting it did not merely over-pin, it
        # CRASHED pin verification — `.next/` holds webpack caches and compiled chunks,
        # and `current_files` reads every unexcluded file as UTF-8, so the first
        # non-text byte raised UnicodeDecodeError and the app never reached boot. Added
        # when #822 brought a second stack whose build output is not named `dist`.
        ".next",
        "__pycache__",
        ".pytest_cache",
        ".git",
        "package-lock.json",
    }
)


class WorkspaceStoreError(Exception):
    """Base error for workspace-store violations."""


class WorkspaceEscapeError(WorkspaceStoreError):
    """A path tried to leave the cycle workspace (§7 item 8)."""


class StaleBaseRevisionError(WorkspaceStoreError):
    """A patch's base revision does not match the live tree — applying it
    would mint a revision whose content is not derivable from base + patch."""


class AlreadySeededError(WorkspaceStoreError):
    """Seed attempted on a workspace that already has different content."""


def _safe_relpath(path: str, *, tracked: Collection[str] | None = ()) -> str:
    """Normalize a workspace-relative path; reject anything that could escape
    the cycle workspace (§7 item 8: agents cannot supply host paths).

    A derived-state name is refused unless ``tracked`` names the path as
    content (X-2, #2420): a checkout's tracked ``package-lock.json``, or one a
    patch's base revision holds. ``None`` means every path given is tracked, a
    Git checkout's own set. A repository's ``.git`` is never content: the
    sandbox never runs Git."""
    norm = str(path).strip().replace("\\", "/")
    if not norm or norm.startswith("/") or norm.startswith("~"):
        raise WorkspaceEscapeError(f"not a workspace-relative path: {path!r}")
    parts = [p for p in norm.split("/") if p not in ("", ".")]
    if not parts or ".." in parts or any(":" in p for p in parts):
        raise WorkspaceEscapeError(f"not a workspace-relative path: {path!r}")
    rel = "/".join(parts)
    if ".git" in parts:
        raise WorkspaceEscapeError(f"a repository's .git is never revision content: {path!r}")
    if _EXCLUDED_SEGMENTS.intersection(parts) and tracked is not None and rel not in tracked:
        raise WorkspaceEscapeError(
            f"derived-state path is not revision content: {path!r} "
            "(installs/build outputs live in the sandbox but are never seeded or patched)"
        )
    return rel


def tree_path(path: str) -> str:
    """A file's path in a tree the sandbox writes outside a workspace, an evaluated tree's copy
    (X-3b, #2414): every name is content, as in a checkout, and the path is refused unless it is
    already in its normal form inside the tree, so no key writes outside the copy."""
    rel = _safe_relpath(path, tracked=None)
    if rel != path:
        raise WorkspaceEscapeError(f"not a tree path in its normal form: {path!r}")
    return rel


def working_directory(path: str) -> str:
    """A declared command's working directory, repository-relative (X-3a, #2421): ``""`` for the
    tree's root, refused when it would leave the tree."""
    return "" if str(path).strip() in ("", ".") else _safe_relpath(path, tracked=None)


# The lease goes last, so a removal a crash interrupts is still leased and the next sweep finishes it.
_STORE_ENTRIES = ("workspace", "copies", "revisions", "lease.json")


def _remove_store_entries(cycle_dir: Path) -> None:
    """Remove what the store wrote under ``cycle_dir`` and keep the rest (the operation journal's
    ``evidence/``); the directory goes once nothing is left in it."""
    for name in _STORE_ENTRIES:
        entry = cycle_dir / name
        if entry.is_dir():
            shutil.rmtree(entry)
        elif entry.exists():
            entry.unlink()
    if cycle_dir.is_dir() and not any(cycle_dir.iterdir()):
        cycle_dir.rmdir()


class WorkspaceStore:
    """Provisioning, revision bookkeeping, pin verification, and cleanup for
    cycle workspaces."""

    def __init__(self, root: Path) -> None:
        self._root = Path(root)

    # -- layout helpers -----------------------------------------------------

    def _cycle_dir(self, cycle_id: str) -> Path:
        if not _CYCLE_ID_RE.fullmatch(cycle_id):
            raise WorkspaceStoreError(f"invalid cycle id: {cycle_id!r}")
        return self._root / cycle_id

    def workspace_dir(self, cycle_id: str) -> Path:
        """The bind-mountable live tree for a cycle."""
        return self._cycle_dir(cycle_id) / "workspace"

    def _revisions_dir(self, cycle_id: str) -> Path:
        return self._cycle_dir(cycle_id) / "revisions"

    def _head_file(self, cycle_id: str) -> Path:
        return self._revisions_dir(cycle_id) / "HEAD"

    def _lease_file(self, cycle_id: str) -> Path:
        return self._cycle_dir(cycle_id) / "lease.json"

    # -- provisioning and content -------------------------------------------

    def provision(self, cycle_id: str) -> Path:
        """Create (idempotently) the cycle's workspace tree."""
        ws = self.workspace_dir(cycle_id)
        ws.mkdir(parents=True, exist_ok=True)
        self._revisions_dir(cycle_id).mkdir(parents=True, exist_ok=True)
        return ws

    def current_files(
        self, cycle_id: str, *, tracked: Collection[str] = ()
    ) -> dict[str, FileContent]:
        """The live tree as a path → content mapping, excluding derived state
        (``_EXCLUDED_SEGMENTS``) — revision content is source, not installs.
        A derived-state name that ``tracked`` holds is content (X-2, #2420).

        Each file is read as the bytes on disk (X-2, #2420): text when they are
        UTF-8, otherwise the bytes themselves. Never in universal-newline mode,
        which read a seeded ``\\r\\n`` file back as ``\\n`` and failed its own pin."""
        files: dict[str, FileContent] = {}
        for key, p in self._live_paths(cycle_id, tracked):
            data = p.read_bytes()
            try:
                content: FileContent = data.decode("utf-8")
            except UnicodeDecodeError:
                content = data
            files[key] = content
        return files

    def current_executables(
        self, cycle_id: str, *, tracked: Collection[str] = ()
    ) -> frozenset[str]:
        """The live tree's files whose owner-executable bit is set (X-2, #2420): a
        script a product's declared command runs directly, such as ``./gradlew``."""
        return frozenset(
            key for key, p in self._live_paths(cycle_id, tracked) if p.stat().st_mode & stat.S_IXUSR
        )

    def _live_paths(self, cycle_id: str, tracked: Collection[str]) -> list[tuple[str, Path]]:
        ws = self.workspace_dir(cycle_id)
        if not ws.is_dir():
            return []
        live: list[tuple[str, Path]] = []
        for p in sorted(ws.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(ws)
            key = str(rel).replace("\\", "/")
            if _EXCLUDED_SEGMENTS.intersection(rel.parts) and key not in tracked:
                continue
            live.append((key, p))
        return live

    # -- revisions ----------------------------------------------------------

    def _persist(
        self,
        revision: WorkspaceRevision,
        files: Mapping[str, FileContent],
        executable: Collection[str] | None = None,
    ) -> None:
        rev_dir = self._revisions_dir(revision.cycle_id)
        rev_dir.mkdir(parents=True, exist_ok=True)
        manifest: dict = {
            "revision": revision.to_dict(),
            "files": {
                p: hashlib.sha256(content_bytes(c)).hexdigest() for p, c in sorted(files.items())
            },
        }
        if executable is not None:
            manifest["executable"] = sorted(executable)
        (rev_dir / f"{revision.revision_id}.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
        self._head_file(revision.cycle_id).write_text(revision.revision_id, encoding="utf-8")

    def latest_revision(self, cycle_id: str) -> WorkspaceRevision | None:
        head = self._head_file(cycle_id)
        if not head.is_file():
            return None
        return self.get_revision(cycle_id, head.read_text(encoding="utf-8").strip())

    def _revision_paths(self, cycle_id: str, revision_id: str) -> frozenset[str]:
        """Every path a persisted revision holds as content (its manifest's files)."""
        return frozenset(self._manifest(cycle_id, revision_id).get("files", ()))

    def _revision_executables(self, cycle_id: str, revision_id: str) -> frozenset[str] | None:
        """The files a persisted revision holds as executable, or ``None`` when its lineage
        carries no modes. Modes are content only in a lineage that began at a repository's
        tracked tree (``RevisionOrigin.TRACKED_TREE``). A scaffold workspace's pin ignores
        them, as it always has, so a filesystem that reports every file executable (a
        Windows mount under WSL) can't break it."""
        manifest = self._manifest(cycle_id, revision_id)
        return frozenset(manifest["executable"]) if "executable" in manifest else None

    def _live_executables(
        self, cycle_id: str, revision_id: str, tracked: Collection[str]
    ) -> frozenset[str]:
        """The live executable bits a revision's pin compares: none, unless it carries modes."""
        if self._revision_executables(cycle_id, revision_id) is None:
            return frozenset()
        return self.current_executables(cycle_id, tracked=tracked)

    def _manifest(self, cycle_id: str, revision_id: str) -> dict:
        path = self._revisions_dir(cycle_id) / f"{revision_id}.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}

    def get_revision(self, cycle_id: str, revision_id: str) -> WorkspaceRevision | None:
        path = self._revisions_dir(cycle_id) / f"{revision_id}.json"
        if not path.is_file():
            return None
        manifest = json.loads(path.read_text(encoding="utf-8"))
        return WorkspaceRevision.from_dict(manifest["revision"])

    def seed(
        self,
        cycle_id: str,
        files: Mapping[str, FileContent],
        *,
        origin: str,
        executable: Collection[str] = (),
        created_at: str | None = None,
    ) -> WorkspaceRevision:
        """Write the initial tree and cut the first revision (§4.6 boundary).
        ``executable`` names the files to seed with their executable bit set
        (X-2, #2420), each one a file the seed carries.

        Idempotent for retries: re-seeding identical content returns the
        existing revision; re-seeding different content over a seeded
        workspace is an error, never a silent overwrite."""
        carries_modes = origin in RevisionOrigin.TRACKED_TREE
        if executable and not carries_modes:
            raise ValueError(
                "executable bits are carried only for a repository's tracked tree "
                f"(a {RevisionOrigin.GIT_CHECKOUT} seed), not a {origin} seed"
            )
        tracked = None if carries_modes else ()
        safe = {_safe_relpath(p, tracked=tracked): c for p, c in files.items()}
        modes = frozenset(_safe_relpath(p, tracked=tracked) for p in executable)
        if not modes <= safe.keys():
            raise ValueError(
                f"executable paths the seed doesn't carry: {sorted(modes - safe.keys())}"
            )
        head = self.latest_revision(cycle_id)
        if head is not None:
            if compute_revision_id(safe, modes) == head.revision_id:
                return head
            raise AlreadySeededError(f"cycle {cycle_id} is already seeded with other content")
        # Cut before writing: a seed the revision refuses (an unknown origin) must leave no
        # file behind, or the next seed's tree holds files its revision doesn't name.
        revision = WorkspaceRevision.cut(
            cycle_id=cycle_id, origin=origin, files=safe, executable=modes, created_at=created_at
        )
        ws = self.provision(cycle_id)
        for rel, content in safe.items():
            target = ws / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content_bytes(content))
            if rel in modes:
                target.chmod(target.stat().st_mode | 0o111)
        self._persist(revision, safe, modes if carries_modes else None)
        return revision

    def apply_patch(
        self,
        cycle_id: str,
        *,
        base_revision_id: str,
        files: Mapping[str, FileContent | None],
        origin: str,
        created_at: str | None = None,
    ) -> tuple[WorkspaceRevision, tuple[str, ...]]:
        """Apply path → content changes (``None`` = delete) on top of ``base``
        and cut the next revision. The live tree must still match ``base`` —
        otherwise the new revision's content would not be derivable from
        base + patch, and the patch is stale (§4.6)."""
        base = self.get_revision(cycle_id, base_revision_id)
        if base is None:
            raise WorkspaceStoreError(f"unknown base revision: {base_revision_id}")
        base_paths = self._revision_paths(cycle_id, base_revision_id)
        current = self.current_files(cycle_id, tracked=base_paths)
        live_modes = self._live_executables(cycle_id, base_revision_id, base_paths)
        if not base.matches(current, live_modes):
            raise StaleBaseRevisionError(
                f"live tree no longer matches base revision {base_revision_id}"
            )
        changed: list[str] = []
        merged = dict(current)
        for path, content in files.items():
            rel = _safe_relpath(path, tracked=base_paths)
            changed.append(rel)
            if content is None:
                merged.pop(rel, None)
            else:
                merged[rel] = content
        # A patched file keeps its mode (writing in place keeps it), and a deleted one drops
        # out; a file the patch adds is not executable. A lineage without modes stays without.
        base_modes = self._revision_executables(cycle_id, base_revision_id)
        modes = None if base_modes is None else base_modes & merged.keys()
        # Merge and cut before touching the tree: a patch refused part-way (an escaping path,
        # an unknown origin) must leave the live tree on its base, or every later patch is stale.
        revision = WorkspaceRevision.cut(
            cycle_id=cycle_id,
            origin=origin,
            files=merged,
            executable=modes or (),
            parent=base,
            created_at=created_at,
        )
        ws = self.workspace_dir(cycle_id)
        for rel in changed:
            target = ws / rel
            if rel in merged:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content_bytes(merged[rel]))
            else:
                target.unlink(missing_ok=True)
        self._persist(revision, merged, modes)
        return revision, tuple(sorted(changed))

    @contextmanager
    def disposable_copy(self, cycle_id: str, revision_id: str) -> Iterator[Path]:
        """A copy of exactly the pinned revision's files, executable bits included, for a
        declared command to run in and be discarded after (X-3a, #2421; contract 3). The
        store keeps hashes, not contents, so the copy is taken from the live tree, and only
        while the tree matches its pin. Nothing a command does reaches the live tree or a
        revision."""
        files, executable = self.read_pinned(cycle_id, revision_id)
        copy = self._cycle_dir(cycle_id) / "copies" / uuid.uuid4().hex
        try:
            for rel, content in files.items():
                target = copy / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content_bytes(content))
                if rel in executable:
                    target.chmod(target.stat().st_mode | 0o111)
            copy.mkdir(parents=True, exist_ok=True)
            yield copy
        finally:
            shutil.rmtree(copy, ignore_errors=True)

    def read_pinned(
        self, cycle_id: str, revision_id: str
    ) -> tuple[dict[str, FileContent], frozenset[str]]:
        """Exactly the pinned revision's files and executable bits, read from the live tree only
        while it matches its pin (contract 3). The store keeps hashes, not contents, so the tree is
        the only copy. A disposable copy (X-3a) and a revision read (SIP-0112's E.4.3 capture) both
        take it this way."""
        if not self.verify_pinned(cycle_id, revision_id):
            raise StaleBaseRevisionError(
                f"live tree no longer matches revision {revision_id}: nothing is read from it"
            )
        tracked = self._revision_paths(cycle_id, revision_id)
        executable = self._live_executables(cycle_id, revision_id, tracked)
        files = self.current_files(cycle_id, tracked=tracked)
        # The pin is checked before the read, and a patch could land between the two, so what
        # was read is held to the pin too: a read is one revision, never a mix of two.
        if compute_revision_id(files, executable) != revision_id:
            raise StaleBaseRevisionError(
                f"live tree moved while revision {revision_id} was read: nothing is returned"
            )
        return files, executable

    def verify_pinned(self, cycle_id: str, revision_id: str) -> bool:
        """§4.6 verification pinning: does the live tree match the named
        revision exactly? Clean-room verification fails on False."""
        revision = self.get_revision(cycle_id, revision_id)
        if revision is None:
            return False
        tracked = self._revision_paths(cycle_id, revision_id)
        return revision.matches(
            self.current_files(cycle_id, tracked=tracked),
            self._live_executables(cycle_id, revision_id, tracked),
        )

    # -- leases and cleanup -------------------------------------------------

    def touch_lease(self, cycle_id: str, *, ttl_seconds: float, now: float) -> None:
        """Record (or renew) the workspace's TTL lease."""
        self._cycle_dir(cycle_id).mkdir(parents=True, exist_ok=True)
        self._lease_file(cycle_id).write_text(
            json.dumps({"expires_at": now + ttl_seconds}), encoding="utf-8"
        )

    def cleanup(self, cycle_id: str) -> None:
        """Remove the cycle's workspace state. Idempotent — cleaning an absent
        workspace is a no-op (§7 item 12)."""
        _remove_store_entries(self._cycle_dir(cycle_id))

    def cleanup_expired(self, *, now: float) -> tuple[str, ...]:
        """Remove every leased workspace whose lease expired. Scans disk, so
        it is restart-recoverable; unleased workspaces are never touched."""
        if not self._root.is_dir():
            return ()
        removed: list[str] = []
        for cycle_dir in sorted(self._root.iterdir()):
            lease = cycle_dir / "lease.json"
            if not lease.is_file():
                continue
            try:
                expires_at = float(json.loads(lease.read_text(encoding="utf-8"))["expires_at"])
            except (ValueError, KeyError, json.JSONDecodeError):
                continue  # malformed lease: leave the workspace alone, never guess
            if expires_at <= now:
                _remove_store_entries(cycle_dir)
                removed.append(cycle_dir.name)
        return tuple(removed)
