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


# --- role resolution (#333): authoritative roster, never fabricated ------------


def test_role_from_env_wins(monkeypatch):
    """An explicit SQUADOPS_AGENT_ROLE is authoritative (the bootstrap selector)."""
    from squadops.agents import entrypoint

    monkeypatch.setenv("SQUADOPS_AGENT_ROLE", "lead")
    assert entrypoint._resolve_role() == "lead"


def test_role_derived_from_instances_when_env_unset(monkeypatch):
    """No role env → resolve from the authoritative roster (instances.yaml) by id."""
    from squadops.agents import entrypoint

    monkeypatch.delenv("SQUADOPS_AGENT_ROLE", raising=False)
    monkeypatch.setenv("SQUADOPS__AGENT__ID", "neo")
    monkeypatch.setattr(entrypoint, "load_instance_config", lambda aid: {"role": "dev"})
    assert entrypoint._resolve_role() == "dev"


def test_a_process_serves_every_role_its_roster_entry_declares(monkeypatch):
    """SIP-0108 §10i item 2: the handler registry has always held several roles' handlers;
    only this resolution restricted a process to one.

    Bug this catches: a one-agent arm registering only its own role's handlers, so the plan
    routes a dev step to it and the process has no dev handler — the task fails on a
    capability miss that reads as a missing handler rather than a roster it can fix.
    """
    from squadops.agents import entrypoint

    monkeypatch.delenv("SQUADOPS_AGENT_SERVES_ROLES", raising=False)
    monkeypatch.setenv("SQUADOPS__AGENT__ID", "han")
    monkeypatch.setattr(
        entrypoint,
        "load_instance_config",
        lambda aid: {"role": "generalist", "serves_roles": ["lead", "dev", "qa"]},
    )

    assert entrypoint._resolve_served_roles("generalist") == ["lead", "dev", "qa"]


def test_the_served_roles_reach_the_handler_registry_not_the_agents_own_role(monkeypatch):
    """Wiring: what `AgentRunner` hands the system, which is what decides the handlers.

    Bug this catches: resolving the list and then still passing ``[self.role]`` — the seam
    that made this a one-role process in the first place, and the one a resolver test alone
    cannot see.
    """
    from squadops.agents.entrypoint import AgentRunner

    monkeypatch.setenv("SQUADOPS__AGENT__ID", "neo")
    runner = AgentRunner(role="generalist", served_roles=["lead", "dev", "qa"])

    assert runner.served_roles == ["lead", "dev", "qa"]
    # Identity is untouched: the prompt, the telemetry role and the prompt layers read it.
    assert runner.role == "generalist"


def test_an_undeclared_roster_entry_serves_its_own_role_and_says_so(monkeypatch, caplog):
    """The roster is data an operator edits and the field is additive, so a container does
    not refuse to boot over it — but it warns, because a process serving less than its
    profile assigns fails every task of the roles it dropped."""
    import logging

    from squadops.agents import entrypoint

    monkeypatch.delenv("SQUADOPS_AGENT_SERVES_ROLES", raising=False)
    monkeypatch.setenv("SQUADOPS__AGENT__ID", "neo")
    monkeypatch.setattr(entrypoint, "load_instance_config", lambda aid: {"role": "dev"})

    with caplog.at_level(logging.WARNING):
        assert entrypoint._resolve_served_roles("dev") == ["dev"]
    assert "declares no `serves_roles`" in caplog.text


def test_every_roster_entry_declares_what_it_serves(monkeypatch):
    """The shipped roster carries the declaration, so no deployed agent takes the warning
    path above. Bug this catches: a new instance added without one."""
    from pathlib import Path

    import yaml

    roster = Path(__file__).resolve().parents[3] / "agents" / "instances" / "instances.yaml"
    entries = yaml.safe_load(roster.read_text())["instances"]
    assert entries
    undeclared = [e["id"] for e in entries if not e.get("serves_roles")]
    assert not undeclared, f"roster entries with no serves_roles: {undeclared}"


def test_role_never_fabricated_from_id(monkeypatch):
    """The bug this catches: the former ``id.split("-")[0]`` fabricated a role for an
    id absent from the roster (e.g. 'quark-1' -> 'quark'), silently mislabeling the
    agent. An unknown id now yields None (→ main() fails loudly), never a guess."""
    from squadops.agents import entrypoint

    monkeypatch.delenv("SQUADOPS_AGENT_ROLE", raising=False)
    monkeypatch.setenv("SQUADOPS__AGENT__ID", "quark-1")
    monkeypatch.setattr(entrypoint, "load_instance_config", lambda aid: None)  # not in roster
    assert entrypoint._resolve_role() is None


def test_role_none_when_nothing_configured(monkeypatch):
    """Neither role env nor id → None (main() logs the error and exits non-zero)."""
    from squadops.agents import entrypoint

    monkeypatch.delenv("SQUADOPS_AGENT_ROLE", raising=False)
    monkeypatch.delenv("SQUADOPS__AGENT__ID", raising=False)
    assert entrypoint._resolve_role() is None
