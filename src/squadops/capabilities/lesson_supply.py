"""Supplying approved lessons to the authoring seams (SIP-0110 §0.9; slice 3c, #2096).

Each task at a consuming seam asks the recall before it is dispatched, with its scope taken from
trusted context: the project and task type from its envelope, the role and model the plan resolved
for it, the cycle's stack, and its unit's pinned snapshot. Every such task's answer is disclosed as
an exposure, a memory-disabled one included. A task is handed lessons only when some are supplied,
on ``LESSONS_INPUT``; a task handed none has exactly the inputs it had before memory existed, so its
prompt renders byte-identical (§0.9).

Which task types consume is their context-assembly contract's declaration (``authoring_seam_of``),
never a branch on the type. Plan writing and build authoring are supplied here, when the run's plan
is composed; repair when the correction runner composes a repair, and proposal writing when a
campaign composes its proposal, each through the same function.

An exposure is one authoring invocation's (§0.2), so a task the loop dispatches again (a correction
round's re-take, an emission retry) asks again and discloses its own answer, under its attempt
(:func:`supply_the_redispatch`, #2162).

Every seam asks through the context-assembly port (Appendix A §3.6, #2176). In 2.3 the port is
:class:`LessonContextAssembly`: one optional section, the lessons today's recall supplies from the snapshot
owner, disclosed as today's exposure, so prompts and exposures are what they were before the port.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import re
from collections.abc import Collection, Sequence
from datetime import datetime
from importlib import resources
from typing import TYPE_CHECKING

from squadops.capabilities.context_assembly import authoring_seam_of
from squadops.capabilities.handlers.fault_injection import PRIOR_ATTEMPTS_KEY
from squadops.capabilities.prompt_budget import prompt_budget
from squadops.cycles.benchmark_registry import cycle_stack
from squadops.cycles.models import HoldKind
from squadops.llm.model_registry import model_family_of
from squadops.memory.context import (
    ChatTurn,
    ContextBundle,
    ContextRequest,
    Disposition,
    Need,
    ProjectBound,
    RecordRef,
    Section,
    SectionKind,
    TaskInvocation,
    UnitRef,
)
from squadops.memory.dispatch_turns import DispatchTurnUnavailable
from squadops.memory.exposures import Exposure
from squadops.memory.lessons import RecallDisposition, Recalled, RecallPolicy, _tokens
from squadops.memory.project_instructions import (
    PROJECT_INSTRUCTIONS_INPUT,
    PinUnknown,
    bound_references,
    unbound_references,
)
from squadops.memory.project_instructions import applicable as project_applicable
from squadops.memory.project_instructions import handed as project_handed
from squadops.memory.project_instructions import section_of as project_section_of
from squadops.memory.recall import LESSONS_INPUT, RecallQuery, UnitKind
from squadops.memory.reference_reading import (
    ReferencesRead,
    measured,
    read_references,
    unread_references,
)
from squadops.memory.references import BindingContext
from squadops.memory.task_instructions import (
    TASK_INSTRUCTIONS_INPUT,
    TaskInstructionsUnavailable,
    applicable,
    handed,
    interventions,
    section_of,
    unresolved_reason,
)
from squadops.ports.memory.context_assembly import ContextAssemblyPort

if TYPE_CHECKING:
    from squadops.cycles.models import Cycle
    from squadops.ports.memory.recall import FailurePatternRecallPort
    from squadops.tasks.models import TaskEnvelope

logger = logging.getLogger(__name__)

#: The slots' managed templates, whose fixed framing (heading and precedence) a section is measured with.
_TASK_SLOT = "request.task_instructions_section"
_PROJECT_SLOT = "request.project_instructions_section"
_LESSON_SLOT = "request.cross_cycle_lessons_section"
#: How a reference's content is shown under its instruction (#2179), its framing measured per reference.
_REFERENCE_SLOT = "request.instruction_reference"


@functools.cache
def _framing(template_id: str) -> int:
    """A slot's fixed framing in tokens (§3.6: a section's size includes it), measured as recall
    measures lessons: the template's body with its variable taken out."""
    text = (
        resources.files("squadops.prompts") / "request_templates" / f"{template_id}.md"
    ).read_text(encoding="utf-8")
    body = text.split("---", 2)[2]
    return _tokens(re.sub(r"\{\{\w+\}\}", "", body).strip())


