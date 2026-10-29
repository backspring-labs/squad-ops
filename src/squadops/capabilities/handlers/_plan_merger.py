"""Plan merger (SIP-0093 PR 93.3).

Function-style deterministic merger that consumes per-role proposals
(``ProposedRoleTasks``) + strategy guidance (``PlanGuidance``) + the
shared brief (``PlanAuthoringBrief``) and produces the canonical
``ImplementationPlan`` plus the auditable ``MergeDecisions`` artifact.

The merger applies SIP-0093 §5.8 rules in order. Rev 1 keeps the algorithm
strictly deterministic — no LLM judgment for warning-severity conflicts,
no auto-gap-filling. Warning brief conflicts are accepted by default with
the proposer's reasoning recorded; blocking conflicts are escalated to
operator notes verbatim. Unresolved cross-proposal dependencies surface in
operator notes rather than being auto-stubbed.

One file ownership rule rides on §5.8 rule 1, domain ownership (SIP-0093 §15b, #2795): an
increment's criterion file that a development task and a qa task both claim is the qa task's
(``_criterion_files_to_qa``).

This module is intentionally stateless and side-effect-free. The handler
shell in ``planning/merge.py`` calls ``merge_proposals(...)`` and wraps
the returned artifacts in a ``HandlerResult``.
"""

from __future__ import annotations

import dataclasses
import logging
from collections.abc import Mapping, Sequence
from typing import Any

import yaml

from squadops.cycles.acceptance_check_spec import check_subject_paths
from squadops.cycles.implementation_plan import (
    ImplementationPlan,
    PlanSummary,
    PlanTask,
    TypedCheck,
)
from squadops.cycles.merge_decisions import (
    BriefConflictDisposition,
    CanonicalTaskProvenance,
    MergeDecisions,
    MissingProposal,
)
from squadops.cycles.plan_authoring_brief import PlanAuthoringBrief
from squadops.cycles.plan_guidance import PlanGuidance
from squadops.cycles.proposed_role_tasks import (
    ProposedRoleTasks,
    ProposedTask,
    canonicalize_dep_ref,
    focus_key,
)
from squadops.tasks.task_types import TaskType, authors_qa_suite

logger = logging.getLogger(__name__)

#: A pair as the merge carries it before indexing: the canonical task, its provenance, and the
#: proposed task it came from (whose ``depends_on_focus`` rule 5 reads).
_Pair = tuple[PlanTask, CanonicalTaskProvenance, ProposedTask]


# Per SIP-0093 §5.8 rule 2 — only the domain owner's task_type lands in
# canonical tasks. Dev tasks proposed by qa are dropped (qa stays in its
# lane); qa tasks proposed by dev are likewise dropped.
_DEV_TASK_TYPES = frozenset({TaskType.DEVELOPMENT_DEVELOP, TaskType.BUILDER_ASSEMBLE})
_QA_TASK_TYPES = frozenset({TaskType.QA_TEST})


