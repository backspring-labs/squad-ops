"""SIP-0100 Task 0.3 — the durable bound scaffold ownership record (plan decision D2).

Persisted once at bind time; the immutable source of truth for write authorization, frozen
integrity verification, restoration, deterministic replay, and evidence. Restoration and replay
use THIS record's bytes — never a re-run of the (possibly newer) expander (D2). Phase 2 derives
``WorkspaceOwnership`` from this record; Phase 0 only defines it and proves it round-trips and
carries bytes for every frozen path.

No wall-clock here (``created_at`` is passed in) — the record must be reproducible for replay.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from squadops.capabilities.scaffold import (
    InterfaceManifest,
    expand,
    fill_slot_paths,
    qa_test_namespace,
)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _normalize(path: str) -> str:
    return str(path).strip().lstrip("./").replace("//", "/")


@dataclass(frozen=True)
class FrozenArtifact:
    """One scaffold-frozen file, pinned by hash AND bytes — so restoration/replay never re-derive
    from the current expander (D2)."""

    path: str  # normalized workspace-relative
    sha256: str
    content: str

    def to_dict(self) -> dict:
        return {"path": self.path, "sha256": self.sha256, "content": self.content}

    @classmethod
    def from_dict(cls, d: dict) -> FrozenArtifact:
        return cls(path=d["path"], sha256=d["sha256"], content=d["content"])


@dataclass(frozen=True)
class BoundScaffoldRecord:
    """Durable bind-time ownership record (D2). Ownership is permanent for the attempt; producer
    authority (WriteGrant, Phase 2.1) is derived separately and is transient."""

    run_id: str
    attempt_id: str
    stack: str
    manifest_hash: str
    contract_hash: str
    expander_id: str  # provenance — which expander materialized this bound instance
    created_at: str  # ISO8601, supplied by the caller (reproducible for replay)
    frozen: tuple[FrozenArtifact, ...] = ()
    fill_slots: tuple[str, ...] = ()
    qa_namespace: tuple[str, ...] = ()

    def frozen_paths(self) -> frozenset[str]:
        return frozenset(f.path for f in self.frozen)

    def frozen_bytes(self, path: str) -> str | None:
        """The bound bytes for a frozen path (the restoration/replay authority), or None."""
        norm = _normalize(path)
        for f in self.frozen:
            if f.path == norm:
                return f.content
        return None

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "attempt_id": self.attempt_id,
            "stack": self.stack,
            "manifest_hash": self.manifest_hash,
            "contract_hash": self.contract_hash,
            "expander_id": self.expander_id,
            "created_at": self.created_at,
            "frozen": [f.to_dict() for f in self.frozen],
            "fill_slots": list(self.fill_slots),
            "qa_namespace": list(self.qa_namespace),
        }

    @classmethod
    def from_dict(cls, d: dict) -> BoundScaffoldRecord:
        return cls(
            run_id=d["run_id"],
            attempt_id=d["attempt_id"],
            stack=d["stack"],
            manifest_hash=d["manifest_hash"],
            contract_hash=d["contract_hash"],
            expander_id=d["expander_id"],
            created_at=d["created_at"],
            frozen=tuple(FrozenArtifact.from_dict(f) for f in d.get("frozen", [])),
            fill_slots=tuple(d.get("fill_slots", [])),
            qa_namespace=tuple(d.get("qa_namespace", [])),
        )


def build_bound_record(
    manifest: InterfaceManifest,
    *,
    run_id: str,
    attempt_id: str,
    created_at: str,
) -> BoundScaffoldRecord:
    """Assemble the bound record from the scaffold. The frozen set is derived the SAME way the
    verification contract derives it (``expand(manifest) − fill_slot_paths(manifest)``), so the
    record's frozen surface equals the contract's by construction — one source of truth."""
    files = {_normalize(f["name"]): f["content"] for f in expand(manifest)}
    fill = tuple(_normalize(p) for p in fill_slot_paths(manifest))
    fill_set = set(fill)
    frozen = tuple(
        FrozenArtifact(path=name, sha256=_sha256(files[name]), content=files[name])
        for name in sorted(files)
        if name not in fill_set
    )
    contract_hash = _sha256("\n".join(f"{f.path}:{f.sha256}" for f in frozen))
    return BoundScaffoldRecord(
        run_id=run_id,
        attempt_id=attempt_id,
        stack=manifest.stack,
        manifest_hash=manifest.content_hash(),
        contract_hash=contract_hash,
        expander_id=manifest.stack,  # the expander is keyed by stack today
        created_at=created_at,
        frozen=frozen,
        fill_slots=fill,
        qa_namespace=qa_test_namespace(manifest),
    )