def _binding_size(template_id: str, texts: list[str]) -> int:
    """A binding section's size, framing included; 0 for a section with nothing to show."""
    return _framing(template_id) + sum(_tokens(t) for t in texts) if texts else 0


def _references_framing(references, read) -> int:
    """The framing of each reference read (its slot's heading and fence), which its section's size
    includes beside the content (#2179); nothing when none was read."""
    shown = {r.ref for r in references if r.ref in read.contents}
    return _framing(_REFERENCE_SLOT) * len(shown)


def _available_for_lessons(prompt_budget: int, binding: int) -> int | None:
    """§3.6's effective lesson budget's second figure: the lesson text the binding sections leave after
    the lesson slot's framing, below zero when not even the framing fits. ``None`` when no binding
    section was supplied, or the budget is unknown, so the snapshot's own budget stands and the
    lessons are today's recall exactly."""
    if binding == 0 or prompt_budget < 0:
        return None
    return prompt_budget - binding - _framing(_LESSON_SLOT)


#: Recall's outcomes, as the lesson section's dispositions (§3.6).
_SECTION_DISPOSITION = {
    RecallDisposition.SUPPLIED: Disposition.SUPPLIED,
    RecallDisposition.NONE_ELIGIBLE: Disposition.NONE_ELIGIBLE,
    RecallDisposition.DISABLED: Disposition.DISABLED,
    RecallDisposition.CONTEXT_NONE: Disposition.CONTEXT_NONE,
    RecallDisposition.OMITTED_BY_BUDGET: Disposition.OMITTED_BY_BUDGET,
    RecallDisposition.INCOMPATIBLE: Disposition.INCOMPATIBLE,
    RecallDisposition.FAILED: Disposition.FAILED,
}


def reaches(selector: Collection[str], task_type: str) -> bool:
    """Whether a task instruction selecting ``selector``'s task types reaches a dispatch of
    ``task_type`` (§3.7): a selected type itself, or a repair that revises a selected type's own
    output (``task_plan.repairs_revising``)."""
    # deferred (cycle): cycles.task_plan loads the context-assembly contracts this module reads
    from squadops.cycles.task_plan import repairs_revising

    return any(task_type == s or task_type in repairs_revising(s) for s in selector)


def unit_of(cycle: Cycle) -> tuple[UnitKind, str]:
    """The unit whose snapshot a cycle's tasks select from (§0.7): its campaign's, or its own."""
    if cycle.campaign_id:
        return UnitKind.CAMPAIGN, cycle.campaign_id
    return UnitKind.CYCLE, cycle.cycle_id


def request_for(
    envelope: TaskEnvelope, *, unit: tuple[UnitKind, str], stack: str, run_id: str
) -> ContextRequest:
    """The task's context request, from trusted context only: its project and cycle from the envelope,
    the role the plan step names and the model the plan resolved, both written by the framework, never
    by an agent (§0.8 step 1), and the unit whose snapshot answers."""
    return ContextRequest(
        binding=ProjectBound(envelope.project_id),
        consumer=TaskInvocation(
            run_id=run_id,
            task_id=envelope.task_id,
            attempt=attempt_of(envelope),
            target_cycle_id=envelope.cycle_id,
            snapshot_owner=UnitRef(*unit),
            task_type=str(envelope.task_type),
            role=str((envelope.metadata or {}).get("role") or ""),
            stack=stack,
            model_family=model_family_of(str(envelope.inputs.get("agent_model") or "")),
            agent_id=envelope.agent_id,
            prompt_budget=prompt_budget(envelope),
        ),
    )


def query_of(request: ContextRequest) -> RecallQuery:
    """Today's recall query for a task invocation's request: its unit is the snapshot owner, never the
    target cycle (§3.7). An empty field matches no lesson (§0.8 step 3)."""
    task = request.consumer
    if not isinstance(task, TaskInvocation) or not isinstance(request.binding, ProjectBound):
        raise TypeError("recall answers a task invocation bound to a project")
    return RecallQuery(
        project_id=request.binding.project_id,
        task_type=task.task_type,
        role=task.role,
        stack=task.stack,
        model_family=task.model_family,
        unit_kind=task.snapshot_owner.kind,
        unit_id=task.snapshot_owner.unit_id,
    )


