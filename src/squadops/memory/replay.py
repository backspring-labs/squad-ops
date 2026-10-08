"""The authoring replay, its pure half (SIP-0110 §0.6, §0.11–§0.12; slice 2, #2106).

A captured ``AuthoringReplayEnvelope`` is authored again at its own seam, under arms that differ only
by the intervention:
- **baseline:** today's prompt at the seam, with its within-cycle rung, and no cross-cycle memory;
- **scoped memory:** the same ordinary inputs, plus the eligible historical guidance;
- **static guidance:** the same guidance under a fixed policy (secondary: selectivity, unnecessary
  injection, token cost).

**Instrument validity** comes first (``validity``): the baseline arm reproduces the captured prompt
byte for byte, and the memory arm differs from it only by the lessons' section. A case that fails
either is excluded, never scored.

**Temporal validity, by evidence time** (``temporal_validity``): every observation a lesson rests on
predates the target's pre-authoring cutoff, its envelope's capture. An earlier admission of the
source unit is not enough: with two units running at once, the one admitted first may fail after the
other authored. A lesson resting on the target's own cycle is **assisted repair**, never transfer.

**Claims:** a replay is a counterfactual (what if this lesson had existed at the cutoff). A
prospective claim is about lessons approved and pinned when a unit ran, and a replay never makes one.

**Isolation:** the replay writes no production memory and learns from none of its own outputs: its
results go to the experiment's own directory, never to the store.

Pure: the in-container runner authors, and the host runner reads the records.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import random
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from squadops.memory.recall import LESSONS_INPUT


class Arm(StrEnum):
    BASELINE = "baseline"
    SCOPED_MEMORY = "scoped_memory"
    STATIC_GUIDANCE = "static_guidance"


class ClaimKind(StrEnum):
    """What a replay result may claim (§0.12): never a prospective claim."""

    COUNTERFACTUAL = "counterfactual"
    #: The lesson rests on the target's own failure: assisted repair, not transfer.
    ASSISTED_REPAIR = "assisted_repair"


@dataclass(frozen=True)
class CitedEvidence:
    """One observation a lesson rests on, with when and where it was observed."""

    observation_id: str
    observed_at: datetime
    cycle_id: str | None = None


@dataclass(frozen=True)
class ReplayLesson:
    revision_id: str
    text: str
    cited: tuple[CitedEvidence, ...]


@dataclass(frozen=True)
class TemporalVerdict:
    valid: bool
    claim: ClaimKind | None
    reason: str


def temporal_validity(
    lesson: ReplayLesson, *, cutoff: datetime, target_cycle_id: str | None
) -> TemporalVerdict:
    """Whether ``lesson`` could have existed at the target's cutoff, and what a result may claim.

    By evidence time, never by admission: every cited observation must be observed before the
    cutoff. A lesson that cites none has no time to check, so it is refused."""
    if not lesson.cited:
        return TemporalVerdict(False, None, "the lesson cites no evidence to date")
    late = sorted(c.observation_id for c in lesson.cited if c.observed_at >= cutoff)
    if late:
        return TemporalVerdict(
            False, None, f"evidence observed at or after the target's cutoff: {late}"
        )
    if target_cycle_id and any(c.cycle_id == target_cycle_id for c in lesson.cited):
        return TemporalVerdict(
            True, ClaimKind.ASSISTED_REPAIR, "the lesson rests on the target's own cycle"
        )
    return TemporalVerdict(True, ClaimKind.COUNTERFACTUAL, "every cited observation predates it")


def arm_inputs(
    own_inputs: Mapping[str, Any],
    arm: Arm,
    *,
    experiment_id: str,
    lessons: Sequence[ReplayLesson] = (),
    static_guidance: str = "",
) -> dict[str, Any]:
    """The inputs one arm hands the handler: the envelope's own inputs, which never carry lessons,
    and for a memory arm the intervention on ``LESSONS_INPUT``, as a live seam is handed it."""
    inputs = {k: v for k, v in own_inputs.items() if k != LESSONS_INPUT}
    if arm is Arm.BASELINE:
        return inputs
    if arm is Arm.SCOPED_MEMORY:
        handed = [{"revision_id": r.revision_id, "text": r.text} for r in lessons]
    else:
        handed = [{"revision_id": "static", "text": static_guidance}]
    if not any(item["text"].strip() for item in handed):
        raise ValueError(f"the {arm.value} arm has no guidance to hand")
    inputs[LESSONS_INPUT] = {"snapshot": f"replay:{experiment_id}:{arm.value}", "lessons": handed}
    return inputs


@dataclass(frozen=True)
class Validity:
    """The instrument-validity check for one case (§0.11)."""

    baseline_exact: bool
    memory_differs_only_by_its_section: bool | None

    @property
    def valid(self) -> bool:
        return self.baseline_exact and self.memory_differs_only_by_its_section is not False


def validity(
    captured: Sequence[str],
    reproduced: Sequence[str],
    baseline: Sequence[str],
    memory: Sequence[str] | None = None,
    section: str = "",
) -> Validity:
    """Each argument is a prompt's message contents, in order: ``captured`` as the envelope recorded
    it, ``reproduced`` re-rendered from the inputs the handler was handed (its own and any lessons
    it was supplied live), ``baseline`` from its own inputs alone, ``memory`` the memory arm's.
    ``section`` is the lessons' rendered section.

    The reproduction must be exact. The memory arm passes when, against the baseline, it only
    inserts lines, and the inserted lines are the section's, every one of them, and the blank lines
    that set it apart. Nothing of the baseline is changed or removed, in any message."""
    exact = list(captured) == list(reproduced)
    if memory is None:
        return Validity(exact, None)
    body = [line for line in section.strip("\n").splitlines() if line.strip()]
    if not body or len(memory) != len(baseline):
        return Validity(exact, False)
    inserted: list[str] = []
    for m, b in zip(memory, baseline, strict=True):
        if m == b:
            continue
        added = _inserted_lines(b, m)
        if added is None:
            return Validity(exact, False)
        inserted.extend(added)
    shown = [line for line in inserted if line.strip()]
    return Validity(exact, shown == body)


def _inserted_lines(baseline: str, memory: str) -> list[str] | None:
    """The lines ``memory`` inserts into ``baseline``, or ``None`` when it changes or removes any."""
    old, new = baseline.splitlines(), memory.splitlines()
    matcher = difflib.SequenceMatcher(a=old, b=new, autojunk=False)
    inserted: list[str] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        if tag == "insert":
            inserted.extend(new[j1:j2])
            continue
        # A blank line of the baseline's replaced by the section and its breaks is still an
        # insertion; anything else replaced or deleted is a change.
        if tag == "replace" and all(not line.strip() for line in old[i1:i2]):
            inserted.extend(new[j1:j2])
            continue
        return None
    return inserted


def schedule(
    case_ids: Sequence[str], arms: Sequence[Arm], generations: int, seed: int
) -> list[tuple[str, Arm, int]]:
    """Every case under every arm, ``generations`` times, paired: each case's arms run together
    within a generation, in an order the seed shuffles, so no arm always runs first."""
    rng = random.Random(seed)
    order: list[tuple[str, Arm, int]] = []
    for generation in range(generations):
        for case in case_ids:
            arms_now = list(arms)
            rng.shuffle(arms_now)
            order.extend((case, arm, generation) for arm in arms_now)
    return order


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


@dataclass(frozen=True)
class ExperimentManifest:
    """What a replay's result depends on, each by version or hash (§0.12). Frozen before scored
    runs: a change to any of it is a different experiment."""

    experiment_id: str
    created_at: datetime
    #: Each case: its envelope, task type, seam, captured prompt's digest and cutoff.
    cases: tuple[Mapping[str, Any], ...]
    arms: tuple[Arm, ...]
    generations: int
    seed: int
    lessons: tuple[Mapping[str, Any], ...]
    static_guidance_sha256: str | None
    #: The model settings the cases were captured with, by model.
    model_settings: tuple[Mapping[str, Any], ...]
    rubric: str
    framework_git_sha: str
    excluded: tuple[Mapping[str, Any], ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "created_at": self.created_at.isoformat(),
            "cases": [dict(c) for c in self.cases],
            "arms": [a.value for a in self.arms],
            "generations": self.generations,
            "seed": self.seed,
            "lessons": [dict(lesson) for lesson in self.lessons],
            "static_guidance_sha256": self.static_guidance_sha256,
            "model_settings": [dict(m) for m in self.model_settings],
            "rubric": self.rubric,
            "framework_git_sha": self.framework_git_sha,
            "excluded": [dict(e) for e in self.excluded],
        }

    def digest(self) -> str:
        """The experiment's identity: everything but when the manifest was written."""
        frozen = {k: v for k, v in self.to_dict().items() if k != "created_at"}
        return _sha(json.dumps(frozen, sort_keys=True))