def _resolve_dependency_edges(
    indexed_pairs: list[tuple[PlanTask, CanonicalTaskProvenance, ProposedTask]],
    focus_to_index: dict[str, int],
    dropped: Mapping[str, Sequence[str]],
) -> tuple[
    list[tuple[PlanTask, CanonicalTaskProvenance]],
    list[tuple[int, str]],
    list[tuple[int, str, str]],
]:
    """Resolve each task's ``depends_on_focus`` references to canonical
    ``task_index`` edges (SIP-0093 rule 5).

    References are normalized (#189) so a role display-name / case variant
    (``development:Backend Models``) resolves against the produced role-id key
    (``dev:backend models``). A reference that still misses after normalization
    is a genuine gap (a focus no task produced) and is returned in
    ``unresolved_deps`` keyed by its normalized form for the operator note.

    §15b: a reference to a development task the merge dropped (``dropped``, each one's own
    ``depends_on_focus`` by its key) is re-pointed to that task's own dependencies
    (:func:`_through_dropped`). A dependency of the dropped task that names no task is returned
    in the third list, as ``(task_index, dropped key, missing key)``.
    """
    resolved_pairs: list[tuple[PlanTask, CanonicalTaskProvenance]] = []
    unresolved_deps: list[tuple[int, str]] = []  # (task_index, missing_key)
    unresolved_through: list[tuple[int, str, str]] = []
    for task, prov, orig in indexed_pairs:
        depends_on: list[int] = []
        for dep_key in orig.depends_on_focus:
            norm_key = canonicalize_dep_ref(dep_key)
            if norm_key in dropped:
                indices, missing = _through_dropped(norm_key, focus_to_index, dropped)
                depends_on.extend(i for i in indices if i != task.task_index)
                unresolved_through.extend((task.task_index, norm_key, m) for m in missing)
                continue
            if norm_key not in focus_to_index:
                unresolved_deps.append((task.task_index, norm_key))
                continue
            if norm_key != dep_key:
                logger.debug(
                    "merge_plan: normalized cross-proposal dependency %r -> %r",
                    dep_key,
                    norm_key,
                )
            depends_on.append(focus_to_index[norm_key])
        resolved_pairs.append((dataclasses.replace(task, depends_on=sorted(set(depends_on))), prov))
    return resolved_pairs, unresolved_deps, unresolved_through


def _through_dropped(
    key: str,
    focus_to_index: Mapping[str, int],
    dropped: Mapping[str, Sequence[str]],
    seen: frozenset[str] = frozenset(),
) -> tuple[list[int], list[str]]:
    """§15b: the canonical tasks a dropped development task depended on, which an edge to it is
    re-pointed to, and the dependencies of its that name no task. A dependency on another dropped
    task is followed through that one too.

    The proposal's own order is acyclic and authored (#578), so a dependent of the dropped task
    already came after everything the dropped task needed: the re-pointed edge keeps both. Moving
    the edge onto the qa task that took the dropped task's files would not: qa tasks follow every
    development task, so a development dependent would come before its new dependency, which
    #578's order check refuses.
    """
    indices: list[int] = []
    missing: list[str] = []
    for dep in dropped[key]:
        norm = canonicalize_dep_ref(dep)
        if norm in focus_to_index:
            indices.append(focus_to_index[norm])
        elif norm in dropped:
            if norm not in seen and norm != key:
                more, unnamed = _through_dropped(norm, focus_to_index, dropped, seen | {key})
                indices.extend(more)
                missing.extend(unnamed)
        else:
            missing.append(norm)
    return indices, missing


