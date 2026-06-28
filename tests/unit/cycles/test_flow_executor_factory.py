"""Factory resolution for the flow executor.

DistributedFlowExecutor was renamed to DispatchedFlowExecutor; the provider
key is ``"dispatched"``.
"""

import pytest

from adapters.cycles.factory import create_flow_executor

pytestmark = pytest.mark.domain_cycles


@pytest.mark.parametrize(
    ("provider", "expected"),
    [
        ("in_process", "InProcessFlowExecutor"),
        ("dispatched", "DispatchedFlowExecutor"),
    ],
)
def test_provider_key_resolves_to_expected_executor(provider, expected):
    """Bug class: a regression in the factory's provider routing would send a
    valid key to the wrong executor (or fail to construct), breaking cycle
    execution wiring."""
    executor = create_flow_executor(provider)
    assert type(executor).__name__ == expected


def test_unknown_provider_raises():
    with pytest.raises(ValueError, match="Unknown flow executor provider"):
        create_flow_executor("bogus")


class TestDispatchedWorkflowTrackerWiring:
    """#250: the dispatched branch routes ``prefect_api_url`` through the shared
    ``create_workflow_tracker`` (NoOp-fallback + init logging) instead of
    inline-building ``PrefectWorkflowTracker`` — without changing the no-URL or
    explicit-tracker paths."""

    def test_prefect_url_builds_prefect_tracker(self):
        """A configured Prefect URL yields a real PrefectWorkflowTracker on the
        executor (the routing actually constructs the adapter)."""
        from adapters.cycles.prefect_workflow_tracker import PrefectWorkflowTracker

        executor = create_flow_executor("dispatched", prefect_api_url="http://prefect:4200/api")
        assert isinstance(executor._workflow_tracker, PrefectWorkflowTracker)

    def test_no_prefect_url_leaves_tracker_none(self):
        """Behavior preserved: with no URL and no explicit tracker, the executor
        gets ``None`` (NOT a NoOp) — exactly as before the refactor."""
        executor = create_flow_executor("dispatched")
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
        executor = create_flow_executor("dispatched", prefect_api_url="http://prefect:4200/api")
        assert isinstance(executor._workflow_tracker, NoOpWorkflowTracker)

    def test_explicit_tracker_takes_precedence_over_url(self):
        """An explicitly injected tracker is used as-is even when a URL is also
        present — the ``if not workflow_tracker`` guard is preserved."""
        from adapters.cycles.noop_workflow_tracker import NoOpWorkflowTracker

        sentinel = NoOpWorkflowTracker()
        executor = create_flow_executor(
            "dispatched",
            workflow_tracker=sentinel,
            prefect_api_url="http://prefect:4200/api",
        )
        assert executor._workflow_tracker is sentinel
