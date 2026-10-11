"""What ``GET /health/host`` reads from Prometheus (#2204)."""

from __future__ import annotations

import pytest

from squadops.api.runtime.host_reading import HOST_QUERIES, instant_value, read_host


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