def merge_proposals(
    *,
    brief: PlanAuthoringBrief,
    dev_proposal: ProposedRoleTasks | None,
    qa_proposal: ProposedRoleTasks | None,
    strategy_guidance: PlanGuidance | None,
    project_id: str,
    cycle_id: str,
    prd_hash: str,
    configured_contributors: list[str],
    missing_proposals: list[MissingProposal],
    criterion_files: Sequence[str],
) -> tuple[ImplementationPlan, MergeDecisions]:
    """Apply the SIP-0093 §5.8 deterministic merge.

    Args:
        brief: Shared upstream brief (RC-22 immutable).
        dev_proposal: Development's proposal, or None if it failed/missing.
        qa_proposal: QA's proposal, or None.
        strategy_guidance: Strategy's overlay guidance, or None.
        project_id / cycle_id / prd_hash: Authoritative identifiers
            stamped into the canonical plan.
        configured_contributors: Roles configured for this cycle —
            drives the missing-proposal operator notes per §5.9.
        missing_proposals: Pre-computed list of ``MissingProposal``
            entries (one per configured role that produced no parseable
            artifact). The caller builds this from the proposer-failure
            artifacts in the cycle stream.
        criterion_files: An increment's new criteria's own test files (SIP-0109 §8.1), empty
            for every other cycle. One that a development task and a qa task both claim is the
            qa task's (§15b, :func:`_criterion_files_to_qa`). Required, never defaulted: a
            caller that forgot it would merge the dual claim the plan gate then refuses (#2795).

    Returns:
        ``(ImplementationPlan, MergeDecisions)`` — both with
        ``authoring_mode: multi_role``. Callers needing sole-author mode
        invoke ``PlanAuthoringService.produce_plan`` directly and build
        the ``MergeDecisions`` shape via ``build_sole_author_decisions``.
    """
    # Rule 2 + 3: domain ownership + dedup. Each proposal already enforces
    # focus_key uniqueness internally (parser-level), so cross-proposal
    # collision is the only remaining shape — handled by domain ownership.
    canonical_pairs: list[tuple[PlanTask, CanonicalTaskProvenance, ProposedTask]] = []

    if dev_proposal is not None:
        for ptask in dev_proposal.tasks:
            if ptask.task_type not in _DEV_TASK_TYPES:
                # Dev proposed a non-dev task type — domain-owner rule
                # drops it. Log for observability; the merge_decisions
                # operator notes will not surface this (it's a proposer
                # bug, not an operator-actionable signal).
                logger.info(
                    "merge_plan: dropping non-dev task type %r proposed by development",
                    ptask.task_type,
                )
                continue
            canonical_pairs.append(_build_canonical_pair(ptask, "development"))

    if qa_proposal is not None:
        for ptask in qa_proposal.tasks:
            if ptask.task_type not in _QA_TASK_TYPES:
                logger.info(
                    "merge_plan: dropping non-qa task type %r proposed by qa",
                    ptask.task_type,
                )
                continue
            canonical_pairs.append(_build_canonical_pair(ptask, "qa"))

    # §15b (#2795): an increment's criterion file a development task and a qa task both claim
    # is the qa task's. Before indexing, so a development task it empties takes no index.
    canonical_pairs, dropped_tasks = _criterion_files_to_qa(canonical_pairs, criterion_files)

    # Rule 8: assign final task indices. Dev tasks first (proposal order),
    # then qa tasks (proposal order). Strategy guidance (rule 6) may bias
    # ordering — Rev 1 records guidance_ids in merge_decisions but does
    # not reorder. Reordering becomes a separate refinement once we see
    # how strategy proposers behave in practice.
    indexed_pairs = [
        (
            dataclasses.replace(task, task_index=i),
            dataclasses.replace(prov, task_index=i),
            orig,
        )
        for i, (task, prov, orig) in enumerate(canonical_pairs)
    ]

    # Rule 5: resolve dependency edges. focus_key → task_index lookup.
    focus_to_index: dict[str, int] = {}
    for task, prov, _orig in indexed_pairs:
        for key in prov.source_proposal_task_keys:
            focus_to_index[key] = task.task_index

    # §15b: an edge to a development task the merge dropped is re-pointed to that task's own
    # dependencies (_through_dropped), never moved onto the qa task that took its files.
    resolved_pairs, unresolved_deps, unresolved_through = _resolve_dependency_edges(
        indexed_pairs,
        focus_to_index,
        {key: gone.depends_on_focus for key, gone in dropped_tasks.items()},
    )

    canonical_tasks = [t for t, _ in resolved_pairs]
    provenance_entries = _record_taken_places(
        [p for _, p in resolved_pairs], dropped_tasks, focus_to_index
    )

    # Rule 1: brief-conflict dispositions
    brief_conflicts_disposition = _resolve_brief_conflicts(dev_proposal, qa_proposal)

    # Rule 9 + §5.9: operator notes
    operator_notes = _build_operator_notes(
        configured_contributors=configured_contributors,
        dev_proposal=dev_proposal,
        qa_proposal=qa_proposal,
        strategy_guidance=strategy_guidance,
        brief_conflicts_disposition=brief_conflicts_disposition,
        unresolved_deps=unresolved_deps,
        merge_notes=[
            *_dropped_task_notes(dropped_tasks, focus_to_index),
            *_unresolved_through_notes(unresolved_through),
        ],
    )

    # Determine proposal_completeness
    successful_roles = _successful_roles(dev_proposal, qa_proposal, strategy_guidance)
    configured_set = set(configured_contributors)
    completeness = "complete" if configured_set == successful_roles else "partial"

    proposal_ids = [p.proposal_id for p in (dev_proposal, qa_proposal) if p is not None]
    guidance_ids = [strategy_guidance.guidance_id] if strategy_guidance else []

    plan = _build_canonical_plan(
        tasks=canonical_tasks,
        project_id=project_id,
        cycle_id=cycle_id,
        prd_hash=prd_hash,
    )
    decisions = MergeDecisions(
        version=1,
        target_plan_id=f"plan-{cycle_id}",
        brief_id=brief.brief_id,
        proposal_ids=proposal_ids,
        guidance_ids=guidance_ids,
        authoring_mode="multi_role",
        sole_author_reason=None,
        proposal_completeness=completeness,
        missing_proposals=missing_proposals,
        canonical_tasks=provenance_entries,
        brief_conflicts_disposition=brief_conflicts_disposition,
        operator_notes=operator_notes,
    )
    return plan, decisions


