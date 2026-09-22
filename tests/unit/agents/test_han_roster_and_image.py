"""Han's roster entry and image inputs agree with the Solo profile (SIP-0108 §10i item 4).

Three declarations describe the same process — the roster entry the entrypoint reads, the
`solo` squad profile the runtime dispatches by, and the per-role image inputs the Dockerfile
installs — and nothing at runtime checks them against each other until a dispatch fails
(`HandlerNotFoundError` names "the two serves_roles declarations disagree") or a qa suite
skips on `missing_tooling`. These tests check them at commit.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from adapters.cycles.config_squad_profile import ConfigSquadProfile
from squadops.agents import entrypoint

REPO = Path(__file__).resolve().parents[3]
ROSTER = REPO / "agents" / "instances" / "instances.yaml"
INSTANCES = REPO / "agents" / "instances"
SQUAD_PROFILES = REPO / "config" / "squad-profiles.yaml"


def _roster_entry(agent_id: str) -> dict:
    data = yaml.safe_load(ROSTER.read_text())
    return next(e for e in data["instances"] if e["id"] == agent_id)


def _packages(role: str, filename: str) -> set[str]:
    path = INSTANCES / role / filename
    if not path.exists():
        return set()
    return {
        line.strip()
        for line in path.read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


async def test_the_roster_and_the_solo_profile_declare_the_same_han():
    """Bug this catches: the roster's `serves_roles` and the profile's disagreeing — the
    exact condition `HandlerNotFoundError` names on a live dispatch — or the roster naming a
    different model than the arm the window pins."""
    roster = _roster_entry("han")
    solo = await ConfigSquadProfile(yaml_path=SQUAD_PROFILES).get_profile("solo")
    han = solo.agents[0]

    assert roster["role"] == han.role == "generalist"
    assert sorted(roster["serves_roles"]) == sorted(han.serves_roles)
    assert roster["model"] == han.model
    assert roster["enabled"] is True and han.enabled


def test_the_entrypoint_resolves_han_to_every_served_role(monkeypatch):
    """Wiring, entered at the entrypoint's resolver with the real roster (#1615 / §10i
    item 2). Bug this catches: the resolver falling back to the agent's own role — one
    handler set registered, five roles' dispatches unanswered — which the log would call
    "serving its own role only"."""
    monkeypatch.delenv("SQUADOPS_AGENT_SERVES_ROLES", raising=False)
    monkeypatch.setenv("SQUADOPS__AGENT__ID", "han")
    monkeypatch.setattr(
        entrypoint, "load_instance_config", lambda aid: _roster_entry(aid) if aid == "han" else None
    )
    served = entrypoint._resolve_served_roles("generalist")
    assert sorted(served) == ["builder", "data", "dev", "lead", "qa", "strat"]


def test_hans_image_installs_the_union_of_every_served_roles_tooling():
    """Bug this catches: a package a specialist's image installs (node for the frontend
    build, pytest for the suites) missing from the generalist's — every qa or build check
    on Han would then skip as `missing_tooling` and the arm would read blocked, not
    measured. The union is computed from the served roles, so a new role-specific list
    fails this the day it is added."""
    served = _roster_entry("han")["serves_roles"]
    for filename in ("system-packages.txt", "npm-global-packages.txt", "requirements.txt"):
        union = set().union(*(_packages(role, filename) for role in served))
        assert _packages("generalist", filename) == union, filename
