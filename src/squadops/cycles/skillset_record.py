"""The skillset record a cycle is created with (SIP-0116 §10).

One record says what the cycle's work required and what the squad's agents supplied: the base
set, the squad, the development profile, the requirements checked, the agent each was assigned
to, and the content loaded. It is stored with the cycle beside ``squad_profile_snapshot_ref``
(Q57) and holds enough to read the assignment later without today's files.

Phase 1 writes the parts that exist before coverage does: the base set, the squad, the
development profile and its declared requirements. ``assignment`` and ``content`` are empty,
and are filled by the coverage check and the skill loader when those are built. Every
development profile requires nothing today, so every record's requirements are empty too.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from typing import Any

from squadops.core.hashing import canonical_sha256
from squadops.cycles.models import SquadProfile
from squadops.stacks.development_profiles import (
    development_profile_fingerprint,
    development_profile_selection_origin,
    effective_development_profile,
    get_development_profile,
)
from squadops.tasks.base_set import BASE_SET_VERSION, base_plannable_task_types

#: The record's schema. The hashing rule is versioned with it: the digest is the SHA-256 of
#: the record's canonical JSON (``squadops.core.hashing``) without its ``digest`` key.
SKILLSET_RECORD_SCHEMA = "squadops.skillset-record/v1"


def skillset_record_digest(record: Mapping[str, Any]) -> str:
    """The digest ``record`` should carry: over everything in it but the digest itself."""
    return canonical_sha256({k: v for k, v in record.items() if k != "digest"})


def build_skillset_record(
    profile: SquadProfile, roster_hash: str, resolved_config: Mapping[str, Any]
) -> dict[str, Any]:
    """The record for a cycle created now, under ``profile`` and ``resolved_config``."""
    name = effective_development_profile(resolved_config)
    development = get_development_profile(name)
    record: dict[str, Any] = {
        "schema": SKILLSET_RECORD_SCHEMA,
        "base_set": {
            "version": BASE_SET_VERSION,
            "plannable": sorted(t.value for t in base_plannable_task_types()),
        },
        "squad": {"profile_id": profile.profile_id, "roster_hash": roster_hash},
        "development_profile": {
            "name": name,
            "origin": development_profile_selection_origin(resolved_config),
            "fingerprint": development_profile_fingerprint(name),
            "platform": (
                dataclasses.asdict(development.platform) if development.platform else None
            ),
        },
        "requirements": [_requirement(entry) for entry in development.requires],
        "assignment": [],
        "content": [],
    }
    record["digest"] = skillset_record_digest(record)
    return record


def _requirement(entry: Any) -> dict[str, Any]:
    """One responsibility's requirement as JSON: lists where the declaration holds tuples."""
    return {
        "role": entry.role,
        "any_of": [
            {
                "skillset": r.skillset,
                "version": r.version,
                "needs": [{"contract": n.contract, "mode": n.mode} for n in r.needs],
            }
            for r in entry.any_of
        ],
    }
