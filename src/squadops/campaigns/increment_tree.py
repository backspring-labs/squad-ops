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
import logging
from collections.abc import Mapping
from typing import Any

from squadops.cycles.delivered_tree import StoredArtifact, delivered_files
from squadops.cycles.vault_reads import retrieve_or_absent

logger = logging.getLogger(__name__)


def accepted_cycle_of(cycle: Any) -> str | None:
    """The accepted cycle an increment builds on, from its ``campaign_proposal`` block; ``None``
    for any other cycle. Keyed on the block, as every other increment seam is
    (``increment_baseline``): a campaign's increment and the reference increment outside any
    campaign (§11a, #1804) both carry one."""
    block = cycle.resolved_config().get("campaign_proposal")
    if not isinstance(block, Mapping):
        return None
    return block.get("accepted_cycle_id") or None


#: The accepted tree a promotion recorded (#1887): ``path -> artifact id`` for the whole app.
ACCEPTED_TREE_ARTIFACT_TYPE = "accepted_tree"
ACCEPTED_TREE_FILENAME = "accepted_tree.json"


async def _delivered(vault: Any, cycle_id: str) -> dict[str, str]:
    """The accepted tree of ``cycle_id``, ``path -> artifact id``: what its promotion recorded
    (#1887), or — for a cycle promoted before the record existed, or never promoted, like a
    reference baseline — its own delivered files, by the one rule every reader shares (#1832)."""
    refs = await vault.list_artifacts(cycle_id=cycle_id)
    recorded = sorted(
        (r for r in refs if r.artifact_type == ACCEPTED_TREE_ARTIFACT_TYPE),
        key=lambda r: str(r.created_at),
    )
    if recorded:
        _ref, content = await vault.retrieve(recorded[-1].artifact_id)
        return dict(json.loads(content))
    return delivered_files(StoredArtifact.from_record(dataclasses.asdict(r)) for r in refs)


async def compose_accepted_tree(vault: Any, built_on: str | None, own_refs: list) -> dict[str, str]:
    """The whole app a cycle delivered (#1887): the accepted tree it was built on (``built_on``,
    the accepted cycle), overlaid with its own delivered files by #881's rule across cycles —
    produced content wins over what it replaces; a scaffold-seeded file never shadows produced
    content (an increment's stub for a slot it did not touch keeps the accepted implementation);
    and among seeded versions the latest wins (the frozen file its candidate regenerated, #1876).
    A calibration builds on nothing, and its tree is what it delivered."""
    inherited = []
    for art_id in (await _delivered(vault, built_on) if built_on else {}).values():
        ref, _content = await vault.retrieve(art_id)
        inherited.append(StoredArtifact.from_record(dataclasses.asdict(ref)))
    own = [StoredArtifact.from_record(dataclasses.asdict(r)) for r in own_refs]
    return delivered_files([*inherited, *own])


async def accepted_tree_refs(
    vault: Any, cycle: Any, frozen: frozenset[str] = frozenset()
) -> list[str]:
    """The artifact ids of the accepted tree's delivered files, for an increment cycle's
    implementation to seed; empty for any other cycle. ``frozen`` (the candidate skeleton's
    frozen paths) is left out: those are regenerated from the candidate manifest, and the
    accepted tree's copies are the baseline's (#1876)."""
    accepted_cycle = accepted_cycle_of(cycle)
    if accepted_cycle is None:
        return []
    chosen = await _delivered(vault, accepted_cycle)
    return [ref for path, ref in chosen.items() if path not in frozen]


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
    #: The approved change request on its own (#1938): what the promotion reads each criterion's
    #: statement from. ``None`` when the proposal stored none.
    change_request_ref: str | None = None


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
        change_request_ref=request,
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
        # §8.3: how each parameterized route's page is brought into being to be rendered.
        "increment_route_seeds": route_seeds(manifest),
        # §8.1: the frozen criteria this change retires, or whose verifiers it replaces.
        "increment_retired_criteria": list(retired_criteria(change_request)),
        # §8.1: of those, each replaced verifier at its own test file, frozen anew from the
        # candidate.
        "increment_replaced_criteria": [
            {"criterion_id": criterion_id, "path": path}
            for criterion_id, path in replaced_criterion_files(resolved_config, change_request)
        ],
    }


