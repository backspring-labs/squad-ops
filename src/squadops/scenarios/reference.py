"""The reference to an evaluation run that SIP-0112's Project history stores (SIP-0113 §4.8;
SIP-0112 §8.2.1; shared contract 5; #2415).

This module holds the reference and its reader and nothing an evaluation found: no outcome, no
result, no scenario. Project history imports this module alone, so no result can reach the
handoff through it (contract 5's phase-1 rule). It imports only the standard library
(``test_contract5_evaluation_reference.py`` holds that).

Its reader refuses an unknown schema major version with a typed error and reads none of it, and
refuses a reference with a field absent, a nullable one included.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

REF_SCHEMA = "outcome-evaluation-ref/v1"
_REF_FAMILY = "outcome-evaluation-ref/"
_IDENTITY = re.compile(r"[0-9a-f]{64}")


class EvaluationInvalid(ValueError):
    """A record or a reference whose content can't be held as given."""


class UnknownSchemaMajor(EvaluationInvalid):
    """A reference under a schema major version this reader doesn't know (SIP-0112 §8.2.1)."""


@dataclass(frozen=True)
class OutcomeEvaluationRef:
    """The reference SIP-0112's Project history stores (contract 5). ``evaluation_id`` is opaque
    to every reader. ``campaign_id`` is null only outside a campaign, never absent."""

    evaluation_id: str
    suite_digest: str
    project_id: str
    campaign_id: str | None
    cycle_id: str
    evaluated_tree_identity: str
    previous_accepted_tree_identity: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": REF_SCHEMA,
            "evaluation_id": self.evaluation_id,
            "suite_digest": self.suite_digest,
            "project_id": self.project_id,
            "campaign_id": self.campaign_id,
            "cycle_id": self.cycle_id,
            "evaluated_tree_identity": self.evaluated_tree_identity,
            "previous_accepted_tree_identity": self.previous_accepted_tree_identity,
        }


_REQUIRED_TEXT = ("evaluation_id", "project_id", "cycle_id")
_IDENTITIES = ("suite_digest", "evaluated_tree_identity")
_NULLABLE = ("campaign_id", "previous_accepted_tree_identity")


def parse_reference(doc: Mapping[str, Any]) -> OutcomeEvaluationRef:
    """Read a stored reference, or refuse it with a typed error, reading none of it."""
    schema = doc.get("schema")
    if not isinstance(schema, str) or not schema.startswith(_REF_FAMILY):
        raise EvaluationInvalid(f"not an outcome evaluation reference: schema {schema!r}")
    if schema != REF_SCHEMA:
        raise UnknownSchemaMajor(f"{schema!r} is not a major version this reader knows")
    absent = [k for k in (*_REQUIRED_TEXT, *_IDENTITIES, *_NULLABLE) if k not in doc]
    if absent:
        raise EvaluationInvalid(f"the reference has no {absent}: every field is present")
    for key in _REQUIRED_TEXT:
        if not isinstance(doc[key], str) or not doc[key].strip():
            raise EvaluationInvalid(f"{key} must be non-empty text, got {doc[key]!r}")
    for key in (*_IDENTITIES, "previous_accepted_tree_identity"):
        value = doc[key]
        if value is None and key == "previous_accepted_tree_identity":
            continue
        if not isinstance(value, str) or not _IDENTITY.fullmatch(value):
            raise EvaluationInvalid(f"{key} must be 64 lowercase hex characters, got {value!r}")
    campaign_id = doc["campaign_id"]
    if campaign_id is not None and (not isinstance(campaign_id, str) or not campaign_id.strip()):
        raise EvaluationInvalid(
            f"campaign_id is text in a campaign and null outside one, got {campaign_id!r}"
        )
    return OutcomeEvaluationRef(**{k: doc[k] for k in (*_REQUIRED_TEXT, *_IDENTITIES, *_NULLABLE)})
