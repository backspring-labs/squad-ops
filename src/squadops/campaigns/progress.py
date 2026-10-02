"""A campaign hears its cycle end (SIP-0109 §10, §11, §12a; #1800, #1709).

At a campaign cycle's completion boundary (``CycleCompletion``, Appendix A's choke point):
1. **the ending** is read: rejected at the increment gate, the proposal run failed, or assessed;
2. **an accepted calibration's tree is promoted** in its own transition, before the decision
   (§10: promotion comes first), its identity the hash of the files the cycle delivered;
3. **the counters** are derived from the campaign's own records: its launches, its control log
   and its cycles' usage. Nothing keeps a second count that could disagree with them;
4. **the continuation decision** runs (``squadops.campaigns.continuation``) and is written in one
   control-log row, keyed by the cycle, with a launch intent under ``proceed``.

A cycle that stopped resumable (paused, or not terminal) has not ended, and is not decided. A
decision already recorded for the cycle is returned, not recomputed (§8.4).
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import logging
import uuid
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime

from squadops.campaigns.continuation import (
    CampaignCounters,
    ContinuationDecision,
    CycleEnding,
    EndedCycle,
    Guard,
    PendingAction,
    campaign_continuation_decision,
    cycle_verdict,
)
from squadops.campaigns.evaluator_trees import FileTree
from squadops.campaigns.evidence import CycleRecords, digest, package
from squadops.campaigns.increment_tree import (
    INCREMENT_EVALUATION_ARTIFACT_TYPE,
    VERIFIER_BUNDLE_ARTIFACT_TYPE,
    increment_seed,
)
from squadops.campaigns.launch_requests import bound_launch, increment_launch
from squadops.campaigns.models import (
    AcceptedTree,
    Campaign,
    CampaignState,
    CampaignTransition,
    ControlOperation,
    ControlOperationRefused,
    ControlOutcome,
    CycleKind,
    LaunchIntentState,
    LaunchRequest,
)
from squadops.cycles.contract_derivation import is_interface_manifest
from squadops.cycles.cycle_assessment import CycleAssessment
from squadops.cycles.cycle_end import CycleStopReason
from squadops.cycles.delivered_tree import StoredArtifact, delivered_files
from squadops.cycles.models import (
    ArtifactRef,
    Cycle,
    GateDecisionValue,
    Run,
    RunStatus,
    WorkloadType,
)
from squadops.cycles.verification_integrity import RunVerdict

logger = logging.getLogger(__name__)

#: The vault type of a campaign's evidence package and digest (§14).
EVIDENCE_ARTIFACT_TYPE = "campaign_evidence"

#: The role on the rows the completion boundary writes for the campaign.
COMPLETION_ROLE = "completion"

#: Stops after which the cycle can still continue: a paused run resumes, and a run still
#: queued or running was not an ending at all (#1754).
_NOT_ENDED = frozenset({CycleStopReason.RUN_PAUSED, CycleStopReason.RUN_NOT_TERMINAL})

#: The states a launched cycle runs in; its end moves the campaign to evaluating first (§17).
_RUNNING_STATES = frozenset(
    {CampaignState.BUILDING, CampaignState.REPAIRING, CampaignState.RETRYING}
)


def cycle_ending(stopped_because: CycleStopReason, last_run: Run) -> CycleEnding:
    """How the cycle ended, for the decision. The increment gate's rejection — and a proposal
    whose revisions were spent, which §9.5 counts as rejected — is ``rejected_at_gate``; a
    proposal run that failed is ``proposal_failed``; everything else reached its assessment."""
    if last_run.workload_type == WorkloadType.PROPOSAL:
        if stopped_because in (CycleStopReason.GATE_REJECTED, CycleStopReason.REVISION_UNAVAILABLE):
            return CycleEnding.REJECTED_AT_GATE
        if last_run.status == RunStatus.FAILED.value:
            return CycleEnding.PROPOSAL_FAILED
    return CycleEnding.ASSESSED


def decision_transition(
    campaign: Campaign,
    decision: ContinuationDecision,
    *,
    ending: CycleEnding,
    verdict: RunVerdict | None,
    launch: LaunchRequest | None,
    unbuilt: str | None = None,
) -> CampaignTransition:
    """The decision's one control-log row (§10). Its binding records the decision whole — the
    row, the ending and verdict it read, and the outcome or the action with its guard — so the
    counters of later decisions are read back from it.

    - a terminal outcome completes the campaign;
    - ``escalate`` moves it to ``escalated``, waiting for the owner;
    - a guardable action under ``paused`` is held: the row records it, and the owner's resume
      executes it (§10);
    - a launch action under ``proceed`` writes its intent (``launch``). ``unbuilt`` names an
      action whose cycle cannot be launched yet; the campaign escalates with that reason rather
      than pretend to launch it.
    """
    binding: dict = {
        "cycle_id": decision.cycle_id,
        "row": decision.row,
        "ending": ending.value,
        "verdict": verdict.value if verdict else None,
    }
    if decision.terminal:
        binding |= {"outcome": decision.outcome.value, "cause": decision.cause.value}
        next_state, outcome = CampaignState.COMPLETED, decision.outcome
    else:
        binding |= {
            "action": decision.action.value,
            "guard": decision.guard.value if decision.guard else None,
            "paused_by": decision.paused_by.value if decision.paused_by else None,
        }
        outcome = None
        if decision.action is PendingAction.ESCALATE:
            next_state = CampaignState.ESCALATED
        elif decision.guard is Guard.PAUSED:
            next_state = CampaignState.PAUSED
        elif unbuilt is not None:
            binding["unbuilt"] = unbuilt
            next_state = CampaignState.ESCALATED
        else:
            next_state = _LAUNCH_STATES[decision.action]
    return CampaignTransition(
        operation=ControlOperation.DECIDE,
        actor="squadops",
        actor_role=COMPLETION_ROLE,
        reason=f"cycle {decision.cycle_id} ended ({ending}); §10 row {decision.row}",
        idempotency_key=decision_key(decision.cycle_id),
        next_state=next_state,
        outcome=outcome,
        target=decision.cycle_id,
        binding=binding,
        launch=launch if next_state in _LAUNCH_STATES.values() else None,
    )


class CannotLaunch(ValueError):
    """An action the owner's word names, whose cycle cannot be launched (and why)."""


