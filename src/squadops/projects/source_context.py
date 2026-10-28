"""A unit's pinned source context (SIP-0112 contract 1, FR-04, FR-09, §D.3; E.4.3).

A Cycle of an external product pins, before it is dispatched, what it develops from:
- the Project Record's version and the Development Configuration revision;
- the authoritative repository;
- the development baseline commit and the last integrated-upstream commit;
- the commit its tree is seeded from, and where that pin came from (H.4's increment pin,
  SIP-0109 §24cd point 1): the Project's baseline, or for a repository-backed Campaign's
  increment the head of its campaign branch, with the verification that made that head.

It is resolved from the registry's record, never from text a caller supplies. A caller may state
the commit it expects (a source precondition), and a stale one is refused rather than silently
moved past. The pinned context is the shape the shared fixture records, and it never changes
for the unit that pinned it; a newer revision applies to the next unit (§B.5.1).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

SOURCE_CONTEXT_SCHEMA = "project-source-context/v1"
#: Where a unit's tree is pinned. ``development_baseline_commit`` keeps meaning the Project's
#: baseline whichever it is: H.2's gate keys a sync's findings on it.
PROJECT_BASELINE, CAMPAIGN_BRANCH = "project_baseline", "campaign_branch"
PINNED_FROM = (PROJECT_BASELINE, CAMPAIGN_BRANCH)
_SCHEMA_MAJOR = re.compile(r"^project-source-context/v(\d+)$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")


class SourceContextInvalid(ValueError):
    pass


@dataclass(frozen=True)
class ProjectSourceContext:
    project_id: str
    record_version: int
    development_configuration_revision: int
    repo_uri: str
    development_baseline_commit: str
    integrated_upstream_commit: str | None
    #: The commit the unit's tree is seeded from, verified against and captured on.
    pinned_commit: str
    pinned_from: str
    #: A ``campaign_branch`` pin's regression baseline: the source verification of the increment
    #: whose promotion made the head (SIP-0109 §24bv point 3). ``None`` at the Project's
    #: baseline, and at the calibration record's commit, whose baseline is its inherited one.
    previous_verification_ref: str | None

    def to_document(self) -> dict[str, Any]:
        return {
            "schema": SOURCE_CONTEXT_SCHEMA,
            "project_id": self.project_id,
            "record_version": self.record_version,
            "development_configuration_revision": self.development_configuration_revision,
            "repo_uri": self.repo_uri,
            "development_baseline_commit": self.development_baseline_commit,
            "integrated_upstream_commit": self.integrated_upstream_commit,
            "pinned_commit": self.pinned_commit,
            "pinned_from": self.pinned_from,
            "previous_verification_ref": self.previous_verification_ref,
        }


def parse_source_context(doc: Mapping[str, Any]) -> ProjectSourceContext:
    """A pinned source context, as stored. An unknown major version is refused before anything
    else is read, and a missing field is refused rather than defaulted (contract 1).

    The pin's three fields were added to v1 for 2.5 (H.4). A context stored before them has
    none, and every unit that stored one was pinned at its Project's baseline, so that is what
    it reads as. Once any of the three is present, all three are required."""
    schema = doc.get("schema")
    match = _SCHEMA_MAJOR.match(schema) if isinstance(schema, str) else None
    if match is None or match.group(1) != "1":
        raise SourceContextInvalid(f"schema {schema!r} is not a source context this reads")
    for key in (
        "project_id",
        "record_version",
        "development_configuration_revision",
        "repo_uri",
        "development_baseline_commit",
        "integrated_upstream_commit",
    ):
        if key not in doc:
            raise SourceContextInvalid(f"{key} is required (it may be null only where stated)")
    baseline = doc["development_baseline_commit"]
    upstream = doc["integrated_upstream_commit"]
    if not (isinstance(baseline, str) and _COMMIT.match(baseline)):
        raise SourceContextInvalid("development_baseline_commit is a Git commit")
    if upstream is not None and not (isinstance(upstream, str) and _COMMIT.match(upstream)):
        raise SourceContextInvalid("integrated_upstream_commit is a Git commit, or null")
    pinned, pinned_from, previous = _pin(doc, baseline)
    return ProjectSourceContext(
        project_id=doc["project_id"],
        record_version=doc["record_version"],
        development_configuration_revision=doc["development_configuration_revision"],
        repo_uri=doc["repo_uri"],
        development_baseline_commit=baseline,
        integrated_upstream_commit=upstream,
        pinned_commit=pinned,
        pinned_from=pinned_from,
        previous_verification_ref=previous,
    )


_PIN_KEYS = ("pinned_commit", "pinned_from", "previous_verification_ref")


def _pin(doc: Mapping[str, Any], baseline: str) -> tuple[str, str, str | None]:
    if not any(key in doc for key in _PIN_KEYS):
        return baseline, PROJECT_BASELINE, None
    for key in _PIN_KEYS:
        if key not in doc:
            raise SourceContextInvalid(f"{key} is required beside the pin's other fields")
    pinned, pinned_from, previous = (doc[k] for k in _PIN_KEYS)
    if not (isinstance(pinned, str) and _COMMIT.match(pinned)):
        raise SourceContextInvalid("pinned_commit is a Git commit")
    if pinned_from not in PINNED_FROM:
        raise SourceContextInvalid(f"pinned_from is one of {', '.join(PINNED_FROM)}")
    if pinned_from == PROJECT_BASELINE and (pinned != baseline or previous is not None):
        raise SourceContextInvalid(
            "a project_baseline pin is the development baseline commit, with no previous "
            "verification"
        )
    if previous is not None and not (isinstance(previous, str) and previous):
        raise SourceContextInvalid("previous_verification_ref is an artifact id, or null")
    return pinned, pinned_from, previous


def is_commit(value: str) -> bool:
    return bool(_COMMIT.match(value))
