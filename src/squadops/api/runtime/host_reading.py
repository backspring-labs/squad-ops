"""What ``GET /health/host`` reads about the machine the deploy runs on (#2204).

The numbers come from Prometheus, which scrapes the host exporter. Each is one instant query, and
a query that fails or returns nothing reads as ``None``: unknown, never healthy (the quiet-box
rule fails closed the same way). ``/health/*`` is the unauthenticated lane, so this carries
numbers only: no process names, command lines, paths or deploy identifiers.
"""

from __future__ import annotations

from typing import Any

#: Each reading, by the name the payload carries, and the instant query that answers it.
HOST_QUERIES: dict[str, str] = {
    "memory_available_bytes": "node_memory_MemAvailable_bytes",
    "memory_total_bytes": "node_memory_MemTotal_bytes",
    "swap_used_bytes": "node_memory_SwapTotal_bytes - node_memory_SwapFree_bytes",
    # The share of the last five minutes some task was stalled on memory: the early sign of the
    # swap thrash that livelocked the box on 2026-08-29.
    "memory_pressure_stalled_ratio": "rate(node_pressure_memory_stalled_seconds_total[5m])",
    "disk_root_available_bytes": 'node_filesystem_avail_bytes{mountpoint="/"}',
    # The hottest ACPI board zone, the reading the board limits below are for, read as the Spark
    # health dashboard reads it. The NVMe sensor is left out: it has its own limit (85 C), and
    # the zones run 30 C hotter under load.
    "temperature_max_celsius": 'max(node_thermal_zone_temp{type="acpitz"})',
    "load_one_minute": "node_load1",
    # The GPU, from the DCGM exporter. A host without one has no samples: unknown, not idle.
    "gpu_utilization_percent": "max(DCGM_FI_DEV_GPU_UTIL)",
    "gpu_power_watts": "sum(DCGM_FI_DEV_POWER_USAGE)",
    "gpu_temperature_celsius": "max(DCGM_FI_DEV_GPU_TEMP)",
}


#: The board's limits (#2204b). The ACPI zones' only trip point is critical at 104 C, and the
#: kernel does no thermal management below it. The warning leaves 6 C of margin; the Spark ran at
#: 88-89 C for two hours under sustained load (2026-09-06). The Spark health dashboard draws the
#: same two lines, held to these by a test.
BOARD_TEMPERATURE_WARN_CELSIUS = 98.0
BOARD_TEMPERATURE_CRITICAL_CELSIUS = 104.0


def host_verdicts(
    host: dict[str, float | None],
    engines_loaded: list[list[str] | None] | None,
    *,
    memory_floor_before_load: int,
    memory_floor_after_load: int,
    disk_floor: int,
) -> dict[str, dict[str, Any]]:
    """Each reading against the limit the project operates by (#2204b): one rule, here, so the
    console colours what this decides and never re-derives it.

    **Memory** is held to the before-load floor only when every engine was read and none holds a
    model: that is the floor an engine needs to load. Otherwise the after-load floor applies, so
    an unread engine never makes a loaded box look short. A reading that is missing is
    ``unknown``, never ``ok``.
    """
    idle = engines_loaded is not None and all(
        loaded is not None and not loaded for loaded in engines_loaded
    )
    memory_floor = memory_floor_before_load if idle else memory_floor_after_load
    return {
        "memory": {
            **_against_floor(host.get("memory_available_bytes"), memory_floor),
            "floor": "before_load" if idle else "after_load",
        },
        "disk": _against_floor(host.get("disk_root_available_bytes"), disk_floor),
        "board_temperature": {"state": _temperature_state(host.get("temperature_max_celsius"))},
    }


def _against_floor(value: float | None, floor: int) -> dict[str, Any]:
    state = "unknown" if value is None else ("below_floor" if value < floor else "ok")
    return {"state": state, "floor_bytes": floor}


def _temperature_state(celsius: float | None) -> str:
    if celsius is None:
        return "unknown"
    if celsius >= BOARD_TEMPERATURE_CRITICAL_CELSIUS:
        return "critical"
    return "warn" if celsius >= BOARD_TEMPERATURE_WARN_CELSIUS else "ok"


def instant_value(body: Any) -> float | None:
    """The first sample of a Prometheus instant-query response, or ``None`` when it has none."""
    try:
        result = body["data"]["result"]
        return float(result[0]["value"][1]) if result else None
    except (KeyError, IndexError, TypeError, ValueError):
        return None


async def read_host(client: Any, prometheus_url: str) -> dict[str, float | None]:
    """Every reading in ``HOST_QUERIES``, each ``None`` when its query could not answer."""
    readings: dict[str, float | None] = {}
    for name, query in HOST_QUERIES.items():
        try:
            resp = await client.get(f"{prometheus_url}/api/v1/query", params={"query": query})
            readings[name] = instant_value(resp.json()) if resp.status_code == 200 else None
        except Exception:  # noqa: BLE001 — an unreachable source is a reading of unknown
            readings[name] = None
    return readings
