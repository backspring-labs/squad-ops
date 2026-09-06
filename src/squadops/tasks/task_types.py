"""Task-type identifiers — strings at the boundary, constants at the core (#559).

Every dispatched task type, single-sourced. The convention this module exists to hold
the codebase to:

1. **Strings at the boundary.** ``task_type`` stays a plain string on the wire — RabbitMQ
   envelopes, Postgres rows, Prefect task names, YAML profiles and contract manifests.
   ``TaskType`` is a ``StrEnum``, so a member *is* its wire string: no serialization
   change, and ``"qa.test" == TaskType.QA_TEST`` holds wherever a boundary hands one in.
2. **Constants at the core.** Core-side comparisons and table keys use the member. A typo
   is an ``AttributeError`` at import; a rename is one line here.
3. **Properties over identity.** When orchestration treats some steps differently, the
   distinguishing property is declared here, next to the member, and the loop consults it.
   ``if task_type == TaskType.X`` in orchestration code is the review smell; the property
   (or a dispatch-table row) is the fix — an identity check names one instance, a property
   names the kind, and the next task type of that kind is covered without knowing about the
   special case.
4. **Tables over chains.** Type-keyed dispatch goes through a declarative mapping consulted
   at one point (``task_plan.repair_steps_for``'s shape), never an ``if``/``elif`` chain.

Guarded by ``tests/unit/architecture/test_task_type_literals_live_at_the_boundary.py``: a
task-type literal in ``src/`` or ``adapters/`` outside this module fails CI.
"""

from __future__ import annotations

from enum import StrEnum


class TaskType(StrEnum):
    """Every task type the framework dispatches, by the string that names it on the wire."""

    # --- strategy (strat) ---
    STRATEGY_ANALYZE_PRD = "strategy.analyze_prd"
    STRATEGY_FRAME_OBJECTIVE = "strategy.frame_objective"
    STRATEGY_PROPOSE_PLAN_GUIDANCE = "strategy.propose_plan_guidance"
    STRATEGY_CORRECTIVE_PLAN = "strategy.corrective_plan"

    # --- development (dev) ---
    DEVELOPMENT_DESIGN = "development.design"
    DEVELOPMENT_DESIGN_PLAN = "development.design_plan"
    DEVELOPMENT_AUTHOR_MANIFEST = "development.author_manifest"
    DEVELOPMENT_PROPOSE_PLAN_TASKS = "development.propose_plan_tasks"
    DEVELOPMENT_DEVELOP = "development.develop"
    DEVELOPMENT_REPAIR = "development.repair"
    DEVELOPMENT_CORRECTION_REPAIR = "development.correction_repair"

    # --- qa ---
    QA_DEFINE_TEST_STRATEGY = "qa.define_test_strategy"
    QA_PROPOSE_PLAN_TASKS = "qa.propose_plan_tasks"
    QA_TEST = "qa.test"
    QA_TEST_REPAIR = "qa.test_repair"
    QA_VALIDATE = "qa.validate"
    QA_VALIDATE_REFINEMENT = "qa.validate_refinement"
    QA_ASSESS_OUTCOMES = "qa.assess_outcomes"

    # --- builder ---
    BUILDER_ASSEMBLE = "builder.assemble"
    BUILDER_ASSEMBLE_REPAIR = "builder.assemble_repair"

    # --- governance (lead) ---
    GOVERNANCE_PREPARE_PLAN_AUTHORING_BRIEF = "governance.prepare_plan_authoring_brief"
    GOVERNANCE_MERGE_PLAN = "governance.merge_plan"
    GOVERNANCE_REVIEW_PLAN = "governance.review_plan"
    GOVERNANCE_INCORPORATE_FEEDBACK = "governance.incorporate_feedback"
    GOVERNANCE_DEFINE_DONE = "governance.define_done"
    GOVERNANCE_REVIEW = "governance.review"
    GOVERNANCE_CORRECTION_DECISION = "governance.correction_decision"
    GOVERNANCE_ROOT_CAUSE_ANALYSIS = "governance.root_cause_analysis"
    GOVERNANCE_CLOSEOUT_DECISION = "governance.closeout_decision"
    GOVERNANCE_PUBLISH_HANDOFF = "governance.publish_handoff"

    # --- data (analytics) ---
    DATA_RESEARCH_CONTEXT = "data.research_context"
    DATA_ANALYZE_FAILURE = "data.analyze_failure"
    DATA_ANALYZE_VERIFICATION = "data.analyze_verification"
    DATA_GATHER_EVIDENCE = "data.gather_evidence"
    DATA_CLASSIFY_UNRESOLVED = "data.classify_unresolved"
    DATA_REPORT = "data.report"
    # SIP-0058 reference workloads — contract manifests without a handler class.
    DATA_COLLECT_CYCLE_SNAPSHOT = "data.collect_cycle_snapshot"
    DATA_PROFILE_CYCLE_METRICS = "data.profile_cycle_metrics"
    DATA_COMPOSE_CYCLE_SUMMARY = "data.compose_cycle_summary"

    # --- properties: the kind of step, declared once beside the members (rule 3) ---

    @property
    def authors_qa_suite(self) -> bool:
        """The step whose emission IS the qa suite — the one the typed suite checks bind to,
        whose expected artifacts must match the test-file patterns, and whose corrections
        must reach past its own files to the dev source."""
        return self is TaskType.QA_TEST

    @property
    def authors_source(self) -> bool:
        """The step whose emission is the application source under test."""
        return self is TaskType.DEVELOPMENT_DEVELOP

    @property
    def fails_without_correction(self) -> bool:
        """A failure here aborts the run rather than entering the correction loop (D9):
        the definition of done is the thing correction would be judged against."""
        return self is TaskType.GOVERNANCE_DEFINE_DONE

    @property
    def domain(self) -> str:
        """The dotted prefix — the role family that owns the step."""
        return self.value.split(".", 1)[0]


def _member_or_none(value: object) -> TaskType | None:
    try:
        return TaskType(str(value))
    except ValueError:
        return None


def authors_qa_suite(task_type: object) -> bool:
    """``TaskType.authors_qa_suite`` for a value that may be a raw string; an unknown
    type is not the qa suite author rather than an error, since plan task types arrive
    from the planner and the caller's question is about the kind, not validity."""
    member = _member_or_none(task_type)
    return bool(member and member.authors_qa_suite)


def authors_source(task_type: object) -> bool:
    """``TaskType.authors_source`` for a value that may be a raw string."""
    member = _member_or_none(task_type)
    return bool(member and member.authors_source)


def fails_without_correction(task_type: object) -> bool:
    """``TaskType.fails_without_correction`` for a value that may be a raw string."""
    member = _member_or_none(task_type)
    return bool(member and member.fails_without_correction)


def task_type_of(value: str) -> TaskType:
    """The member for a wire string, or ``ValueError`` naming the unknown type.

    The boundary's one translation point: a string arriving from a profile, an envelope
    or a row becomes a member here, and an unknown one is refused rather than carried."""
    return TaskType(value)