def build_sole_author_decisions(
    *,
    brief: PlanAuthoringBrief,
    cycle_id: str,
    sole_author_reason: str,
    canonical_tasks: list[PlanTask],
    missing_proposals: list[MissingProposal],
) -> MergeDecisions:
    """Construct ``MergeDecisions`` for a sole-author cycle.

    Used by the merger when no proposals are available. ``sole_author_reason``
    must be ``no_contributors_configured`` (configured mode) or
    ``all_proposals_failed`` (degraded mode). The two render different
    operator-visible warnings at gate.
    """
    operator_notes_parts: list[str] = []
    if sole_author_reason == "all_proposals_failed":
        operator_notes_parts.append(
            "Multi-role authoring degraded to sole-author: every configured proposer failed."
        )
        # Per-role missing-proposal warnings still surface in degraded mode
        # so the operator can see which roles failed.
        for mp in missing_proposals:
            if mp.role == "qa":
                operator_notes_parts.append(
                    "QA coverage warning: plan was authored without qa-domain input."
                )
            elif mp.role == "development":
                operator_notes_parts.append(
                    "Implementation decomposition warning: plan was "
                    "authored without dev-domain input."
                )
            elif mp.role == "strategy":
                operator_notes_parts.append(
                    "Ordering/priority warning: plan ordering was assigned "
                    "without strategy guidance."
                )

    provenance_entries = [
        CanonicalTaskProvenance(
            task_index=t.task_index,
            source_proposal_task_keys=[],
            proposed_by=[],
            merge_action="gap_filled",
            reason=(
                "Sole-author fallback via PlanAuthoringService — no proposer "
                "contribution available."
            ),
        )
        for t in canonical_tasks
    ]

    return MergeDecisions(
        version=1,
        target_plan_id=f"plan-{cycle_id}",
        brief_id=brief.brief_id,
        proposal_ids=[],
        guidance_ids=[],
        authoring_mode="sole_author",
        sole_author_reason=sole_author_reason,
        proposal_completeness="sole_author",
        missing_proposals=missing_proposals if sole_author_reason == "all_proposals_failed" else [],
        canonical_tasks=provenance_entries,
        brief_conflicts_disposition=[],
        operator_notes="\n".join(operator_notes_parts),
    )


def emit_plan_yaml(plan: ImplementationPlan) -> str:
    """Serialize an ImplementationPlan to YAML matching the SIP-0092 M1 shape."""
    return yaml.safe_dump(_plan_to_dict(plan), sort_keys=False, allow_unicode=True)


