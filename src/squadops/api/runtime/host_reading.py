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
    "temperature_max_celsius": "max(node_hwmon_temp_celsius)",
    "load_one_minute": "node_load1",
    # The GPU, from the DCGM exporter. A host without one has no samples: unknown, not idle.
    "gpu_utilization_percent": "max(DCGM_FI_DEV_GPU_UTIL)",
    "gpu_power_watts": "sum(DCGM_FI_DEV_POWER_USAGE)",
    "gpu_temperature_celsius": "max(DCGM_FI_DEV_GPU_TEMP)",
}


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
