"""The inter-workload gate — #1507 step 3 (docs/plans/1-9-0-completion-boundary-map.md).

What ``execute_cycle`` does between one workload and the next, moved out as found: validate the
authored plan (a system rejection re-rolls framing, #522/#669), take the design's questions to the
operator or pass a question-free design through the same dispatch (M4, #807), revise on a
returned-for-revision (#811), stop on a rejection or an unrecognized decision (#466), and store the
refinement notes of an approval (D10).

The loop's control flow is returned, typed, instead of acted on here: where the body said
``continue`` it returns ``RE_EXECUTE``, where it said ``break`` it returns ``STOP`` with the reason,
and falling through is ``PROCEED``. Every step carries the loop state the body may have changed
(the current run, the forwarding overrides, the two counters), read through ``step`` at the moment
it returns, so the body keeps its own local names and is otherwise verbatim.

It borrows late (defended-bespoke-decisions §38), by an explicit list of the executor's names.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from typing import Any
from uuid import uuid4

from squadops.campaigns.escalation import (
    EscalationIdentity,
    escalations,
    opening_transition,
    plan_identity,
)
from squadops.campaigns.gate import (
    INCREMENT_RULING_GATE,
    INCREMENT_SEED_PRODUCER,
    binding_from_change_request,
    submission,
)
from squadops.campaigns.models import (
    ControlOperationRefused,
    CycleKind,
    PlanGate,
    SubmittedProposal,
)
from squadops.campaigns.plan_review_tier import (
    GATE_DECIDED_BY_PLAN_REVIEW_TIER,
    TierVerdict,
    plan_footprint,
    plan_review_tier,
)
from squadops.capabilities.handlers.planning.proposal import CHANGE_REQUEST_ARTIFACT_TYPE
from squadops.cycles.cycle_end import CycleStopReason
from squadops.cycles.gate_decisions import record_gate_decision
from squadops.cycles.gate_promotion import promote_run_artifacts
from squadops.cycles.models import (
    APPROVING_DECISIONS,
    ArtifactRef,
    Cycle,
    GateDecision,
    GateDecisionValue,
    RunStatus,
    WorkloadType,
)
from squadops.events.types import EventType

# The executor's logger name: the gate's lines are read by where they have always come from.
logger = logging.getLogger("adapters.cycles.dispatched_flow_executor")


#: The decider of a plan-validation refusal: a re-rolled framing's earlier run carries it (§24bj).
PLAN_VALIDATION_DECIDER = "system:plan_validation"


class GateOutcome(StrEnum):
    """What the sequencing loop does next."""

    PROCEED = "proceed"
    RE_EXECUTE = "re_execute"
    STOP = "stop"


@dataclass(frozen=True)
class GateStep:
    """The gate's decision for the loop, with the loop state it leaves."""

    outcome: GateOutcome
    stopped_because: CycleStopReason | None
    current_run_id: str
    forwarding_overrides: dict | None
    framing_rerolls: int
    framing_revisions: int