#: The actions the owner's word executes (§10): a held one on resume, or the one an escalation
#: ruling names. ``escalate`` is the waiting itself; stopping is ``abort``.
OWNER_ACTIONS = frozenset(
    {
        PendingAction.PROPOSE,
        PendingAction.ABANDON_AND_PROPOSE,
        PendingAction.REPAIR,
        PendingAction.RETRY,
    }
)


def held_action(log: list) -> PendingAction | None:
    """The action a pausing limit holds (§10): the one recorded on the latest applied row into
    ``paused``, when that row was a decision whose guard paused it. A supervisor's pause holds
    nothing, and its resume returns the campaign where it was."""
    for entry in reversed(log):
        if entry.outcome != ControlOutcome.APPLIED or entry.next_state != CampaignState.PAUSED:
            continue
        if entry.prior_state == CampaignState.PAUSED:
            continue
        if (
            entry.operation == ControlOperation.DECIDE
            and entry.binding.get("guard") == Guard.PAUSED
        ):
            return PendingAction(entry.binding["action"])
        return None
    return None


#: The cycles that build an increment's change: the increment, and its retries and repairs
#: (§10a). Each is judged by its own evaluation (§8) and promoted when accepted.
_INCREMENT_KINDS = (CycleKind.INCREMENT, CycleKind.RETRY, CycleKind.REPAIR)

#: The cycles whose accepted tree a promotion makes the campaign's (§12a).
_PROMOTED_KINDS = (CycleKind.CALIBRATION, *_INCREMENT_KINDS)

#: An increment's approved seed: its candidate manifest and change request (#1840).
_SEED_TYPES = frozenset({"interface_manifest", "change_request"})

