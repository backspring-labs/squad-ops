"""What the quiet-box check reads (SIP-0109 §9.3; #1802).

``box.py`` decides; this reads. The declared models come from the active deploy record (#1720),
and each engine's resident models from its LLM port's ``list_loaded_models``, with the requests
it is serving where it reports them (``requests_in_flight``, SIP-0111 §5.5). An engine that
cannot report what it holds is read as unreadable, never as empty: an empty listing would read
as a quiet box.

The GPU's compute processes are not read here. The runtime-api container has no GPU device, so
the check is model-only until it is granted one (§24l).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from squadops.campaigns.box import (
    BoxLease,
    EngineReading,
    LaunchVerdict,
    Model,
    Quietness,
    box_quietness,
    launch_verdict,
)
from squadops.cycles.models import CycleStatus, RunStatus
from squadops.ports.llm.provider import LLMCapability


def declared_models(record: Any) -> tuple[Model, ...]:
    """The models the active deploy record declares, with their digests. ``None`` when no deploy
    has been recorded: nothing is declared, so any resident model makes the box loud."""
    if record is None:
        return ()
    return tuple(Model(m.model, m.digest) for m in record.models)


async def read_engines(engines: Mapping[str, Any]) -> tuple[EngineReading, ...]:
    """Each engine's resident models, by name, through its port. Every engine is read, and a
    failure is that engine's reading, not the caller's exception."""

    readings: list[EngineReading] = []
    for name, port in engines.items():
        if not port.supports(LLMCapability.LOADED_MODELS):
            readings.append(EngineReading(name, None, "the engine cannot report loaded models"))
            continue
        try:
            loaded = await port.list_loaded_models()
            # SIP-0111 §5.5: the count is read on the engine's authenticated source, so an engine
            # that refuses the key is unread, never quiet. A busy engine is still quiet (§24cu).
            in_flight = (
                await port.requests_in_flight()
                if port.supports(LLMCapability.REQUESTS_IN_FLIGHT)
                else None
            )
        except Exception as e:  # noqa: BLE001 — an unread engine is a reading, not a crash
            readings.append(EngineReading(name, None, f"{type(e).__name__}: {e}"))
            continue
        readings.append(
            EngineReading(name, tuple(Model(m.name, m.digest) for m in loaded), in_flight=in_flight)
        )
    return tuple(readings)


@dataclass(frozen=True)
class BoxSnapshot:
    """The box as one read saw it: its lease, each engine's reading, and whether it is quiet."""

    lease: BoxLease | None
    readings: tuple[EngineReading, ...]
    quietness: Quietness


class BoxReader:
    """The box as the runtime reads it (§9.3; #1802): its lease, whether it is quiet against the
    active deploy record, and the runs in flight on it. Every launch path asks it, and every
    lease change reads its runs, so the guarantee has one reader."""

    def __init__(
        self,
        *,
        campaigns: Any,
        deploy_registry: Any,
        engines: Mapping[str, Any],
        project_registry: Any,
        cycle_registry: Any,
    ) -> None:
        self._campaigns = campaigns
        self._deploy_registry = deploy_registry
        self._engines = dict(engines)
        self._projects = project_registry
        self._cycles = cycle_registry

    async def snapshot(self) -> BoxSnapshot:
        """The lease read first, then every engine, then the quietness they give."""
        lease = await self._campaigns.box_lease()
        declared = declared_models(await self._deploy_registry.latest())
        readings = await read_engines(self._engines)
        return BoxSnapshot(lease, readings, box_quietness(declared, readings))

    async def verdict(self) -> LaunchVerdict:
        """Whether a cycle may launch now: the lease read first, then every engine."""
        snap = await self.snapshot()
        return launch_verdict(snap.lease, snap.quietness, datetime.now(UTC))

    async def runs_in_flight(self) -> tuple[str, ...]:
        """Every run executing on the box now, by id. A run waiting at a gate or queued to start
        is not in flight: a queued run's start waits on the lease."""

        running: list[str] = []
        for project in await self._projects.list_projects():
            for cycle in await self._cycles.list_cycles(
                project.project_id, status=CycleStatus.ACTIVE, limit=500
            ):
                running.extend(
                    r.run_id
                    for r in await self._cycles.list_runs(cycle.cycle_id)
                    if r.status == RunStatus.RUNNING.value
                )
        return tuple(running)
