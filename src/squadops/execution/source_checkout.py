"""A source-backed run's starting tree and its per-task view (SIP-0112 E.4.3).

A Cycle that pins an external Project's source (contract 1) starts from that product's tree at
the pinned commit:
- every tracked file is seeded as the run's starting content, with a manifest of the checkout
  beside it, as an increment is seeded with its accepted tree (SIP-0109 §7.3);
- whatever the squad produces for a path wins over the checkout's copy;
- every file it doesn't touch is delivered as it was.

Each task is handed a bounded ``source_repository`` input rather than the tree (squadops.projects
.checkout): the map, the product's instruction files and the current content of the files it
names.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any
from uuid import uuid4

from squadops.capabilities.handlers.cycle.validation import _classify_file
from squadops.cycles.emission_integrity import EMISSION_STATUS_FAILED
from squadops.cycles.models import ArtifactRef, Cycle
from squadops.cycles.task_plan import REPAIR_TASK_TYPES
from squadops.projects.checkout import (
    CHECKOUT_MANIFEST_FILENAME,
    CHECKOUT_MANIFEST_TYPE,
    SOURCE_CHECKOUT,
    CheckoutManifest,
    manifest_of,
    source_repository_input,
)
from squadops.projects.configuration import baseline_tree


class SourceCheckoutRefused(RuntimeError):
    """A source-backed run that can't start from its product's tree, with the reason."""


async def seed_checkout_artifacts(
    cycle: Cycle, run_id: str, *, vault: Any, repository: Any, registry: Any
) -> list[str]:
    """Seed the run with its product's tree at the pinned commit; return the stored ids, the
    checkout's manifest first."""
    context = cycle.source_context
    if context is None:
        return []
    if repository is None:
        raise SourceCheckoutRefused("this runtime has no managed clone to read the source from")
    project = await registry.get_project(cycle.project_id)
    configuration = await registry.get_development_configuration(
        cycle.project_id, context.development_configuration_revision
    )
    tree = await baseline_tree(
        repository,
        cycle.project_id,
        context.repo_uri,
        project.source.base_ref,
        context.development_baseline_commit,
    )
    if tree.capability_gaps:
        raise SourceCheckoutRefused(
            "capability gap: the run cannot carry " + "; ".join(tree.capability_gaps)
        )
    manifest = manifest_of(
        context.development_baseline_commit,
        tree.files,
        tree.executable,
        [s.path for s in configuration.instruction_sources],
    )
    provenance = {
        "producing_task_type": SOURCE_CHECKOUT,
        "checkout_commit": context.development_baseline_commit,
    }
    ids = [
        await _store(
            vault,
            cycle,
            run_id,
            CHECKOUT_MANIFEST_FILENAME,
            manifest.to_json(),
            CHECKOUT_MANIFEST_TYPE,
            "application/json",
            provenance,
        )
    ]
    for path, content in sorted(tree.files.items()):
        artifact_type, media_type = _classify_file(path)
        ids.append(
            await _store(vault, cycle, run_id, path, content, artifact_type, media_type, provenance)
        )
    return ids


async def _store(
    vault: Any,
    cycle: Cycle,
    run_id: str,
    filename: str,
    content: bytes,
    artifact_type: str,
    media_type: str,
    metadata: dict[str, Any],
) -> str:
    ref = ArtifactRef(
        artifact_id=f"art_{uuid4().hex[:12]}",
        project_id=cycle.project_id,
        cycle_id=cycle.cycle_id,
        run_id=run_id,
        artifact_type=artifact_type,
        filename=filename,
        content_hash=sha256(content).hexdigest(),
        size_bytes=len(content),
        media_type=media_type,
        created_at=datetime.now(UTC),
        metadata=dict(metadata),
    )
    await vault.store(ref, content)
    return ref.artifact_id


async def task_source_repository(
    vault: Any, stored_artifacts: list[tuple[str, ArtifactRef]], named: Iterable[str]
) -> dict[str, Any] | None:
    """The ``source_repository`` input for one task of a source-backed run, or ``None`` for
    any other run. A path's current content is the squad's latest accepted emission for it, or
    the checkout's when the squad hasn't touched it."""
    manifest_id = next(
        (i for i, ref in stored_artifacts if ref.artifact_type == CHECKOUT_MANIFEST_TYPE), None
    )
    if manifest_id is None:
        return None
    _ref, raw = await vault.retrieve(manifest_id)
    manifest = CheckoutManifest.from_json(raw)
    wanted = set(named) | set(manifest.instruction_paths)
    latest: dict[str, str] = {}
    for art_id, ref in stored_artifacts:
        if ref.filename not in wanted or ref.filename in manifest.binary:
            continue
        # As the executor's own resolution reads the workspace: a failed emission is never
        # input, and a repair candidate is unaccepted until it is re-stored as the task's own.
        if ref.metadata.get("emission_status") == EMISSION_STATUS_FAILED:
            continue
        if ref.metadata.get("producing_task_type", "") in REPAIR_TASK_TYPES:
            continue
        latest[ref.filename] = art_id
    current = {}
    for path, art_id in latest.items():
        _ref, content = await vault.retrieve(art_id)
        current[path] = content.decode("utf-8", errors="replace")
    return source_repository_input(manifest, current, named)
