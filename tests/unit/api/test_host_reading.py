"""What ``GET /health/host`` reads from Prometheus (#2204)."""

from __future__ import annotations

import pytest

from squadops.api.runtime.host_reading import (
    BOARD_TEMPERATURE_CRITICAL_CELSIUS,
    BOARD_TEMPERATURE_WARN_CELSIUS,
    HOST_QUERIES,
    host_verdicts,
    instant_value,
    read_host,
)


class _Resp:
    def __init__(self, status: int, body: object) -> None:
        self.status_code = status
        self._body = body

    def json(self) -> object:
        return self._body


class _Prometheus:
    """A Prometheus that answers each query from a table, or fails it."""

    def __init__(self, answers: dict[str, object], *, down: bool = False) -> None:
        self.answers = answers
        self.down = down
        self.queries: list[str] = []

    async def get(self, url, params=None):
        if self.down:
            raise ConnectionError("prometheus unreachable")
        query = params["query"]
        self.queries.append(query)
        value = self.answers.get(query)
        result = [] if value is None else [{"metric": {}, "value": [0, str(value)]}]
        return _Resp(200, {"status": "success", "data": {"result": result}})


async def test_every_reading_is_one_query_answered_by_its_first_sample():
    """Bug caught: a reading bound to the wrong query, so the panel showed swap as memory."""
    prometheus = _Prometheus({HOST_QUERIES["memory_available_bytes"]: 115932524544})

    readings = await read_host(prometheus, "http://prometheus:9090")

    assert set(readings) == set(HOST_QUERIES)
    assert readings["memory_available_bytes"] == 115932524544.0
    assert readings["swap_used_bytes"] is None  # no sample: unknown, not zero
    assert prometheus.queries == list(HOST_QUERIES.values())


async def test_an_unreachable_prometheus_reads_every_number_as_unknown():
    """Bug caught: a down source reported as an empty, healthy host (the quiet-box rule fails
    closed the same way)."""
    readings = await read_host(_Prometheus({}, down=True), "http://prometheus:9090")

    assert readings == {name: None for name in HOST_QUERIES}


@pytest.mark.parametrize(
    "body",
    [
        {"data": {"result": []}},
        {"error": "bad query"},
        None,
        {"data": {"result": [{"value": [0, "x"]}]}},
    ],
)
def test_a_response_without_a_numeric_sample_is_unknown(body):
    assert instant_value(body) is None


# --------------------------------------------------------------------------- #2204b: the verdicts

_FLOORS = {
    "memory_floor_before_load": 90 * 2**30,
    "memory_floor_after_load": 16 * 2**30,
    "disk_floor": 150 * 10**9,
}


@pytest.mark.parametrize(
    ("available", "engines", "state", "floor"),
    [
        (17 * 2**30, [["qwen3.8:27b"]], "ok", "after_load"),
        (16 * 2**30 - 1, [["qwen3.8:27b"]], "below_floor", "after_load"),
        (16 * 2**30, [["qwen3.8:27b"]], "ok", "after_load"),  # the floor itself is enough
        (89 * 2**30, [[]], "below_floor", "before_load"),  # nothing loaded: room to load one
        (91 * 2**30, [[], []], "ok", "before_load"),
        (60 * 2**30, [[], None], "ok", "after_load"),  # an unread engine may hold a model
        (60 * 2**30, None, "ok", "after_load"),  # the box unread
        (None, [["m"]], "unknown", "after_load"),
    ],
)
def test_memory_is_held_to_the_floor_the_box_is_at(available, engines, state, floor):
    """Bugs caught: an idle box with 60 GiB free shown as healthy, when no engine could load on
    it; a loaded box shown short against the before-load floor; an unread value shown as ok."""
    verdicts = host_verdicts({"memory_available_bytes": available}, engines, **_FLOORS)
    assert verdicts["memory"] == {
        "state": state,
        "floor_bytes": _FLOORS[f"memory_floor_{floor}"],
        "floor": floor,
    }


@pytest.mark.parametrize(
    ("celsius", "disk", "temperature_state", "disk_state"),
    [
        (88.6, 324e9, "ok", "ok"),
        (98.0, 150e9, "warn", "ok"),
        (103.9, 149.9e9, "warn", "below_floor"),
        (104.0, None, "critical", "unknown"),
        (None, 150e9, "unknown", "ok"),
    ],
)
def test_the_board_and_the_disk_change_state_at_the_documented_values(
    celsius, disk, temperature_state, disk_state
):
    verdicts = host_verdicts(
        {"temperature_max_celsius": celsius, "disk_root_available_bytes": disk}, [[]], **_FLOORS
    )
    assert verdicts["board_temperature"] == {"state": temperature_state}
    assert verdicts["disk"] == {"state": disk_state, "floor_bytes": 150 * 10**9}


def test_the_spark_dashboard_draws_the_limits_the_api_decides_by():
    """Bug caught: the panel and the dashboard's lines disagreeing about a limit. The dashboard
    drew the disk floor at 150 GiB while the API held it at 150 GB (#2204b)."""
    import json
    from pathlib import Path

    from squadops.campaigns.box import DISK_FLOOR_BYTES, MEMORY_FLOOR_AFTER_LOAD_BYTES

    dashboard = Path(__file__).resolve().parents[3] / (
        "infra/grafana/dashboards/Spark/spark-health.json"
    )
    panels = json.loads(dashboard.read_text(encoding="utf-8"))["panels"]

    def steps(title: str) -> list[set[float]]:
        return [
            {s["value"] for s in p["fieldConfig"]["defaults"]["thresholds"]["steps"]} - {None}
            for p in panels
            if p.get("title") == title
        ]

    assert steps("Memory available") == [{MEMORY_FLOOR_AFTER_LOAD_BYTES}] * 2
    assert steps("Free disk on /") == steps("Free disk on / (host root)") == [{DISK_FLOOR_BYTES}]
    board = {BOARD_TEMPERATURE_WARN_CELSIUS, BOARD_TEMPERATURE_CRITICAL_CELSIUS}
    assert steps("Hottest board zone") == steps("Board thermal zones (ACPI)") == [board]
