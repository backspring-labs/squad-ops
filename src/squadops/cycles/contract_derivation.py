"""Derive a verification contract from a seeded interface manifest (#779, M0b).

Two artifacts, and the distinction matters throughout this module: the **interface
manifest** is the design — endpoints, entities, views — and the **verification
contract** is the checklist derived from it, naming every criterion the finished app
must satisfy. A cycle can be given both, or only the manifest. This module handles the
second case by producing the contract the manifest implies.

Bind mode is keyed on a seeded ``contract_ref``, which is correct for seeded mode and
impossible for authored mode: a manifest the squad has just written has no
pre-existing contract to point at. Producing one was three manual steps
(``contract_gate.py`` → ``artifacts ingest`` → pass the id) for an artifact that is
**mechanically derivable** from the manifest — an equality #777 pinned as exact.

This module owns that derivation and the seeded-manifest lookup that feeds it, so the
create path and (later, at M1) the framing→implementation boundary share **one**
derivation path rather than growing two that drift.

Deriving *and persisting*, never deriving in memory: a contract with no artifact id
cannot be replayed, audited, or hash-frozen. Seeded mode's guarantee is that the
contract is a pinned artifact; authored mode gets the same guarantee, not a weaker one.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

if TYPE_CHECKING:  # pragma: no cover - typing only
    from collections.abc import Iterable

    from squadops.ports.cycles.artifact_vault import ArtifactVaultPort

#: The filename an interface manifest carries, whichever rail it arrived on. Matched
#: alongside the ``interface_manifest`` artifact type because both exist in the wild.
SEEDED_MANIFEST_FILENAME = "interface_manifest.yaml"

#: Artifact type for a derived contract — deliberately the SAME type the manual
#: ``artifacts ingest`` path uses, so nothing downstream can tell a derived contract
#: from an ingested one. Provenance belongs in the artifact record, not in a divergent
#: type that every consumer would then have to learn about.
CONTRACT_ARTIFACT_TYPE = "verification_contract"
CONTRACT_FILENAME = "verification_contract.yaml"


class ContractDerivationError(Exception):
    """The manifest could not produce a contract."""


def is_interface_manifest(ref: Any) -> bool:
    """True when an artifact ref is an interface manifest — **whoever wrote it**.

    Provenance-neutral by design. It was ``is_seeded_manifest`` until #791 made a
    squad-authored manifest possible, at which point a name asserting the operator put
    it there described only half the callers. The predicate never checked provenance and
    must not start: the create path, the executor's seeded lookup, and #796's
    authored-manifest lookup all ask the same question — *is this the manifest?*

    One rule, one copy. A second copy is how the ends start disagreeing about which
    artifact is the manifest.
    """
    return ref.filename == SEEDED_MANIFEST_FILENAME or (
        getattr(ref, "artifact_type", None) == "interface_manifest"
    )


def find_interface_manifest(stored: Iterable[tuple[str, Any]]) -> str | None:
    """The artifact id of the interface manifest among ``(artifact_id, ref)`` pairs.

    The in-run counterpart of :func:`load_seeded_manifest_content`, which reads the
    cycle's seeded rail. This one reads what the current run has produced so far, which
    is where an authored manifest lives before any promotion or forwarding has happened
    (#796). Last match wins: a re-rolled authoring stage stores a new manifest, and the
    later one is the design in force.
    """
    found: str | None = None
    for artifact_id, ref in stored:
        if is_interface_manifest(ref):
            found = artifact_id
    return found


async def load_seeded_manifest_content(
    vault: ArtifactVaultPort, refs: Iterable[str] | None
) -> str | None:
    """Raw content of the seeded interface manifest among ``refs``, or ``None``.

    Unreadable refs are skipped rather than fatal: callers report an absent manifest in
    their own terms (the create path rejects, the executor records a #494/#496 gate
    rejection).
    """
    for ref_id in refs or []:
        try:
            ref, content_bytes = await vault.retrieve(ref_id)
        except Exception:
            continue
        if is_interface_manifest(ref):
            return content_bytes.decode(errors="replace")
    return None


def derive_contract_bytes(manifest_content: str) -> bytes:
    """The verification contract implied by a manifest, as the bytes to store.

    Pure. Raises :class:`ContractDerivationError` with the parse failure named — an
    unusable manifest must surface as a rejection, never as a silent fall-through to
    author mode, because an operator who seeded a manifest asked for bind mode and an
    unbound green would carry none of the criteria they expected.
    """
    from squadops.capabilities.scaffold import InterfaceManifest
    from squadops.capabilities.scaffold_contract import emit_contract_yaml

    try:
        manifest = InterfaceManifest.from_yaml(manifest_content)
    except Exception as exc:  # noqa: BLE001 - any parse/shape failure is one rejection
        raise ContractDerivationError(f"interface manifest did not parse: {exc}") from exc

    try:
        return emit_contract_yaml(manifest).encode("utf-8")
    except Exception as exc:  # noqa: BLE001 - expander refusal is a rejection, not a crash
        raise ContractDerivationError(
            f"manifest parsed but no contract could be derived from it: {exc}"
        ) from exc


async def derive_and_store_contract(
    vault: ArtifactVaultPort,
    project_id: str,
    manifest_content: str,
    *,
    cycle_id: str | None = None,
    run_id: str | None = None,
) -> str:
    """Derive the contract, store it as an artifact, return its id.

    The stored artifact records that it was derived rather than ingested, so a later
    reader can tell where it came from without the type differing.
    """
    from squadops.cycles.models import ArtifactRef

    content = derive_contract_bytes(manifest_content)
    ref = ArtifactRef(
        artifact_id=f"art_{uuid4().hex[:12]}",
        project_id=project_id,
        artifact_type=CONTRACT_ARTIFACT_TYPE,
        filename=CONTRACT_FILENAME,
        content_hash=hashlib.sha256(content).hexdigest(),
        size_bytes=len(content),
        media_type="application/yaml",
        created_at=datetime.now(UTC),
        cycle_id=cycle_id,
        # #796: an in-run derivation attaches to the run, so the contract is promoted
        # with the rest of the framing output at gate approval and forwards to the
        # implementation workload on the rails a seeded contract already uses.
        run_id=run_id,
        metadata={"derived_from": "interface_manifest", "derivation": "scaffold_contract"},
    )
    stored = await vault.store(ref, content)
    return stored.artifact_id
