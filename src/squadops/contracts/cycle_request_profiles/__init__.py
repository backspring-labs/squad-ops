"""
CycleRequestProfile loader (SIP-0065 §5).

Loads CRP YAML profiles from the bundled profiles/ directory,
computes override diffs, and provides the canonical merge helper.
"""

from __future__ import annotations

from importlib import resources
from pathlib import Path
from typing import Any

import yaml

from squadops.contracts.cycle_request_profiles.schema import CycleRequestProfile
from squadops.stacks.request_defaults import request_defaults_for

#: The operator's request profiles, one per intent (#316, the taxonomy's R2.4). The stack, pulse
#: checks, multi-role authoring, the correction path and a prior cycle's plan are set at create
#: time, never in a name. ``build``, ``wrapup`` and ``benchmark`` are also old names, and keep their
#: released YAML byte for byte.
OPERATOR_PROFILES = ("smoke", "build", "validate", "implement", "ship", "wrapup", "benchmark")
#: The campaign's own profiles: named by the campaign code, never chosen by an operator, and
#: resolved by SIP-0109's pinned definitions (R2.4, decision 4).
CAMPAIGN_PROFILES = (
    "campaign-reference",
    "campaign-proposal",
    "campaign-increment",
    "campaign-increment-asks",
    # SIP-0112 H.4 point 3 (2.5): a repository-backed Project's increments, with no stack.
    "campaign-increment-source",
)

_PROFILES_PACKAGE = "squadops.contracts.cycle_request_profiles.profiles"


def _profiles_dir() -> Path:
    """Resolve the profiles directory via importlib.resources."""
    return resources.files(_PROFILES_PACKAGE)  # type: ignore[return-value]


def list_profiles() -> list[str]:
    """Every profile name that resolves (without .yaml extension): the operator's, the campaign's,
    and every old name, frozen so a pinned config resolves to what it ran (R2.4). The operator's
    listing is ``OPERATOR_PROFILES``."""
    profiles_dir = _profiles_dir()
    names = []
    for item in profiles_dir.iterdir():  # type: ignore[union-attr]
        if hasattr(item, "name") and item.name.endswith(".yaml"):
            names.append(item.name.removesuffix(".yaml"))
    return sorted(names)


def load_profile(name: str = "default") -> CycleRequestProfile:
    """Load and validate a CRP profile by name.

    Args:
        name: Profile name (without .yaml extension). Defaults to "default".

    Returns:
        Validated CycleRequestProfile.

    Raises:
        FileNotFoundError: If the profile does not exist.
    """
    profiles_dir = _profiles_dir()
    profile_path = profiles_dir / f"{name}.yaml"  # type: ignore[operator]

    if not profile_path.is_file():  # type: ignore[union-attr]
        available = list_profiles()
        raise FileNotFoundError(f"CRP profile {name!r} not found. Available: {available}")

    raw = yaml.safe_load(profile_path.read_text())  # type: ignore[union-attr]
    return CycleRequestProfile(**raw)


def merge_config(defaults: dict, overrides: dict) -> dict:
    """Single canonical merge rule: {**defaults, **overrides}.

    Used by CRP logic, request building, and tests — never inline {**d, **o}.
    This matches compute_config_hash() in lifecycle.py which does the same merge.

    Args:
        defaults: CRP default values.
        overrides: User-supplied override values.

    Returns:
        Merged configuration dict.
    """
    return {**defaults, **overrides}


def compute_overrides(defaults: dict, user_values: dict) -> dict:
    """Compute the explicit delta between user values and CRP defaults.

    Returns ONLY fields where user_values differ from defaults (SIP-0065 §5.3).
    A field whose user-supplied value equals the default MUST NOT appear.
    A field where the user-supplied value differs MUST appear.

    Args:
        defaults: CRP default values.
        user_values: User-supplied values (from --set flags and prompts).

    Returns:
        Dict containing only the fields that differ from defaults.
    """
    overrides: dict[str, Any] = {}
    for key, value in user_values.items():
        if key not in defaults or defaults[key] != value:
            overrides[key] = value
    return overrides


def resolved_defaults(profile_name: str, user_values: dict | None = None) -> dict:
    """A cycle's applied defaults (#316, R2.3). For an operator profile, the stack's request
    defaults sit beneath the profile's own keys, and the caller's overrides sit above both. The
    stack is the one the cycle builds on: the caller's ``build_profile``.

    Every other profile, frozen or the campaign's, gets nothing from a stack. Some declare the
    stack's keys and some don't (``campaign-proposal`` pins its stack and none of them), so this
    is what keeps every old name resolving to exactly what it ran, whatever stack the caller
    passes (R2.4)."""
    crp = load_profile(profile_name)
    if profile_name not in OPERATOR_PROFILES:
        return dict(crp.defaults)
    stack = merge_config(crp.defaults, user_values or {}).get("build_profile")
    return {**request_defaults_for(stack), **crp.defaults}


#: The profile defaults that are top-level fields of a cycle-create request, not config keys.
CRP_BODY_FIELDS = (
    "build_strategy",
    "task_flow_policy",
    "expected_artifact_types",
    "experiment_context",
)


def cycle_request_body(
    profile_name: str,
    *,
    squad_profile_id: str,
    user_values: dict | None = None,
    notes: str | None = None,
    prd_ref: str | None = None,
) -> dict:
    """The cycle-create request a profile and the caller's values make: exactly the body
    ``squadops cycles create`` sends, so a cycle a campaign launches server-side (SIP-0109 §12b)
    is created from the same request an operator's would be."""
    defaults = resolved_defaults(profile_name, user_values)
    merged = merge_config(defaults, user_values or {})
    body: dict[str, Any] = {
        "squad_profile_id": squad_profile_id,
        "applied_defaults": defaults,
        "execution_overrides": compute_overrides(defaults, merged),
        "request_profile": profile_name,
        "notes": notes,
    }
    if prd_ref:
        body["prd_ref"] = prd_ref
    for key in CRP_BODY_FIELDS:
        if key in merged:
            body[key] = merged[key]
    return body
