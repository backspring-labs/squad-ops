"""Reviewed annotations (SIP-0110 §0.4, #2160): how a return classified only in prose enters.

What bugs would these catch? An annotation that counts as a second occurrence of its ruling (§0.2's
invariant: one failure is never two pieces of evidence); one that classifies before anyone reviewed
it; one that rewrites the observation it annotates; a review rewritten after the fact; and an
annotation that loses the case's original context or classifies outside its source's vocabulary.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from adapters.memory.cross_cycle import InMemoryCrossCycleMemoryStore
from squadops.memory.annotation import (
    Annotation,
    AnnotationRefused,
    annotate,
    citable,
    classified_view,
    effective_classification,
    review,
)
from squadops.memory.observations import (
    UNCLASSIFIED,
    VOCABULARY_PROPOSAL,
    Classification,
    Observation,
    ObservationSource,
)
from tests.unit.memory.test_lessons import T0

pytestmark = [pytest.mark.domain_memory]

PROSE = Observation(
    source=ObservationSource.PROPOSAL_RULING,
    source_id="proposal_ruling:cmp_51919765933d:ctl_d1437f79b284",
    project_id="group_run",
    observed_at=T0,
    classification=Classification(
        UNCLASSIFIED, rationale="no classification of this version was recorded"
    ),
    campaign_id="cmp_51919765933d",
    evidence={"notes": "T3 holds because the accepted app has no capacity concept"},
)
CLASSIFIED = Observation(
    source=ObservationSource.PROPOSAL_RULING,
    source_id="proposal_ruling:cmp_c4b81554bd59:ctl_0d94790c5185",
    project_id="group_run",
    observed_at=T0,
    classification=Classification(VOCABULARY_PROPOSAL, ("criteria_not_checkable",)),
    campaign_id="cmp_c4b81554bd59",
)


def _annotate(observation: Observation = PROSE, now=T0, **change) -> Annotation:
    fields = {
        "values": ["criteria_not_checkable"],
        "target_behavior": "criterion_already_satisfied",
        "evidence": {"ruling": "T3 holds", "settled_by": "the manifest declares no capacity"},
        "context": {"deploy": "rebuild 20, before #1947", "prompt": "the proposal block, verbatim"},
        "annotator": "claude-opus-5-5",
        "now": now,
    }
    return annotate(observation, **{**fields, **change})


def test_an_annotation_classifies_only_once_reviewed_and_adds_no_occurrence():
    """§0.4 and §0.2's invariant. Bugs caught: a proposed annotation already making a prose return
    citable; a reviewed one adding the ruling as a second observation; the original observation's
    classification or evidence rewritten by the reading."""
    proposed = _annotate()

    assert effective_classification(PROSE, [proposed]) == PROSE.classification
    assert citable([PROSE, CLASSIFIED], [proposed]) == {CLASSIFIED.source_id}

    reviewed = review(proposed, reviewed_by="owner", now=T0 + timedelta(hours=1))
    view = classified_view([PROSE, CLASSIFIED], [reviewed])

    assert [o.source_id for o in view] == [PROSE.source_id, CLASSIFIED.source_id]
    assert view[0].classification == Classification(
        VOCABULARY_PROPOSAL, ("criteria_not_checkable",)
    )
    assert (view[0].evidence, view[0].observed_at) == (PROSE.evidence, PROSE.observed_at)
    assert PROSE.classification.vocabulary == UNCLASSIFIED
    assert citable([PROSE, CLASSIFIED], [reviewed]) == {PROSE.source_id, CLASSIFIED.source_id}


@pytest.mark.parametrize(
    ("change", "match"),
    [
        ({"values": []}, "an annotation classifies"),
        ({"values": ["made_up_class"]}, "not among"),
        ({"evidence": {}}, "evidence"),
        ({"context": {"deploy": "rebuild 20"}}, "names no prompt"),
        ({"annotator": "  "}, "who drafted"),
    ],
    ids=["no class", "outside the vocabulary", "no evidence", "no prompt context", "no annotator"],
)
def test_an_annotation_without_its_class_evidence_or_context_is_refused(change, match):
    """Bug caught: a classification entered with nothing a reader could check it against, or one
    in a vocabulary its source does not use."""
    with pytest.raises(AnnotationRefused, match=match):
        _annotate(**change)


def test_a_review_stands_and_the_latest_reviewed_annotation_is_read():
    """Bugs caught: a second review rewriting who reviewed it; a later, unreviewed annotation
    overriding a reviewed one; the stored body losing a field when it is read back."""
    first = review(_annotate(), reviewed_by="owner", now=T0 + timedelta(hours=1))
    with pytest.raises(AnnotationRefused, match="never rewritten"):
        review(first, reviewed_by="someone else", now=T0 + timedelta(hours=2))

    pending = _annotate(values=["ambiguous_manifest_delta"], now=T0 + timedelta(hours=3))
    assert effective_classification(PROSE, [first, pending]).values == ("criteria_not_checkable",)

    later = review(pending, reviewed_by="owner", now=T0 + timedelta(hours=4), note="re-read")
    assert effective_classification(PROSE, [first, later]).values == ("ambiguous_manifest_delta",)
    assert Annotation.from_dict(later.to_dict()) == later


async def test_the_store_keeps_an_annotation_beside_an_observation_it_holds():
    """Bugs caught: an annotation stored for an observation the store never recorded; a second
    write of one annotation adding another; a second review replacing the first."""
    store = InMemoryCrossCycleMemoryStore()
    await store.record_observations([PROSE])
    proposed = _annotate()

    with pytest.raises(KeyError):
        await store.record_annotation(_annotate(CLASSIFIED))
    assert await store.record_annotation(proposed) is True
    assert await store.record_annotation(proposed) is False

    await store.record_annotation_review(review(proposed, reviewed_by="owner", now=T0))
    await store.record_annotation_review(review(proposed, reviewed_by="other", now=T0))

    [held] = await store.list_annotations("group_run")
    assert held.reviewed_by == "owner"
    assert await store.list_observations("group_run") == [PROSE]