def attempt_of(envelope: TaskEnvelope) -> int:
    """Which dispatch of its task ``envelope``'s next one is: the executor's attempt stamp (#1304),
    which counts the attempts already made, plus one. The captured envelope carries the same
    stamp, so an exposure and its authoring join on it."""
    return int((envelope.inputs or {}).get(PRIOR_ATTEMPTS_KEY) or 0) + 1


def lessons_input(recalled: Recalled | None) -> dict | None:
    """What a task is handed on ``LESSONS_INPUT``, or ``None`` when nothing was supplied."""
    if recalled is None or not recalled.supplied:
        return None
    return {
        "snapshot": recalled.snapshot_id,
        "lessons": [
            {"revision_id": e.revision.revision_id, "text": e.revision.text}
            for e in recalled.supplied
        ],
    }


async def supply_for_cycle(
    envelopes: Sequence[TaskEnvelope],
    *,
    recall: FailurePatternRecallPort,
    cycle: Cycle,
    run_id: str,
    now: datetime,
) -> list[TaskEnvelope]:
    """:func:`supply_lessons` for a run of ``cycle``: its unit and its stack (``cycle_stack``)."""

    return await supply_lessons(
        envelopes,
        recall=recall,
        unit=unit_of(cycle),
        stack=cycle_stack(cycle) or "",
        run_id=run_id,
        now=now,
    )


async def supply_lessons(
    envelopes: Sequence[TaskEnvelope],
    *,
    recall: FailurePatternRecallPort,
    unit: tuple[UnitKind, str],
    stack: str,
    run_id: str,
    now: datetime,
) -> list[TaskEnvelope]:
    """``envelopes``, each consuming task's with the lessons it is supplied, in order. Every
    consuming task's answer is disclosed; a task that consumes nothing is passed through as is.

    #2178: composed in one dispatch turn, and disclosed only when every task's binding sections are
    complete. A run supplies its authoring tasks before its first dispatch, so one held task holds
    the run, and the rest are composed again at its release: disclosed now, their answers would
    read as dispatched (§5w) and handed (§5v), and refuse the very change that releases it."""
    consuming = [
        (i, envelope)
        for i, envelope in enumerate(envelopes)
        if authoring_seam_of(str(envelope.task_type)) is not None
    ]
    bundles = await _composed(
        [envelope for _, envelope in consuming],
        recall=recall,
        unit=unit,
        stack=stack,
        run_id=run_id,
        now=now,
    )
    supplied = list(envelopes)
    for (i, envelope), bundle in zip(consuming, bundles, strict=True):
        inputs = dict(envelope.inputs)
        for key, value in _handed(bundle):
            if value is not None:
                inputs[key] = value
        if inputs != envelope.inputs:
            supplied[i] = dataclasses.replace(envelope, inputs=inputs)
    return supplied


async def supply_the_redispatch(
    envelopes: Sequence[TaskEnvelope | None],
    *,
    recall: FailurePatternRecallPort,
    cycle: Cycle,
    run_id: str,
    now: datetime,
) -> None:
    """A task the loop is about to dispatch again is another authoring invocation (§0.2, #2162):
    it asks its unit's snapshot again and discloses its own exposure, under its attempt.

    The loop re-dispatches the envelopes it already holds, so what this attempt is handed replaces
    what the one before it was handed, in place, on each of them: a lesson the earlier answer
    supplied and this one does not is taken off, or the envelope would carry a lesson its exposure
    says it never got. The first of ``envelopes`` is the task's own; the rest (the enriched copy the
    loop dispatches) are kept equal to it. A task at no consuming seam is left as it is.
    """

    held = [e for e in envelopes if e is not None]
    if not held:
        return
    if authoring_seam_of(str(held[0].task_type)) is None:
        return
    [bundle] = await _composed(
        [held[0]],
        recall=recall,
        unit=unit_of(cycle),
        stack=cycle_stack(cycle) or "",
        run_id=run_id,
        now=now,
    )
    # #2178: each dispatch reads its task instructions again, so one withdrawn since the attempt
    # before is gone from this one, and nothing is copied from that attempt.
    for envelope in held:
        for key, value in _handed(bundle):
            if value is None:
                envelope.inputs.pop(key, None)
            else:
                envelope.inputs[key] = value


