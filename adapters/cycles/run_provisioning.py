"""A run's provisioning — #1507 step 2 (docs/plans/1-9-0-completion-boundary-map.md).

What ``execute_run`` does before it dispatches, moved out as found and split in two around
admission, which sits between them: ``prepare`` loads the cycle and the run, marks the run
running, announces its start or resume, and loads the plan, contract and manifest into a task
plan; ``seed`` validates a build-only run and seeds the prior artifacts, the skeleton and the
test scaffold. The admission between them is ``RunAdmission``.

**Partial state is recorded as it is reached.** ``execute_run``'s ``finally`` hands
``RunCompletion.finalize`` the cycle, the plan and the contract, and a run that fails partway
finalizes with whichever of them it had reached — a contract loaded before a failing plan
generation still arrives. Returning them only at the end would hand finalization ``None``
instead, a behaviour change hidden in an extraction. So each is written to ``RunInProgress``
on the line after the line that establishes it, and the bodies are otherwise verbatim.

It borrows late (defended-bespoke-decisions §38): every port and helper is read through the
executor at call time, under the names the bodies already used.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from adapters.cycles.execution_errors import _ExecutionError
from squadops.cycles.models import Cycle, RunStatus, WorkloadType
from squadops.cycles.task_plan import generate_task_plan
from squadops.events.types import EventType


@dataclass
class RunInProgress:
    """What ``execute_run``'s ``finally`` reads, recorded the moment each is known.

    Mutable on purpose, unlike the cycle models: it is the running record of how far a run got,
    so that a failure finalizes with exactly that (module docstring).
    """

    cycle: Cycle | None = None
    plan: list[Any] | None = None
    verification_contract: Any = None
    recruited_agent_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProvisionedRun:
    """What ``prepare`` established, for admission, seeding and dispatch."""

    run: Any
    run_root: Any
    profile: Any
    existing_checkpoint: Any
    participating_agent_ids: set[str] = field(default_factory=set)


class RunProvisioning:
    """Everything ``execute_run`` does before dispatch, bar admission."""

    #: What provisioning borrows from the executor, read at call time (§38) under the names the
    #: bodies below already used — the whole of its dependency on the executor.
    BORROWED = (
        "_artifact_vault",
        "_cycle_event_bus",
        "_cycle_registry",
        "_load_contract_for_run",
        "_load_interface_manifest_for_run",
        "_load_plan_for_run",
        "_prepare_cycle_for_run",
        "_seed_skeleton_artifacts",
        "_seed_verification_scaffold_artifacts",
        "_seeded_manifest_for_authoring",
        "_squad_profile",
    )

    def __init__(self, *, executor: Callable[[], Any]) -> None:
        self._executor = executor

    def __getattr__(self, name: str) -> Any:
        if name in RunProvisioning.BORROWED:
            return getattr(self._executor(), name)
        raise AttributeError(name)

    async def prepare(
        self,
        state: RunInProgress,
        cycle_id: str,
        run_id: str,
        profile_id: str | None,
        *,
        forwarding_overrides: dict | None,
    ) -> ProvisionedRun:
        cycle, run_root = await self._prepare_cycle_for_run(
            cycle_id, run_id, forwarding_overrides=forwarding_overrides
        )
        state.cycle = cycle
        run = await self._cycle_registry.get_run(run_id)
        profile, _ = await self._squad_profile.resolve_snapshot(profile_id)

        # queued/failed/paused -> running. Skipped when already RUNNING:
        # the resume/retry routes flip the run to RUNNING before enqueuing
        # execution (#222/#256), and RUNNING -> RUNNING is an illegal
        # transition — the unconditional call instantly failed every
        # resumed run on a lifecycle-enforcing registry (#342).
        if run.status != RunStatus.RUNNING.value:
            await self._cycle_registry.update_run_status(run_id, RunStatus.RUNNING)

        # SIP-0079: Check if resuming from checkpoint
        existing_checkpoint = await self._cycle_registry.get_latest_checkpoint(run_id)
        if existing_checkpoint:
            self._cycle_event_bus.emit(
                EventType.RUN_RESUMED,
                entity_type="run",
                entity_id=run_id,
                context={
                    "cycle_id": cycle_id,
                    "run_id": run_id,
                    "project_id": cycle.project_id,
                },
                payload={"checkpoint_index": existing_checkpoint.checkpoint_index},
            )
        else:
            self._cycle_event_bus.emit(
                EventType.RUN_STARTED,
                entity_type="run",
                entity_id=run_id,
                context={
                    "cycle_id": cycle_id,
                    "run_id": run_id,
                    "project_id": cycle.project_id,
                },
            )

        # SIP-0086 / SIP-0092: Load implementation plan for implementation
        # workloads. The plan is produced by the planning workload and
        # forwarded via plan_artifact_refs. Loading it here (not mid-loop)
        # keeps the executor deterministic — the plan is fully materialized
        # before task dispatch begins.
        implementation_plan = await self._load_plan_for_run(cycle, run)

        # SIP-0098 98.3: a seeded contract_ref switches the cycle to bind mode.
        # Loaded here (alongside the plan) so net-a inside generate_task_plan can
        # validate the plan's criteria_refs and dispatch can resolve them into
        # TypedChecks. Absent contract = author mode = today's behavior.
        verification_contract = await self._load_contract_for_run(cycle, run)
        state.verification_contract = verification_contract

        # pf-42: the proposer binds criteria for the fill slots but is told nothing
        # about the frozen files, so a check it wants on one is written against an
        # invented interior. The manifest is what those files expand from, so it is
        # the authority on their contents.
        #
        # Read from the OPERATOR-SEEDED rail, not `_load_interface_manifest_for_run`
        # — that one returns None for a framing run by design (#496), and framing is
        # exactly when the proposer needs this. The #496 rule is that a framing run
        # must not expand or carry skeleton FILES; describing the interface in a
        # prompt materializes nothing, so it stays inside that rule. Bind mode
        # already requires a seeded manifest (#494), so this is the same document
        # the gate hash-checks and the skeleton later expands from.
        interface_manifest = None
        if verification_contract is not None:
            interface_manifest = await self._seeded_manifest_for_authoring(cycle)

        # SIP-0109 §7.3: an increment's framing frames its approved change request.
        change_request = None
        if run.workload_type == WorkloadType.FRAMING:
            from squadops.campaigns.increment_tree import approved_change_request

            change_request = await approved_change_request(self._artifact_vault, cycle)

        plan = generate_task_plan(
            cycle,
            run,
            profile,
            plan=implementation_plan,
            contract=verification_contract,
            interface_manifest=interface_manifest,
            change_request=change_request,
        )
        state.plan = plan
        participating_agent_ids = {e.agent_id for e in plan}
        return ProvisionedRun(
            run=run,
            run_root=run_root,
            profile=profile,
            existing_checkpoint=existing_checkpoint,
            participating_agent_ids=participating_agent_ids,
        )

    async def seed(
        self, state: RunInProgress, provisioned: ProvisionedRun, run_id: str
    ) -> tuple[list[str], Any]:
        """The seed artifact refs and the skeleton's manifest (``None`` without one)."""
        cycle, run = state.cycle, provisioned.run
        existing_checkpoint = provisioned.existing_checkpoint
        # Build-only validation (D6): require plan_artifact_refs
        include_plan = bool(cycle.resolved_config().get("plan_tasks", True))
        include_build = bool(cycle.resolved_config().get("build_tasks"))
        seed_artifact_refs: list[str] = []
        if include_build and not include_plan:
            # Legacy build-only run: plan_artifact_refs are mandatory
            plan_refs = cycle.execution_overrides.get("plan_artifact_refs")
            if not plan_refs:
                raise _ExecutionError("plan_artifact_refs required for build-only cycle")
            seed_artifact_refs = list(plan_refs)
        elif run.workload_type is not None:
            # Multi-workload run: seed from forwarded planning artifacts
            plan_refs = cycle.execution_overrides.get("plan_artifact_refs")
            if plan_refs:
                seed_artifact_refs = list(plan_refs)

        # SIP-0099 99.3: if framing forwarded an interface manifest, expand it into a
        # walking skeleton and seed those files so develop fills the fixed slots.
        # Data-driven: no manifest -> seed_artifact_refs unchanged = byte-identical to
        # today (the manifest itself is already among plan_artifact_refs; this ADDS the
        # expanded skeleton). Logic lives in helpers (#290 god-file rule).
        # #881: never on resume. The checkpoint's artifact_refs already carry the
        # original seed set, and a fresh set stores NEW artifact ids that
        # _seed_prior_artifacts appends AFTER the restored state — last-writer-wins
        # per filename then hands every fill slot back to a stub that throws by
        # design, so the resumed run tests the skeleton instead of the app.
        interface_manifest = await self._load_interface_manifest_for_run(cycle, run)
        if interface_manifest is not None and existing_checkpoint is None:
            skeleton_refs = await self._seed_skeleton_artifacts(interface_manifest, cycle, run_id)
            seed_artifact_refs.extend(skeleton_refs)
            # SIP-0104: the deterministic test scaffold rides the same seed act, and
            # only on top of an actually-seeded skeleton — the tree its shells'
            # imports resolve against is the tree this run carries. Same #881
            # no-resume rule by construction (this whole branch is seed-time only).
            if skeleton_refs:
                seed_artifact_refs.extend(
                    await self._seed_verification_scaffold_artifacts(
                        interface_manifest, cycle, run_id
                    )
                )
                # SIP-0109 §7.3: an increment builds on the accepted tree. Its delivered files
                # are produced content, so they take every slot the stubs above would fill
                # (#881); only what the increment adds stays a stub.
                from squadops.campaigns.increment_tree import accepted_tree_refs

                seed_artifact_refs.extend(await accepted_tree_refs(self._artifact_vault, cycle))
        return seed_artifact_refs, interface_manifest
