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