def emit_merge_decisions_yaml(decisions: MergeDecisions) -> str:
    """Serialize a MergeDecisions to YAML matching the SIP-0093 §5.7 shape."""
    return yaml.safe_dump(_decisions_to_dict(decisions), sort_keys=False, allow_unicode=True)


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _build_canonical_pair(
    ptask: ProposedTask,
    proposing_role: str,
) -> tuple[PlanTask, CanonicalTaskProvenance, ProposedTask]:
    """Convert a ProposedTask to a (PlanTask, CanonicalTaskProvenance) pair.

    The third tuple element preserves the original ProposedTask so the
    dependency-resolution pass can read its ``depends_on_focus`` keys
    after the task_index assignment.
    """
    plan_task = PlanTask(
        task_index=0,  # assigned in rule-8 pass
        task_type=ptask.task_type,
        role=ptask.role,
        focus=ptask.focus,
        description=ptask.description,
        expected_artifacts=list(ptask.expected_artifacts),
        acceptance_criteria=list(ptask.acceptance_criteria),
        depends_on=[],  # resolved in rule-5 pass
        criteria_refs=list(ptask.criteria_refs),  # SIP-0098 98.3: carry bind refs through
    )
    provenance = CanonicalTaskProvenance(
        task_index=0,
        source_proposal_task_keys=[focus_key(ptask.role, ptask.focus)],
        proposed_by=[proposing_role],
        merge_action="accepted",
        reason=(
            f"{proposing_role}-proposed {ptask.task_type} task accepted "
            "via domain-owner rule (§5.8 rule 2)."
        ),
    )
    return plan_task, provenance, ptask


@dataclasses.dataclass(frozen=True)
class _DroppedTask:
    """A development-side task §15b dropped whole: every file it named is a criterion file that a
    qa task writes. ``writers`` are those qa tasks' focus keys, in proposal order;
    ``depends_on_focus`` is the dropped task's own, which an edge to it is re-pointed to."""

    focus: str
    proposed_by: tuple[str, ...]
    task_type: str
    files: tuple[str, ...]
    writers: tuple[str, ...]
    depends_on_focus: tuple[str, ...]


def _criterion_files_to_qa(
    pairs: list[_Pair], criterion_files: Sequence[str]
) -> tuple[list[_Pair], dict[str, _DroppedTask]]:
    """SIP-0093 §15b (#2795): an increment's criterion file that a development-side task and a
    qa task both claim is the qa task's. SIP-0109 §24m: the qa role writes the test that proves
    the criterion, and a file only a development task names doesn't count.

    - The file leaves the development task's ``expected_artifacts``, and so do the task's typed
      checks that read it (``check_subject_paths``): the task no longer writes it, and a check
      on a file the task's own tree lacks fails at its evaluation whatever its code does. The
      task's provenance becomes ``modified``, its reason naming each file and its writer.
    - A development task left with nothing to write is dropped: its whole deliverable is the qa
      tasks'. Returned by focus key, for the provenance of the qa tasks that take its place, for
      the edges that pointed at it, and for its operator note: its description, prose criteria
      and ``criteria_refs`` go with it, so product work it described has no writer.
    - A file no qa task claims stays where it is, so no criterion file is left unclaimed.

    Any other dual claim, and a criterion file two qa tasks claim, is left for the plan validator
    to refuse (#673): nothing establishes an owner for those. With no criterion files, or no dual
    claim on one, the pairs come back as they came.
    """
    criteria = set(criterion_files)
    writers: dict[str, list[str]] = {}
    for task, prov, _orig in pairs:
        if authors_qa_suite(task.task_type):
            for artifact in task.expected_artifacts:
                if artifact in criteria:
                    writers.setdefault(artifact, []).extend(prov.source_proposal_task_keys)
    if not writers:
        return pairs, {}

    kept: list[_Pair] = []
    dropped: dict[str, _DroppedTask] = {}
    for task, prov, orig in pairs:
        given = (
            []
            if authors_qa_suite(task.task_type)
            else list(dict.fromkeys(a for a in task.expected_artifacts if a in writers))
        )
        if not given:
            kept.append((task, prov, orig))
            continue
        takers = tuple(dict.fromkeys(k for a in given for k in writers[a]))
        remaining = [a for a in task.expected_artifacts if a not in writers]
        if not remaining:
            [key] = prov.source_proposal_task_keys
            dropped[key] = _DroppedTask(
                focus=task.focus,
                proposed_by=tuple(prov.proposed_by),
                task_type=str(task.task_type),
                files=tuple(given),
                writers=takers,
                depends_on_focus=tuple(orig.depends_on_focus),
            )
            logger.info(
                "merge_plan: dropping %s; qa task(s) %s write every file it named (§15b)",
                key,
                list(takers),
            )
            continue
        checks = [c for c in task.acceptance_criteria if not _reads_any(c, given)]
        dropped_checks = len(task.acceptance_criteria) - len(checks)
        kept.append(
            (
                dataclasses.replace(task, expected_artifacts=remaining, acceptance_criteria=checks),
                dataclasses.replace(
                    prov,
                    merge_action="modified",
                    reason=(
                        f"{prov.reason} Modified by SIP-0093 §15b: the criterion files "
                        f"{', '.join(given)} are written by qa task(s) {', '.join(takers)}, "
                        "which claim them too, so they left this task's expected_artifacts"
                        + (
                            f", with the {dropped_checks} typed check(s) it held on them."
                            if dropped_checks
                            else "."
                        )
                    ),
                ),
                orig,
            )
        )
    return kept, dropped


