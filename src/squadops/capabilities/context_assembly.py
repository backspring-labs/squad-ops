"""Per-task-type context-assembly contracts (#663, 1.5 B1).

The capability-owned answer to "what does a task type's envelope contain?" —
previously four private tables and three branches inside
``DispatchedFlowExecutor._enrich_envelope`` (the accretion pattern: every
per-task-input fix grew the executor). Each task type declares ONE frozen
``ContextAssemblyContract`` here; the executor keeps a single, readable
composition point that reads the contract and performs the I/O, with zero
task-type opinions of its own.

Design boundary (plan B1, decided before code): contracts are **declarative
data, not enricher callables** — there is no pipeline of arbitrary functions
to sequence and no shared-dict mutation, so the composition stays singular
and deterministic by construction. Adding a new task type's use of existing
context kinds (or changing a filter) is a registry-entry edit beside the
capability code; a genuinely NEW context kind is a composer change, which is
correct — it is a new composition rule, not a new opinion.

Pure module: no I/O, no executor imports, importable from both the runtime
executor and agent-side capability code. (Contracts don't live on handler
classes because handlers are agent-side and the executor is runtime-side —
attribute-homed contracts would drag handler imports into runtime-api.)
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from squadops.campaigns.proposed_behaviours import QA_PROPOSED_BEHAVIOURS_ARTIFACT_TYPE
from squadops.cycles.write_authorization import normalize_ws_path
from squadops.memory.authoring_envelope import AuthoringSeam
from squadops.stacks.response_shape import response_surface_instructions
from squadops.stacks.scaffold import (
    client_surface_instructions,
    error_seam_instructions,
    frozen_surface_index_lines,
    model_surface_instructions,
    testid_surface_instructions,
)
from squadops.tasks.task_types import TaskType

# ---------------------------------------------------------------------------
# Fragment vocabulary
# ---------------------------------------------------------------------------

#: Where a resolved artifact-contents mapping lands on the envelope.
LANDING_INPUTS = "inputs"  # top-level ``inputs["artifact_contents"]`` (build tasks, D3)
LANDING_PRIOR_OUTPUTS = "prior_outputs"  # envelope-local ``prior_outputs["artifact_contents"]``
#   copy (#657 planning chain — the loop-level dict stays lean for checkpoints, RC-4)

#: Manifest-derived seam surfaces a task type may request (#588 / pf-45 / #659).
#: Constant == the envelope inputs key it lands under.
SURFACE_ERROR_CONTRACT = "error_contract"
SURFACE_MODEL = "model_surface"
SURFACE_TESTID = "testid_surface"
#: The qa-keyed landing of the SAME testid inventory (#667): identical
#: deriver, distinct envelope key — each handler reads its own variant.
SURFACE_DOM_TESTID = "dom_testid_surface"
#: #668: the frozen client's call surface — what a suite's mock of the client must honour.
SURFACE_CLIENT = "frozen_client_surface"
#: #861: what each scaffold-frozen file declares. The plan author has had this since pf-42;
#: the developer that must IMPORT from those files had not, and roll 7 died of it — it wrote
#: `import { runStore } from '@/lib/store'` against a module exporting
#: `reset, all, insert, find, nextId`, then repaired to the same invented name because the
#: repair path was blind identically. A name the author cannot see is a name it will invent.
SURFACE_FROZEN = "frozen_surface"
#: #1029: what each endpoint's SUCCESS body must carry. The developer received the error
#: contract, the model surface, the testids and the frozen index — and nothing about the
#: shape of a successful response, so the suite derived one from the manifest and the app
#: decided another. The last green roll spent its entire correction budget reconciling
#: them; the 1.6.1 shakedown died on it. Pinning the shell without this only makes the
#: gate stricter than the author it judges can see.
SURFACE_RESPONSE = "response_surface"


#: #2681: the supplement a seam's handler adds to its system prompt, which the composer counts
#: (``squadops.capabilities.prompt_budget``): the development profile's (develop) or the build
#: profile's (the builder).
SUPPLEMENT_DEVELOPMENT_PROFILE = "development_profile"
SUPPLEMENT_BUILD_PROFILE = "build_profile"


@dataclass(frozen=True)
class ArtifactFilter:
    """A stored-artifact selection spec (the shape ``_resolve_artifact_contents``
    consumes): pick by producing task type, by artifact type, with a fallback
    type-set applied only when the primary axes select nothing."""

    by_producing_task: tuple[str, ...] = ()
    by_type: tuple[str, ...] = ()
    by_type_fallback: tuple[str, ...] = ()

    def to_spec(self) -> dict[str, list[str]]:
        spec: dict[str, list[str]] = {}
        if self.by_producing_task:
            spec["by_producing_task"] = list(self.by_producing_task)
        if self.by_type:
            spec["by_type"] = list(self.by_type)
        if self.by_type_fallback:
            spec["by_type_fallback"] = list(self.by_type_fallback)
        return spec


@dataclass(frozen=True)
class ContextAssemblyContract:
    """One task type's context declaration — dispatch-time and plan-time.

    Dispatch-time (composed by the executor's ``_enrich_envelope``):
    ``artifact_filter``/``artifact_landing``: which stored artifacts the task
    sees and where they land. ``acceptance_workspace``: thread the full
    accepted tree for typed-acceptance evaluation (#643 — rides separately
    from the curated prompt context). ``manifest_surfaces``: which scaffold
    seam-instruction sets to thread, presence-keyed (#588/pf-45/#659).
    ``wrapup_evidence``: the run-level CycleOutcome injection applies when any
    planned task carries this flag (#683).

    Plan-time (composed by ``generate_task_plan``, S3 — the flags name WHO
    receives an input class; the derivation mechanics stay with the plan
    composer): ``plan_rejection_context``: a #522 framing re-roll threads the
    prior framing's rejection reasons onto this task (#669).
    ``bind_criteria_index``: in bind mode this proposer receives the
    contract's criteria index + the frozen-surface index, so it binds
    covered-file criteria instead of authoring them (SIP-0098 98.3 / pf-42).
    ``prior_cycle_brief``: in a retry or a repair this author is handed the failed cycle's
    brief, the record of the cycle it recovers from (#1692, SIP-0109 §10a).
    ``bind_behavioral_surface``: in bind mode this task receives the
    contract's behavioral surface — serialized probes (98.5), the
    endpoint→fill-slot ownership map (#688), pinned-status expectation lines
    (#629/pf-54), and the DOM anchor inventory (#659) — all presence-keyed.
    """

    artifact_filter: ArtifactFilter | None = None
    artifact_landing: str = LANDING_INPUTS
    acceptance_workspace: bool = False
    manifest_surfaces: tuple[str, ...] = ()
    wrapup_evidence: bool = False
    plan_rejection_context: bool = False
    prior_cycle_brief: bool = False
    bind_criteria_index: bool = False
    bind_behavioral_surface: bool = False
    #: SIP-0104 P3: this task receives the deterministic test scaffold (slot table +
    #: shell files) and authors in fill mode when the stack opts in. Derived from the
    #: interface manifest at injection (Gate 1 byte-equivalence makes re-derivation
    #: exact); presence-keyed like every surface here.
    bind_verification_scaffold: bool = False
    #: SIP-0109 §8: this task judges an increment. At plan time it is handed the increment's
    #: id, each new criterion's own file and the candidate's declared routes; at dispatch the
    #: accepted tree the increment builds on (the accepted cycle's delivered files, as the run
    #: seeded them, #1842), beside the candidate (``acceptance_workspace``).
    increment_evaluation: bool = False
    #: #1884 (the owner's rule): an increment's test author is handed what its tests may assert
    #: (``increment_test_scope``: the approved criteria and the frozen ones' statements), and is
    #: told the rule through ``request.increment_test_scope_appendix``. Declared on the task that
    #: authors the suite; its repair inherits it through ``REPAIR_PRESENCE_KEYS``.
    increment_test_scope: bool = False
    #: SIP-0110 §0.9: the authoring seam this task is, where cross-cycle memory is supplied and
    #: where its pre-authoring state is captured for replay (#2105). Plan writing is not declared
    #: here: it is the #2058 call site, read from ``plan_rejection_context``
    #: (:func:`authoring_seam_of`), so the fact has one author.
    authoring_seam: AuthoringSeam | None = None
    #: #2681: what an authoring seam's prompt is made of besides its inputs and memory's sections,
    #: so the composer counts what the handler renders (``squadops.capabilities.prompt_budget``).
    #: Every request template the handler may render, each counted whole: an appendix renders only
    #: with its input, so the count is an upper bound. A tuple inside is a set of alternatives, of
    #: which a prompt renders one (a path's main template, a stack's fill-only appendix), counted at
    #: its largest. Memory's own section templates aren't here, since the composer measures those
    #: sections itself.
    prompt_templates: tuple[str | tuple[str, ...], ...] = ()
    #: The inputs the task carries that its handler never renders, so they aren't counted. Anything
    #: not named here is counted, so a new input reads as rendered until it's declared otherwise.
    unrendered_inputs: frozenset[str] = frozenset()
    #: The supplement the handler adds to the system prompt (``SUPPLEMENT_*``), or none.
    system_supplement: str = ""
    #: Whether the handler renders its development profile's fill-only appendix, which the profile
    #: names (``DevelopmentProfile.fill_only_template``), so it's counted at the largest shipped.
    fill_only_appendix: bool = False


_EMPTY_CONTRACT = ContextAssemblyContract()


# ---------------------------------------------------------------------------
# The registry
# ---------------------------------------------------------------------------

#: #643/#644: acceptance/patch-verification workspace composition — the full
#: accepted tree (scaffold siblings included), single-sourced with qa.test's
#: prompt context (qa evaluates the same tree it reads).
ACCEPTANCE_WORKSPACE_FILTER = ArtifactFilter(
    by_producing_task=(
        TaskType.QA_VALIDATE,
        TaskType.BUILDER_ASSEMBLE,
        TaskType.DEVELOPMENT_DEVELOP,
    ),
    by_type=("source", "config"),
    by_type_fallback=("document",),
)

#: SIP-0109 §8: the tree an increment's evaluation judges — the candidate as built, with its qa
#: suites. Discrimination freezes each criterion's own test file from it and runs it on both
#: trees, so a workspace cut to source and config (the filter above) leaves every criterion
#: ``not_run`` (#1880, the reference increment).
INCREMENT_CANDIDATE_FILTER = ArtifactFilter(
    by_producing_task=ACCEPTANCE_WORKSPACE_FILTER.by_producing_task,
    by_type=(*ACCEPTANCE_WORKSPACE_FILTER.by_type, "test"),
    by_type_fallback=ACCEPTANCE_WORKSPACE_FILTER.by_type_fallback,
)

_DEV_SURFACES = (
    SURFACE_ERROR_CONTRACT,
    SURFACE_MODEL,
    SURFACE_TESTID,
    SURFACE_FROZEN,
    SURFACE_RESPONSE,
)

# --- #2681: what each authoring seam's prompt is made of, as its handler renders it --------
#: The context slots every build and plan author shares (``context_sections``): the product a
#: source-backed run changes and a retry's prior cycle. Memory's own slots are measured apart.
_SHARED_CONTEXT_TEMPLATES = (
    "request.source_repository_appendix",
    "request.source_repository_checks_block",
    "request.source_repository_existing_files_block",
    "request.source_repository_instructions_block",
    "request.prior_cycle_brief_appendix",
)
#: What a cycle task's re-dispatch appends: the emission retry's feedback and the disputes.
_CYCLE_TASK_RETRY_TEMPLATES = (
    "request.cycle_emission_retry_feedback",
    "request.cycle_cap_exhausted_retry",
    "request.cycle_cap_truncated_retry",
    "request.disputed_checks_appendix",
)
_DEVELOP_APPENDIX_TEMPLATES = (
    "request.development_develop_error_contract_appendix",
    "request.development_develop_frozen_surface_appendix",
    "request.development_develop_model_surface_appendix",
    "request.development_develop_response_surface_appendix",
    "request.development_develop_testid_surface_appendix",
)
_PLANNING_TEMPLATES = (
    "request.planning_task_base",
    "request.increment_framing_section",
    "request.plan_reroll_rejected_plan_appendix",
    "request.plan_reroll_rejection_appendix",
    "request.target_stack_section",
    "request.design_revision_request_appendix",
    *_SHARED_CONTEXT_TEMPLATES,
)
_PLAN_PROPOSAL_TEMPLATES = (
    "request.plan_authoring_rules_appendix",
    "request.plan_bind_criteria_appendix",
    "request.plan_blocking_gaps_appendix",
    "request.plan_frozen_surface_appendix",
    "request.plan_increment_criteria_appendix",
    "request.plan_increment_footprint_appendix",
    "request.plan_increment_frozen_appendix",
    "request.plan_increment_regenerated_appendix",
    "request.increment_test_scope_appendix",
    *_SHARED_CONTEXT_TEMPLATES,
)
#: Inputs a build author carries for its evaluation, never shown in its prompt.
_EVALUATION_ONLY_INPUTS = frozenset(
    {"acceptance_workspace_files", "workspace_revision_id", "artifact_refs"}
)

CONTEXT_CONTRACTS: dict[str, ContextAssemblyContract] = {
    # --- build tasks (D3): curated prompt context + acceptance workspace ----
    TaskType.DEVELOPMENT_DEVELOP: ContextAssemblyContract(
        artifact_filter=ArtifactFilter(
            by_producing_task=(
                TaskType.STRATEGY_ANALYZE_PRD,
                TaskType.DEVELOPMENT_DESIGN,
                TaskType.DEVELOPMENT_DEVELOP,
            ),
            by_type_fallback=("document",),
        ),
        acceptance_workspace=True,
        # #588/pf-45/#659: the error-contract raise convention, the model
        # field surface, and the DOM testid inventory — to the INITIAL author
        # on the same transport repairs have always used.
        manifest_surfaces=_DEV_SURFACES,
        prior_cycle_brief=True,
        authoring_seam=AuthoringSeam.BUILD_AUTHORING,
        prompt_templates=(
            (
                "request.development_develop.code_generate",
                "request.development_develop.focused_build_task",
            ),
            "request.development_develop_narrative_criteria_appendix",
            "request.development_develop_prior_artifacts_appendix",
            "request.cycle_repair_contract_expectations_appendix",
            *_DEVELOP_APPENDIX_TEMPLATES,
            *_SHARED_CONTEXT_TEMPLATES,
            *_CYCLE_TASK_RETRY_TEMPLATES,
        ),
        unrendered_inputs=_EVALUATION_ONLY_INPUTS | {"resolved_config"},
        system_supplement=SUPPLEMENT_DEVELOPMENT_PROFILE,
        fill_only_appendix=True,
    ),
    TaskType.BUILDER_ASSEMBLE: ContextAssemblyContract(
        artifact_filter=ArtifactFilter(
            by_producing_task=(TaskType.DEVELOPMENT_DEVELOP,),
            by_type=("source", "config"),
            by_type_fallback=("document",),
        ),
        acceptance_workspace=True,
        prior_cycle_brief=True,
        authoring_seam=AuthoringSeam.BUILD_AUTHORING,
        prompt_templates=(
            "request.builder_assemble.build_assemble",
            *_SHARED_CONTEXT_TEMPLATES,
            *_CYCLE_TASK_RETRY_TEMPLATES,
        ),
        unrendered_inputs=_EVALUATION_ONLY_INPUTS,
        system_supplement=SUPPLEMENT_BUILD_PROFILE,
    ),
    # qa.test's prompt context IS the full accepted tree (#644); in bind mode
    # it additionally carries the contract's behavioral surface at PLAN time.
    #
    # frozen_surface (roll 9, cyc_a92eaa4f4052): the suite author imports app modules
    # and packages, and the prompt-scoped artifact view is cut to the suite's own
    # package prefix — so the tree it imports FROM is exactly what it cannot see.
    # Roll 9's suite opened with `import request from 'supertest'` against a
    # package.json declaring no such package, and V2's wrote `from .store import reset`
    # against a module reachable only as `backend.store`. Same transport dev has
    # had since #861; the index's per-file lines carry the import-as form and the
    # dependency surface for precisely these two failures.
    TaskType.QA_TEST: ContextAssemblyContract(
        artifact_filter=ACCEPTANCE_WORKSPACE_FILTER,
        acceptance_workspace=True,
        bind_behavioral_surface=True,
        manifest_surfaces=(SURFACE_FROZEN,),
        bind_verification_scaffold=True,
        prior_cycle_brief=True,
        increment_test_scope=True,
        authoring_seam=AuthoringSeam.BUILD_AUTHORING,
        prompt_templates=(
            "request.qa_test.test_validate",
            "request.qa_test_assembly_notes_appendix",
            "request.qa_test_behavior_contract_appendix",
            "request.qa_test_client_surface_appendix",
            "request.qa_test_dom_anchor_appendix",
            "request.qa_test_frozen_surface_appendix",
            "request.qa_test_proposed_behaviours_appendix",
            "request.qa_test_retained_cases_appendix",
            "request.qa_test_retake_appendix",
            "request.qa_test_fill_mode_appendix",
            "request.cycle_repair_anchored_edit_appendix",
            "request.cycle_repair_current_files",
            "request.increment_test_scope_appendix",
            *_SHARED_CONTEXT_TEMPLATES,
            *_CYCLE_TASK_RETRY_TEMPLATES,
        ),
        unrendered_inputs=_EVALUATION_ONLY_INPUTS,
    ),
    # --- planning chain (#657): upstream documents on an envelope-local
    # prior_outputs copy; all four authoring types receive a re-roll's
    # rejection context (#669 — fresh dice previously meant zero teaching,
    # fay-10 re-tripped the same class three times). governance.merge_plan takes
    # NEITHER artifact threading nor rejection context: by merge time both proposals
    # collide on the proposed_plan_tasks.yaml filename, so artifact threading would
    # silently drop one proposal (the merger consumes brief_outcome/
    # proposal_outcome output keys instead), and its normal merge path is
    # deterministic — no prompt for rejection context to teach.
    # bind_criteria_index (SIP-0098 98.3): dev/qa propose BUILD tasks and so
    # bind covered-file criteria; strategy proposes guidance and the brief
    # author frames — neither is indexed.
    #
    # #846: "its normal merge path is deterministic" was true of the merge and hid the
    # case that matters. When no plan_authoring_contributors are configured the proposers
    # never run, and merge_plan authors the whole plan itself through an LLM — the
    # sole-author fallback, which is the DEFAULT for every CRP but validation-multirole.
    # Reading merge_plan's absence here as "this task type has no prompt" left the one
    # author that actually reaches implementation as the only one never given the
    # contract. Measured on cyc_0edb55919384: 0 criteria_refs, 3 frozen files claimed,
    # 8 invented paths. So it is present now, for the index alone.
    TaskType.GOVERNANCE_MERGE_PLAN: ContextAssemblyContract(bind_criteria_index=True),
    TaskType.GOVERNANCE_PREPARE_PLAN_AUTHORING_BRIEF: ContextAssemblyContract(
        artifact_filter=ArtifactFilter(
            by_producing_task=(
                TaskType.DATA_RESEARCH_CONTEXT,
                TaskType.STRATEGY_FRAME_OBJECTIVE,
                TaskType.DEVELOPMENT_DESIGN_PLAN,
                TaskType.QA_DEFINE_TEST_STRATEGY,
            ),
        ),
        artifact_landing=LANDING_PRIOR_OUTPUTS,
        plan_rejection_context=True,
        prior_cycle_brief=True,
        prompt_templates=_PLANNING_TEMPLATES,
    ),
    # #811: the technical design answers an operator's revision request too. A note about
    # the interface is a note about the design, and a revision that changed only the manifest
    # would leave `technical_design.md` describing an interface that no longer exists.
    TaskType.DEVELOPMENT_DESIGN_PLAN: ContextAssemblyContract(
        plan_rejection_context=True,
        prior_cycle_brief=True,
        prompt_templates=_PLANNING_TEMPLATES,
    ),
    # #1692: an increment's test strategy covers its new criteria, and a retry's is written
    # knowing which of them failed before.
    TaskType.QA_DEFINE_TEST_STRATEGY: ContextAssemblyContract(prior_cycle_brief=True),
    # SIP-0103 §5c.1 (#791): the manifest author's input contract, as data. The PRD and
    # the blueprint's vocabulary arrive on the envelope; what lands here is the cycle's
    # OWN framing — strategy's frame (which §5a has constraining scope from above) and
    # dev's technical design, which the manifest is the typed expression of. Summaries
    # alone are 240 characters and would make the author re-derive a design it just wrote.
    # Nothing from outside the cycle: the reference manifest is excluded by §4, and
    # cross-cycle recall is a declared future extension, not an omission.
    TaskType.DEVELOPMENT_AUTHOR_MANIFEST: ContextAssemblyContract(
        artifact_filter=ArtifactFilter(
            by_producing_task=(
                TaskType.STRATEGY_FRAME_OBJECTIVE,
                TaskType.DEVELOPMENT_DESIGN_PLAN,
            ),
        ),
        artifact_landing=LANDING_PRIOR_OUTPUTS,
        plan_rejection_context=True,
        prompt_templates=(
            "request.development_author_manifest",
            "request.manifest_authoring_rules_appendix",
            "request.manifest_revision_feedback",
            "request.manifest_revision_request_appendix",
            *_SHARED_CONTEXT_TEMPLATES,
        ),
    ),
    TaskType.DEVELOPMENT_PROPOSE_PLAN_TASKS: ContextAssemblyContract(
        artifact_filter=ArtifactFilter(
            by_producing_task=(
                TaskType.GOVERNANCE_PREPARE_PLAN_AUTHORING_BRIEF,
                TaskType.DEVELOPMENT_DESIGN_PLAN,
            ),
        ),
        artifact_landing=LANDING_PRIOR_OUTPUTS,
        plan_rejection_context=True,
        bind_criteria_index=True,
        prior_cycle_brief=True,
        prompt_templates=("request.development_propose_plan_tasks", *_PLAN_PROPOSAL_TEMPLATES),
    ),
    TaskType.QA_PROPOSE_PLAN_TASKS: ContextAssemblyContract(
        artifact_filter=ArtifactFilter(
            by_producing_task=(
                TaskType.GOVERNANCE_PREPARE_PLAN_AUTHORING_BRIEF,
                TaskType.DEVELOPMENT_DESIGN_PLAN,
                TaskType.QA_DEFINE_TEST_STRATEGY,
                TaskType.DEVELOPMENT_PROPOSE_PLAN_TASKS,
            ),
        ),
        artifact_landing=LANDING_PRIOR_OUTPUTS,
        plan_rejection_context=True,
        bind_criteria_index=True,
        prior_cycle_brief=True,
        prompt_templates=("request.qa_propose_plan_tasks", *_PLAN_PROPOSAL_TEMPLATES),
    ),
    TaskType.STRATEGY_PROPOSE_PLAN_GUIDANCE: ContextAssemblyContract(
        artifact_filter=ArtifactFilter(
            by_producing_task=(
                TaskType.GOVERNANCE_PREPARE_PLAN_AUTHORING_BRIEF,
                TaskType.STRATEGY_FRAME_OBJECTIVE,
            ),
        ),
        artifact_landing=LANDING_PRIOR_OUTPUTS,
        plan_rejection_context=True,
        prior_cycle_brief=True,
        prompt_templates=("request.strategy_propose_plan_guidance", *_PLAN_PROPOSAL_TEMPLATES),
    ),
    # --- wrap-up pipeline (#683): the run-level verification_evidence
    # injection fires when any planned task carries the flag.
    # --- SIP-0109 §8: an increment's acceptance judges the candidate against the accepted
    # tree, so it is handed both.
    TaskType.QA_EVALUATE_INCREMENT: ContextAssemblyContract(
        acceptance_workspace=True, increment_evaluation=True
    ),
    # --- SIP-0110 §0.9: the proposal and the pulse-check repair are authoring seams. Neither
    # threads other context through this registry: the proposal's arrives on its launch
    # (SIP-0109 §9.1), and the pulse repair chain composes its own (SIP-0070).
    TaskType.STRATEGY_PROPOSE_INCREMENT: ContextAssemblyContract(
        authoring_seam=AuthoringSeam.PROPOSAL_WRITING,
        # SIP-0113 §4.5: its ``proposal_evidence`` input is rendered, so it's counted as its own.
        prompt_templates=(
            "request.strategy_propose_increment",
            # SIP-0113 §4.5: what the proposal is shown of its accepted tree, from its evidence.
            "request.proposal_accepted_prd",
            "request.proposal_outcome_goals",
            "request.proposal_quality_moves",
            "request.proposal_abandoned_increment",
            "request.proposal_frozen_conventions",
            "request.proposal_prd_section",
            "request.proposal_qa_proposed_behaviours",
            "request.proposal_supervisor_revision",
            "request.proposal_unapproved_proposals",
            "request.change_request_revision_feedback",
        ),
    ),
    TaskType.DEVELOPMENT_REPAIR: ContextAssemblyContract(
        authoring_seam=AuthoringSeam.REPAIR, prompt_templates=("request.repair_task_base",)
    ),
    TaskType.DATA_GATHER_EVIDENCE: ContextAssemblyContract(wrapup_evidence=True),
    TaskType.QA_ASSESS_OUTCOMES: ContextAssemblyContract(wrapup_evidence=True),
    TaskType.DATA_CLASSIFY_UNRESOLVED: ContextAssemblyContract(wrapup_evidence=True),
    TaskType.GOVERNANCE_CLOSEOUT_DECISION: ContextAssemblyContract(wrapup_evidence=True),
    TaskType.GOVERNANCE_PUBLISH_HANDOFF: ContextAssemblyContract(wrapup_evidence=True),
}


#: Task types that dispatch with NO curated context, on purpose — each with the reason.
#:
#: Before this set existed, an absent registry entry was unreadable: it meant either "this
#: task needs nothing" or "nobody decided", and the two are indistinguishable exactly when
#: it matters. That ambiguity is how #846 happened — `governance.merge_plan`'s absence was
#: read as "the merger consumes proposer outputs, no prompt to curate", which was true of
#: the merge path and silently wrong about the sole-author path that reaches
#: implementation on every default CRP. A task type in NEITHER structure fails the
#: context-completeness test, so adding a task type forces the decision to be recorded
#: here rather than defaulted invisibly.
#:
#: Repair task types are deliberately not listed: they dispatch through the correction
#: runner with ``REPAIR_CONTEXT_CONTRACT`` (their curated context IS declared, above).
DECLARED_NO_CONTEXT: frozenset[str] = frozenset(
    {
        # Basic-cycle document chain (SIP-0066 §5.4): prompts build from the PRD and
        # prior_outputs on the envelope; no typed acceptance judges these outputs.
        TaskType.STRATEGY_ANALYZE_PRD,
        TaskType.DEVELOPMENT_DESIGN,
        TaskType.QA_VALIDATE,
        TaskType.DATA_REPORT,
        TaskType.GOVERNANCE_REVIEW,
        # Framing backbone upstream of the planning chain: these AUTHOR the documents
        # the planning filters above select; their own inputs are envelope-native.
        TaskType.DATA_RESEARCH_CONTEXT,
        TaskType.STRATEGY_FRAME_OBJECTIVE,
        # Sign-off only (SIP-0093): the gate package rides prior_outputs, and plan
        # validation is deterministic and upstream of this task.
        TaskType.GOVERNANCE_REVIEW_PLAN,
        # Implementation-workload framing head: emits the done-definition from the
        # PRD and plan already on the envelope.
        TaskType.GOVERNANCE_DEFINE_DONE,
        # Refinement pair (SIP-0078 §5.10): feedback and validation both arrive as
        # explicit envelope inputs from the refinement request.
        TaskType.GOVERNANCE_INCORPORATE_FEEDBACK,
        TaskType.QA_VALIDATE_REFINEMENT,
        # Correction protocol (SIP-0079 §7.7): the correction runner composes their
        # evidence inputs (failure_evidence, correction context) explicitly per failure.
        TaskType.DATA_ANALYZE_FAILURE,
        TaskType.GOVERNANCE_CORRECTION_DECISION,
    }
)


#: #667: the repair envelope's own context declaration (S2) — the anchor
#: surface must survive the correction loop, RE-DERIVED from the manifest
#: (same deriver as initial dispatch), never copied from the failed envelope:
#: the dev repair chain is routinely reached from a failed qa.test task
#: (SUBJECT locus), whose envelope carries only the qa-keyed variant. Both
#: key variants ride every repair envelope; each handler reads its own.
#: SURFACE_FROZEN (roll 7, cyc_0e301961f099): #861 gave the INITIAL dev author the
#: frozen index and left the repair envelope without it — so the repair that followed
#: roll 7's invented `runStore` import "invented the same name again because it was
#: blind identically" and the chain terminated as plan_defect on a defect no repair
#: could see. This threads the key; the repair mixin renders it (dev: inside the
#: fill-only appendix; qa: its own appendix — ``_RepairPromptMixin``).
#: #1060: the declaration was THREE surfaces short of what the repair mixin already
#: renders. `_render_fill_only_section` builds an error-contract block and a
#: model-surface block from `inputs["error_contract"]` / `inputs["model_surface"]`, and
#: its comment claims "parity with develop's four surfaces" — but neither key was ever
#: threaded here, so both blocks have rendered EMPTY since they were written. The
#: renderer was added and the data never was.
#:
#: `response_surface` is the third, and the one that cost cyc_87c12c7f199e: the manifest
#: declares `participants: list[Participant]`, #1029's frozen-spine floor reported the
#: shape defect on all FOUR rounds, and every repair re-emitted `string[]` because the
#: one agent retrying a shape defect was the only one never shown the shape.
#:
#: Kept in step by `test_repair_threads_every_surface_the_developer_gets` — a comment
#: asking for parity is what produced two inert renderers.
REPAIR_CONTEXT_CONTRACT = ContextAssemblyContract(
    authoring_seam=AuthoringSeam.REPAIR,
    prompt_templates=(
        ("request.cycle_repair_task", "request.cycle_task_base"),
        "request.cycle_repair_anchored_edit_appendix",
        "request.cycle_repair_anchored_edit_retry",
        "request.cycle_repair_app_traceback_appendix",
        ("request.cycle_repair_closing_scoped", "request.cycle_repair_closing_whole_file"),
        "request.cycle_repair_contract_expectations_appendix",
        "request.cycle_repair_current_files",
        "request.cycle_repair_decision_lead",
        "request.cycle_repair_decision_rule",
        "request.cycle_repair_loop_state",
        ("request.cycle_repair_output_scoped", "request.cycle_repair_output_whole_file"),
        "request.qa_test_client_surface_appendix",
        "request.qa_test_dom_anchor_appendix",
        "request.qa_test_frozen_surface_appendix",
        "request.qa_test_repair_failing_cases_appendix",
        "request.qa_test_repair_fill_appendix",
        "request.disputed_checks_appendix",
        *_DEVELOP_APPENDIX_TEMPLATES,
    ),
    # The repair shows the failed task's named files from the accepted tree (its current-files
    # section), so that tree is counted whole, an upper bound. It never shows the curated context
    # or the product's repository, and has no shared context slots.
    unrendered_inputs=frozenset(
        {
            "workspace_revision_id",
            "artifact_refs",
            "artifact_contents",
            "source_repository",
            "resolved_config",
        }
    ),
    fill_only_appendix=True,
    manifest_surfaces=(
        SURFACE_ERROR_CONTRACT,
        SURFACE_MODEL,
        SURFACE_TESTID,
        SURFACE_DOM_TESTID,
        SURFACE_CLIENT,
        SURFACE_FROZEN,
        SURFACE_RESPONSE,
    ),
)

#: Presence-keyed retest forwarding (S2): failed-envelope inputs a retest
#: re-dispatch copies ONLY when present — probe-less contracts thread no key
#: (#639), the typed-acceptance workspace forwards exactly when the original
#: dispatch carried it (#643), and the retest's from-scratch suite re-author
#: needs the DOM anchor surface the original dispatch carried (#667). A key
#: silently forwarded as empty would flip the handlers' presence-gated
#: sections.
RETEST_PRESENCE_KEYS: tuple[str, ...] = (
    "contract_probes",
    "acceptance_workspace_files",
    # #734 Slice A: the workspace identity travels WITH the forwarded tree,
    # so retest evidence shows the forwarded id == the failed task's id —
    # the forwarded-vs-reassembled distinction, visible for the first time.
    "workspace_revision_id",
    SURFACE_DOM_TESTID,
    # #668: the retest's re-author mocks beneath the same frozen client.
    SURFACE_CLIENT,
    # SIP-0104 P3: a retest that re-authors from scratch must still be in fill
    # mode — losing the key would flip it back to whole-suite authorship.
    "verification_scaffold",
)


def retest_forwarded_inputs(failed_inputs: Mapping[str, Any]) -> dict[str, Any]:
    """The failed task's context a retest re-dispatch carries forward (#456).

    Unconditional keys are the failed task's workspace and contract identity —
    the retest must evaluate the same tree against the same contract (missing
    workspace defaults to empty; the runner skips the doomed dispatch before
    composing). ``RETEST_PRESENCE_KEYS`` forward presence-keyed.
    """
    forwarded: dict[str, Any] = {
        "resolved_config": failed_inputs.get("resolved_config", {}),
        "artifact_contents": failed_inputs.get("artifact_contents", {}),
        "subtask_focus": failed_inputs.get("subtask_focus"),
        "expected_artifacts": failed_inputs.get("expected_artifacts", []),
        "acceptance_criteria": failed_inputs.get("acceptance_criteria", []),
    }
    for key in RETEST_PRESENCE_KEYS:
        if failed_inputs.get(key):
            forwarded[key] = failed_inputs[key]
    return forwarded


#: #1229: a repair evaluates the failed task's typed criteria on its own patched tree
#: BEFORE returning — in the agent container, where the stack's toolchain lives — and the
#: executor's verification consumes those executed rows. That evaluation needs the same
#: workspace the primary and the verifier materialise (#643: module-level checks false-fail
#: a correct fill in a patch-only tree), so the repair forwards it exactly as the retest
#: does: presence-keyed, with the revision id that names the tree.
REPAIR_PRESENCE_KEYS: tuple[str, ...] = (
    "acceptance_workspace_files",
    "workspace_revision_id",
    # #1884: the correction loop builds a repair's envelope, not ``_increment_inputs``, so a
    # qa repair re-authoring an increment's suite sees the rule only if the scope rides here.
    "increment_test_scope",
)

#: #1264: the failed task's own emitted files, forwarded to its repair from the failed
#: RESULT (not the failed inputs — a task's artifacts are its output). The verifier overlays
#: them beneath the patch (``result.outputs["artifacts"]`` rides the failure); the repair's
#: agent-side evaluation must see the same tree, or a dev repair of a qa failure evaluates the
#: qa suite's criteria on a tree without the suite and every row is ``file_not_found``
#: (cyc_4ec4ad5e2ca1: six executed failures about a file the patch never touched, twice).
REPAIR_FAILED_ARTIFACTS_KEY = "failed_task_artifacts"

#: SIP-0086 §12a change 3 (1.8.2 plan §3.3): a qa suite's re-take after its round's repair was
#: refunded is an edit request on the suite it already wrote. The executor sets it where it
#: refunds the round, from the failed result's suite files (``{path: content}``), for exactly one
#: dispatch; the qa handler shows those files and applies the edits the re-take makes to them.
#: On deploy A every such re-take re-emitted the suite whole — zero scoped qa transactions in five
#: runs on the App Router stack (1.8.1 set record, §10b).
RETAKE_CURRENT_FILES_KEY = "retake_current_files"


def retake_suite_files(result_outputs: Mapping[str, Any] | None) -> dict[str, str]:
    """``{path: content}`` for the suite files a failed qa result emitted — the re-take's base."""
    return {
        str(a["name"]): str(a.get("content") or "")
        for a in (result_outputs or {}).get("artifacts") or ()
        if isinstance(a, Mapping) and a.get("type") == "test" and a.get("name")
    }


def scaffold_shell_paths(inputs: Mapping[str, Any]) -> set[str]:
    """The scaffold's shells, by path — the files a fill-mode task fills by slot (§9.3) and never
    edits or re-emits. Read from the scaffold input the runner threads (its pristine ``files`` and
    the task's ``current_files``); no scaffold, no shells."""
    scaffold = inputs.get("verification_scaffold")
    if not isinstance(scaffold, Mapping):
        return set()

    shells: set[str] = set()
    for key in ("files", "current_files"):
        for entry in scaffold.get(key) or []:
            name = entry.get("name") if isinstance(entry, Mapping) else getattr(entry, "path", None)
            if name:
                shells.add(normalize_ws_path(str(name)))
    return {path for path in shells if path}


def forwarded_failed_artifacts(result_outputs: Mapping[str, Any] | None) -> dict[str, Any]:
    """``{REPAIR_FAILED_ARTIFACTS_KEY: [...]}`` when the failed result emitted files, else
    ``{}`` — presence-keyed like ``repair_forwarded_inputs``, so an empty forward never
    claims a tree."""
    files = failed_task_artifacts(result_outputs)
    return {REPAIR_FAILED_ARTIFACTS_KEY: files} if files else {}


def failed_task_artifacts(result_outputs: Mapping[str, Any] | None) -> list[dict[str, str]]:
    """``[{name, content}]`` for every emitted file on a failed result — the set the verifier
    overlays, in the shape the handler materialises. Entries without both are not files."""
    out: list[dict[str, str]] = []
    for art in (result_outputs or {}).get("artifacts") or ():
        # #1884: the qa author's proposal outlet is stored, never overlaid on a tree.
        if not isinstance(art, dict) or art.get("type") == QA_PROPOSED_BEHAVIOURS_ARTIFACT_TYPE:
            continue
        name, content = art.get("name"), art.get("content")
        if isinstance(name, str) and name and isinstance(content, str):
            out.append({"name": name, "content": content})
    return out


def repair_forwarded_inputs(failed_inputs: Mapping[str, Any]) -> dict[str, Any]:
    """The failed task's typed-acceptance workspace a repair dispatch carries (#1229).

    Presence-keyed: a key forwarded as empty would claim a tree the original dispatch
    never carried. ``acceptance_criteria`` and ``resolved_config`` already ride the repair
    envelope; this adds only what the agent-side evaluation is missing.
    """
    return {key: failed_inputs[key] for key in REPAIR_PRESENCE_KEYS if failed_inputs.get(key)}


def get_context_contract(task_type: str) -> ContextAssemblyContract:
    """The task type's declared contract; the empty contract for undeclared
    types (base enrichment only — chain context and artifact refs)."""
    return CONTEXT_CONTRACTS.get(task_type, _EMPTY_CONTRACT)


def prompt_contract_of(task_type: str) -> ContextAssemblyContract:
    """The contract that declares ``task_type``'s prompt (#2681): its own, or for a correction
    loop's repair type the shared ``REPAIR_CONTEXT_CONTRACT``, as :func:`authoring_seam_of` reads
    its seam."""
    contract = get_context_contract(task_type)
    if contract.authoring_seam is not None or contract.plan_rejection_context:
        return contract
    # deferred (cycle): cycles.task_plan loads this module
    from squadops.cycles.task_plan import REPAIR_TASK_TYPES

    return REPAIR_CONTEXT_CONTRACT if task_type in REPAIR_TASK_TYPES else contract


def authoring_seam_of(task_type: str) -> AuthoringSeam | None:
    """The authoring seam ``task_type`` is (SIP-0110 §0.9), or ``None``.

    Plan writing is the six types declaring ``plan_rejection_context`` (#2058's call site), read
    from that declaration. The correction loop's repair types share ``REPAIR_CONTEXT_CONTRACT``,
    which the correction runner composes them with, so its seam is theirs."""
    contract = get_context_contract(task_type)
    if contract.authoring_seam is not None:
        return contract.authoring_seam
    if contract.plan_rejection_context:
        return AuthoringSeam.PLAN_WRITING
    # Local: task_plan imports this module, so a module-level import would be a cycle.
    # deferred (cycle): cycles.task_plan loads this module
    from squadops.cycles.task_plan import REPAIR_TASK_TYPES

    if task_type in REPAIR_TASK_TYPES:
        return REPAIR_CONTEXT_CONTRACT.authoring_seam
    return None


def dispatch_artifact_filter_spec(task_type: str) -> dict[str, list[str]] | None:
    """The build-lane (INPUTS-landing) filter spec for ``task_type``, or None.

    The default the executor's artifact resolution applies when no explicit
    spec is passed — including the correction loop's RC3 re-resolution, which
    must select the same universe dispatch selected (plus repair candidates).
    Planning filters are excluded: their PRIOR_OUTPUTS landing is a different
    transport and RC3 never applies to them.
    """
    contract = get_context_contract(task_type)
    if contract.artifact_filter is None or contract.artifact_landing != LANDING_INPUTS:
        return None
    return contract.artifact_filter.to_spec()


def wrapup_evidence_applies(plan_task_types: Any) -> bool:
    """True when any planned task type declares the wrap-up evidence flag (#683)."""
    return any(get_context_contract(t).wrapup_evidence for t in plan_task_types)


def manifest_surface_fragments(
    contract: ContextAssemblyContract, interface_manifest: Any
) -> dict[str, list[str]]:
    """The presence-keyed manifest seam fragments the contract requests.

    Pure derivation from the manifest; an empty instruction set contributes no
    key (the handlers' sections are presence-gated). Scaffold import is lazy —
    the module stays light for callers that never thread surfaces.
    """
    if not contract.manifest_surfaces:
        return {}
    # #1029 lives in the module that owns the derivation, not in scaffold.py: the
    # response floor already has one home and a second copy would be a second answer.

    derivations = {
        SURFACE_ERROR_CONTRACT: error_seam_instructions,
        SURFACE_MODEL: model_surface_instructions,
        SURFACE_TESTID: testid_surface_instructions,
        SURFACE_DOM_TESTID: testid_surface_instructions,
        SURFACE_CLIENT: client_surface_instructions,
        SURFACE_FROZEN: frozen_surface_index_lines,
        SURFACE_RESPONSE: response_surface_instructions,
    }
    fragments: dict[str, list[str]] = {}
    for surface in contract.manifest_surfaces:
        lines = derivations[surface](interface_manifest)
        if lines:
            fragments[surface] = lines
    return fragments
