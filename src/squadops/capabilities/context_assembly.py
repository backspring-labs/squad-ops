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
    bind_criteria_index: bool = False
    bind_behavioral_surface: bool = False
    #: SIP-0104 P3: this task receives the deterministic test scaffold (slot table +
    #: shell files) and authors in fill mode when the stack opts in. Derived from the
    #: interface manifest at injection (Gate 1 byte-equivalence makes re-derivation
    #: exact); presence-keyed like every surface here.
    bind_verification_scaffold: bool = False


_EMPTY_CONTRACT = ContextAssemblyContract()


# ---------------------------------------------------------------------------
# The registry
# ---------------------------------------------------------------------------

#: #643/#644: acceptance/patch-verification workspace composition — the full
#: accepted tree (scaffold siblings included), single-sourced with qa.test's
#: prompt context (qa evaluates the same tree it reads).
ACCEPTANCE_WORKSPACE_FILTER = ArtifactFilter(
    by_producing_task=("qa.validate", "builder.assemble", "development.develop"),
    by_type=("source", "config"),
    by_type_fallback=("document",),
)

_DEV_SURFACES = (
    SURFACE_ERROR_CONTRACT,
    SURFACE_MODEL,
    SURFACE_TESTID,
    SURFACE_FROZEN,
    SURFACE_RESPONSE,
)