def _reads_any(criterion: Any, paths: Sequence[str]) -> bool:
    """Whether ``criterion`` is a typed check that reads one of ``paths``."""
    return isinstance(criterion, TypedCheck) and bool(
        check_subject_paths(criterion.check, criterion.params) & set(paths)
    )


def _record_taken_places(
    provenance: list[CanonicalTaskProvenance],
    dropped: dict[str, _DroppedTask],
    focus_to_index: dict[str, int],
) -> list[CanonicalTaskProvenance]:
    """§15b: each qa task that took a dropped development task's place records it as merged: the
    dropped task's key among its sources, its role among its proposers, and why."""
    out = list(provenance)
    for key, gone in dropped.items():
        for writer in gone.writers:
            i = focus_to_index[writer]
            prov = out[i]
            out[i] = dataclasses.replace(
                prov,
                source_proposal_task_keys=[*prov.source_proposal_task_keys, key],
                proposed_by=list(dict.fromkeys([*prov.proposed_by, *gone.proposed_by])),
                merge_action="merged",
                reason=(
                    f"{prov.reason} It takes the place of {'/'.join(gone.proposed_by)}-proposed "
                    f"{gone.task_type} task {key!r} (SIP-0093 §15b): every file that task named is a "
                    f"criterion file a qa task writes ({', '.join(gone.files)}), so the merge "
                    "dropped it."
                ),
            )
    return out


def _dropped_task_notes(
    dropped: dict[str, _DroppedTask], focus_to_index: dict[str, int]
) -> list[str]:
    """§15b: one operator note per task the merge dropped, naming its focus and what went with
    it. The qa tasks that take its place record its key in their provenance; this says what they
    don't take."""
    return [
        f"Task dropped: {'/'.join(gone.proposed_by)}-proposed {gone.task_type} task "
        f"{gone.focus!r} ({key}), since every file it named is a criterion file that canonical "
        f"task(s) {', '.join(str(focus_to_index[w]) for w in gone.writers)} write (SIP-0093 "
        "§15b). Its description, prose criteria and criteria_refs are not carried: if it "
        "described product work, no task writes that work."
        for key, gone in dropped.items()
    ]


def _unresolved_through_notes(unresolved: list[tuple[int, str, str]]) -> list[str]:
    """§15b: one operator note per dependency a re-pointed edge couldn't resolve: the dropped
    task's own dependency named no task a proposer produced."""
    return [
        f"Unresolved cross-proposal dependency: canonical task {i} depended on {via!r}, which the "
        f"merge dropped (SIP-0093 §15b). The edge was re-pointed to that task's own dependencies, "
        f"and {missing!r} among them names no task a proposer produced. Operator review required "
        "(gap_fill candidate)."
        for i, via, missing in unresolved
    ]


