"""Configurable secondary-timeout params reach the actual call (#158).

Bug this guards: secondary HTTP timeouts (model-list probe, agent-card fetch)
were hardcoded, so operators couldn't tune them for slow networks. Each is now
a constructor param — these tests confirm the param actually flows to the GET
call (not just stored), so a regression back to a hardcoded literal is caught.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.domain_agents]


class _FakeResp:
    status_code = 200

    def __init__(self, data: dict):
        self._data = data

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return self._data


class _RecordingClient:
    """Captures the timeout passed to each .get() call."""

    def __init__(self, data: dict):
        self._data = data
        self.timeouts: list[float] = []

    async def get(self, url, timeout=None, **_kw):
        self.timeouts.append(timeout)
        return _FakeResp(self._data)


def _patch_client(monkeypatch, adapter, client) -> None:
    async def _fake_get_client():
        return client

    monkeypatch.setattr(adapter, "_get_client", _fake_get_client)


async def test_ollama_model_list_timeout_flows_to_call(monkeypatch):
    from adapters.llm.ollama import OllamaAdapter

    client = _RecordingClient({"models": []})
    adapter = OllamaAdapter(model_list_timeout_seconds=99.0)
    _patch_client(monkeypatch, adapter, client)

    await adapter.refresh_models()

    assert client.timeouts == [99.0]


async def test_ollama_model_list_timeout_default(monkeypatch):
    from adapters.llm.ollama import _DEFAULT_MODEL_LIST_TIMEOUT, OllamaAdapter

    client = _RecordingClient({"models": []})
    adapter = OllamaAdapter()  # default
    _patch_client(monkeypatch, adapter, client)

    await adapter.refresh_models()

    assert client.timeouts == [_DEFAULT_MODEL_LIST_TIMEOUT]


async def test_a2a_agent_card_timeout_flows_to_call(monkeypatch):
    from adapters.comms.a2a_client import A2AClientAdapter

    client = _RecordingClient({"name": "agent"})
    adapter = A2AClientAdapter(agent_card_timeout_seconds=99.0)
    _patch_client(monkeypatch, adapter, client)

    await adapter.get_agent_card("http://agent:8000")

    assert client.timeouts == [99.0]


def test_secondary_timeout_params_exist_and_default():
    """Constructor params exist with sane named-constant defaults (no magic numbers)."""
    from adapters.comms.a2a_client import _DEFAULT_AGENT_CARD_TIMEOUT
    from adapters.comms.rabbitmq import _DEFAULT_CONSUME_POLL_TIMEOUT
    from adapters.tools.docker import _DEFAULT_HEALTH_TIMEOUT, DockerAdapter

    assert _DEFAULT_AGENT_CARD_TIMEOUT > 0
    assert _DEFAULT_CONSUME_POLL_TIMEOUT > 0
    # docker health timeout is honored via the constructor
    assert DockerAdapter(health_timeout_seconds=42.0)._health_timeout == 42.0
    assert DockerAdapter()._health_timeout == _DEFAULT_HEALTH_TIMEOUT
