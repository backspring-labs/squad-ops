"""The identity-permutation test over the roster (#1373).

CLAUDE.md's rule: agent names are user-configurable and never appear in source — an agent
is its *role*, and a persona (``agents/instances/instances.yaml``) is an id the roster binds
to a role. The former entrypoint carried a hardcoded ``{name: role}`` map with an
``id.split("-")[0]`` fallback (#333); this pins the property the 1.7.0 plan asked for once
the map was gone: **any persona in any role wires the same agent** — the handler registry
bound is the role's, the queues are named from the persona's id, and nothing in the wiring
consults the persona's display name. Read from the real roster and the real squad profiles,
so a new persona or a new role is covered the day it is declared.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml

pytestmark = [pytest.mark.domain_agents]

REPO = Path(__file__).resolve().parents[3]


def _personas() -> list[dict]:
    data = yaml.safe_load((REPO / "agents" / "instances" / "instances.yaml").read_text())
    return list(data["instances"])


def _profile_roles() -> list[str]:
    data = yaml.safe_load((REPO / "config" / "squad-profiles.yaml").read_text())
    profiles = data["profiles"]
    profiles = profiles.values() if isinstance(profiles, dict) else profiles
    return sorted({m["role"] for p in profiles for m in (p.get("agents") or [])})


def _persona_id(persona: dict) -> str:
    return persona["id"]


def _runner(persona: dict, role: str, monkeypatch):
    """The runner ``main()`` builds for this (persona, role), with the roster entry the
    real loader would return and the port adapters replaced (RabbitMQ, Ollama, …)."""
    from squadops.agents import entrypoint

    monkeypatch.setattr(
        entrypoint, "load_instance_config", lambda aid: persona if aid == persona["id"] else None
    )
    runner = entrypoint.AgentRunner(role=role, agent_id=persona["id"])
    runner._config = MagicMock()
    ports = {
        name: MagicMock()
        for name in ("llm", "memory", "prompt_service", "queue", "metrics", "events", "filesystem")
    }

    async def _create_ports(config):
        return ports

    monkeypatch.setattr(runner, "_create_ports", _create_ports)
    return runner


def test_the_roster_and_the_profiles_this_test_reads_are_not_empty():
    personas, roles = _personas(), _profile_roles()
    assert len(personas) >= 6 and {"lead", "dev", "qa", "strat", "builder", "data"} <= set(roles)
    assert all(p.get("id") and p.get("role") and p.get("model") for p in personas)


@pytest.mark.parametrize("role", _profile_roles())
@pytest.mark.parametrize("persona", _personas(), ids=_persona_id)
async def test_any_persona_in_any_role_binds_the_roles_registry(persona, role, monkeypatch):
    """The bug this catches: a wiring that derives the role from the id (or the display
    name) binds the roster's handlers instead of the assigned role's, so `neo` run as qa
    would carry the dev handlers and answer no qa dispatch."""
    from squadops.bootstrap.handlers import create_handler_registry

    runner = _runner(persona, role, monkeypatch)
    system = await runner._create_system()
    assert system.config.roles == [role]
    assert sorted(system.handler_registry.list_task_types()) == sorted(
        create_handler_registry(roles=[role]).list_task_types()
    )


def _swaps() -> list[tuple[dict, str]]:
    """Every (persona, role) where the role is not the roster's own and the two roles'
    registries differ — the pairs where a roster-derived binding would be visibly wrong."""
    from squadops.bootstrap.handlers import create_handler_registry

    types_of = {
        r: set(create_handler_registry(roles=[r]).list_task_types()) for r in _profile_roles()
    }
    return [
        (p, role)
        for p in _personas()
        for role in _profile_roles()
        if p["role"] != role and types_of[role] != types_of.get(p["role"], set())
    ]


@pytest.mark.parametrize(
    ("persona", "role"), _swaps(), ids=lambda v: v if isinstance(v, str) else v["id"]
)
async def test_a_swapped_persona_carries_the_assigned_roles_handlers_not_its_rosters(
    persona, role, monkeypatch
):
    from squadops.bootstrap.handlers import create_handler_registry

    runner = _runner(persona, role, monkeypatch)
    bound = set((await runner._create_system()).handler_registry.list_task_types())
    rosters_own = set(create_handler_registry(roles=[persona["role"]]).list_task_types())
    assert bound == set(create_handler_registry(roles=[role]).list_task_types())
    assert bound != rosters_own


@pytest.mark.parametrize("persona", _personas(), ids=_persona_id)
async def test_queues_are_named_from_the_id_and_never_from_the_display_name(persona, monkeypatch):
    """Entered at the consumer the live agent runs; the broker names it sees are the
    persona's id (``max_comms``), never its display name (``Max``) or a role literal."""
    runner = _runner(persona, "lead", monkeypatch)
    queue = MagicMock()
    queue.ensure_queue = AsyncMock()
    subscription = MagicMock()
    subscription.cancel = AsyncMock()
    queue.subscribe = AsyncMock(return_value=subscription)
    queue.close = AsyncMock()
    runner._queue = queue
    runner._shutdown_event.set()  # the consumer parks on this; pre-set so it returns

    await runner._consume_tasks()

    queue.ensure_queue.assert_awaited_once_with(f"{persona['id']}_replies")
    assert queue.subscribe.await_args.args[0] == f"{persona['id']}_comms"
    names = [queue.ensure_queue.await_args.args[0], queue.subscribe.await_args.args[0]]
    display = persona.get("display_name", "")
    if display and display != persona["id"]:
        assert all(display not in name for name in names)
    assert all("lead" not in name for name in names), "a role literal is not an identity"
