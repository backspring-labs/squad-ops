"""Reviewed annotations: how a return classified only in prose enters (SIP-0110 §0.4; #2160).

A historical return whose class is only in its ruling's prose is ``unclassified``, and produces no
pattern. It enters through a **reviewed annotation**, which keeps both the original ruling and the
annotation's provenance:

- **Beside the observation, never in it.** The observation keeps its identity, its original
  classification and its evidence as projected. An annotation adds no occurrence, so one ruling
  never becomes two pieces of evidence (§0.2's invariant).
- **What it records:** the classification it proposes, in the source's own vocabulary; the target
  behavior it substantiates, if any; its evidence (the ruling's own words and what settles them);
  the case's original context (the deploy and the prompt the author was given); and who drafted it.
- **In force only once reviewed.** A person holding ``memory:approve`` reviews it, and the review
  records who and when. An unreviewed annotation classifies nothing.
- **Append-only.** A later annotation of the same observation is read only once it is reviewed, and
  the latest reviewed one is the observation's effective classification.

**What it does not do:** it reconstructs no pre-authoring envelope, and it turns no historical
diagnostic case into a held-out replay case (§0.11). It improves traceability, nothing more.
"""

from __future__ import annotations

import dataclasses
import hashlib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from squadops.campaigns.models import ProposalClassification
from squadops.memory.observations import (
    UNCLASSIFIED,
    VOCABULARY_ATTRIBUTION,
    VOCABULARY_PLAN_VALIDATOR,
    VOCABULARY_PROPOSAL,
    Classification,
    Observation,
    ObservationSource,
)

#: Each source's own vocabulary (§0.4): an annotation classifies in it, never in another's.
SOURCE_VOCABULARY: Mapping[ObservationSource, str] = {
    ObservationSource.PLAN_REVIEW: VOCABULARY_PLAN_VALIDATOR,
    ObservationSource.CORRECTION_ROUND: VOCABULARY_ATTRIBUTION,
    ObservationSource.PROPOSAL_RULING: VOCABULARY_PROPOSAL,
}

#: What an annotation's context must name, so a reader can return to the case as it was authored.
REQUIRED_CONTEXT = ("deploy", "prompt")


class AnnotationRefused(ValueError):
    """An annotation, or a review, the rules refuse, with the reason."""


@dataclass(frozen=True)
class Annotation:
    """A proposed classification of one observation, with its evidence, and its review."""

    project_id: str
    #: The observation annotated. Its identity is the annotation's subject, never a new occurrence.
    source_id: str
    classification: Classification
    #: The target behavior the annotation substantiates beneath the class (§0.4), if any.
    target_behavior: str | None
    #: The ruling's own words and the elements that settle the classification.
    evidence: Mapping[str, Any]
    #: The case's original context: at least its deploy and the prompt the author was given.
    context: Mapping[str, Any]
    #: Who drafted it: a model and its version, or a person.
    annotator: str
    annotated_at: datetime
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    review_note: str | None = None

    @property
    def annotation_id(self) -> str:
        key = f"{self.source_id}|{self.annotated_at.isoformat()}"
        return "ann_" + hashlib.sha256(key.encode()).hexdigest()[:16]

    @property
    def reviewed(self) -> bool:
        return self.reviewed_by is not None and self.reviewed_at is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "annotation_id": self.annotation_id,
            "project_id": self.project_id,
            "source_id": self.source_id,
            "classification": self.classification.to_dict(),
            "target_behavior": self.target_behavior,
            "evidence": dict(self.evidence),
            "context": dict(self.context),
            "annotator": self.annotator,
            "annotated_at": self.annotated_at.isoformat(),
            "reviewed_by": self.reviewed_by,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "review_note": self.review_note,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Annotation:
        c = data["classification"]
        reviewed_at = data.get("reviewed_at")
        return cls(
            project_id=str(data["project_id"]),
            source_id=str(data["source_id"]),
            classification=Classification(
                vocabulary=str(c["vocabulary"]),
                values=tuple(str(v) for v in c.get("values") or ()),
                rationale=c.get("rationale"),
            ),
            target_behavior=data.get("target_behavior"),
            evidence=dict(data.get("evidence") or {}),
            context=dict(data.get("context") or {}),
            annotator=str(data["annotator"]),
            annotated_at=datetime.fromisoformat(str(data["annotated_at"])),
            reviewed_by=data.get("reviewed_by"),
            reviewed_at=datetime.fromisoformat(str(reviewed_at)) if reviewed_at else None,
            review_note=data.get("review_note"),
        )