def _resolve_brief_conflicts(
    dev_proposal: ProposedRoleTasks | None,
    qa_proposal: ProposedRoleTasks | None,
) -> list[BriefConflictDisposition]:
    """Apply §5.8 rule 1: warning → accepted, blocking → escalated.

    The Rev 1 policy is conservative: the merger does not arbitrate
    warning-severity conflicts on substantive grounds (that would require
    LLM judgment or a richer rule set). Every warning is accepted with
    the proposer's reasoning preserved; every blocking is escalated.
    Operators see both at gate via merge_decisions.yaml.
    """
    out: list[BriefConflictDisposition] = []
    for proposal in (dev_proposal, qa_proposal):
        if proposal is None:
            continue
        for bc in proposal.brief_conflicts:
            if bc.severity == "blocking":
                out.append(
                    BriefConflictDisposition(
                        brief_field=bc.brief_field,
                        severity="blocking",
                        disposition="escalated_to_operator",
                        reason=(
                            f"Blocking conflict raised by {proposal.proposing_role} "
                            f"on {bc.brief_field}: {bc.reason}"
                        ),
                    )
                )
            else:
                out.append(
                    BriefConflictDisposition(
                        brief_field=bc.brief_field,
                        severity="warning",
                        disposition="accepted",
                        reason=(
                            f"Warning conflict from {proposal.proposing_role} accepted: {bc.reason}"
                        ),
                    )
                )
    return out


def _successful_roles(
    dev_proposal: ProposedRoleTasks | None,
    qa_proposal: ProposedRoleTasks | None,
    strategy_guidance: PlanGuidance | None,
) -> set[str]:
    roles: set[str] = set()
    if dev_proposal is not None:
        roles.add("development")
    if qa_proposal is not None:
        roles.add("qa")
    if strategy_guidance is not None:
        roles.add("strategy")
    return roles


def _build_operator_notes(
    *,
    configured_contributors: list[str],
    dev_proposal: ProposedRoleTasks | None,
    qa_proposal: ProposedRoleTasks | None,
    strategy_guidance: PlanGuidance | None,
    brief_conflicts_disposition: list[BriefConflictDisposition],
    unresolved_deps: list[tuple[int, str]],
    merge_notes: list[str],
) -> str:
    """Build the operator_notes prose per §5.9 + §5.8 gap-fill policy."""
    parts: list[str] = []
    successful = _successful_roles(dev_proposal, qa_proposal, strategy_guidance)
    configured = set(configured_contributors)

    # §5.9 required missing-role warnings
    if "qa" in configured and "qa" not in successful:
        parts.append("QA coverage warning: plan was authored without qa-domain input.")
    if "development" in configured and "development" not in successful:
        parts.append(
            "Implementation decomposition warning: plan was authored without dev-domain input."
        )
    if "strategy" in configured and "strategy" not in successful:
        parts.append(
            "Ordering/priority warning: plan ordering was assigned without strategy guidance."
        )

    # Escalated brief conflicts
    for d in brief_conflicts_disposition:
        if d.disposition == "escalated_to_operator":
            parts.append(f"Brief conflict escalated ({d.brief_field}): {d.reason}")

    # Unresolved cross-proposal dependencies (rule 7 gap-fill candidates).
    # Rev 1 surfaces these as operator notes rather than auto-filling — the
    # operator decides whether to add the missing component or reject the
    # qa task that references it.
    if unresolved_deps:
        for task_index, missing_key in unresolved_deps:
            parts.append(
                f"Unresolved cross-proposal dependency: canonical task "
                f"{task_index} references {missing_key!r} which no proposer "
                f"produced. Operator review required (gap_fill candidate)."
            )
    # §15b: the tasks the criterion-file rule dropped, and what a re-pointed edge left unresolved.
    parts.extend(merge_notes)

    return "\n".join(parts)