def _handed(bundle: ContextBundle) -> tuple[tuple[str, dict | None], ...]:
    """What a task is handed on each supplied input, ``None`` where nothing is supplied."""
    task, project = bundle.task_instructions, bundle.project_instructions
    return (
        (LESSONS_INPUT, lessons_input(bundle.recalled)),
        (TASK_INSTRUCTIONS_INPUT, dict(task) if task else None),
        (PROJECT_INSTRUCTIONS_INPUT, dict(project) if project else None),
    )


async def _composed(
    envelopes: Sequence[TaskEnvelope],
    *,
    recall: FailurePatternRecallPort,
    unit: tuple[UnitKind, str],
    stack: str,
    run_id: str,
    now: datetime,
) -> list[ContextBundle]:
    """Each invocation's context, through the port, assembled with its task's trusted scope and
    disclosed under its attempt. A binding section that is incomplete holds its task (§3.6): only
    the first held task's answer is disclosed, marked held, and the hold is raised with why.

    #2545: read and disclosed in the unit's dispatch turn, so a re-binding or an instruction added
    after admission lands before the reads or after the exposures, never between them. A turn that
    isn't given holds the first task, as an unreadable store does."""
    if not envelopes:
        return []
    assembly = LessonContextAssembly(recall, now=now)
    try:
        async with recall.dispatch_turn(*unit):
            bundles = [
                await assembly.assemble(request_for(e, unit=unit, stack=stack, run_id=run_id))
                for e in envelopes
            ]
            held = next((b for b in bundles if not b.complete), None)
            for bundle in [held] if held is not None else bundles:
                await assembly.disclose(bundle)
    except DispatchTurnUnavailable as e:
        first = envelopes[0]
        raise TaskInstructionsUnavailable(
            f"task {first.task_id} is held: {e}",
            task_id=first.task_id,
            task_type=str(first.task_type),
            unresolved=((f"dispatch_turn:{unit[0].value}:{unit[1]}", str(e), HoldKind.STORE),),
        ) from e
    if held is not None:
        raise _unavailable(held)
    return bundles


def _unavailable(bundle: ContextBundle) -> TaskInstructionsUnavailable:
    """The hold an incomplete bundle raises: its task, each record it couldn't bind with why and
    whether the store failed it, and the sections that held."""
    task = bundle.request.consumer
    assert isinstance(task, TaskInvocation)  # only a task invocation's bundle binds
    incomplete = [
        s
        for s in bundle.sections
        if s.need is Need.BINDING and s.disposition is Disposition.INCOMPLETE
    ]
    why = "; ".join(unresolved_reason(s) for s in incomplete)
    return TaskInstructionsUnavailable(
        f"task {task.task_id} is held: {why}",
        task_id=task.task_id,
        task_type=task.task_type,
        unresolved=tuple(
            (
                f"{ref.record_id}@{ref.revision}" if ref.revision else ref.record_id,
                reason,
                HoldKind.STORE if s.store_failed else HoldKind.INPUT,
            )
            for s in incomplete
            for ref, reason in s.unresolved
        ),
        sections=tuple(s.kind.value for s in incomplete),
    )


