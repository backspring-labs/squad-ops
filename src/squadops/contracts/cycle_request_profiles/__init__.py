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

_PROFILES_PACKAGE = "squadops.contracts.cycle_request_profiles.profiles"


def _profiles_dir() -> Path:
    """Resolve the profiles directory via importlib.resources."""
    return resources.files(_PROFILES_PACKAGE)  # type: ignore[return-value]


def list_profiles() -> list[str]:
    """Return sorted list of available profile names (without .yaml extension)."""
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
        raise FileNotFoundError(
            f"CRP profile {name!r} not found. Available: {available}"
        )

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
