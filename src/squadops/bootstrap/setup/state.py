"""Bootstrap state file management (SIP-0081).

Written only by the Python CLI (R3). State is informational —
doctor always re-checks live state.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

_STATE_DIR = Path(".squadops") / "bootstrap"


@dataclass
class BootstrapState:
    """Persisted bootstrap run metadata."""

    profile: str
    schema_version: int
    last_run: str  # ISO timestamp
    steps_completed: list[str] = field(default_factory=list)
    detected_versions: dict[str, str] = field(default_factory=dict)
    doctor_summary: dict[str, int] = field(default_factory=dict)


def write_state(state: BootstrapState, *, state_dir: Path | None = None) -> Path:
    """Write bootstrap state to disk.

    Args:
        state: The state to persist.
        state_dir: Override state directory (for testing).

    Returns:
        Path to the written state file.
    """
    base = state_dir or _STATE_DIR
    base.mkdir(parents=True, exist_ok=True)
    path = base / f"{state.profile}.json"
    path.write_text(json.dumps(asdict(state), indent=2))
    return path


def read_state(profile: str, *, state_dir: Path | None = None) -> BootstrapState | None:
    """Read bootstrap state from disk.

    Args:
        profile: Profile name to read state for.
        state_dir: Override state directory (for testing).

    Returns:
        BootstrapState if file exists and is valid, None otherwise.
    """
    base = state_dir or _STATE_DIR
    path = base / f"{profile}.json"
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text())
        return BootstrapState(
            profile=raw["profile"],
            schema_version=raw["schema_version"],
            last_run=raw["last_run"],
            steps_completed=raw.get("steps_completed", []),
            detected_versions=raw.get("detected_versions", {}),
            doctor_summary=raw.get("doctor_summary", {}),
        )
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        logger.warning("Corrupt bootstrap state at %s: %s", path, exc)
        return None
