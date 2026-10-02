"""The tree an increment builds on (SIP-0109 §7.1, §7.3; #1705).

An increment cycle's implementation starts from the campaign's accepted tree: the files the
accepted cycle delivered (one rule, ``delivered_tree``, #1833), seeded beside the walking
skeleton the candidate manifest expands into. They are produced content, so the workspace's
rule — a scaffold stub never shadows produced content (#881) — hands every existing file its
accepted implementation, and only what the increment adds is a stub to fill.
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Mapping
from typing import Any

from squadops.campaigns.models import CycleKind
from squadops.cycles.delivered_tree import StoredArtifact, delivered_files


def accepted_cycle_of(cycle: Any) -> str | None:
    """The accepted cycle an increment cycle builds on, from its launch's ``campaign_proposal``
    block; ``None`` for any other cycle."""
    if getattr(cycle, "kind", None) != CycleKind.INCREMENT:
        return None
    block = cycle.resolved_config().get("campaign_proposal") or {}
    return block.get("accepted_cycle_id") or None


async def accepted_tree_refs(vault: Any, cycle: Any) -> list[str]:
    """The artifact ids of the accepted tree's delivered files, for an increment cycle's
    implementation to seed; empty for any other cycle."""
    accepted_cycle = accepted_cycle_of(cycle)
    if accepted_cycle is None:
        return []
    refs = await vault.list_artifacts(cycle_id=accepted_cycle)
    chosen = delivered_files(StoredArtifact.from_record(dataclasses.asdict(r)) for r in refs)
    return list(chosen.values())


def increment_footprint(resolved_config: Any, candidate: Any) -> tuple[str, ...] | None:
    """The files an increment may touch (§7.2): derived from the accepted manifest its launch
    carries and the candidate manifest its framing binds to, exactly as the change request's
    footprint was. ``None`` for any cycle that is not an increment."""
    from squadops.campaigns.change_request import derive_footprint_from
    from squadops.capabilities.scaffold import InterfaceManifest

    baseline = increment_baseline(resolved_config)
    if candidate is None or baseline is None:
        return None
    return derive_footprint_from(InterfaceManifest.from_yaml(baseline), candidate)


def increment_baseline(resolved_config: Any) -> str | None:
    """The accepted manifest an increment cycle's launch carries, or ``None`` for any other
    cycle."""
    if not isinstance(resolved_config, Mapping):
        return None
    block = resolved_config.get("campaign_proposal")
    if not isinstance(block, Mapping):
        return None
    baseline = block.get("baseline_manifest")
    return baseline if isinstance(baseline, str) and baseline.strip() else None


async def approved_change_request(vault: Any, cycle: Any) -> str | None:
    """The change request an increment cycle's framing frames (§7.3): the approved document the
    proposal run stored, forwarded into the framing run's ``plan_artifact_refs`` beside the
    candidate manifest. Its stored hash is checked, so a document altered after it was ruled on
    is refused. ``None`` for any cycle that is not an increment.

    An increment's framing without its change request is refused, not framed as a new
    application: the approved change is the framed objective, and nothing replaces it."""
    from squadops.campaigns.change_request import load_stored_change_request
    from squadops.capabilities.handlers.planning.proposal import CHANGE_REQUEST_ARTIFACT_TYPE

    if increment_baseline(cycle.resolved_config()) is None:
        return None
    for ref_id in cycle.execution_overrides.get("plan_artifact_refs") or ():
        ref, content = await vault.retrieve(ref_id)
        if ref.artifact_type == CHANGE_REQUEST_ARTIFACT_TYPE:
            document = content.decode("utf-8")
            load_stored_change_request(document)
            return document
    raise ValueError(
        f"increment cycle {cycle.cycle_id}: its framing was forwarded no approved "
        f"{CHANGE_REQUEST_ARTIFACT_TYPE}, and an increment frames nothing else"
    )


@dataclasses.dataclass(frozen=True)
class IncrementSeed:
    """What an approved increment binds its later workloads to (§7.3)."""

    #: The candidate manifest, then the approved change request when stored.
    plan_refs: tuple[str, ...]
    contract_ref: str | None


async def increment_seed(vault: Any, registry: Any, cycle: Any, completed_run: Any) -> Any:
    """The approved increment's seed, as the increment gate stored and promoted it on the
    proposal run (#1840): the candidate manifest, the contract derived from it, and the change
    request. ``None`` for any cycle that is not an increment, and before an approval.

    It binds **every** workload after the proposal, as a creation-time seed binds every workload
    of an ordinary cycle: the framing binds to it, and the implementation's skeleton, accepted
    tree and contract all hang from it (#1842). Read from the registry and the vault, never from
    the previous workload's forwarding, so a restart's rebuild (#434) forwards the same."""
    from squadops.capabilities.handlers.planning.proposal import CHANGE_REQUEST_ARTIFACT_TYPE
    from squadops.cycles.contract_derivation import CONTRACT_ARTIFACT_TYPE
    from squadops.cycles.manifest_authoring import MANIFEST_ARTIFACT_TYPE
    from squadops.cycles.models import RunStatus, WorkloadType

    if increment_baseline(cycle.resolved_config()) is None:
        return None
    if completed_run.workload_type == WorkloadType.PROPOSAL:
        proposal = completed_run
    else:
        approved = [
            r
            for r in await registry.list_runs(cycle.cycle_id)
            if r.workload_type == WorkloadType.PROPOSAL and r.status == RunStatus.COMPLETED.value
        ]
        if not approved:
            return None
        proposal = max(approved, key=lambda r: r.run_number)
    promoted = await vault.list_artifacts(run_id=proposal.run_id, promotion_status="promoted")

    def latest(artifact_type: str) -> str | None:
        refs = [a for a in promoted if a.artifact_type == artifact_type]
        return max(refs, key=lambda a: a.created_at).artifact_id if refs else None

    manifest = latest(MANIFEST_ARTIFACT_TYPE)
    if manifest is None:
        return None
    request = latest(CHANGE_REQUEST_ARTIFACT_TYPE)
    return IncrementSeed(
        plan_refs=(manifest, *((request,) if request else ())),
        contract_ref=latest(CONTRACT_ARTIFACT_TYPE),
    )


@dataclasses.dataclass(frozen=True)
class CriterionFile:
    """A new criterion and its own test file (SIP-0109 §8.1): the qa role writes the test that
    discriminates it there, and its verifier bundle is frozen from that file."""

    criterion_id: str
    surface_kind: str
    surface: str
    path: str


def increment_criterion_files(change_request: str, stack: str) -> tuple[CriterionFile, ...]:
    """Each new criterion of the approved change request, with its file on ``stack``
    (``scaffold.criterion_test_path``). The document is the stored one, hash-checked."""
    from squadops.campaigns.change_request import load_stored_change_request
    from squadops.capabilities.scaffold import criterion_test_path

    request = load_stored_change_request(change_request)
    return tuple(
        CriterionFile(
            c.id,
            str(c.surface_kind),
            c.surface,
            criterion_test_path(stack, c.id, str(c.surface_kind)),
        )
        for c in request.criteria
    )


#: The artifact an increment's evaluation writes, which the completion hook reads (§8.4).
INCREMENT_EVALUATION_ARTIFACT_TYPE = "increment_evaluation"
INCREMENT_EVALUATION_FILENAME = "increment_evaluation.json"
#: A frozen criterion's verifier bundle, stored at its increment's promotion (§8.1).
VERIFIER_BUNDLE_ARTIFACT_TYPE = "verifier_bundle"


def declared_routes(manifest: Any) -> dict[str, tuple[str, ...]]:
    """Each client route the manifest declares, with the test ids its page must render (§8.3)."""
    frontend = getattr(manifest, "frontend", None)
    return {r.path: tuple(r.testids) for r in (getattr(frontend, "routes", None) or ())}


def increment_evaluation_inputs(
    resolved_config: Mapping[str, Any], change_request: str, manifest: Any
) -> dict[str, Any]:
    """What an increment's evaluation task is handed at plan time: the increment's id, each new
    criterion's own file (§8.1) and the routes the candidate declares (§8.3). The two trees are
    the dispatch's: the accepted tree as seeded (#1842) and the candidate as built."""
    from squadops.capabilities.scaffold import scaffold_stack_for

    block = resolved_config.get("campaign_proposal") or {}
    return {
        "increment_id": str(block.get("proposal_id") or ""),
        "increment_criterion_files": [
            {"criterion_id": f.criterion_id, "path": f.path}
            for f in increment_criterion_files(change_request, scaffold_stack_for(resolved_config))
        ],
        "increment_declared_routes": {
            path: list(testids) for path, testids in declared_routes(manifest).items()
        },
        # §8.1: the criteria earlier increments froze, as this increment's launch pinned them.
        "increment_frozen_criteria": [dict(f) for f in block.get("frozen_criteria") or ()],
    }


async def accepted_tree_contents(
    vault: Any, resolved_config: Any, stored: list[tuple[str, Any]]
) -> dict[str, str]:
    """The accepted tree an increment's run was seeded with (#1842), as ``path -> content``:
    the run's stored artifacts that belong to the accepted cycle its launch names. Empty for a
    cycle that is not an increment."""
    block = (
        resolved_config.get("campaign_proposal") if isinstance(resolved_config, Mapping) else None
    )
    accepted_cycle = (block or {}).get("accepted_cycle_id") if isinstance(block, Mapping) else None
    if not accepted_cycle:
        return {}
    files: dict[str, str] = {}
    for artifact_id, ref in stored:
        if getattr(ref, "cycle_id", None) != accepted_cycle:
            continue
        _, content = await vault.retrieve(artifact_id)
        files[ref.filename] = content.decode("utf-8", errors="replace")
    return files


async def frozen_bundle_contents(vault: Any, resolved_config: Any) -> dict[str, dict]:
    """The stored bundle of each criterion an increment's launch pinned, by criterion id. An
    unreadable one is left out, and its criterion is judged ``blocked_unverified``."""
    block = (
        resolved_config.get("campaign_proposal") if isinstance(resolved_config, Mapping) else None
    )
    pinned = (block or {}).get("frozen_criteria") if isinstance(block, Mapping) else None
    bundles: dict[str, dict] = {}
    for pin in pinned or ():
        try:
            _ref, content = await vault.retrieve(pin["bundle_ref"])
            bundles[str(pin["criterion_id"])] = json.loads(content.decode("utf-8"))
        except Exception:  # noqa: BLE001 — a bundle that cannot be read is blocked, not a crash
            continue
    return bundles
