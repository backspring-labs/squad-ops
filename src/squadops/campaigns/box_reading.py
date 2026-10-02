"""What the quiet-box check reads (SIP-0109 §9.3; #1802).

``box.py`` decides; this reads. The declared models come from the active deploy record (#1720),
and each engine's resident models from its LLM port's ``list_loaded_models``. An engine that
cannot report what it holds is read as unreadable, never as empty: an empty listing would read
as a quiet box.

The GPU's compute processes are not read here. The runtime-api container has no GPU device, so
the check is model-only until it is granted one (§24l).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from squadops.campaigns.box import EngineReading, Model


def declared_models(record: Any) -> tuple[Model, ...]:
    """The models the active deploy record declares, with their digests. ``None`` when no deploy
    has been recorded: nothing is declared, so any resident model makes the box loud."""
    if record is None:
        return ()
    return tuple(Model(m.model, m.digest) for m in record.models)


async def read_engines(engines: Mapping[str, Any]) -> tuple[EngineReading, ...]:
    """Each engine's resident models, by name, through its port. Every engine is read, and a
    failure is that engine's reading, not the caller's exception."""
    from squadops.ports.llm.provider import LLMCapability

    readings: list[EngineReading] = []
    for name, port in engines.items():
        if not port.supports(LLMCapability.LOADED_MODELS):
            readings.append(EngineReading(name, None, "the engine cannot report loaded models"))
            continue
        try:
            loaded = await port.list_loaded_models()
        except Exception as e:  # noqa: BLE001 — an unread engine is a reading, not a crash
            readings.append(EngineReading(name, None, f"{type(e).__name__}: {e}"))
            continue
        readings.append(EngineReading(name, tuple(Model(m.name, m.digest) for m in loaded)))
    return tuple(readings)
