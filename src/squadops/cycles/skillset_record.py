"""The skillset record a cycle is created with (SIP-0116 §10).

One record says what the cycle's work required and what the squad's agents supplied: the base
set, the squad, the development profile, the requirements checked, the agent each was assigned
to, and the content loaded. It is stored with the cycle beside ``squad_profile_snapshot_ref``
(Q57) and holds enough to read the assignment later without today's files.

``assignment`` and ``offered`` come from the coverage check (``skillset_coverage``), which
cycle preflight has already passed by the time a record is built: each requirement, the agent
it routed to and the skillset that agent supplied, and the contracts those skillsets put in
front of the planner. ``content`` is empty until the skill loader is built. Every development
profile requires nothing today, so every record's requirements, assignment and offered
contracts are empty too.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from typing import Any

from squadops.capabilities.capability_contracts import CapabilityContractDeclaration
from squadops.capabilities.skillsets import Skillset
from squadops.core.hashing import canonical_sha256
from squadops.cycles.models import SquadProfile
from squadops.cycles.skillset_coverage import cycle_coverage
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
    profile: SquadProfile,
    roster_hash: str,
    resolved_config: Mapping[str, Any],
    catalog: Mapping[str, Skillset],
    contracts: Mapping[str, CapabilityContractDeclaration] | None = None,
) -> dict[str, Any]:
    """The record for a cycle created now, under ``profile`` and ``resolved_config``, with the
    skillsets ``catalog`` holds."""
    name = effective_development_profile(resolved_config)
    development = get_development_profile(name)
    coverage = cycle_coverage(profile, resolved_config, catalog, contracts)
    if not coverage.covered:
        # Cycle preflight refuses an uncovered cycle before anything is built. A record
        # written anyway would hold requirements beside an empty assignment, and read later
        # as a cycle that ran with its work covered.
        raise ValueError(
            "a skillset record is written only for a cycle whose requirements are covered: "
            + " ".join(f.message for f in coverage.findings)
        )
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
        "assignment": [dataclasses.asdict(a) for a in coverage.assignments],
        "offered": [
            {**dataclasses.asdict(o), "task_type": o.task_type.value} for o in coverage.offered
        ],
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
