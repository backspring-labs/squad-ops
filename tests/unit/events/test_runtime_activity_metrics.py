"""The runtime's activity reaches its metrics, and the dashboards read what it sets (#2204).

The metrics bridge existed and nothing subscribed it, so the runtime exported no activity at all:
Grafana could not say when a run started or a deploy happened. These enter at the bus factory the
runtime's startup calls, and hold the dashboards to the names the bridge and the runtime set.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

import pytest

from adapters.events.factory import create_cycle_event_bus
from squadops.events.bridges.metrics import _COUNTER_MAP, _MARKER_MAP
from squadops.events.types import EventType

pytestmark = [pytest.mark.domain_events]

_REPO = Path(__file__).resolve().parents[3]
_DASHBOARDS = [
    _REPO / "infra/grafana/dashboards/Spark/spark-health.json",
    _REPO / "infra/grafana/dashboards/Squad/squad-model-calls.json",
]
#: The collector's Prometheus exporter prefixes every metric (infra/otel-collector/config.yaml).
_NAMESPACE = "squadops_"


class _Metrics:
    """A metrics port that keeps what it was told, in order."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def counter(self, name, value=1.0, labels=None):
        self.calls.append(("counter", name, value, labels))

    def gauge(self, name, value, labels=None):
        self.calls.append(("gauge", name, value, labels))

    def histogram(self, name, value, labels=None, **_):
        self.calls.append(("histogram", name, value, labels))


def _bus(metrics: _Metrics):
    return create_cycle_event_bus(
        "in_process", source_service="runtime-api", source_version="t", metrics=metrics
    )


def test_a_run_reaches_the_metrics_through_the_bus_the_runtime_builds():
    """Bug caught: the bridge never subscribed, which is how the runtime shipped with it. A run's
    start and failure each count once and set a marker at the event's own time."""
    metrics = _Metrics()
    bus = _bus(metrics)

    bus.emit(EventType.RUN_STARTED, entity_type="run", entity_id="run_1", context={})
    bus.emit(EventType.RUN_FAILED, entity_type="run", entity_id="run_1", context={})

    counters = [(c[1], c[3]) for c in metrics.calls if c[0] == "counter"]
    assert counters == [
        ("runs_started_total", {"entity_type": "run"}),
        ("runs_failed_total", {"entity_type": "run"}),
    ]
    markers = [(c[1], c[3]) for c in metrics.calls if c[0] == "gauge"]
    assert markers == [
        ("run_started_timestamp_seconds", {}),
        ("run_finished_timestamp_seconds", {"outcome": "failed"}),
    ]
    now = datetime.now(UTC).timestamp()
    assert all(abs(c[2] - now) < 60 for c in metrics.calls if c[0] == "gauge")


def test_a_campaign_transition_is_read_by_the_state_it_reached():
    metrics = _Metrics()
    _bus(metrics).emit(
        EventType.CAMPAIGN_TRANSITIONED,
        entity_type="campaign",
        entity_id="cmp_1",
        context={},
        payload={"next_state": "closed", "prior_state": "running"},
    )
    assert [(c[0], c[1], c[3]) for c in metrics.calls] == [
        (
            "counter",
            "campaign_transitions_total",
            {"entity_type": "campaign", "next_state": "closed"},
        ),
        ("gauge", "campaign_transition_timestamp_seconds", {"next_state": "closed"}),
    ]


def test_without_a_metrics_port_the_bus_records_nothing_and_still_delivers():
    """Edge: every other composition (agents, tests) builds the bus without metrics."""
    seen = []
    bus = create_cycle_event_bus("in_process", source_service="t", source_version="t")
    bus.subscribe(type("S", (), {"on_event": lambda self, e: seen.append(e.event_type)})())
    bus.emit(EventType.RUN_STARTED, entity_type="run", entity_id="run_1", context={})
    assert seen == [EventType.RUN_STARTED]


def test_every_metric_the_dashboards_read_is_one_the_runtime_sets():
    """Bug caught: a renamed metric. A panel or marker querying a name nothing sets draws nothing,
    with no error, which reads exactly like a quiet box."""
    set_by_the_runtime = (
        set(_COUNTER_MAP.values())
        | {name for name, _ in _MARKER_MAP.values()}
        | {"runtime_started_timestamp_seconds"}
    )
    queried: set[str] = set()
    for path in _DASHBOARDS:
        board = json.loads(path.read_text(encoding="utf-8"))
        exprs = [a["expr"] for a in board["annotations"]["list"]]
        exprs += [t["expr"] for p in board["panels"] for t in p.get("targets", [])]
        for expr in exprs:
            queried |= {
                m.removeprefix(_NAMESPACE)
                for m in re.findall(r"\bsquadops_[a-z0-9_]+", expr)
                if not m.startswith("squadops_llm_")
            }
    assert queried, "the dashboards query none of the runtime's activity"
    assert queried <= set_by_the_runtime, sorted(queried - set_by_the_runtime)
    # Every marker reads an event-time gauge, in milliseconds, as Grafana's series-as-time needs.
    markers = json.loads(_DASHBOARDS[0].read_text(encoding="utf-8"))["annotations"]["list"]
    assert {m["name"] for m in markers} == {
        "Deploys",
        "Runs started",
        "Runs finished",
        "Campaign transitions",
    }
    assert all(m["useValueForTime"] and m["expr"].endswith("* 1000") for m in markers)
