"""The memory-disabled declaration (SIP-0110 §0.7; the 2.2 plan's D12).

A cycle declares it in its execution config (``memory: disabled``, an override or a request
profile's default; read from the one merge, ``Cycle.resolved_config``), as a fault or a replay is
declared, so it is recognizable from the stored cycle alone. Cycle create refuses any other value
(``preflight.memory_declaration_decision``). A cycle that declares it pins no
snapshot, every authoring seam records a ``memory_disabled`` exposure, and its prompts render as
if memory did not exist. **Its observations are still recorded** (§0.3). The verification-set
driver writes it on every counted regression roll, so an approved lesson never moves the yardstick
unannounced.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

#: The ``execution_overrides`` key a cycle declares memory under.
MEMORY_DECLARATION_KEY = "memory"
DISABLED = "disabled"
ENABLED = "enabled"


def memory_disabled(config: Mapping[str, Any] | None) -> bool:
    """Whether a cycle's effective config declares memory disabled. An unknown value is refused
    rather than read either way: a typo must not silently hand a counted roll its lessons."""
    value = (config or {}).get(MEMORY_DECLARATION_KEY)
    if value is None:
        return False
    text = str(value).strip().lower()
    if text == DISABLED:
        return True
    if text == ENABLED:
        return False
    raise ValueError(f"{MEMORY_DECLARATION_KEY} must be {DISABLED!r} or {ENABLED!r}, not {value!r}")