#: Where a launch action takes the campaign (§17).
_LAUNCH_STATES = {
    PendingAction.PROPOSE: CampaignState.AT_PROPOSAL,
    PendingAction.ABANDON_AND_PROPOSE: CampaignState.AT_PROPOSAL,
    PendingAction.RETRY: CampaignState.RETRYING,
    PendingAction.REPAIR: CampaignState.REPAIRING,
}


def increment_verdict(
    kind: CycleKind, ending: CycleEnding, evaluation: dict | None
) -> RunVerdict | None:
    """An increment's own acceptance (§8): its evaluation's verdict. One that reached its
    assessment without an evaluation is ``blocked_unverified`` — never accepted unjudged. ``None``
    for every other cycle, and for an increment that never reached its build."""
    if kind not in _INCREMENT_KINDS or ending is not CycleEnding.ASSESSED:
        return None
    if evaluation is None:
        return RunVerdict.BLOCKED_UNVERIFIED
    try:
        return RunVerdict(str(evaluation.get("verdict")))
    except ValueError:
        return RunVerdict.BLOCKED_UNVERIFIED


def frozen_criteria(log: list) -> tuple[dict, ...]:
    """Every criterion the campaign's promotions froze and none retired (§8.1), from the control
    log, in order."""
    frozen: dict[str, dict] = {}
    for entry in log:
        if (
            entry.operation is not ControlOperation.PROMOTE
            or entry.outcome is not ControlOutcome.APPLIED
        ):
            continue
        for criterion_id in entry.binding.get("retired_criteria") or ():
            frozen.pop(criterion_id, None)
        for criterion in entry.binding.get("frozen_criteria") or ():
            frozen[criterion["criterion_id"]] = dict(criterion)
    return tuple(frozen.values())


def _approved(log: list, block: Mapping) -> bool:
    """Whether an applied ruling approved this proposal version (§9.2)."""
    return any(
        entry.operation is ControlOperation.RULE
        and entry.outcome is ControlOutcome.APPLIED
        and entry.binding.get("decision") == GateDecisionValue.APPROVED.value
        and entry.binding.get("proposal_id") == block.get("proposal_id")
        and entry.binding.get("version") == block.get("version")
        for entry in log
    )


def decision_key(cycle_id: str) -> str:
    """One decision per campaign cycle (§10): the key is the cycle's."""
    return f"decide:{cycle_id}"


@dataclass(frozen=True)
class CycleRecord:
    """What the counters read of one of the campaign's cycles."""

    kind: CycleKind
    tokens: int


def derive_counters(
    campaign: Campaign,
    log: list,
    launched: list[CycleRecord],
    *,
    ending: CycleEnding,
    now: datetime,
    objective_met: bool,
) -> CampaignCounters:
    """The counters, read from the campaign's own records with the ending cycle counted (§24b).

    ``log`` is the control log; ``launched`` the cycles its launches created, in order, this one
    last. Repair and retry cycles count since the increment cycle they serve; the rejected
    proposals in a row and the unaccepted increments are read from the earlier decisions' rows.
    """
    started = next(
        (e.committed_at for e in log if e.operation == ControlOperation.START), campaign.created_at
    )
    since_increment = []
    for record in launched:
        if record.kind in (CycleKind.INCREMENT, CycleKind.CALIBRATION):
            since_increment = []
        else:
            since_increment.append(record.kind)
    applied = [e for e in log if e.outcome == ControlOutcome.APPLIED]
    decisions = [
        e.binding for e in applied if e.operation == ControlOperation.DECIDE and "row" in e.binding
    ]
    rejected_in_row = 1 if ending is CycleEnding.REJECTED_AT_GATE else 0
    if rejected_in_row:
        for binding in reversed(decisions):
            if binding.get("ending") != CycleEnding.REJECTED_AT_GATE:
                break
            rejected_in_row += 1
    return CampaignCounters(
        cycles=len(launched),
        elapsed_s=int((now - started).total_seconds()),
        tokens=sum(r.tokens for r in launched),
        repair_cycles=since_increment.count(CycleKind.REPAIR),
        retry_cycles=since_increment.count(CycleKind.RETRY),
        rejected_proposals_in_row=rejected_in_row,
        # An abandonment is counted wherever it was executed: by a decision under ``proceed``,
        # or by the owner's word (a held action resumed, an escalation ruled).
        unaccepted_increments=sum(
            1
            for e in applied
            if e.binding.get("action") == PendingAction.ABANDON_AND_PROPOSE
            and (e.operation != ControlOperation.DECIDE or e.binding.get("guard") == Guard.PROCEED)
        ),
        objective_met=objective_met,
    )


