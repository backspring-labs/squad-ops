"""A proposal the supervisor rates and nothing builds (SIP-0109 §11a; §24af; #1804).

§11a: beside the reference increment, "the strategy role also runs a proposal against the same
baseline and objective. That proposal is recorded and rated by the supervisor, not built." The
proposal runs on ``campaign-proposal`` (the proposal workload alone, with no gate), so there is no
gate to rule: a ruling decides what happens next, and nothing happens next here.

So the rating is a typed record beside the change request, not a ruling. Its verdict is the
ruling the supervisor would have made, in the ruling's own three outcomes, and three short
ratings say why: whether the scope fits the objective, whether each criterion can tell the
baseline from the change, and whether the footprint is as small as the change. It is bound to
the change request's ``content_hash``, so a rating of a document other than the one on record is
refused, as a stale ruling is.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

import yaml

#: The artifact a rating is stored as, on the proposal cycle, beside its change request.
PROPOSAL_RATING_ARTIFACT_TYPE = "proposal_rating"
PROPOSAL_RATING_FILENAME = "proposal_rating.yaml"


class RatingVerdict(StrEnum):
    """The ruling the supervisor would have made (§9.2's three outcomes)."""

    WOULD_APPROVE = "would_approve"
    WOULD_RETURN = "would_return"
    WOULD_REJECT = "would_reject"


class RatingDimension(StrEnum):
    """What the supervisor rates, each from 1 (poor) to 3 (sound)."""

    SCOPE_FIT = "scope_fit"
    CRITERIA_DISCRIMINABILITY = "criteria_discriminability"
    FOOTPRINT_SIZE = "footprint_size"


@dataclass(frozen=True)
class Rating:
    score: int
    note: str


@dataclass(frozen=True)
class ProposalRating:
    """One rating of one proposal version, bound to the document the supervisor read."""

    proposal_id: str
    version: int
    content_hash: str
    verdict: RatingVerdict
    reason: str
    ratings: dict[RatingDimension, Rating]
    rated_by: str
    rated_at: datetime

    def __post_init__(self) -> None:
        problems = [
            f"{name} is required"
            for name, value in (
                ("proposal_id", self.proposal_id),
                ("content_hash", self.content_hash),
                ("reason", self.reason),
                ("rated_by", self.rated_by),
            )
            if not str(value or "").strip()
        ]
        missing = [d.value for d in RatingDimension if d not in self.ratings]
        if missing:
            problems.append(f"every dimension is rated; missing {', '.join(missing)}")
        for dimension, rating in self.ratings.items():
            if isinstance(rating.score, bool) or rating.score not in (1, 2, 3):
                problems.append(f"{dimension} scores 1, 2 or 3, not {rating.score!r}")
            if not rating.note.strip():
                problems.append(f"{dimension} carries a note")
        if problems:
            raise ValueError("the rating is incomplete: " + "; ".join(problems))


def rating_from_request(
    body: dict[str, Any], *, change_request: Any, rated_by: str, rated_at: datetime
) -> ProposalRating:
    """The rating a supervisor's request makes of the change request on record.

    Raises:
        ValueError: If the request rates another document than the one on record, names an
            unknown verdict or dimension, or leaves anything unrated (each reason, at once).
    """
    stated = str(body.get("content_hash") or "")
    if stated != change_request.content_hash:
        raise ValueError(
            f"the rating is bound to content_hash {stated!r}, and the proposal on record is "
            f"{change_request.content_hash!r}: rate the document the cycle stored"
        )
    try:
        verdict = RatingVerdict(body.get("verdict"))
    except ValueError as e:
        raise ValueError(
            f"verdict is one of {', '.join(v.value for v in RatingVerdict)}, not "
            f"{body.get('verdict')!r}"
        ) from e
    ratings: dict[RatingDimension, Rating] = {}
    for name, value in (body.get("ratings") or {}).items():
        try:
            dimension = RatingDimension(name)
        except ValueError as e:
            raise ValueError(
                f"{name!r} is not a rating dimension; the dimensions are "
                f"{', '.join(d.value for d in RatingDimension)}"
            ) from e
        value = value if isinstance(value, dict) else {}
        ratings[dimension] = Rating(value.get("score"), str(value.get("note") or ""))
    return ProposalRating(
        proposal_id=change_request.proposal_id,
        version=change_request.version,
        content_hash=change_request.content_hash,
        verdict=verdict,
        reason=str(body.get("reason") or ""),
        ratings=ratings,
        rated_by=rated_by,
        rated_at=rated_at,
    )


def rating_document(rating: ProposalRating) -> str:
    """The rating as the YAML stored beside the change request."""
    return yaml.safe_dump(
        {
            "proposal_id": rating.proposal_id,
            "version": rating.version,
            "content_hash": rating.content_hash,
            "verdict": rating.verdict.value,
            "reason": rating.reason,
            "ratings": {
                d.value: {"score": rating.ratings[d].score, "note": rating.ratings[d].note}
                for d in RatingDimension
            },
            "rated_by": rating.rated_by,
            "rated_at": rating.rated_at.isoformat(),
        },
        sort_keys=False,
        allow_unicode=True,
    )
