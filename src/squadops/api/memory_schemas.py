"""Request bodies for Cross-Cycle Memory's lesson routes (SIP-0110 §0.6, slice 3d)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ApplicabilityDTO(BaseModel):
    """Where a lesson applies; the project is the route's. Every field names what it covers."""

    task_types: list[str] = Field(min_length=1)
    roles: list[str] = Field(min_length=1)
    stacks: list[str] = Field(min_length=1)
    model_families: list[str] = Field(min_length=1)

    model_config = ConfigDict(extra="forbid")


class LessonDraftRequest(BaseModel):
    """The auditor's draft (D15): a revision of the target behavior's pattern."""

    target_behavior: str
    text: str
    applicability: ApplicabilityDTO
    template_id: str
    template_version: str
    drafter_model: str
    drafter_version: str
    cited_observations: list[str] = Field(min_length=1)

    model_config = ConfigDict(extra="forbid")


class ReplayCheckDTO(BaseModel):
    reference: str
    result: str

    model_config = ConfigDict(extra="forbid")


class CombinedCheckDTO(BaseModel):
    """The auditor's check of the draft with every approved lesson supplied beside it (§0.6)."""

    revision_ids: list[str]
    verdict: Literal["no_conflict", "conflict"]
    reference: str

    model_config = ConfigDict(extra="forbid")


class LessonApprovalRequest(BaseModel):
    """The owner's approval. ``applicability`` defaults to the revision's own, and may narrow it."""

    ruling: str
    replay_check: ReplayCheckDTO
    combined_check: CombinedCheckDTO
    applicability: ApplicabilityDTO | None = None

    model_config = ConfigDict(extra="forbid")


class RevocationRequest(BaseModel):
    reason: str

    model_config = ConfigDict(extra="forbid")


class AssessmentRequest(BaseModel):
    """One target's state in an exposure's authored output (SIP-0110 §0.10)."""

    pattern_id: str
    state: Literal["present", "absent", "not_applicable", "unassessed"]
    #: Whether the output did its required work; an absence requires it.
    required_work_done: bool | None = None
    rubric: str
    evidence: str

    model_config = ConfigDict(extra="forbid")


class AnnotationRequest(BaseModel):
    """A proposed classification of an observation classified only in prose (SIP-0110 §0.4, #2160).
    It classifies nothing until the owner reviews it."""

    values: list[str] = Field(min_length=1)
    target_behavior: str | None = None
    rationale: str | None = None
    #: The ruling's own words and the elements that settle the classification.
    evidence: dict[str, Any] = Field(min_length=1)
    #: The case's original context: at least ``deploy`` and ``prompt``.
    context: dict[str, Any]
    #: Who drafted it: a model and its version, or a person.
    annotator: str

    model_config = ConfigDict(extra="forbid")


class AnnotationReviewRequest(BaseModel):
    note: str = ""

    model_config = ConfigDict(extra="forbid")
