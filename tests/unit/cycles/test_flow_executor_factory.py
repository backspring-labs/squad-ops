"""Factory resolution for the flow executor.

DistributedFlowExecutor was renamed to DispatchedFlowExecutor; the provider
key is ``"dispatched"``.
"""

import ast
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from adapters.cycles.factory import create_flow_executor
from adapters.noop.ports import NoOpFailurePatternRecall

pytestmark = pytest.mark.domain_cycles

# #1987: the dependencies the executor cannot be built without are required, with no default.
# These say what they are: an executor wired to nothing outside this test.
_UNWIRED = {
    "cycle_registry": None,
    "artifact_vault": None,
    "queue": None,
    "squad_profile": None,
    "project_registry": None,
    "campaign_registry": None,
    "campaign_progress": None,
    "box_verdict": None,
    # #1964: required, and inert in 2.1; it has no ``None`` meaning, so the fixture passes it.
    "failure_recall": NoOpFailurePatternRecall(),
}
_REQUIRED = (*_UNWIRED, "task_timeout")


@pytest.mark.parametrize(
    ("provider", "expected"),
    [
        ("dispatched", "DispatchedFlowExecutor"),
    ],
)
def test_provider_key_resolves_to_expected_executor(provider, expected):
    """Bug class: a regression in the factory's provider routing would send a
    valid key to the wrong executor (or fail to construct), breaking cycle
    execution wiring. ``"in_process"`` was removed with its executor (#1984), so it is now
    refused like any unknown provider (``test_unknown_provider_raises`` below)."""
    executor = create_flow_executor(provider, **_UNWIRED, task_timeout=300.0)
    assert type(executor).__name__ == expected


def test_the_dispatched_executor_is_refused_without_a_declared_task_timeout():
    """1.8.2 item 15. Bug this catches: the factory's old ``kwargs.get("task_timeout", 300.0)``
    — a hung-agent detector nobody chose, set by whichever composition root forgot it."""
    with pytest.raises(TypeError, match="task_timeout"):
        create_flow_executor("dispatched", **_UNWIRED)


@pytest.mark.parametrize("missing", list(_UNWIRED))
def test_each_dependency_is_refused_when_the_root_leaves_it_out(missing):
    """#1987. Bug this catches: a dependency with a default of ``None``. Leaving out
    ``box_verdict`` would build an executor that starts runs with no box read, and nothing
    would say so."""
    deps = {k: v for k, v in _UNWIRED.items() if k != missing}
    with pytest.raises(TypeError, match=missing):
        create_flow_executor("dispatched", **deps, task_timeout=60.0)


def test_a_misspelled_keyword_is_refused_at_construction():
    """#1987. Bug this catches: the factory's old ``**kwargs``, where ``box_verdcit=…`` was
    read by nothing and the box check was silently off."""
    with pytest.raises(TypeError, match="box_verdcit"):
        create_flow_executor("dispatched", **_UNWIRED, task_timeout=60.0, box_verdcit=AsyncMock())


def test_the_runtime_root_wires_every_required_dependency_to_an_object():
    """#1987's proof, entered at the runtime's own call (``api/runtime/main.py``). Bug this
    catches: the root passing ``None`` (or nothing) for a dependency whose absence turns a check
    off, while every executor test, built on its own fakes, stays green.

    The call's keywords are read from main.py, each bound to a distinct object, and passed
    through the factory; each must arrive on the executor as that same object."""
    main = Path(__file__).resolve().parents[3] / "src/squadops/api/runtime/main.py"
    [call] = [
        node
        for node in ast.walk(ast.parse(main.read_text()))
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "create_flow_executor"
    ]
    passed = {k.arg: k.value for k in call.keywords}
    assert set(_REQUIRED) <= set(passed)
    for name in _UNWIRED:
        value = passed[name]
        assert not (isinstance(value, ast.Constant) and value.value is None), name

    wired = {name: MagicMock(name=name) for name in _UNWIRED}
    executor = create_flow_executor("dispatched", **wired, task_timeout=60.0)
    for name, obj in wired.items():
        assert getattr(executor, f"_{name}") is obj, name


def test_the_declared_task_timeout_reaches_the_dispatcher():
    """Wiring: the value the composition root declares is the one the dispatcher waits on."""
    executor = create_flow_executor("dispatched", **_UNWIRED, task_timeout=1234.0)
    assert executor._task_dispatcher._task_timeout == 1234.0


@pytest.mark.parametrize("provider", ["bogus", "in_process"])
def test_unknown_provider_raises(provider):
    with pytest.raises(ValueError, match="Unknown flow executor provider"):
        create_flow_executor(provider, **_UNWIRED, task_timeout=60.0)


class TestDispatchedWorkflowTrackerWiring:
    """#250: the dispatched branch routes ``prefect_api_url`` through the shared
    ``create_workflow_tracker`` (NoOp-fallback + init logging) instead of
    inline-building ``PrefectWorkflowTracker`` — without changing the no-URL or
    explicit-tracker paths."""

    def test_prefect_url_builds_prefect_tracker(self):
        """A configured Prefect URL yields a real PrefectWorkflowTracker on the
        executor (the routing actually constructs the adapter)."""
        from adapters.cycles.prefect_workflow_tracker import PrefectWorkflowTracker

        executor = create_flow_executor(
            "dispatched", **_UNWIRED, task_timeout=300.0, prefect_api_url="http://prefect:4200/api"
        )
        assert isinstance(executor._workflow_tracker, PrefectWorkflowTracker)

    def test_no_prefect_url_leaves_tracker_none(self):
        """Behavior preserved: with no URL and no explicit tracker, the executor
        gets ``None`` (NOT a NoOp) — exactly as before the refactor."""
        executor = create_flow_executor("dispatched", **_UNWIRED, task_timeout=300.0)
        assert executor._workflow_tracker is None

    def test_prefect_construction_failure_falls_back_to_noop(self, monkeypatch):
        """The gain: because the branch now routes through the shared factory, a
        PrefectWorkflowTracker construction failure falls back to a
        NoOpWorkflowTracker instead of raising out of the factory and breaking
        executor wiring (the old inline build would propagate the error)."""
        import adapters.cycles.prefect_workflow_tracker as pwt
        from adapters.cycles.noop_workflow_tracker import NoOpWorkflowTracker

        def _boom(*args, **kwargs):
            raise RuntimeError("prefect unreachable at construction")

        monkeypatch.setattr(pwt, "PrefectWorkflowTracker", _boom)
        executor = create_flow_executor(
            "dispatched", **_UNWIRED, task_timeout=300.0, prefect_api_url="http://prefect:4200/api"
        )
        assert isinstance(executor._workflow_tracker, NoOpWorkflowTracker)

    def test_explicit_tracker_takes_precedence_over_url(self):
        """An explicitly injected tracker is used as-is even when a URL is also
        present — the ``if not workflow_tracker`` guard is preserved."""
        from adapters.cycles.noop_workflow_tracker import NoOpWorkflowTracker

        sentinel = NoOpWorkflowTracker()
        executor = create_flow_executor(
            "dispatched",
            **_UNWIRED,
            task_timeout=300.0,
            workflow_tracker=sentinel,
            prefect_api_url="http://prefect:4200/api",
        )
        assert executor._workflow_tracker is sentinel