class LessonContextAssembly(ContextAssemblyPort):
    """The context-assembly port as 2.3 builds it (Appendix A §3.6, #2176): inert.

    Its one section is SIP-0110's lessons, optional, answered by today's recall from the snapshot owner, and
    its disclosure is today's exposure. There is no binding section yet, so every bundle is complete, and
    the lesson budget is the snapshot's own: recall applies it, exactly as before (its effective-budget
    input is #2179's). A chat turn's lesson section is ``not_applicable``, and its exposure is #2180's.
    """

    def __init__(self, recall: FailurePatternRecallPort, *, now: datetime) -> None:
        self._recall = recall
        self._now = now

    async def assemble(self, request: ContextRequest) -> ContextBundle:
        if isinstance(request.consumer, ChatTurn):
            lessons = Section(SectionKind.LESSONS, Need.OPTIONAL, Disposition.NOT_APPLICABLE)
            return ContextBundle(request, (lessons,), complete=True)
        task_unread, bound = await self._task_instructions(request)
        project_unread, pinned = await self._project_instructions(request)
        # #2179: each reference either section hands, read at its bound revision, once.
        read = await self._read_references(request, bound, pinned)
        # The project instructions take what the task instructions leave (§3.6), each binding
        # section measured with its slot's framing and the content of the references it hands.
        budget = request.consumer.prompt_budget
        task_refs = [r for b in bound for r in b.references]
        task_size = _binding_size(
            _TASK_SLOT, [measured(b.text, b.references, read) for b in bound]
        ) + _references_framing(task_refs, read)
        instructions = task_unread or section_of(
            bound,
            budget=budget,
            framing=_framing(_TASK_SLOT) + _references_framing(task_refs, read),
            read=read,
        )
        left = max(0, budget - task_size) if budget >= 0 else -1
        project_refs = [r for p in pinned for r in p.references if r.ref not in dict(p.unbound)]
        project = project_unread or project_section_of(
            pinned,
            budget=left,
            framing=_framing(_PROJECT_SLOT) + _references_framing(project_refs, read),
            read=read,
        )
        project_size = _binding_size(
            _PROJECT_SLOT,
            [measured(p.text, [r for r in p.references if r.ref not in dict(p.unbound)], read)
             for p in pinned],
        ) + _references_framing(project_refs, read)  # fmt: skip
        available = _available_for_lessons(budget, task_size + project_size)
        try:
            recalled = await self._recall.recall(
                dataclasses.replace(query_of(request), available_lesson_tokens=available)
            )
        except Exception:  # the port never raises: a recall that raised is a failed one, never none
            logger.exception("recall raised for task %s", request.consumer.task_id)
            recalled = Recalled(snapshot_id=None, disposition=RecallDisposition.FAILED)
        if recalled.disposition is RecallDisposition.CONTEXT_NONE:
            # §3.7: the snapshot pinned none, and its project section says it was withheld rather
            # than that none applied, so the exposure records the experiment it ran.
            project = Section(
                SectionKind.PROJECT_INSTRUCTIONS, Need.BINDING, Disposition.CONTEXT_NONE
            )
        lessons = Section(
            SectionKind.LESSONS,
            Need.OPTIONAL,
            _SECTION_DISPOSITION[recalled.disposition],
            supplied=tuple(
                RecordRef(e.revision.pattern_id, str(e.revision.revision))
                for e in recalled.supplied
            ),
            omitted=tuple((RecordRef.of_revision_id(r), why) for r, why in recalled.omitted),
            effective_budget=(
                recalled.lesson_budget["effective"]
                if recalled.lesson_budget is not None
                else RecallPolicy().token_budget
            ),
        )
        return ContextBundle(
            request,
            (instructions, project, lessons),
            complete=Disposition.INCOMPLETE not in (instructions.disposition, project.disposition),
            recalled=recalled,
            task_instructions=handed(bound, read),
            project_instructions=project_handed(pinned, read),
        )

    async def _read_references(self, request: ContextRequest, bound, pinned) -> ReferencesRead:
        """Each reference the dispatch would be handed, read at its bound revision through the
        unit's recall (#2179): a task instruction's, and each a project instruction's admission
        bound."""
        task = request.consumer
        if not isinstance(task, TaskInvocation) or not isinstance(request.binding, ProjectBound):
            return ReferencesRead()
        ctx = BindingContext(
            project_id=request.binding.project_id,
            unit_kind=task.snapshot_owner.kind.value,
            unit_id=task.snapshot_owner.unit_id,
        )
        references = [r for b in bound for r in b.references] + [
            r for p in pinned for r in p.references if r.ref not in dict(p.unbound)
        ]
        return await read_references(
            references, lambda reference: self._recall.read_reference(reference, ctx)
        )

    async def _project_instructions(self, request: ContextRequest):
        """The snapshot owner's pinned project instructions that apply to this dispatch (#2179),
        with no section, or the section that stands for them: not applicable, or incomplete when
        the snapshot can't be read, since it binds and never reads as none (§3.6)."""
        task = request.consumer
        kind = SectionKind.PROJECT_INSTRUCTIONS
        if not isinstance(task, TaskInvocation) or not isinstance(request.binding, ProjectBound):
            return Section(kind, Need.BINDING, Disposition.NOT_APPLICABLE), []
        owner = task.snapshot_owner
        try:
            pinned = await self._recall.pinned_instructions(
                owner.kind, owner.unit_id, request.binding.project_id,
                cycle_id=task.target_cycle_id,
            )  # fmt: skip
        except Exception as e:
            logger.warning(
                "project_instructions_unreadable unit=%s:%s task=%s",
                owner.kind,
                owner.unit_id,
                task.task_id,
                exc_info=True,
            )
            why = (
                str(e)
                if isinstance(e, PinUnknown)
                else f"the unit's pin could not be checked against the project's records ({e})"
            )
            unread = RecordRef(f"snapshot:{owner.kind}:{owner.unit_id}", "")
            unresolved = ((unread, why),)
            return (
                Section(
                    kind,
                    Need.BINDING,
                    Disposition.INCOMPLETE,
                    unresolved=unresolved,
                    store_failed=True,
                ),
                [],
            )
        chosen = project_applicable(
            pinned, task_type=task.task_type, role=task.role, stack=task.stack
        )
        return None, chosen

    async def _task_instructions(self, request: ContextRequest):
        """The task instructions that apply (#2178), with no section, or the section that stands
        for them: not applicable, or incomplete when the store can't be read, since it never
        reads as none (§3.6)."""
        task = request.consumer
        if not isinstance(task, TaskInvocation) or not isinstance(request.binding, ProjectBound):
            kind, need = SectionKind.TASK_INSTRUCTIONS, Need.BINDING
            return Section(kind, need, Disposition.NOT_APPLICABLE), []
        try:
            records = await self._recall.task_instructions(
                request.binding.project_id, task.target_cycle_id
            )
        except Exception:
            logger.warning(
                "task_instructions_unreadable cycle=%s task=%s",
                task.target_cycle_id,
                task.task_id,
                exc_info=True,
            )
            unread = RecordRef(f"task_instructions:{task.target_cycle_id}", "")
            return (
                Section(
                    SectionKind.TASK_INSTRUCTIONS,
                    Need.BINDING,
                    Disposition.INCOMPLETE,
                    unresolved=((unread, "the memory records could not be read"),),
                    store_failed=True,
                ),
                [],
            )
        bound = applicable(
            records,
            cycle_id=task.target_cycle_id,
            reaches=lambda selector: reaches(selector, task.task_type),
        )
        return None, bound

    async def disclose(self, bundle: ContextBundle) -> None:
        task = bundle.request.consumer
        if not isinstance(task, TaskInvocation) or bundle.recalled is None:
            return
        seam = authoring_seam_of(task.task_type)
        if seam is None:
            return
        await self._recall.disclose(
            Exposure.of(
                run_id=task.run_id,
                task_id=task.task_id,
                cycle_id=task.target_cycle_id,
                agent_id=task.agent_id,
                seam=seam.value,
                query=query_of(bundle.request),
                recalled=bundle.recalled,
                recorded_at=self._now,
                attempt=task.attempt,
                task_instructions=_section_record(
                    bundle.section(SectionKind.TASK_INSTRUCTIONS),
                    marked=interventions(bundle.task_instructions),
                    bound=bound_references(bundle.task_instructions),
                    omitted=unread_references(bundle.task_instructions),
                ),
                project_instructions=_section_record(
                    bundle.section(SectionKind.PROJECT_INSTRUCTIONS),
                    bound=bound_references(bundle.project_instructions),
                    omitted=unbound_references(bundle.project_instructions)
                    + unread_references(bundle.project_instructions),
                ),
            )
        )


def _section_record(
    section: Section | None,
    *,
    marked: Sequence[str] = (),
    bound: Sequence[dict] = (),
    omitted: Sequence[dict] = (),
) -> dict | None:
    """A binding section as its exposure keeps it: the disposition, each revision supplied, and
    each that couldn't be with why, the interventions among them (§3.5), and each reference a
    unit's admission bound and the revision it was handed at (§3.7, T16). ``None`` for no
    section, so an exposure with no instructions read is what it was before #2178."""
    if section is None or section.disposition is Disposition.NONE_ELIGIBLE:
        return None
    return {
        "disposition": section.disposition.value,
        "supplied": [{"record_id": r.record_id, "revision": r.revision} for r in section.supplied],
        "unresolved": [
            {"record_id": r.record_id, "revision": r.revision, "why": why}
            for r, why in section.unresolved
        ],
        # Only when one was handed, so every other exposure is recorded as it was.
        **({"interventions": list(marked)} if marked else {}),
        **({"bound_references": list(bound)} if bound else {}),
        **({"omitted_references": list(omitted)} if omitted else {}),
    }
