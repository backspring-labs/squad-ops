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
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from collections.abc import Mapping
from pathlib import Path

from squadops.execution.models import (
    WorkspaceRevision,
    compute_revision_id,
)

_CYCLE_ID_RE = re.compile(r"[A-Za-z0-9_\-]+")


class WorkspaceStoreError(Exception):
    """Base error for workspace-store violations."""


class WorkspaceEscapeError(WorkspaceStoreError):
    """A path tried to leave the cycle workspace (§7 item 8)."""


class StaleBaseRevisionError(WorkspaceStoreError):
    """A patch's base revision does not match the live tree — applying it
    would mint a revision whose content is not derivable from base + patch."""


class AlreadySeededError(WorkspaceStoreError):
    """Seed attempted on a workspace that already has different content."""


def _safe_relpath(path: str) -> str:
    """Normalize a workspace-relative path; reject anything that could escape
    the cycle workspace (§7 item 8: agents cannot supply host paths)."""
    norm = str(path).strip().replace("\\", "/")
    if not norm or norm.startswith("/") or norm.startswith("~"):
        raise WorkspaceEscapeError(f"not a workspace-relative path: {path!r}")
    parts = [p for p in norm.split("/") if p not in ("", ".")]
    if not parts or ".." in parts or any(":" in p for p in parts):
        raise WorkspaceEscapeError(f"not a workspace-relative path: {path!r}")
    return "/".join(parts)


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

    def current_files(self, cycle_id: str) -> dict[str, str]:
        """The live tree as a path → content mapping."""
        ws = self.workspace_dir(cycle_id)
        if not ws.is_dir():
            return {}
        return {
            str(p.relative_to(ws)).replace("\\", "/"): p.read_text(encoding="utf-8")
            for p in sorted(ws.rglob("*"))
            if p.is_file()
        }

    # -- revisions ----------------------------------------------------------

    def _persist(self, revision: WorkspaceRevision, files: Mapping[str, str]) -> None:
        rev_dir = self._revisions_dir(revision.cycle_id)
        rev_dir.mkdir(parents=True, exist_ok=True)
        manifest = {
            "revision": revision.to_dict(),
            "files": {
                p: hashlib.sha256(c.encode("utf-8")).hexdigest() for p, c in sorted(files.items())
            },
        }
        (rev_dir / f"{revision.revision_id}.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
        self._head_file(revision.cycle_id).write_text(revision.revision_id, encoding="utf-8")

    def latest_revision(self, cycle_id: str) -> WorkspaceRevision | None:
        head = self._head_file(cycle_id)
        if not head.is_file():
            return None
        return self.get_revision(cycle_id, head.read_text(encoding="utf-8").strip())

    def get_revision(self, cycle_id: str, revision_id: str) -> WorkspaceRevision | None:
        path = self._revisions_dir(cycle_id) / f"{revision_id}.json"
        if not path.is_file():
            return None
        manifest = json.loads(path.read_text(encoding="utf-8"))
        return WorkspaceRevision.from_dict(manifest["revision"])

    def seed(
        self,
        cycle_id: str,
        files: Mapping[str, str],
        *,
        origin: str,
        created_at: str | None = None,
    ) -> WorkspaceRevision:
        """Write the initial tree and cut the first revision (§4.6 boundary).

        Idempotent for retries: re-seeding identical content returns the
        existing revision; re-seeding different content over a seeded
        workspace is an error, never a silent overwrite."""
        head = self.latest_revision(cycle_id)
        if head is not None:
            if compute_revision_id({_safe_relpath(p): c for p, c in files.items()}) == (
                head.revision_id
            ):
                return head
            raise AlreadySeededError(f"cycle {cycle_id} is already seeded with other content")
        ws = self.provision(cycle_id)
        safe = {_safe_relpath(p): c for p, c in files.items()}
        for rel, content in safe.items():
            target = ws / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        revision = WorkspaceRevision.cut(
            cycle_id=cycle_id, origin=origin, files=safe, created_at=created_at
        )
        self._persist(revision, safe)
        return revision

    def apply_patch(
        self,
        cycle_id: str,
        *,
        base_revision_id: str,
        files: Mapping[str, str | None],
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
        current = self.current_files(cycle_id)
        if not base.matches(current):
            raise StaleBaseRevisionError(
                f"live tree no longer matches base revision {base_revision_id}"
            )
        ws = self.workspace_dir(cycle_id)
        changed: list[str] = []
        merged = dict(current)
        for path, content in files.items():
            rel = _safe_relpath(path)
            changed.append(rel)
            if content is None:
                merged.pop(rel, None)
                (ws / rel).unlink(missing_ok=True)
            else:
                merged[rel] = content
                target = ws / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
        revision = WorkspaceRevision.cut(
            cycle_id=cycle_id, origin=origin, files=merged, parent=base, created_at=created_at
        )
        self._persist(revision, merged)
        return revision, tuple(sorted(changed))

    def verify_pinned(self, cycle_id: str, revision_id: str) -> bool:
        """§4.6 verification pinning: does the live tree match the named
        revision exactly? Clean-room verification fails on False."""
        revision = self.get_revision(cycle_id, revision_id)
        if revision is None:
            return False
        return revision.matches(self.current_files(cycle_id))

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
        cycle_dir = self._cycle_dir(cycle_id)
        if cycle_dir.exists():
            shutil.rmtree(cycle_dir)

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
                shutil.rmtree(cycle_dir)
                removed.append(cycle_dir.name)
        return tuple(removed)
