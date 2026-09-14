"""The agent root refuses an unset telemetry selector before it builds any port (#1449).

Entry point: ``AgentRunner._create_ports``, the method the agent's start-up calls. The root
used to read ``config.telemetry.backend or "otel"``, a masking default one step above the
factory's, so an agent with no telemetry configuration ran OpenTelemetry nobody chose.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

pytestmark = [pytest.mark.domain_agents]


@pytest.mark.parametrize("backend", [None, ""])
async def test_an_unset_telemetry_backend_is_refused_before_any_port_is_built(backend):
    from squadops.agents.entrypoint import AgentRunner

    with patch.object(AgentRunner, "__init__", lambda self, *a, **kw: None):
        runner = AgentRunner.__new__(AgentRunner)
    config = SimpleNamespace(telemetry=SimpleNamespace(backend=backend))

    with (
        patch("adapters.llm.factory.create_llm_provider") as llm,
        pytest.raises(ValueError, match="SQUADOPS__TELEMETRY__BACKEND"),
    ):
        await runner._create_ports(config)

    llm.assert_not_called()
