"""A unit's pinned source context (SIP-0112 contract 1, FR-04, FR-09, §D.3; E.4.3).

A Cycle of an external product pins, before it is dispatched, what it develops from:
- the Project Record's version and the Development Configuration revision;
- the authoritative repository;
- the development baseline commit and the last integrated-upstream commit.

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

    def to_document(self) -> dict[str, Any]:
        return {
            "schema": SOURCE_CONTEXT_SCHEMA,
            "project_id": self.project_id,
            "record_version": self.record_version,
            "development_configuration_revision": self.development_configuration_revision,
            "repo_uri": self.repo_uri,
            "development_baseline_commit": self.development_baseline_commit,
            "integrated_upstream_commit": self.integrated_upstream_commit,
        }


def parse_source_context(doc: Mapping[str, Any]) -> ProjectSourceContext:
    """A pinned source context, as stored. An unknown major version is refused before anything
    else is read, and a missing field is refused rather than defaulted (contract 1)."""
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
    return ProjectSourceContext(
        project_id=doc["project_id"],
        record_version=doc["record_version"],
        development_configuration_revision=doc["development_configuration_revision"],
        repo_uri=doc["repo_uri"],
        development_baseline_commit=baseline,
        integrated_upstream_commit=upstream,
    )


def is_commit(value: str) -> bool:
    return bool(_COMMIT.match(value))