def manifest(
    *,
    experiment_id: str,
    created_at: datetime,
    envelopes: Iterable[Mapping[str, Any]],
    arms: Sequence[Arm],
    generations: int,
    seed: int,
    lessons: Sequence[ReplayLesson],
    static_guidance: str,
    rubric: str,
    framework_git_sha: str,
    excluded: Sequence[Mapping[str, Any]] = (),
) -> ExperimentManifest:
    cases, settings = [], {}
    for e in envelopes:
        cases.append(
            {
                "envelope_id": e["envelope_id"],
                "task_type": e["task_type"],
                "seam": e["seam"],
                "messages_sha256": e["messages_sha256"],
                "captured_at": e["captured_at"],
            }
        )
        kwargs = e.get("chat_kwargs") or {}
        model = str(kwargs.get("model") or "")
        settings[model] = {k: kwargs[k] for k in sorted(kwargs) if k != "messages"}
    return ExperimentManifest(
        experiment_id=experiment_id,
        created_at=created_at,
        cases=tuple(cases),
        arms=tuple(arms),
        generations=generations,
        seed=seed,
        lessons=tuple({"revision_id": r.revision_id, "text_sha256": _sha(r.text)} for r in lessons),
        static_guidance_sha256=_sha(static_guidance) if static_guidance else None,
        model_settings=tuple({"model": m, **s} for m, s in sorted(settings.items())),
        rubric=rubric,
        framework_git_sha=framework_git_sha,
        excluded=tuple(excluded),
    )
