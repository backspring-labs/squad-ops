"""``scripts/dev/studio_worker_proof.py``: the settings it builds the worker from, and its queueing.

What bugs would these catch?
- #3282: since R5.30 the registry refuses an operation whose origin names no owner, and the proof
  queued its rounds with ``{"requested_by": …}``, so on main it raised before its first round.
- #3193: the proof built its runner from the worker's required settings alone, so a worker its
  owner had declared dedicated ran here as one that wasn't (read live on 2026-11-26: the play was
  refused ``not_dedicated`` with all four settings written).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from adapters.remote_execution.game_dev_roblox_studio import worker as studio_worker
from adapters.remote_execution.game_dev_roblox_studio.front import SETTINGS as FRONT_SETTINGS
from adapters.remote_execution.memory_worker_registry_store import MemoryWorkerRegistryStore
from squadops.remote_execution.registry import WorkerRegistry
from tests.unit.remote_execution.registry_contract import Clock, request

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "dev" / "studio_worker_proof.py"
_spec = importlib.util.spec_from_file_location("studio_worker_proof", _SCRIPT)
proof = importlib.util.module_from_spec(_spec)
sys.modules["studio_worker_proof"] = proof
_spec.loader.exec_module(proof)

PREFIX = "SQUADOPS__WORKER__"
REQUIRED = {PREFIX + name.upper(): f"/the/{name}" for name in studio_worker.SETTINGS}
DECLARED = {
    PREFIX + "ROBLOX_STUDIO_DEDICATED": "true",
    PREFIX + "ROBLOX_STUDIO_WINDOW_START": "2026-11-26T22:00:00-05:00",
    PREFIX + "ROBLOX_STUDIO_WINDOW_END": "2026-11-26T23:00:00-05:00",
    PREFIX + "ROBLOX_STUDIO_IDLE_THRESHOLD_S": "60",
}


def test_a_dedicated_workers_four_settings_reach_the_runner_as_they_do_on_the_worker():
    settings = proof.worker_settings({**REQUIRED, **DECLARED, "UNRELATED": "x"})

    assert {name: settings[name] for name in FRONT_SETTINGS} == {
        "roblox_studio_dedicated": "true",
        "roblox_studio_window_start": "2026-11-26T22:00:00-05:00",
        "roblox_studio_window_end": "2026-11-26T23:00:00-05:00",
        "roblox_studio_idle_threshold_s": "60",
    }
    assert set(settings) == set(studio_worker.SETTINGS) | set(FRONT_SETTINGS)


def test_an_optional_setting_left_out_is_never_defaulted():
    settings = proof.worker_settings({**REQUIRED, PREFIX + "ROBLOX_STUDIO_DEDICATED": "true"})

    assert set(settings) == set(studio_worker.SETTINGS) | {"roblox_studio_dedicated"}


async def test_a_round_is_queued_under_an_owner_the_registry_reads(capsys):
    """Entered at the proof's own ``_round``, over the real registry. With no worker registered
    the round isn't queued, by the registry's ordinary answer: on main it raised first
    (``ValueError: the origin names no cycle_id``)."""
    registry = WorkerRegistry(MemoryWorkerRegistryStore(), clock=Clock())

    queued = await proof._round(registry, request())

    assert queued is False
    assert "not queued: NoWorker" in capsys.readouterr().out
