"""The lesson-text diagnostic (SIP-0110 Appendix A §3.7, T9; #2179 stage 2).

In a unit that withholds the lessons (``memory: disabled``, or ``memory_context: none``), a prompt that
contains an approved lesson's text, whitespace normalized, is flagged. It is a **signal**, reported
beside the structural guarantees and never as proof either way: it misses a paraphrase, and it can
match a legitimate requirement. A flag is reviewed, never failed automatically.

The prompts read are the authoring envelopes' messages (§0.11): the four seams memory reaches, the
only prompts captured whole. A lesson counts only while its approval was in force at the envelope's
capture. One approved later could not have reached the prompt, and its text matching would only say
the lesson quotes the prompt it was drafted from.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

from squadops.memory.build_report import declared_arms
from squadops.memory.declarations import ARM_LESSONS_ON
from squadops.memory.lessons import Approval, PatternRevision

if TYPE_CHECKING:
    from squadops.memory.exposures import Exposure
    from squadops.ports.cycles.cycle_registry import CycleRegistryPort
    from squadops.ports.memory.cross_cycle import CrossCycleMemoryStorePort


@dataclass(frozen=True)
class LessonTextSignal:
    """One envelope's prompt that holds one approved lesson's text."""

    run_id: str
    task_id: str
    seam: str
    captured_at: str
    revision_id: str


def _normalized(text: str) -> str:
    return " ".join(text.split())


def _in_force(approval: Approval, at: datetime) -> bool:
    return approval.approved_at <= at and (approval.revoked_at is None or approval.revoked_at > at)


def lesson_text_signals(
    run_id: str,
    envelopes: Iterable[Mapping[str, Any]],
    lessons: Sequence[PatternRevision],
    approvals: Sequence[Approval],
) -> tuple[LessonTextSignal, ...]:
    """Each of a withholding run's envelopes whose messages hold the text of a lesson approved at
    its capture, once per such lesson."""
    texts = {r.revision_id: _normalized(r.text) for r in lessons if r.text.strip()}
    signals = []
    for envelope in envelopes:
        captured = datetime.fromisoformat(str(envelope["captured_at"]))
        sent = _normalized(" ".join(str(m.get("content", "")) for m in envelope["messages"]))
        approved = sorted({a.revision_id for a in approvals if _in_force(a, captured)})
        signals += [
            LessonTextSignal(
                run_id=run_id,
                task_id=str(envelope["task_id"]),
                seam=str(envelope["seam"]),
                captured_at=str(envelope["captured_at"]),
                revision_id=revision_id,
            )
            for revision_id in approved
            if revision_id in texts and texts[revision_id] in sent
        ]
    return tuple(signals)


async def withheld_lesson_signals(
    exposures: Iterable[Exposure],
    *,
    project_id: str,
    cycles: CycleRegistryPort,
    store: CrossCycleMemoryStorePort,
) -> tuple[LessonTextSignal, ...]:
    """The diagnostic over every run whose cycle declared the lessons withheld (either
    declaration): read from the cycle's own declaration, so a cycle whose recalls all failed is
    still read. A cycle whose declaration can't be read is not."""
    exposures = list(exposures)
    arms = await declared_arms((e.cycle_id for e in exposures), cycles=cycles)
    runs = sorted(
        {e.run_id for e in exposures if arms.get(e.cycle_id, ARM_LESSONS_ON) != ARM_LESSONS_ON}
    )
    if not runs:
        return ()
    lessons = await store.list_revisions(project_id)
    approvals = await store.list_approvals(project_id)
    signals: list[LessonTextSignal] = []
    for run_id in runs:
        envelopes = await cycles.list_authoring_envelopes(run_id)
        signals += lesson_text_signals(run_id, envelopes, lessons, approvals)
    return tuple(signals)
