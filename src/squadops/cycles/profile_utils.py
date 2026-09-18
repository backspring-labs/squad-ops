"""Squad profile validation utilities (SIP-0075 §1.3)."""

from __future__ import annotations

import re

from squadops.cycles.models import (
    ALLOWED_CONFIG_OVERRIDE_KEYS,
    ProfileValidationError,
)
from squadops.llm.models import REASONING_LEVELS

# Profile ID constraints.
_PROFILE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9\-]{0,62}[a-z0-9]$")
_PROFILE_ID_MAX_LEN = 64


def slugify_profile_name(name: str) -> str:
    """Convert a profile name to a URL-safe slug for use as profile_id.

    Rules: lowercase, non-alphanumeric runs become single hyphens,
    leading/trailing hyphens stripped, max 64 chars.
    """
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    slug = slug[:_PROFILE_ID_MAX_LEN]
    slug = slug.rstrip("-")
    if not slug:
        raise ProfileValidationError(f"Cannot slugify name to valid profile_id: {name!r}")
    return slug


def validate_profile_id(profile_id: str) -> None:
    """Raise ProfileValidationError if profile_id is invalid."""
    if not profile_id:
        raise ProfileValidationError("profile_id must not be empty")
    if len(profile_id) > _PROFILE_ID_MAX_LEN:
        raise ProfileValidationError(
            f"profile_id exceeds {_PROFILE_ID_MAX_LEN} characters: {profile_id!r}"
        )
    if not _PROFILE_ID_PATTERN.match(profile_id):
        raise ProfileValidationError(
            f"profile_id must be lowercase alphanumeric with hyphens: {profile_id!r}"
        )


def validate_config_overrides(overrides: dict) -> list[str]:
    """Return list of unknown keys in config_overrides."""
    return sorted(set(overrides.keys()) - ALLOWED_CONFIG_OVERRIDE_KEYS)


def validate_reasoning_override(overrides: dict) -> list[str]:
    """Errors for a ``reasoning`` override whose value is not a ReasoningLevel (#927).

    Checked here, at the profile boundary, because nothing downstream re-checks
    it: a misspelt level would reach the adapter and be sent as "reasoning on".
    """
    if "reasoning" not in overrides:
        return []
    level = overrides["reasoning"]
    if level in REASONING_LEVELS:
        return []
    return [
        f"config_overrides.reasoning must be one of {', '.join(sorted(REASONING_LEVELS))}; "
        f"got {level!r}"
    ]


def validate_agent_entries(agents: list[dict]) -> list[str]:
    """Validate agent entries, returning a list of error messages.

    Checks: non-empty agent_id, non-empty model, no duplicate agent_ids, a non-empty
    ``serves_roles`` on every enabled agent, and no role served by two enabled agents.

    The last two are what make the declared role → agent map a map (SIP-0108 §10i item 1):
    an agent that declares nothing assigns nothing, and two enabled agents answering for one
    role has no defined winner — the resolver would silently take whichever the profile
    listed first. A disabled agent declares nothing and is exempt, so a profile may keep a
    retired member beside the agent that replaced it.
    """
    errors: list[str] = []
    seen_ids: set[str] = set()
    role_owner: dict[str, str] = {}

    for i, agent in enumerate(agents):
        agent_id = agent.get("agent_id", "")
        if not agent_id or not agent_id.strip():
            errors.append(f"agents[{i}]: agent_id must not be empty")
        elif agent_id in seen_ids:
            errors.append(f"agents[{i}]: duplicate agent_id {agent_id!r}")
        else:
            seen_ids.add(agent_id)

        model = agent.get("model", "")
        if not model or not model.strip():
            errors.append(f"agents[{i}]: model must not be empty")

        overrides = agent.get("config_overrides", {})
        unknown = validate_config_overrides(overrides)
        if unknown:
            errors.append(f"agents[{i}]: unknown config_overrides keys: {', '.join(unknown)}")
        errors.extend(f"agents[{i}]: {e}" for e in validate_reasoning_override(overrides))

        if agent.get("enabled", True):
            declared = tuple(agent.get("serves_roles") or ())
            if not declared:
                errors.append(
                    f"agents[{i}]: `serves_roles` must declare at least one role — for an "
                    f"agent that serves only its own role write [{agent.get('role', '')}]"
                )
            for role in declared:
                if not role or not role.strip():
                    errors.append(f"agents[{i}]: role must not be empty")
                elif role in role_owner:
                    errors.append(
                        f"agents[{i}]: role {role!r} is already served by "
                        f"{role_owner[role]!r} — a role resolves to exactly one agent"
                    )
                else:
                    role_owner[role] = agent_id

    return errors