#: Reads a cycle's assessment from the stores: ``adapters.cycles.cycle_evidence.assess_cycle``.
Assess = Callable[[str], Awaitable[CycleAssessment]]


class CampaignProgress:
    def __init__(
        self,
        *,
        campaigns,
        cycles,
        vault,
        assess: Assess,
        launch: Callable[[], Awaitable[object]],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._campaigns = campaigns
        self._cycles = cycles
        self._vault = vault
        self._assess = assess
        self._launch = launch
        self._clock = clock

    async def cycle_ended(
        self, cycle: Cycle, last_run: Run, stopped_because: CycleStopReason
    ) -> ContinuationDecision | None:
        """Decide the campaign's next step for an ended cycle. ``None`` when the cycle did not
        end, the campaign has completed, or the decision was already recorded."""
        if stopped_because in _NOT_ENDED:
            return None
        campaign = await self._campaigns.get_campaign(cycle.campaign_id)
        if campaign.state is CampaignState.COMPLETED:
            return None
        log = await self._campaigns.control_log(campaign.campaign_id)
        if any(e.idempotency_key == decision_key(cycle.cycle_id) for e in log):
            return None

        latest = await self._assess(cycle.cycle_id)
        ending = cycle_ending(stopped_because, last_run)
        kind = CycleKind(cycle.kind)
        evaluation = None
        if kind in _INCREMENT_KINDS and ending is CycleEnding.ASSESSED:
            evaluation = await self._increment_evaluation(last_run)
        ended = EndedCycle(
            cycle.cycle_id, kind, ending, increment_verdict(kind, ending, evaluation)
        )
        verdict = cycle_verdict(latest, ended)

        # §12a: a calibration's tree, and an increment's when its own acceptance holds too (§8.4).
        if kind in _PROMOTED_KINDS and verdict is RunVerdict.ACCEPTED:
            campaign = await self._promote(campaign, cycle, last_run, evaluation)
        if campaign.state in _RUNNING_STATES:
            campaign = await self._evaluating(campaign, cycle)

        launched = await self._launched_cycles(campaign)
        decision = campaign_continuation_decision(
            campaign,
            derive_counters(
                campaign,
                await self._campaigns.control_log(campaign.campaign_id),
                launched,
                ending=ending,
                now=self._clock(),
                objective_met=False,
            ),
            ended,
            latest,
        )
        launch, unbuilt = None, None
        if not decision.terminal and decision.guard is Guard.PROCEED:
            built = await self._launch_for(campaign, decision.action, cycle)
            launch, unbuilt = (built, None) if isinstance(built, LaunchRequest) else (None, built)
        try:
            result = await self._campaigns.transition(
                campaign.campaign_id,
                decision_transition(
                    campaign,
                    decision,
                    ending=ending,
                    verdict=verdict,
                    launch=launch,
                    unbuilt=unbuilt,
                ),
            )
        except ControlOperationRefused as refused:
            logger.error(
                "campaign_decision_refused",
                extra={"cycle_id": cycle.cycle_id, "refusal": str(refused.entry.refusal)},
            )
            return decision
        if result.intent is not None:
            await self._launch()
        if decision.terminal:
            await self.materialize_package(campaign.campaign_id)
        return decision

    async def _promote(
        self, campaign: Campaign, cycle: Cycle, last_run: Run, evaluation: dict | None = None
    ) -> Campaign:
        """§12a: the accepted tree is the files the cycle delivered, identified by their hash,
        in a transition of its own keyed by the cycle and that identity. An increment's new
        criteria are frozen with it (§8.1): each bundle stored, and named on the row, so every
        later increment is launched with it."""
        refs = await self._vault.list_artifacts(cycle_id=cycle.cycle_id, run_id=last_run.run_id)
        chosen = delivered_files(StoredArtifact.from_record(dataclasses.asdict(r)) for r in refs)
        files = {}
        for name, art_id in chosen.items():
            _ref, content = await self._vault.retrieve(art_id)
            files[name] = content
        identity = FileTree.of(files).identity
        frozen = await self._freeze_bundles(cycle, last_run, evaluation)
        result = await self._campaigns.transition(
            campaign.campaign_id,
            CampaignTransition(
                operation=ControlOperation.PROMOTE,
                actor="squadops",
                actor_role=COMPLETION_ROLE,
                reason=f"cycle {cycle.cycle_id} accepted: its {len(files)} delivered files",
                idempotency_key=f"promote:{cycle.cycle_id}:{identity}",
                next_state=campaign.state,
                target=cycle.cycle_id,
                binding={
                    "cycle_id": cycle.cycle_id,
                    "identity": identity,
                    "files": len(files),
                    "frozen_criteria": frozen,
                    "retired_criteria": list((evaluation or {}).get("retired") or ()),
                },
                accepted=AcceptedTree(identity, cycle.cycle_id),
            ),
        )
        return result.campaign

    async def owner_action(
        self,
        campaign: Campaign,
        action: PendingAction,
        *,
        held: bool,
        actor: str,
        actor_role: str,
        reason: str,
        idempotency_key: str,
    ) -> CampaignTransition:
        """The owner's word executing ``action`` (§10), as a ``resume`` row: a launch action's
        intent is written in it, and ``abandon_and_propose`` records its abandonment with it.
        The action is executed as recorded — a held one is never recomputed. Raises
        :class:`CannotLaunch` for an action this campaign cannot execute."""
        if action not in OWNER_ACTIONS:
            raise CannotLaunch(f"{action} is not an action the owner's word executes")
        built = await self._launch_for(campaign, action, await self._last_decided_cycle(campaign))
        if isinstance(built, str):
            raise CannotLaunch(built)
        return CampaignTransition(
            operation=ControlOperation.RESUME,
            actor=actor,
            actor_role=actor_role,
            reason=reason,
            idempotency_key=idempotency_key,
            next_state=_LAUNCH_STATES[action],
            expected_state=campaign.state,
            binding={"action": action.value, "executes": "held" if held else "ruling"},
            launch=built,
        )

    async def materialize_package(self, campaign_id: str) -> tuple[str, str, str]:
        """Store the campaign's evidence package and its digest (§14, #1710): a projection of
        its records, idempotent by the package's identity. Returns (identity, the package's
        artifact id, the digest's). A cycle whose assessment cannot be read is in the package
        with the reason, never left out."""
        campaign = await self._campaigns.get_campaign(campaign_id)
        log = await self._campaigns.control_log(campaign_id)
        launches = await self._campaigns.launch_intents(campaign_id)
        records = []
        for intent in launches:
            if not intent.cycle_id:
                continue
            try:
                assessment = await self._assess(intent.cycle_id)
            except Exception as e:  # noqa: BLE001 — the package says what it could not read
                assessment = {"unreadable": f"{type(e).__name__}: {e}"}
            records.append(
                CycleRecords(
                    cycle_id=intent.cycle_id,
                    kind=intent.cycle_kind.value,
                    assessment=assessment,
                    failure_records=await self._cycles.get_failure_records(intent.cycle_id),
                )
            )
        doc = package(campaign, log, launches, records)
        for ref in await self._vault.list_artifacts(
            project_id=campaign.project_id, artifact_type=EVIDENCE_ARTIFACT_TYPE
        ):
            if (
                ref.metadata.get("campaign_id") == campaign_id
                and ref.metadata.get("identity") == doc["identity"]
                and ref.metadata.get("part") == "package"
            ):
                digest_id = ref.metadata.get("digest_artifact_id", "")
                return doc["identity"], ref.artifact_id, digest_id
        digest_ref = await self._store_evidence(
            campaign,
            doc["identity"],
            "digest",
            f"campaign-{campaign_id}-digest.md",
            digest(doc).encode("utf-8"),
            "text/markdown",
            {},
        )
        package_ref = await self._store_evidence(
            campaign,
            doc["identity"],
            "package",
            f"campaign-{campaign_id}-package.json",
            json.dumps(doc, sort_keys=True, indent=1).encode("utf-8"),
            "application/json",
            {"digest_artifact_id": digest_ref.artifact_id},
        )
        return doc["identity"], package_ref.artifact_id, digest_ref.artifact_id

    async def _store_evidence(
        self,
        campaign: Campaign,
        identity: str,
        part: str,
        filename: str,
        content: bytes,
        media_type: str,
        extra: dict,
    ):
        return await self._vault.store(
            ArtifactRef(
                artifact_id=f"art_{uuid.uuid4().hex[:12]}",
                project_id=campaign.project_id,
                artifact_type=EVIDENCE_ARTIFACT_TYPE,
                filename=filename,
                content_hash=hashlib.sha256(content).hexdigest(),
                size_bytes=len(content),
                media_type=media_type,
                created_at=self._clock(),
                metadata={
                    "campaign_id": campaign.campaign_id,
                    "identity": identity,
                    "part": part,
                    **extra,
                },
            ),
            content,
        )

    async def _increment_evaluation(self, run: Run) -> dict | None:
        """The increment's evaluation (§8), as its implementation run wrote it, or ``None``."""
        refs = await self._vault.list_artifacts(run_id=run.run_id)
        written = sorted(
            (r for r in refs if r.artifact_type == INCREMENT_EVALUATION_ARTIFACT_TYPE),
            key=lambda r: str(r.created_at),
        )
        if not written:
            return None
        _ref, content = await self._vault.retrieve(written[-1].artifact_id)
        try:
            document = json.loads(content.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            logger.error("increment_evaluation_unreadable", extra={"run_id": run.run_id})
            return None
        return document if isinstance(document, dict) else None

    async def _freeze_bundles(self, cycle: Cycle, run: Run, evaluation: dict | None) -> list[dict]:
        """Store each new criterion's verifier bundle (§8.1), once: a replayed promotion finds
        the bundle already stored under its address and reuses it."""
        if not evaluation:
            return []
        stored = {
            r.metadata.get("bundle_address"): r.artifact_id
            for r in await self._vault.list_artifacts(cycle_id=cycle.cycle_id, run_id=run.run_id)
            if r.artifact_type == VERIFIER_BUNDLE_ARTIFACT_TYPE
        }
        frozen = []
        for criterion_id, bundle in sorted((evaluation.get("new_bundles") or {}).items()):
            address = str(bundle["address"])
            artifact_id = stored.get(address) or await self._store_bundle(
                cycle, run, criterion_id, bundle
            )
            frozen.append(
                {
                    "criterion_id": criterion_id,
                    "test_path": str(bundle.get("test_path") or ""),
                    "bundle_ref": artifact_id,
                    "bundle_address": address,
                }
            )
        return frozen

    async def _store_bundle(self, cycle: Cycle, run: Run, criterion_id: str, bundle: dict) -> str:
        content = json.dumps(
            {"criterion_id": criterion_id, **bundle}, indent=2, sort_keys=True
        ).encode("utf-8")
        ref = ArtifactRef(
            artifact_id=f"art_{uuid.uuid4().hex[:12]}",
            project_id=cycle.project_id,
            artifact_type=VERIFIER_BUNDLE_ARTIFACT_TYPE,
            filename=f"verifier_bundle_{criterion_id}.json",
            content_hash=hashlib.sha256(content).hexdigest(),
            size_bytes=len(content),
            media_type="application/json",
            created_at=self._clock(),
            cycle_id=cycle.cycle_id,
            run_id=run.run_id,
            metadata={"criterion_id": criterion_id, "bundle_address": str(bundle["address"])},
        )
        await self._vault.store(ref, content)
        return ref.artifact_id

    async def _launch_for(
        self, campaign: Campaign, action: PendingAction, cycle: Cycle | None
    ) -> LaunchRequest | str:
        """The cycle a launch action writes (§10, §10a), or why it cannot be launched."""
        if action in (PendingAction.PROPOSE, PendingAction.ABANDON_AND_PROPOSE):
            return await self._propose_launch(campaign)
        kind = {PendingAction.RETRY: CycleKind.RETRY, PendingAction.REPAIR: CycleKind.REPAIR}.get(
            action
        )
        if kind is None:
            return f"{action} launches no cycle"
        if cycle is None:
            return f"no decided cycle to {action}"
        return await self._bound_launch(campaign, cycle, kind)

    async def _bound_launch(
        self, campaign: Campaign, cycle: Cycle, kind: CycleKind
    ) -> LaunchRequest | str:
        """§10a: a retry or a repair reuses exactly the increment's bound change request, ruling,
        baseline and footprint. A retry starts a fresh candidate on the accepted tree; a repair
        continues the failed cycle's candidate under its approved plan. The binding is re-checked:
        the baseline must still be the accepted tree, and the ruling that approved this version
        must be on record. A mismatch launches nothing — any change of scope, baseline or content
        needs a new proposal and ruling."""
        block = cycle.resolved_config().get("campaign_proposal")
        if not isinstance(block, dict) or not block.get("proposal_id"):
            return f"cycle {cycle.cycle_id} carries no bound change request to {kind}"
        accepted = campaign.accepted.identity if campaign.accepted else None
        if block.get("baseline_tree") != accepted:
            return (
                f"the bound ruling no longer matches: {cycle.cycle_id}'s baseline "
                f"{str(block.get('baseline_tree'))[:12]} is not the accepted tree"
            )
        log = await self._campaigns.control_log(campaign.campaign_id)
        if not _approved(log, block):
            return (
                f"no approving ruling is on record for {block['proposal_id']} "
                f"version {block.get('version')}"
            )
        seeds = await self._bound_seeds(cycle)
        if seeds is None:
            return f"cycle {cycle.cycle_id}'s approved seed cannot be found"
        plan_refs, contract_ref = seeds
        if kind is CycleKind.REPAIR:
            plan = await self._approved_plan(cycle)
            if plan is None:
                return f"cycle {cycle.cycle_id} has no approved implementation plan to repair under"
            # The failed cycle's candidate is the repair's starting tree (``starting_tree_refs``).
            block = {**block, "repair_of": cycle.cycle_id}
            plan_refs = [*plan_refs, *([plan] if plan not in plan_refs else [])]
        try:
            return bound_launch(campaign, kind, block, plan_refs, contract_ref)
        except (FileNotFoundError, ValueError) as e:
            return f"the policy's proposal profile cannot launch a {kind}: {e}"

    async def _approved_plan(self, cycle: Cycle) -> str | None:
        """The implementation plan the failed cycle built under (§10a): its framing's approved
        plan, or — for a repair of a repair — the one that repair was launched with."""
        refs = await self._vault.list_artifacts(cycle_id=cycle.cycle_id)
        plans = sorted(
            (
                r
                for r in refs
                if r.artifact_type == "control_implementation_plan"
                and r.promotion_status == "promoted"
            ),
            key=lambda r: str(r.created_at),
        )
        if plans:
            return plans[-1].artifact_id
        forwarded = list((cycle.execution_overrides or {}).get("plan_artifact_refs") or ())
        for ref_id in reversed(forwarded):
            try:
                ref, _content = await self._vault.retrieve(ref_id)
            except Exception:  # noqa: BLE001 — an unreadable ref is absent, never a crash
                continue
            if ref.artifact_type == "control_implementation_plan":
                return ref_id
        return None

    async def _bound_seeds(self, cycle: Cycle) -> tuple[list[str], str | None] | None:
        """The increment's approved seeds: from its approved proposal run (#1840), or — for a
        cycle that itself reused them — from that cycle's own launch."""
        runs = await self._cycles.list_runs(cycle.cycle_id)
        last = max(runs, key=lambda r: r.run_number) if runs else None
        if last is not None:
            seed = await increment_seed(self._vault, self._cycles, cycle, last)
            if seed is not None:
                return list(seed.plan_refs), seed.contract_ref
        # The seed types alone: a repaired cycle's launch also carried the plan it built under,
        # which a later retry frames afresh and must not inherit.
        overrides = cycle.execution_overrides or {}
        refs = []
        for ref_id in overrides.get("plan_artifact_refs") or ():
            try:
                ref, _content = await self._vault.retrieve(ref_id)
            except Exception:  # noqa: BLE001 — an unreadable seed is absent, never a crash
                logger.warning("bound seed %s unreadable", ref_id, exc_info=True)
                continue
            if ref.artifact_type in _SEED_TYPES:
                refs.append(ref_id)
        return (refs, overrides.get("contract_ref")) if refs else None

    async def _last_decided_cycle(self, campaign: Campaign) -> Cycle | None:
        """The cycle the campaign's latest decision was made for: the one a held action, or an
        escalation ruling's named action, continues."""
        log = await self._campaigns.control_log(campaign.campaign_id)
        decided = [e for e in log if e.operation is ControlOperation.DECIDE and e.target]
        if not decided:
            return None
        return await self._cycles.get_cycle(decided[-1].target)

    async def _propose_launch(self, campaign: Campaign) -> LaunchRequest | str:
        """The increment cycle a ``propose`` writes, from the accepted tree's manifest — or why
        it cannot be launched."""
        if campaign.accepted is None:
            return "the campaign has no accepted tree to propose against"
        refs = await self._vault.list_artifacts(cycle_id=campaign.accepted.cycle_id)
        manifests = sorted(
            (r for r in refs if is_interface_manifest(r)), key=lambda r: str(r.created_at)
        )
        if not manifests:
            return f"the accepted cycle {campaign.accepted.cycle_id} stored no interface manifest"
        _ref, content = await self._vault.retrieve(manifests[-1].artifact_id)
        frozen = frozen_criteria(await self._campaigns.control_log(campaign.campaign_id))
        try:
            return increment_launch(campaign, content.decode("utf-8"), frozen)
        except FileNotFoundError as e:
            return f"the policy's proposal profile cannot be loaded: {e}"

    async def _evaluating(self, campaign: Campaign, cycle: Cycle) -> Campaign:
        result = await self._campaigns.transition(
            campaign.campaign_id,
            CampaignTransition(
                operation=ControlOperation.DECIDE,
                actor="squadops",
                actor_role=COMPLETION_ROLE,
                reason=f"cycle {cycle.cycle_id} ended: evaluating",
                idempotency_key=f"evaluate:{cycle.cycle_id}",
                next_state=CampaignState.EVALUATING,
                target=cycle.cycle_id,
                binding={"cycle_id": cycle.cycle_id},
            ),
        )
        return result.campaign

    async def _launched_cycles(self, campaign: Campaign) -> list[CycleRecord]:
        records = []
        for intent in await self._campaigns.launch_intents(campaign.campaign_id):
            if intent.state is not LaunchIntentState.LAUNCHED or not intent.cycle_id:
                continue
            tokens = 0
            for run in await self._cycles.list_runs(intent.cycle_id):
                summary = await self._cycles.get_run_loop_summary(run.run_id)
                if summary is not None:
                    totals = summary.usage.totals()
                    tokens += totals.prompt_tokens + totals.completion_tokens
            records.append(CycleRecord(intent.cycle_kind, tokens))
        return records