async def accepted_tree_contents(vault: Any, resolved_config: Any) -> dict[str, str]:
    """The accepted tree an increment builds on (#1842), as ``path -> content``: the delivered
    files of the accepted cycle its launch names, whole — read from that cycle, not from what
    the run was seeded with, which leaves out the frozen files the candidate regenerates
    (#1876). The baseline overlay needs the baseline's own. Empty for a cycle that is not an
    increment."""
    block = (
        resolved_config.get("campaign_proposal") if isinstance(resolved_config, Mapping) else None
    )
    accepted_cycle = (block or {}).get("accepted_cycle_id") if isinstance(block, Mapping) else None
    if not accepted_cycle:
        return {}
    files: dict[str, str] = {}
    for path, artifact_id in (await _delivered(vault, accepted_cycle)).items():
        _, content = await vault.retrieve(artifact_id)
        files[path] = content.decode("utf-8", errors="replace")
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
            got = await retrieve_or_absent(vault, pin["bundle_ref"])
            if got is not None:
                bundles[str(pin["criterion_id"])] = json.loads(got[1].decode("utf-8"))
        except Exception as e:  # noqa: BLE001 — a bundle that cannot be read is blocked, not a crash
            logger.warning(
                "frozen criterion pin %s could not be read (%s: %s)", pin, type(e).__name__, e
            )
            continue
    return bundles


def route_seeds(manifest: Any) -> dict[str, dict[str, Any]]:
    """What brings a parameterized route's page into being (§8.3): for a declared client route
    with one parameter (``/runs/:run_id``), the create request on its collection (``POST
    /runs``) with the body the create probe sends (``create_request_body``), and the
    parameter the created resource's id fills. A route with no such create, or more than one
    parameter, has no seed: its page cannot be reached, so it is never rendered and stays
    ``blocked_unverified``, never passed. A route with no parameter needs none."""
    from squadops.capabilities.scaffold_contract import create_request_body

    api = getattr(manifest, "api", None)
    creates = {
        ep.path: ep
        for ep in (getattr(api, "endpoints", None) or ())
        if ep.method == "POST" and "{" not in ep.path
    }
    seeds: dict[str, dict[str, Any]] = {}
    for path in declared_routes(manifest):
        segments = path.split("/")
        params = [s for s in segments if route_param(s) is not None]
        if len(params) != 1:
            continue
        collection = "/".join(segments[: segments.index(params[0])]) or "/"
        # A manifest with an API base path writes its endpoints under it (a Next.js app's
        # ``/api/runs`` for its ``/runs/{run_id}`` page, #1973); the collection is either.
        base = str(getattr(api, "base_path", "") or "").rstrip("/")
        endpoint = (
            creates.get(collection)
            or (creates.get(base + collection) if base else None)
            or _under_a_written_prefix(creates, collection)
        )
        if endpoint is None:
            continue
        seeds[path] = {
            "method": "POST",
            "path": endpoint.path,
            "json": create_request_body(manifest, endpoint),
            "param": route_param(params[0]),
            # The segment as the manifest writes it, which the rendered path replaces (#1973).
            "segment": params[0],
        }
    return seeds


def _under_a_written_prefix(creates: dict[str, Any], collection: str) -> Any:
    """The create a manifest wrote under a prefix of its own instead of in ``base_path``: a
    Next.js app's ``/api/runs`` with no base path (2.1 rebuild 2's roll, ``cyc_d94c3742bb88``).
    The one POST whose path is the collection beneath leading segments; ``None`` when none is or
    more than one is, so an ambiguous page stays unseeded, never guessed."""
    if collection == "/":
        return None
    found = [
        endpoint
        for path, endpoint in creates.items()
        if path.endswith(collection) and path[: -len(collection)].startswith("/")
    ]
    return found[0] if len(found) == 1 else None


def route_param(segment: str) -> str | None:
    """A client route segment's parameter name, or ``None`` for a literal segment. A manifest
    writes a parameter either way, ``:run_id`` (the router's syntax) or ``{run_id}`` (the API's;
    the Next.js manifests do, #1973), and both are one parameter."""
    if segment.startswith(":") and len(segment) > 1:
        return segment[1:]
    if segment.startswith("{") and segment.endswith("}") and len(segment) > 2:
        return segment[1:-1]
    return None


def retired_criteria(change_request: str) -> tuple[str, ...]:
    """The frozen criteria an approved change request retires, or whose verifier it replaces
    (§8.1): either way the old bundle is no longer frozen. A replacement's new bundle is frozen
    from the candidate (``replaced_criterion_files``)."""
    from squadops.campaigns.change_request import load_stored_change_request

    request = load_stored_change_request(change_request)
    return tuple(sorted({r.criterion_id for r in (*request.retires, *request.replaces_verifiers)}))