CONTEXT_CONTRACTS: dict[str, ContextAssemblyContract] = {
    # --- build tasks (D3): curated prompt context + acceptance workspace ----
    "development.develop": ContextAssemblyContract(
        artifact_filter=ArtifactFilter(
            by_producing_task=(
                "strategy.analyze_prd",
                "development.design",
                "development.develop",
            ),
            by_type_fallback=("document",),
        ),
        acceptance_workspace=True,
        # #588/pf-45/#659: the error-contract raise convention, the model
        # field surface, and the DOM testid inventory — to the INITIAL author
        # on the same transport repairs have always used.
        manifest_surfaces=_DEV_SURFACES,
    ),
    "builder.assemble": ContextAssemblyContract(
        artifact_filter=ArtifactFilter(
            by_producing_task=("development.develop",),
            by_type=("source", "config"),
            by_type_fallback=("document",),
        ),
        acceptance_workspace=True,
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
    "qa.test": ContextAssemblyContract(
        artifact_filter=ACCEPTANCE_WORKSPACE_FILTER,
        acceptance_workspace=True,
        bind_behavioral_surface=True,
        manifest_surfaces=(SURFACE_FROZEN,),
        bind_verification_scaffold=True,
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
    "governance.merge_plan": ContextAssemblyContract(bind_criteria_index=True),
    "governance.prepare_plan_authoring_brief": ContextAssemblyContract(
        artifact_filter=ArtifactFilter(
            by_producing_task=(
                "data.research_context",
                "strategy.frame_objective",
                "development.design_plan",
                "qa.define_test_strategy",
            ),
        ),
        artifact_landing=LANDING_PRIOR_OUTPUTS,
        plan_rejection_context=True,
    ),
    # #811: the technical design answers an operator's revision request too. A note about
    # the interface is a note about the design, and a revision that changed only the manifest
    # would leave `technical_design.md` describing an interface that no longer exists.
    "development.design_plan": ContextAssemblyContract(plan_rejection_context=True),
    # SIP-0103 §5c.1 (#791): the manifest author's input contract, as data. The PRD and
    # the blueprint's vocabulary arrive on the envelope; what lands here is the cycle's
    # OWN framing — strategy's frame (which §5a has constraining scope from above) and
    # dev's technical design, which the manifest is the typed expression of. Summaries
    # alone are 240 characters and would make the author re-derive a design it just wrote.
    # Nothing from outside the cycle: the reference manifest is excluded by §4, and
    # cross-cycle recall is a declared future extension, not an omission.
    "development.author_manifest": ContextAssemblyContract(
        artifact_filter=ArtifactFilter(
            by_producing_task=(
                "strategy.frame_objective",
                "development.design_plan",
            ),
        ),
        artifact_landing=LANDING_PRIOR_OUTPUTS,
        plan_rejection_context=True,
    ),
    "development.propose_plan_tasks": ContextAssemblyContract(
        artifact_filter=ArtifactFilter(
            by_producing_task=(
                "governance.prepare_plan_authoring_brief",
                "development.design_plan",
            ),
        ),
        artifact_landing=LANDING_PRIOR_OUTPUTS,
        plan_rejection_context=True,
        bind_criteria_index=True,
    ),
    "qa.propose_plan_tasks": ContextAssemblyContract(
        artifact_filter=ArtifactFilter(
            by_producing_task=(
                "governance.prepare_plan_authoring_brief",
                "development.design_plan",
                "qa.define_test_strategy",
                "development.propose_plan_tasks",
            ),
        ),
        artifact_landing=LANDING_PRIOR_OUTPUTS,
        plan_rejection_context=True,
        bind_criteria_index=True,
    ),
    "strategy.propose_plan_guidance": ContextAssemblyContract(
        artifact_filter=ArtifactFilter(
            by_producing_task=(
                "governance.prepare_plan_authoring_brief",
                "strategy.frame_objective",
            ),
        ),
        artifact_landing=LANDING_PRIOR_OUTPUTS,
        plan_rejection_context=True,
    ),
    # --- wrap-up pipeline (#683): the run-level verification_evidence
    # injection fires when any planned task carries the flag.
    "data.gather_evidence": ContextAssemblyContract(wrapup_evidence=True),
    "qa.assess_outcomes": ContextAssemblyContract(wrapup_evidence=True),
    "data.classify_unresolved": ContextAssemblyContract(wrapup_evidence=True),
    "governance.closeout_decision": ContextAssemblyContract(wrapup_evidence=True),
    "governance.publish_handoff": ContextAssemblyContract(wrapup_evidence=True),
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
        "strategy.analyze_prd",
        "development.design",
        "qa.validate",
        "data.report",
        "governance.review",
        # Framing backbone upstream of the planning chain: these AUTHOR the documents
        # the planning filters above select; their own inputs are envelope-native.
        "data.research_context",
        "strategy.frame_objective",
        "qa.define_test_strategy",
        # Sign-off only (SIP-0093): the gate package rides prior_outputs, and plan
        # validation is deterministic and upstream of this task.
        "governance.review_plan",
        # Implementation-workload framing head: emits the done-definition from the
        # PRD and plan already on the envelope.
        "governance.define_done",
        # Refinement pair (SIP-0078 §5.10): feedback and validation both arrive as
        # explicit envelope inputs from the refinement request.
        "governance.incorporate_feedback",
        "qa.validate_refinement",
        # Correction protocol (SIP-0079 §7.7): the correction runner composes their
        # evidence inputs (failure_evidence, correction context) explicitly per failure.
        "data.analyze_failure",
        "governance.correction_decision",
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
REPAIR_CONTEXT_CONTRACT = ContextAssemblyContract(
    manifest_surfaces=(SURFACE_TESTID, SURFACE_DOM_TESTID, SURFACE_FROZEN),
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


def get_context_contract(task_type: str) -> ContextAssemblyContract:
    """The task type's declared contract; the empty contract for undeclared
    types (base enrichment only — chain context and artifact refs)."""
    return CONTEXT_CONTRACTS.get(task_type, _EMPTY_CONTRACT)


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
    from squadops.capabilities.response_shape import response_surface_instructions
    from squadops.capabilities.scaffold import (
        error_seam_instructions,
        frozen_surface_index_lines,
        model_surface_instructions,
        testid_surface_instructions,
    )

    derivations = {
        SURFACE_ERROR_CONTRACT: error_seam_instructions,
        SURFACE_MODEL: model_surface_instructions,
        SURFACE_TESTID: testid_surface_instructions,
        SURFACE_DOM_TESTID: testid_surface_instructions,
        SURFACE_FROZEN: frozen_surface_index_lines,
        SURFACE_RESPONSE: response_surface_instructions,
    }
    fragments: dict[str, list[str]] = {}
    for surface in contract.manifest_surfaces:
        lines = derivations[surface](interface_manifest)
        if lines:
            fragments[surface] = lines
    return fragments
