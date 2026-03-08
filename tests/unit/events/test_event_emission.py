"""Emission coverage tests — every taxonomy event has at least one valid emission point.

Phase 3e: Validates that each of the 28 EventType constants is referenced
in at least one emit() call site (executor or route). Uses AST-level source
scanning to verify wiring without executing the full pipeline.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from squadops.events.types import EventType

pytestmark = [pytest.mark.domain_events]

# ---- Source-level coverage: every EventType constant appears in an emit() call ----

# Collect all 28 event type constant names
_ALL_EVENT_TYPE_ATTRS = [
    attr
    for attr in dir(EventType)
    if not attr.startswith("_")
    and attr == attr.upper()
    and isinstance(getattr(EventType, attr), str)
]

# SIP-0083 workload events — all emission points now present
_SIP_0083_PENDING_EMISSION: set[str] = set()


def _find_event_type_refs_in_file(filepath: Path) -> set[str]:
    """Parse a Python file and return EventType.X references found."""
    source = filepath.read_text()
    tree = ast.parse(source)
    refs = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            # Match EventType.SOMETHING
            if (
                isinstance(node.value, ast.Name)
                and node.value.id == "EventType"
                and node.attr in _ALL_EVENT_TYPE_ATTRS
            ):
                refs.add(node.attr)
    return refs


# Source files that contain emit() calls
_EXECUTOR_PATH = Path("adapters/cycles/distributed_flow_executor.py")
_CYCLES_ROUTE = Path("src/squadops/api/routes/cycles/cycles.py")
_RUNS_ROUTE = Path("src/squadops/api/routes/cycles/runs.py")
_ARTIFACTS_ROUTE = Path("src/squadops/api/routes/cycles/artifacts.py")

_ALL_EMISSION_FILES = [_EXECUTOR_PATH, _CYCLES_ROUTE, _RUNS_ROUTE, _ARTIFACTS_ROUTE]


@pytest.fixture(scope="module")
def all_emitted_types() -> set[str]:
    """Collect all EventType.X references across emission source files."""
    refs: set[str] = set()
    for path in _ALL_EMISSION_FILES:
        refs |= _find_event_type_refs_in_file(path)
    return refs


class TestEmissionCoverage:
    """Every EventType constant must appear in at least one emission source file."""

    @pytest.mark.parametrize(
        "attr",
        [a for a in _ALL_EVENT_TYPE_ATTRS if a not in _SIP_0083_PENDING_EMISSION],
    )
    def test_event_type_has_emission_point(self, attr: str, all_emitted_types: set[str]) -> None:
        assert attr in all_emitted_types, (
            f"EventType.{attr} ({getattr(EventType, attr)}) has no emit() call site "
            f"in any emission source file"
        )

    def test_all_28_types_defined(self, all_emitted_types: set[str]) -> None:
        assert len(_ALL_EVENT_TYPE_ATTRS) == 28

    def test_wired_types_covered(self, all_emitted_types: set[str]) -> None:
        wired = set(_ALL_EVENT_TYPE_ATTRS) - _SIP_0083_PENDING_EMISSION
        missing = wired - all_emitted_types
        assert not missing, f"Missing emission points for: {sorted(missing)}"


class TestExecutorEmissionPoints:
    """Verify executor contains the expected event types."""

    @pytest.fixture(scope="class")
    def executor_refs(self) -> set[str]:
        return _find_event_type_refs_in_file(_EXECUTOR_PATH)

    @pytest.mark.parametrize(
        "attr",
        [
            "RUN_STARTED",
            "RUN_COMPLETED",
            "RUN_FAILED",
            "RUN_CANCELLED",
            "RUN_PAUSED",
            "RUN_RESUMED",
            "TASK_DISPATCHED",
            "TASK_SUCCEEDED",
            "TASK_FAILED",
            "PULSE_BOUNDARY_REACHED",
            "PULSE_SUITE_EVALUATED",
            "PULSE_BOUNDARY_DECIDED",
            "PULSE_REPAIR_STARTED",
            "PULSE_REPAIR_EXHAUSTED",
            "CHECKPOINT_CREATED",
            "CHECKPOINT_RESTORED",
            "CORRECTION_INITIATED",
            "CORRECTION_DECIDED",
            "CORRECTION_COMPLETED",
            "WORKLOAD_COMPLETED",
            "WORKLOAD_GATE_AWAITING",
            "WORKLOAD_ADVANCED",
        ],
    )
    def test_executor_emits(self, attr: str, executor_refs: set[str]) -> None:
        assert attr in executor_refs

    def test_executor_has_22_types(self, executor_refs: set[str]) -> None:
        assert len(executor_refs) == 22


class TestRouteEmissionPoints:
    """Verify route files contain the expected event types."""

    def test_cycles_route_emits_cycle_created(self) -> None:
        refs = _find_event_type_refs_in_file(_CYCLES_ROUTE)
        assert "CYCLE_CREATED" in refs

    def test_cycles_route_emits_cycle_cancelled(self) -> None:
        refs = _find_event_type_refs_in_file(_CYCLES_ROUTE)
        assert "CYCLE_CANCELLED" in refs

    def test_runs_route_emits_run_created(self) -> None:
        refs = _find_event_type_refs_in_file(_RUNS_ROUTE)
        assert "RUN_CREATED" in refs

    def test_runs_route_emits_gate_decided(self) -> None:
        refs = _find_event_type_refs_in_file(_RUNS_ROUTE)
        assert "GATE_DECIDED" in refs

    def test_artifacts_route_emits_artifact_stored(self) -> None:
        refs = _find_event_type_refs_in_file(_ARTIFACTS_ROUTE)
        assert "ARTIFACT_STORED" in refs

    def test_artifacts_route_emits_artifact_promoted(self) -> None:
        refs = _find_event_type_refs_in_file(_ARTIFACTS_ROUTE)
        assert "ARTIFACT_PROMOTED" in refs


class TestEmitCallSitePayloadFields:
    """Verify that emit calls include required payload fields from the taxonomy."""

    def _extract_emit_calls(self, filepath: Path) -> list[ast.Call]:
        """Extract all .emit() call AST nodes from a file."""
        source = filepath.read_text()
        tree = ast.parse(source)
        calls = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if (
                    isinstance(func, ast.Attribute)
                    and func.attr == "emit"
                    and any(kw.arg == "entity_type" for kw in node.keywords)
                ):
                    calls.append(node)
        return calls

    def _get_keyword_value(self, call: ast.Call, name: str) -> str | None:
        for kw in call.keywords:
            if kw.arg == name:
                if isinstance(kw.value, ast.Constant):
                    return kw.value.value
                if isinstance(kw.value, ast.Attribute):
                    return kw.value.attr
        return None

    def test_all_emit_calls_have_entity_type(self) -> None:
        for path in _ALL_EMISSION_FILES:
            calls = self._extract_emit_calls(path)
            for call in calls:
                entity_type = self._get_keyword_value(call, "entity_type")
                assert entity_type is not None, f"emit() in {path} missing entity_type keyword"

    def test_all_emit_calls_have_entity_id(self) -> None:
        for path in _ALL_EMISSION_FILES:
            calls = self._extract_emit_calls(path)
            for call in calls:
                has_entity_id = any(kw.arg == "entity_id" for kw in call.keywords)
                assert has_entity_id, f"emit() in {path} missing entity_id keyword"

    def test_all_emit_calls_have_context(self) -> None:
        for path in _ALL_EMISSION_FILES:
            calls = self._extract_emit_calls(path)
            for call in calls:
                has_context = any(kw.arg == "context" for kw in call.keywords)
                assert has_context, f"emit() in {path} missing context keyword"

    def test_most_emit_calls_have_payload(self) -> None:
        """Most emit calls include payload; some (run.started, run.completed,
        run.cancelled) omit it because the port defaults to None."""
        total_calls = 0
        with_payload = 0
        for path in _ALL_EMISSION_FILES:
            calls = self._extract_emit_calls(path)
            for call in calls:
                total_calls += 1
                if any(kw.arg == "payload" for kw in call.keywords):
                    with_payload += 1
        # At least 35 of 40 calls have payload (a few lifecycle events omit it)
        assert with_payload >= 35

    def test_total_emit_call_count(self) -> None:
        """Sanity check: 38 executor + 7 route = 45 total emit calls."""
        total = 0
        for path in _ALL_EMISSION_FILES:
            total += len(self._extract_emit_calls(path))
        assert total == 45