def replaced_criterion_files(
    resolved_config: Mapping[str, Any], change_request: str
) -> tuple[tuple[str, str], ...]:
    """Each frozen criterion whose verifier the approved change request replaces (§8.1), at the
    test file its launch pinned, as ``(criterion_id, path)``: the new verifier is written where
    the old one was, and its bundle frozen from the candidate there. A replacement of a criterion
    this launch did not pin names no file, and is none."""
    from squadops.campaigns.change_request import load_stored_change_request

    request = load_stored_change_request(change_request)
    pinned = {
        str(pin["criterion_id"]): str(pin.get("test_path") or "")
        for pin in (resolved_config.get("campaign_proposal") or {}).get("frozen_criteria") or ()
    }
    return tuple(
        (r.criterion_id, pinned[r.criterion_id])
        for r in request.replaces_verifiers
        if pinned.get(r.criterion_id)
    )


def increment_frozen_files(
    resolved_config: Any, change_request: str | None
) -> tuple[tuple[str, str], ...]:
    """The test files of the criteria this increment's launch pinned as frozen and its approved
    change does not retire (§8.1), as ``(criterion_id, path)``. Empty for any other cycle."""
    if not change_request or increment_baseline(resolved_config) is None:
        return ()
    block = resolved_config.get("campaign_proposal") or {}
    retired = set(retired_criteria(change_request))
    return tuple(
        (str(pin["criterion_id"]), str(pin["test_path"]))
        for pin in block.get("frozen_criteria") or ()
        if pin.get("test_path") and pin["criterion_id"] not in retired
    )


def increment_test_scope(
    resolved_config: Any, change_request: str | None
) -> dict[str, list[dict[str, str]]] | None:
    """What a test in this increment may assert (#1884, the owner's rule): the approved change's
    criteria (id, statement, observable) and the statements of the criteria this increment's
    launch pinned as frozen and the change does not retire. Present for every increment, a
    ``refactor`` with no criteria included; ``None`` for any other cycle.

    The statements of the frozen ones come from the pins (#1938 stores each beside its bundle); a
    pin from before #1938 carries none, and its statement is ``""``."""
    if not change_request or increment_baseline(resolved_config) is None:
        return None
    from squadops.campaigns.change_request import load_stored_change_request

    request = load_stored_change_request(change_request)
    block = resolved_config.get("campaign_proposal") or {}
    retired = set(retired_criteria(change_request))
    return {
        "criteria": [
            {"id": c.id, "statement": c.statement, "observable": c.observable}
            for c in request.criteria
        ],
        "frozen": [
            {"criterion_id": str(pin["criterion_id"]), "statement": str(pin.get("statement") or "")}
            for pin in block.get("frozen_criteria") or ()
            if pin["criterion_id"] not in retired
        ],
    }


def test_scope_lines(scope: Mapping[str, Any]) -> str:
    """The scope as ``request.increment_test_scope_appendix``'s index: data only, one line per
    criterion, the prose the asset's (#448). Never empty, so the rule renders for an increment
    that has no criterion at all."""
    lines = [
        f"- {c['id']} (this change): {c['statement']}. Observable: {c['observable']}"
        for c in scope.get("criteria") or ()
    ]
    lines += [
        f"- {f['criterion_id']} (frozen by an earlier increment): "
        f"{f['statement'] or 'statement not recorded'}"
        for f in scope.get("frozen") or ()
    ]
    return "\n".join(lines) or "- none"


async def starting_tree_refs(
    vault: Any, cycle: Any, frozen: frozenset[str] = frozenset()
) -> list[str]:
    """The tree an increment-family implementation starts from (§10a): the accepted tree's
    delivered files, and — for a repair — the failed cycle's delivered candidate laid over them,
    so the repair continues the failed work rather than starting it again. Both are produced
    content, so each takes its slots from the skeleton's stubs (#881), and the later wins.

    Neither supplies a scaffold-frozen file (``frozen``, the candidate skeleton's): the skeleton
    regenerates those from the candidate manifest, and a carried-over copy would win over it —
    the baseline's model under the candidate's routes (#1876, the reference increment)."""
    refs = await accepted_tree_refs(vault, cycle, frozen)
    block = cycle.resolved_config().get("campaign_proposal")
    failed = block.get("repair_of") if isinstance(block, Mapping) else None
    if not failed:
        return refs
    chosen = await _delivered(vault, failed)
    return refs + [ref for path, ref in chosen.items() if path not in frozen and ref not in refs]
