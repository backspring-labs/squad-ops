"""The memory declarations: memory disabled (SIP-0110 §0.7; the 2.2 plan's D12), and
``memory_context: none`` (Appendix A §3.7; #2179).

A cycle declares it in its execution config (``memory: disabled``, an override or a request
profile's default; read from the one merge, ``Cycle.resolved_config``), as a fault or a replay is
declared, so it is recognizable from the stored cycle alone. Cycle create refuses any other value
(``preflight.memory_declaration_decision``). A cycle that declares it pins no
snapshot, every authoring seam records a ``memory_disabled`` exposure, and its prompts render as
if memory did not exist. **Its observations are still recorded** (§0.3). The verification-set
driver writes it on every counted regression roll, so an approved lesson never moves the yardstick
unannounced. Appendix A §3.7 names it the ``lessons: disabled`` arm: its unit still pins the project
instructions, so its arms differ only in the lessons.

``memory_context: none`` is the other experiment, named apart. It withholds the project instructions
and the lessons, and keeps the unit's own task instructions and its ordinary inputs. It changes the
task's requirements, so it never reads a lesson's effect: its exposures carry their own disposition.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

#: The ``execution_overrides`` key a cycle declares memory under.
MEMORY_DECLARATION_KEY = "memory"
DISABLED = "disabled"
ENABLED = "enabled"
#: The ``execution_overrides`` key a cycle withholds memory's whole context under (§3.7).
CONTEXT_DECLARATION_KEY = "memory_context"
NONE = "none"

#: The arms a cycle runs under (§3.7), read from its declaration, so a report keeps them apart.
ARM_CONTEXT_NONE = "memory_context: none"
ARM_LESSONS_DISABLED = "lessons: disabled"
ARM_LESSONS_ON = "lessons on"


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


def memory_context_none(config: Mapping[str, Any] | None) -> bool:
    """Whether a cycle's effective config declares ``memory_context: none``. It withholds the
    lessons too, so ``memory: enabled`` beside it is refused, as is any value but ``none``: read
    either way, a typo would run one experiment and record it as the other."""
    value = (config or {}).get(CONTEXT_DECLARATION_KEY)
    if value is None:
        return False
    if str(value).strip().lower() != NONE:
        raise ValueError(f"{CONTEXT_DECLARATION_KEY} is {NONE!r} when declared, not {value!r}")
    if (config or {}).get(MEMORY_DECLARATION_KEY) is not None and not memory_disabled(config):
        raise ValueError(
            f"{CONTEXT_DECLARATION_KEY}: {NONE} withholds the lessons, so "
            f"{MEMORY_DECLARATION_KEY}: {ENABLED} contradicts it"
        )
    return True


def arm_of(config: Mapping[str, Any] | None) -> str:
    """The experiment a cycle's effective config declares: ``memory_context: none``, its own;
    ``lessons: disabled``, the lesson comparison's control; or lessons on. Read from the
    declaration, never from what recall answered, so a cycle whose every recall failed still
    reports the arm it was created under."""
    if memory_context_none(config):
        return ARM_CONTEXT_NONE
    return ARM_LESSONS_DISABLED if memory_disabled(config) else ARM_LESSONS_ON