class WorkloadGate:
    """The gate between one workload and the next."""

    BORROWED = (
        "_approve_gate_without_questions",
        "_artifact_vault",
        "_campaign_registry",
        "_create_next_workload_run",
        "_cycle_event_bus",
        "_cycle_registry",
        "_design_questions_for_gate",
        "_load_run_plan_yaml",
        "_poll_inter_workload_gate",
        "_reject_invalid_plan_before_workload_gate",
        "_run_manifest_content",
    )

    def __init__(self, *, executor: Callable[[], Any]) -> None:
        self._executor = executor

    def __getattr__(self, name: str) -> Any:
        if name in WorkloadGate.BORROWED:
            return getattr(self._executor(), name)
        raise AttributeError(name)

    async def decide(
        self,
        *,
        cycle: Cycle,
        cycle_id: str,
        run: Any,
        workload_entry: dict,
        gate_name: str,
        current_run_id: str,
        forwarding_overrides: dict | None,
        framing_rerolls: int,
        framing_revisions: int,
        max_framing_rerolls: int,
        max_framing_revisions: int,
        reentry: bool = False,
    ) -> GateStep:
        def step(outcome: GateOutcome, stopped_because: CycleStopReason | None = None) -> GateStep:
            return GateStep(
                outcome,
                stopped_because,
                current_run_id,
                forwarding_overrides,
                framing_rerolls,
                framing_revisions,
            )

        # #1922: on a re-entry after a restart, a gate that already holds its decision is not
        # asked again. Its poller died with the process, the decision landed meanwhile (or
        # before), and the sequence goes on from it as the poller would have.
        recorded = (
            next((d for d in reversed(run.gate_decisions) if d.gate_name == gate_name), None)
            if reentry
            else None
        )
        if recorded is not None:
            decision = recorded
            run_cycle = cycle.with_overrides(forwarding_overrides)
            logger.info(
                "Gate %r on run %s already holds its decision (%s by %s): re-entered after a "
                "restart, it is not asked again (#1922)",
                gate_name,
                current_run_id,
                recorded.decision,
                recorded.decided_by,
            )
        else:
            # #464: the inter-workload gate is the plan gate our cycle
            # shapes actually traverse (the mid-run _handle_gate path only
            # fires for task_flow_policy gates) — validate the authored
            # plan BEFORE asking the operator to review it. A doomed plan
            # gets a rejection, not a review request.
            #
            # #473: mechanical rejection is congruent with a human
            # --reject: a REJECTED gate decision is recorded (visible in
            # `runs show` / gate_decisions), GATE_DECIDED is emitted, and
            # the sequence stops cleanly — never a silent orchestrator
            # death the operator can only diagnose by re-reviewing the
            # manifest by hand (the 3.13 stall).
            #
            # The plan is judged against the cycle as this run saw it: what forwarding handed the
            # run — an increment's seeded contract and manifest (SIP-0109 §7.3) — is not on the
            # registry's cycle, and without it every bind-mode net reads author mode.
            run_cycle = cycle.with_overrides(forwarding_overrides)
            plan_errors = await self._reject_invalid_plan_before_workload_gate(
                run, run_cycle, gate_name
            )
            if plan_errors:
                rejection = GateDecision(
                    gate_name=gate_name,
                    decision=GateDecisionValue.REJECTED.value,
                    decided_by=PLAN_VALIDATION_DECIDER,
                    decided_at=datetime.now(UTC),
                    notes="; ".join(plan_errors),
                )
                await record_gate_decision(
                    self._cycle_registry,
                    self._artifact_vault,
                    self._cycle_event_bus,
                    project_id=cycle.project_id,
                    cycle_id=cycle_id,
                    run_id=current_run_id,
                    decision=rejection,
                )
                logger.error(
                    "Plan auto-rejected at gate %r on run %s: %s",
                    gate_name,
                    current_run_id,
                    "; ".join(plan_errors),
                )
                # #522: a *system* plan-validation rejection is a stochastic
                # framing fault (the rule the model tripped is already in its
                # prompt), not an operator's verdict — the retry a human would
                # grant instantly. Re-roll framing, bounded by
                # ``framing_max_rerolls``, rather than killing the cycle. The
                # rejection stays in gate_decisions (evidence, #473); the
                # superseded framing run is CANCELLED so the positional
                # run↔workload invariant (#257/D14) holds — exactly one
                # non-cancelled run per position. A human --reject is a
                # different decided_by and never reaches this branch.
                if (
                    workload_entry.get("type") == "framing"
                    and framing_rerolls < max_framing_rerolls
                ):
                    framing_rerolls += 1
                    await self._cycle_registry.cancel_run(current_run_id)
                    # #669: the re-roll must revise, not re-dice — thread
                    # what died and why into the new framing's authoring
                    # prompts on the §6.6 forwarding rail. The rail is
                    # rebuilt at the next workload advance, so the context
                    # never leaks past framing; a second re-roll replaces
                    # the first's context with the latest rejection.
                    rejected_plan_yaml = await self._load_run_plan_yaml(run)
                    rejection_context: dict[str, Any] = {"rejection_reasons": list(plan_errors)}
                    if rejected_plan_yaml:
                        rejection_context["rejected_plan_yaml"] = rejected_plan_yaml
                    forwarding_overrides = {
                        **(forwarding_overrides or {}),
                        "framing_rejection_context": rejection_context,
                    }
                    reroll_run = await self._create_next_workload_run(
                        cycle,
                        run,
                        workload_entry,
                        config_hash=run.resolved_config_hash,
                    )
                    current_run_id = reroll_run.run_id
                    self._cycle_event_bus.emit(
                        EventType.WORKLOAD_ADVANCED,
                        entity_type="workload",
                        entity_id=current_run_id,
                        context={"cycle_id": cycle_id, "run_id": current_run_id},
                        payload={
                            "workload_type": "framing",
                            "reason": "framing_reroll_on_system_rejection",
                            "reroll": framing_rerolls,
                        },
                    )
                    logger.info(
                        "Framing re-roll %d/%d on cycle %s: new framing run %s",
                        framing_rerolls,
                        max_framing_rerolls,
                        cycle_id,
                        current_run_id,
                    )
                    return step(GateOutcome.RE_EXECUTE)  # same index — re-execute framing
                return step(GateOutcome.STOP, CycleStopReason.PLAN_REJECTED)
            # M4 (#807): the gate stops only when the DESIGN asks a question. A
            # manifest that declares no unresolved decision has already been approved by
            # the deterministic gates, and a review that adds nothing is worse than no
            # review — it manufactures the appearance of one. Keyed on the design, never
            # on who wrote it (Guard 1a).
            tier: TierVerdict | None = None
            if gate_name == INCREMENT_RULING_GATE:
                # SIP-0109 §9.2: the supervisor's ruling alone moves this gate. An increment cycle
                # carries its baseline's manifest, which asks nothing, so #807's pass-through would
                # approve the increment unread; the proposal is submitted to the campaign instead.
                await self._submit_proposal(cycle, run)
                questions = None
            else:
                # #1905: the cycle as this run saw it, as the plan check above reads it. An
                # increment's seeded manifest reached its framing through the forwarded overrides,
                # which the stored cycle does not carry, so the question check found no design and
                # every increment's plan gate asked a human.
                questions = await self._design_questions_for_gate(run, run_cycle)
                tier = await self._plan_review_tier(cycle, run, current_run_id, questions)
            if tier is not None and tier.approves:
                # §24bj: a campaign that declares the tier has its plan gate decided by it, and
                # never by #807's pass-through, whose approvals the tier's are a subset of.
                decision = await self._approve_gate_by_tier(
                    cycle.project_id, current_run_id, cycle_id, gate_name, tier
                )
            elif tier is None and questions is not None and not questions:
                # Synthesized, not short-circuited: the decision runs through the SAME
                # exhaustive dispatch below that a human's answer does, so a
                # pass-through cannot reach a path an approval would not.
                decision = await self._approve_gate_without_questions(
                    cycle.project_id, current_run_id, cycle_id, gate_name
                )
            else:
                self._cycle_event_bus.emit(
                    EventType.WORKLOAD_GATE_AWAITING,
                    entity_type="workload",
                    entity_id=current_run_id,
                    context={"cycle_id": cycle_id, "run_id": current_run_id},
                    # The questions ARE the review request (§5c.10): an operator shown
                    # "approve?" reviews nothing; one shown "the PRD does not define the
                    # expansion checkpoint — which is it?" answers what only they know.
                    payload={
                        "gate_name": gate_name,
                        "open_questions": list(questions or ()),
                        # §24bj: what the tier could not establish, when the campaign declares it
                        **(
                            {"tier_failed": [str(c.condition) for c in tier.failed]}
                            if tier is not None
                            else {}
                        ),
                    },
                )
                if tier is not None:
                    logger.info(
                        "Gate %r on run %s escalates from the plan-review tier: %s",
                        gate_name,
                        current_run_id,
                        "; ".join(f"{c.condition}: {c.reading}" for c in tier.failed),
                    )
                    await self._open_escalation(
                        cycle, run, run_cycle, current_run_id, gate_name, tier, questions
                    )
                if questions:
                    logger.info(
                        "Gate %r on run %s is waiting on %d design question(s): %s",
                        gate_name,
                        current_run_id,
                        len(questions),
                        "; ".join(questions),
                    )
                decision = await self._poll_inter_workload_gate(
                    current_run_id,
                    cycle,
                    gate_name,
                )

        if decision.decision == GateDecisionValue.REJECTED:
            return step(
                GateOutcome.STOP, CycleStopReason.GATE_REJECTED
            )  # Run stays COMPLETED; rejection in gate_decisions

        if decision.decision == GateDecisionValue.RETURNED_FOR_REVISION:
            # #466: revision is NOT an approval — the sequence must never advance
            # with the un-revised plan (the 3.10 false-approve). #811 makes the
            # revision actually happen instead of stopping: without it the gate could
            # ask a design question and then do nothing with the answer, which is the
            # rubber stamp it replaced wearing a better costume.
            #
            # Deliberately the SAME path a system rejection takes (#522/#669), driven
            # by a different trigger — a second re-execution loop beside a proven one
            # is how they drift.
            if workload_entry.get("type") == WorkloadType.PROPOSAL:
                # SIP-0109 §9.2: the supervisor never edits a proposal. The strategy role
                # writes the next version, shown the note and the version it revises, and
                # the new version is submitted and ruled on afresh.
                revised = await self._proposal_revision(cycle, run, decision)
                if revised is None:
                    # §9.5: the revisions of one proposal are spent; it counts as rejected.
                    logger.info(
                        "Gate %r returned_for_revision on run %s: the proposal's revision "
                        "budget is spent, so it counts as rejected",
                        gate_name,
                        current_run_id,
                    )
                    return step(GateOutcome.STOP, CycleStopReason.REVISION_UNAVAILABLE)
                await self._cycle_registry.cancel_run(current_run_id)
                forwarding_overrides = {
                    **(forwarding_overrides or {}),
                    "campaign_proposal": revised,
                }
                revision_run = await self._create_next_workload_run(
                    cycle, run, workload_entry, config_hash=run.resolved_config_hash
                )
                current_run_id = revision_run.run_id
                self._cycle_event_bus.emit(
                    EventType.WORKLOAD_ADVANCED,
                    entity_type="workload",
                    entity_id=current_run_id,
                    context={"cycle_id": cycle_id, "run_id": current_run_id},
                    payload={
                        "workload_type": WorkloadType.PROPOSAL,
                        "reason": "proposal_revision_on_supervisor_request",
                        "revision": revised["version"],
                    },
                )
                return step(GateOutcome.RE_EXECUTE)
            if (
                workload_entry.get("type") == "framing"
                and framing_revisions < max_framing_revisions
            ):
                framing_revisions += 1
                # Cancel FIRST: the positional run↔workload invariant (#257/D14) is
                # exactly one non-cancelled run per position, and the superseded run
                # still occupies this one.
                await self._cycle_registry.cancel_run(current_run_id)
                revision_context: dict[str, Any] = {
                    "rejection_reasons": [
                        decision.notes.strip() or "The reviewer returned this design for revision."
                    ]
                }
                # §5c.6's "revise, don't re-roll": without the prior manifest the new
                # framing re-authors from scratch with a hint attached, which is the
                # fay-6 new-dice failure in disguise.
                prior_manifest = await self._run_manifest_content(run, run_cycle)
                if prior_manifest:
                    revision_context["prior_manifest_yaml"] = prior_manifest
                forwarding_overrides = {
                    **(forwarding_overrides or {}),
                    "framing_rejection_context": revision_context,
                    # #811: the superseded run whose completed prefix the revision
                    # restores instead of re-earning.
                    "framing_revision_source": run.run_id,
                }
                revision_run = await self._create_next_workload_run(
                    cycle,
                    run,
                    workload_entry,
                    config_hash=run.resolved_config_hash,
                )
                current_run_id = revision_run.run_id
                self._cycle_event_bus.emit(
                    EventType.WORKLOAD_ADVANCED,
                    entity_type="workload",
                    entity_id=current_run_id,
                    context={"cycle_id": cycle_id, "run_id": current_run_id},
                    payload={
                        "workload_type": "framing",
                        "reason": "framing_revision_on_operator_request",
                        "revision": framing_revisions,
                    },
                )
                logger.info(
                    "Gate %r returned_for_revision on run %s: revising (%d/%d) in "
                    "new framing run %s with the reviewer's notes as authoring "
                    "context",
                    gate_name,
                    run.run_id,
                    framing_revisions,
                    max_framing_revisions,
                    current_run_id,
                )
                return step(GateOutcome.RE_EXECUTE)  # same index — re-execute framing, revised
            logger.info(
                "Gate %r returned_for_revision on run %s: stopping the workload sequence — %s",
                gate_name,
                current_run_id,
                (
                    f"the revision budget is spent ({framing_revisions}/{max_framing_revisions})"
                    if workload_entry.get("type") == "framing"
                    else "only a framing workload can be revised"
                ),
            )
            return step(GateOutcome.STOP, CycleStopReason.REVISION_UNAVAILABLE)

        if decision.decision not in APPROVING_DECISIONS:
            # #466: exhaustive dispatch — an unknown/future decision
            # value must never silently act as an approval.
            logger.warning(
                "Gate %r on run %s carries unrecognized decision %r: "
                "stopping the workload sequence",
                gate_name,
                current_run_id,
                decision.decision,
            )
            return step(GateOutcome.STOP, CycleStopReason.GATE_DECISION_UNRECOGNIZED)

        # Write refinement notes as artifact (D10). #2029: the decision promoted the run's
        # artifacts when it was recorded, before these notes existed, so they are promoted here
        # too: the next workload's forwarding reads promoted artifacts only, and the record
        # keeps them with the plan they refine. Nothing renders them to a model; they are the
        # operator's record.
        if decision.decision == GateDecisionValue.APPROVED_WITH_REFINEMENTS and decision.notes:
            artifact_content = f"# Refinement Notes\n\n{decision.notes}\n"
            content_bytes = artifact_content.encode()
            refinement_ref = ArtifactRef(
                artifact_id=f"art_{uuid4().hex[:12]}",
                project_id=cycle.project_id,
                cycle_id=cycle.cycle_id,
                run_id=current_run_id,
                artifact_type="document",
                filename="refinement_notes.md",
                content_hash=sha256(content_bytes).hexdigest(),
                size_bytes=len(content_bytes),
                media_type="text/markdown",
                created_at=datetime.now(UTC),
                metadata={"producing_task_type": "gate.refinement_notes"},
            )
            await self._artifact_vault.store(refinement_ref, content_bytes)
            await self._cycle_registry.append_artifact_refs(
                current_run_id, (refinement_ref.artifact_id,)
            )
            await promote_run_artifacts(self._artifact_vault, current_run_id)

        if gate_name == INCREMENT_RULING_GATE:
            # SIP-0109 §7.3 (#1705 step a): the approved increment's framing binds to the
            # candidate manifest — the accepted one with the approved delta applied.
            await self._seed_increment(cycle, run)

        return step(GateOutcome.PROCEED)

    async def _plan_review_tier(
        self, cycle: Cycle, run: Any, current_run_id: str, questions: tuple[str, ...] | None
    ) -> TierVerdict | None:
        """§24bj: the tier's verdict on this plan gate, or ``None`` when the cycle's campaign does
        not declare it: a supervised campaign, or a cycle no campaign launched."""
        if not cycle.campaign_id:
            return None
        if self._campaign_registry is None:
            raise RuntimeError(
                f"campaign cycle {cycle.cycle_id} reached its plan gate on an executor wired "
                "without a campaign registry, so the plan gate its campaign declares is unreadable"
            )
        campaign = await self._campaign_registry.get_campaign(cycle.campaign_id)
        if campaign.policy.plan_gate is not PlanGate.TIER:
            return None
        if cycle.kind is None:
            raise ValueError(
                f"campaign cycle {cycle.cycle_id} records no kind, so the tier cannot tell a "
                "calibration, which the scope does not hold, from an increment"
            )
        framings = await self._cycle_registry.list_runs(
            cycle.cycle_id, workload_type=WorkloadType.FRAMING
        )
        refused = [
            r.run_id
            for r in framings
            if r.run_id != current_run_id
            and any(
                d.decided_by == PLAN_VALIDATION_DECIDER
                and d.decision == GateDecisionValue.REJECTED.value
                for d in r.gate_decisions
            )
        ]
        return plan_review_tier(
            kind=CycleKind(cycle.kind),
            open_questions=questions,
            footprint=plan_footprint(await self._load_run_plan_yaml(run)),
            allowed_scope=campaign.objective.allowed_scope,
            refused_framing_runs=refused,
        )

    async def _approve_gate_by_tier(
        self, project_id: str, run_id: str, cycle_id: str, gate_name: str, tier: TierVerdict
    ) -> GateDecision:
        """Record the tier's approval and return it, so it runs through the same dispatch a
        person's answer takes (#807's shape: recorded, never implied). Its notes say what each
        condition read; the one recorder promotes the run's artifacts (#1986)."""
        decision = GateDecision(
            gate_name=gate_name,
            decision=GateDecisionValue.APPROVED.value,
            decided_by=GATE_DECIDED_BY_PLAN_REVIEW_TIER,
            decided_at=datetime.now(UTC),
            notes=tier.notes(),
        )
        await record_gate_decision(
            self._cycle_registry,
            self._artifact_vault,
            self._cycle_event_bus,
            project_id=project_id,
            cycle_id=cycle_id,
            run_id=run_id,
            decision=decision,
        )
        return decision

    async def _open_escalation(
        self,
        cycle: Cycle,
        run: Any,
        run_cycle: Cycle,
        current_run_id: str,
        gate_name: str,
        tier: TierVerdict,
        questions: tuple[str, ...] | None,
    ) -> None:
        """§24bj: the tier could not approve, so the gate escalates. One ``escalation_opened`` row,
        keyed by what it is about, so re-entering the gate after a restart replays it; the gate
        then waits for a person, and the sweep ends the escalation."""
        assert cycle.campaign_id is not None and self._campaign_registry is not None
        campaign = await self._campaign_registry.get_campaign(cycle.campaign_id)
        proposal = run_cycle.resolved_config().get("campaign_proposal") or {}
        identity = EscalationIdentity(
            campaign_id=cycle.campaign_id,
            cycle_id=cycle.cycle_id,
            run_id=current_run_id,
            gate_name=gate_name,
            proposal_id=proposal.get("proposal_id"),
            proposal_version=proposal.get("version"),
            baseline=campaign.accepted.identity if campaign.accepted else None,
            plan_identity=plan_identity(
                await self._run_manifest_content(run, run_cycle),
                await self._load_run_plan_yaml(run),
            ),
        )
        log = await self._campaign_registry.control_log(cycle.campaign_id)
        if any(e.escalation_id == identity.escalation_id for e in escalations(log, campaign.state)):
            # A restart re-entered the gate: the escalation stands, and its bound runs from when
            # it was first opened. Writing it again would be refused as a conflicting key.
            return
        try:
            await self._campaign_registry.transition(
                cycle.campaign_id,
                opening_transition(identity, tier, questions, datetime.now(UTC)),
            )
        except ControlOperationRefused as refused:
            logger.error(
                "plan_gate_escalation_refused",
                extra={
                    "cycle_id": cycle.cycle_id,
                    "run_id": current_run_id,
                    "refusal": str(refused.entry.refusal),
                },
            )

    async def _submit_proposal(self, cycle: Cycle, run: Any) -> None:
        """Pin the proposal this run produced at its campaign's increment gate (SIP-0109 §9.2).

        The gate then waits for the supervisor's ruling, which binds to exactly this proposal.
        Keyed by the run, so re-entering the gate after a restart replays the row. A refusal is
        recorded by the registry and logged here: the gate still waits, and a ruling against a
        proposal the campaign does not hold is refused as stale.
        """
        if not cycle.campaign_id:
            raise ValueError(
                f"cycle {cycle.cycle_id} reached the {INCREMENT_RULING_GATE} gate without a "
                "campaign: only a campaign increment cycle declares it"
            )
        if self._campaign_registry is None:
            raise RuntimeError(
                f"campaign cycle {cycle.cycle_id} reached its {INCREMENT_RULING_GATE} gate on "
                "an executor wired without a campaign registry"
            )
        document = await self._change_request_document(run)
        proposal = SubmittedProposal(
            binding=binding_from_change_request(document),
            cycle_id=cycle.cycle_id,
            run_id=run.run_id,
        )
        campaign = await self._campaign_registry.get_campaign(cycle.campaign_id)
        try:
            await self._campaign_registry.transition(
                cycle.campaign_id, submission(campaign.state, proposal)
            )
        except ControlOperationRefused as refused:
            logger.error(
                "proposal_submission_refused",
                extra={
                    "cycle_id": cycle.cycle_id,
                    "run_id": run.run_id,
                    "refusal": str(refused.entry.refusal),
                },
            )

    async def _change_request_document(self, run: Any) -> str:
        """The change request the proposal run stored. A proposal workload that completed
        without one is a defect, never a gate with nothing to rule on."""
        for ref_id in tuple(run.artifact_refs or ()):
            ref, content = await self._artifact_vault.retrieve(ref_id)
            if ref.artifact_type == CHANGE_REQUEST_ARTIFACT_TYPE:
                return content.decode("utf-8")
        raise ValueError(
            f"run {run.run_id} reached the {INCREMENT_RULING_GATE} gate with no "
            f"{CHANGE_REQUEST_ARTIFACT_TYPE} artifact"
        )

    async def _proposal_revision(
        self, cycle: Cycle, run: Any, decision: GateDecision
    ) -> dict | None:
        """The ``campaign_proposal`` block the revision run proposes from, or ``None`` when the
        proposal's revisions are spent (§9.5).

        The budget is the campaign's ``max_proposal_revisions``, carried on the block; the
        revisions already made are the cycle's superseded proposal runs, read from the registry
        so a restart counts the same. The new version follows the one the supervisor returned,
        read from its stored change request, and the block carries that change request and the
        note: revise, don't re-roll (#811).
        """
        block = cycle.resolved_config().get("campaign_proposal")
        if not isinstance(block, dict) or "max_revisions" not in block:
            raise ValueError(
                f"cycle {cycle.cycle_id}: its campaign_proposal block carries no max_revisions — "
                "the campaign's revision budget is declared by its launch, never defaulted"
            )
        runs = await self._cycle_registry.list_runs(cycle.cycle_id)
        superseded = sum(
            1
            for r in runs
            if r.workload_type == WorkloadType.PROPOSAL and r.status == RunStatus.CANCELLED.value
        )
        if superseded >= int(block["max_revisions"]):
            return None
        document = await self._change_request_document(run)
        returned = binding_from_change_request(document)
        return {
            **block,
            "version": returned.version + 1,
            "supervisor_note": (decision.notes or "").strip(),
            "prior_change_request": document,
        }

    async def _seed_increment(self, cycle: Cycle, run: Any) -> None:
        """Store the approved increment's candidate manifest and the contract derived from it
        as the proposal run's promoted artifacts, where the next workload's forwarding finds
        them (``_build_forwarding_overrides``): framing then runs in bind mode against them,
        and authors no manifest (§7.3: the manifest is the baseline's plus the typed delta).

        Re-entering the gate after a restart finds the seed already stored and stores nothing.
        """
        from squadops.campaigns.change_request import (
            apply_manifest_delta,
            load_stored_change_request,
        )
        from squadops.cycles.contract_derivation import (
            SEEDED_MANIFEST_FILENAME,
            derive_and_store_contract,
        )
        from squadops.cycles.gate_promotion import promote_run_artifacts
        from squadops.cycles.manifest_authoring import MANIFEST_ARTIFACT_TYPE

        stored = await self._artifact_vault.list_artifacts(run_id=run.run_id)
        if any(r.metadata.get("producing_task_type") == INCREMENT_SEED_PRODUCER for r in stored):
            return
        request = load_stored_change_request(await self._change_request_document(run))
        block = cycle.resolved_config().get("campaign_proposal") or {}
        baseline = str(block.get("baseline_manifest") or "")
        if not baseline.strip():
            raise ValueError(
                f"cycle {cycle.cycle_id}: its campaign_proposal block carries no baseline "
                "manifest, so the approved delta has nothing to apply to"
            )
        candidate = apply_manifest_delta(baseline, request.manifest_delta).encode("utf-8")
        await self._artifact_vault.store(
            ArtifactRef(
                artifact_id=f"art_{uuid4().hex[:12]}",
                project_id=cycle.project_id,
                cycle_id=cycle.cycle_id,
                run_id=run.run_id,
                artifact_type=MANIFEST_ARTIFACT_TYPE,
                filename=SEEDED_MANIFEST_FILENAME,
                content_hash=sha256(candidate).hexdigest(),
                size_bytes=len(candidate),
                media_type="text/yaml",
                created_at=datetime.now(UTC),
                metadata={
                    "producing_task_type": INCREMENT_SEED_PRODUCER,
                    "proposal_id": request.proposal_id,
                    "version": request.version,
                },
            ),
            candidate,
        )
        await derive_and_store_contract(
            self._artifact_vault,
            cycle.project_id,
            candidate.decode("utf-8"),
            cycle_id=cycle.cycle_id,
            run_id=run.run_id,
        )
        await promote_run_artifacts(self._artifact_vault, run.run_id)