def _build_canonical_plan(
    *,
    tasks: list[PlanTask],
    project_id: str,
    cycle_id: str,
    prd_hash: str,
) -> ImplementationPlan:
    """Wrap the merged tasks in an ImplementationPlan."""
    dev_count = sum(1 for t in tasks if t.task_type in _DEV_TASK_TYPES)
    qa_count = sum(1 for t in tasks if t.task_type in _QA_TASK_TYPES)
    summary = PlanSummary(
        total_dev_tasks=dev_count,
        total_qa_tasks=qa_count,
        total_tasks=len(tasks),
        estimated_layers=[],
    )
    return ImplementationPlan(
        version=1,
        project_id=project_id,
        cycle_id=cycle_id,
        prd_hash=prd_hash,
        tasks=tasks,
        summary=summary,
    )


def _plan_to_dict(plan: ImplementationPlan) -> dict[str, Any]:
    """Serialize an ImplementationPlan back to its YAML-mapping shape."""
    return {
        "version": plan.version,
        "project_id": plan.project_id,
        "cycle_id": plan.cycle_id,
        "prd_hash": plan.prd_hash,
        "tasks": [_plan_task_to_dict(t) for t in plan.tasks],
        "summary": {
            "total_dev_tasks": plan.summary.total_dev_tasks,
            "total_qa_tasks": plan.summary.total_qa_tasks,
            "total_tasks": plan.summary.total_tasks,
            "estimated_layers": list(plan.summary.estimated_layers),
        },
    }


def _plan_task_to_dict(task: PlanTask) -> dict[str, Any]:
    return {
        "task_index": task.task_index,
        "task_type": task.task_type,
        "role": task.role,
        "focus": task.focus,
        "description": task.description,
        "expected_artifacts": list(task.expected_artifacts),
        "acceptance_criteria": [_criterion_to_dict(c) for c in task.acceptance_criteria],
        "depends_on": list(task.depends_on),
        # SIP-0098 98.3: emit criteria_refs only when present so contract-less merged
        # plans stay byte-identical to today (from_yaml defaults the field to []).
        **({"criteria_refs": list(task.criteria_refs)} if task.criteria_refs else {}),
    }


def _criterion_to_dict(criterion: Any) -> Any:
    """Serialize either a prose string or a TypedCheck back to YAML shape."""
    if isinstance(criterion, TypedCheck):
        flat: dict[str, Any] = {"check": criterion.check}
        if criterion.severity != "error":
            flat["severity"] = criterion.severity
        if criterion.description:
            flat["description"] = criterion.description
        flat.update(criterion.params)
        return flat
    return criterion


def _decisions_to_dict(decisions: MergeDecisions) -> dict[str, Any]:
    return {
        "version": decisions.version,
        "target_plan_id": decisions.target_plan_id,
        "brief_id": decisions.brief_id,
        "proposal_ids": list(decisions.proposal_ids),
        "guidance_ids": list(decisions.guidance_ids),
        "authoring_mode": decisions.authoring_mode,
        "sole_author_reason": decisions.sole_author_reason,
        "proposal_completeness": decisions.proposal_completeness,
        "missing_proposals": [
            {"role": m.role, "failure_reason": m.failure_reason}
            for m in decisions.missing_proposals
        ],
        "canonical_tasks": [
            {
                "task_index": ct.task_index,
                "source_proposal_task_keys": list(ct.source_proposal_task_keys),
                "proposed_by": list(ct.proposed_by),
                "merge_action": ct.merge_action,
                "reason": ct.reason,
            }
            for ct in decisions.canonical_tasks
        ],
        "brief_conflicts_disposition": [
            {
                "brief_field": d.brief_field,
                "severity": d.severity,
                "disposition": d.disposition,
                "reason": d.reason,
            }
            for d in decisions.brief_conflicts_disposition
        ],
        "operator_notes": decisions.operator_notes,
    }