def annotate(
    observation: Observation,
    *,
    values: Iterable[str],
    target_behavior: str | None,
    evidence: Mapping[str, Any],
    context: Mapping[str, Any],
    annotator: str,
    now: datetime,
    rationale: str | None = None,
) -> Annotation:
    """A proposed classification of ``observation`` in its source's own vocabulary. It classifies
    nothing until it is reviewed.

    Raises:
        AnnotationRefused: no class, a value outside the source's vocabulary, no evidence, a
            context missing its deploy or prompt, or no annotator.
    """
    vocabulary = SOURCE_VOCABULARY[observation.source]
    classes = tuple(str(v).strip() for v in values if str(v).strip())
    if not classes:
        raise AnnotationRefused(
            "an annotation classifies: a return that stays unclassified needs no annotation"
        )
    if vocabulary == VOCABULARY_PROPOSAL:
        known = {c.value for c in ProposalClassification}
        unknown = sorted(set(classes) - known)
        if unknown:
            raise AnnotationRefused(
                f"a proposal ruling is classified in {vocabulary}: {unknown} are not among "
                f"{sorted(known)}"
            )
    if not evidence:
        raise AnnotationRefused("an annotation records the evidence that settles it")
    missing = [k for k in REQUIRED_CONTEXT if not str(context.get(k) or "").strip()]
    if missing:
        raise AnnotationRefused(
            f"an annotation keeps the case's original context: it names no {', '.join(missing)}"
        )
    if not annotator.strip():
        raise AnnotationRefused("an annotation names who drafted it")
    return Annotation(
        project_id=observation.project_id,
        source_id=observation.source_id,
        classification=Classification(vocabulary, classes, rationale),
        target_behavior=(target_behavior or "").strip() or None,
        evidence=dict(evidence),
        context=dict(context),
        annotator=annotator.strip(),
        annotated_at=now,
    )


def review(
    annotation: Annotation, *, reviewed_by: str, now: datetime, note: str = ""
) -> Annotation:
    """The annotation, reviewed: from now on it is its observation's classification, until a later
    reviewed annotation supersedes it.

    Raises:
        AnnotationRefused: already reviewed (a review is never rewritten), or no reviewer.
    """
    if annotation.reviewed:
        raise AnnotationRefused(
            f"{annotation.annotation_id} was reviewed by {annotation.reviewed_by} at "
            f"{annotation.reviewed_at.isoformat() if annotation.reviewed_at else '?'}: a review "
            "is never rewritten; annotate again to change the classification"
        )
    if not reviewed_by.strip():
        raise AnnotationRefused("a review names its reviewer")
    return dataclasses.replace(
        annotation,
        reviewed_by=reviewed_by.strip(),
        reviewed_at=now,
        review_note=note.strip() or None,
    )


def effective_classification(
    observation: Observation, annotations: Iterable[Annotation]
) -> Classification:
    """The observation's classification as memory reads it: the latest reviewed annotation of it,
    or, with none, the classification it was projected with."""
    reviewed = [a for a in annotations if a.source_id == observation.source_id and a.reviewed]
    if not reviewed:
        return observation.classification
    return max(reviewed, key=lambda a: (a.reviewed_at, a.annotated_at)).classification


def classified_view(
    observations: Iterable[Observation], annotations: Iterable[Annotation]
) -> list[Observation]:
    """Each observation with its effective classification, same identity and evidence: a reading,
    never a stored change. The store keeps the observation as it was projected."""
    held = list(annotations)
    return [
        dataclasses.replace(o, classification=effective_classification(o, held))
        for o in observations
    ]


def citable(observations: Iterable[Observation], annotations: Iterable[Annotation]) -> set[str]:
    """The observations a lesson may cite: recorded, and classified, originally or by a reviewed
    annotation. An ``unclassified`` one produces no pattern (§0.4)."""
    return {
        o.source_id
        for o in classified_view(observations, annotations)
        if o.classification.vocabulary != UNCLASSIFIED
    }
