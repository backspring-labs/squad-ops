"""AgentRunner identity resolution — no fabricated agent id (#333).

Identity is required config, never defaulted. The former ``f"{role}-001"`` fallback
masked a missing ``SQUADOPS__AGENT__ID`` and misdirected diagnosis to the
instance-config load. These tests pin that a missing id now fails loudly at the
right place, and that a configured id (env or explicit) still resolves.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.domain_agents]


def test_missing_agent_id_raises_at_the_right_place_not_fabricated(monkeypatch):
    """No ``SQUADOPS__AGENT__ID`` and no explicit id → a clear error naming the
    missing var, raised BEFORE the instance-config load. The bug this catches: the
    old ``f"{role}-001"`` default fabricated 'lead-001', which then failed the
    instance-config load with a misdirecting 'no instance configuration' message."""
    from squadops.agents.entrypoint import AgentRunner

    monkeypatch.delenv("SQUADOPS__AGENT__ID", raising=False)

    with pytest.raises(ValueError) as exc_info:
        AgentRunner(role="lead")

    msg = str(exc_info.value)
    assert "SQUADOPS__AGENT__ID" in msg
    # Fails naming the real cause, NOT the downstream instance-config misdirection.
    assert "instance configuration" not in msg


def test_env_agent_id_used_when_no_param(monkeypatch):
    """A configured ``SQUADOPS__AGENT__ID`` resolves as the identity (no param)."""
    from squadops.agents import entrypoint

    monkeypatch.setenv("SQUADOPS__AGENT__ID", "neo")
    monkeypatch.setattr(
        entrypoint, "load_instance_config", lambda aid: {"model": "m", "display_name": aid}
    )

    runner = entrypoint.AgentRunner(role="dev")
    assert runner.agent_id == "neo"


def test_explicit_agent_id_overrides_env(monkeypatch):
    """An explicit id wins over the env var — the param is authoritative."""
    from squadops.agents import entrypoint

    monkeypatch.setenv("SQUADOPS__AGENT__ID", "neo")
    monkeypatch.setattr(entrypoint, "load_instance_config", lambda aid: {"model": "m"})

    runner = entrypoint.AgentRunner(role="lead", agent_id="max")
    assert runner.agent_id == "max"


def test_empty_string_agent_id_is_rejected(monkeypatch):
    """An empty ``SQUADOPS__AGENT__ID`` is not a valid identity — it must not slip
    through as a falsy-but-present value; it fails the same as unset."""
    from squadops.agents.entrypoint import AgentRunner

    monkeypatch.setenv("SQUADOPS__AGENT__ID", "")

    with pytest.raises(ValueError, match="SQUADOPS__AGENT__ID"):
        AgentRunner(role="qa")
