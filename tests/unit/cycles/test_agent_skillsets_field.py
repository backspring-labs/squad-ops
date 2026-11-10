"""An agent's declared ``skillsets`` (SIP-0116 §5.2, phase 1): carried at every boundary a
profile crosses, and covered by the squad snapshot only where declared (Q57)."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from adapters.cycles.config_squad_profile import ConfigSquadProfile
from adapters.cycles.postgres_squad_profile import PostgresSquadProfile
from squadops.api.error_handlers import register_domain_error_handlers
from squadops.api.routes.cycles.mapping import profile_to_response
from squadops.api.routes.cycles.profiles import router
from squadops.cycles.lifecycle import compute_profile_snapshot_hash
from squadops.cycles.models import AgentProfileEntry, SquadProfile
from squadops.cycles.profile_utils import validate_agent_entries

pytestmark = [pytest.mark.domain_orchestration]

_REPO = Path(__file__).resolve().parents[3]
_NOW = datetime(2026, 11, 9, tzinfo=UTC)


def _profile(*, eve_skillsets: tuple[str, ...] = ()) -> SquadProfile:
    return SquadProfile(
        profile_id="game-dev-fixture",
        name="Fixture",
        description="",
        version=3,
        agents=(
            AgentProfileEntry("neo", "dev", "m-dev", True, {"temperature": 0.2}, ("dev",)),
            AgentProfileEntry("eve", "qa", "m-qa", True, {}, ("qa",), eve_skillsets),
        ),
        created_at=_NOW,
    )


def test_a_profile_declaring_no_skillsets_hashes_as_it_did_before_the_field_existed():
    """Bug caught: the new key entering the payload unconditionally. Every stored
    ``squad_profile_snapshot_ref`` and every verification set's frozen prefix would then stop
    matching a squad nobody changed. The expected digest is built here from the payload as it
    was written before SIP-0116, key for key."""
    before = {
        "profile_id": "game-dev-fixture",
        "version": 3,
        "agents": [
            {
                "agent_id": "neo",
                "role": "dev",
                "model": "m-dev",
                "enabled": True,
                "config_overrides": {"temperature": 0.2},
                "serves_roles": ["dev"],
            },
            {
                "agent_id": "eve",
                "role": "qa",
                "model": "m-qa",
                "enabled": True,
                "config_overrides": {},
                "serves_roles": ["qa"],
            },
        ],
    }
    expected = hashlib.sha256(
        json.dumps(before, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()

    assert compute_profile_snapshot_hash(_profile()) == expected


def test_a_declared_skillset_is_part_of_the_squad_snapshot():
    """Bug caught: two squads that carry different equipment snapshotting the same, so a
    Campaign pinned on one could run the other unnoticed."""
    plain = compute_profile_snapshot_hash(_profile())
    equipped = compute_profile_snapshot_hash(_profile(eve_skillsets=("fixture-qa",)))
    other = compute_profile_snapshot_hash(_profile(eve_skillsets=("fixture-qa", "second")))

    assert len({plain, equipped, other}) == 3


def test_the_same_skillsets_in_another_order_are_the_same_squad():
    one = compute_profile_snapshot_hash(_profile(eve_skillsets=("a-set", "b-set")))
    two = compute_profile_snapshot_hash(_profile(eve_skillsets=("b-set", "a-set")))

    assert one == two


def test_the_postgres_row_carries_declared_skillsets_and_omits_an_empty_list():
    """Bug caught: the row dropping the field, so a profile reads back unequipped and its
    snapshot no longer matches the one the YAML or the API produced."""
    adapter = PostgresSquadProfile.__new__(PostgresSquadProfile)
    profile = _profile(eve_skillsets=("fixture-qa",))
    stored = json.loads(json.dumps(adapter._agents_to_dicts(profile.agents)))

    assert "skillsets" not in stored[0]
    assert stored[1]["skillsets"] == ["fixture-qa"]

    row = {
        "profile_id": profile.profile_id,
        "name": profile.name,
        "description": profile.description,
        "version": profile.version,
        "agents": stored,
        "created_at": profile.created_at,
    }
    read_back = adapter._row_to_profile(row)

    assert read_back.agents[0].skillsets == ()
    assert read_back.agents[1].skillsets == ("fixture-qa",)
    assert compute_profile_snapshot_hash(read_back) == compute_profile_snapshot_hash(profile)


async def test_the_yaml_file_reads_an_agents_skillsets(tmp_path):
    path = tmp_path / "squad-profiles.yaml"
    path.write_text(
        "profiles:\n"
        "  - profile_id: fixture\n"
        "    name: Fixture\n"
        "    description: ''\n"
        "    version: 1\n"
        "    agents:\n"
        "      - {agent_id: neo, role: dev, model: m, serves_roles: [dev]}\n"
        "      - {agent_id: eve, role: qa, model: m, serves_roles: [qa],"
        " skillsets: [fixture-qa]}\n"
    )

    profile = await ConfigSquadProfile(path).get_profile("fixture")

    assert [a.skillsets for a in profile.agents] == [(), ("fixture-qa",)]


@pytest.fixture(scope="module")
def driver():
    path = _REPO / "scripts" / "dev" / "verification_set_driver.py"
    spec = importlib.util.spec_from_file_location("verification_set_driver_skillsets", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["verification_set_driver_skillsets"] = module
    spec.loader.exec_module(module)
    return module


def test_the_driver_reads_the_same_snapshot_as_the_runtime_for_an_equipped_squad(
    driver, monkeypatch
):
    """The wire seam: runtime hash → response DTO → the driver's rebuild. Bug caught: the
    field covered by the hash and dropped by the response or by the driver, so every counting
    roll on an equipped squad refuses to launch reading "SQUAD PROFILE CHANGED"."""
    equipped = _profile(eve_skillsets=("fixture-qa",))
    monkeypatch.setattr(driver, "login", lambda: None)
    monkeypatch.setattr(
        driver, "sh", lambda cmd, check=True: profile_to_response(equipped).model_dump_json()
    )

    live = driver.live_squad_snapshot("game-dev-fixture")

    assert live == compute_profile_snapshot_hash(equipped)
    assert live != compute_profile_snapshot_hash(_profile())


@pytest.fixture
def stored_profiles():
    port = AsyncMock()
    port.create_profile.side_effect = lambda p: p
    port.get_active_profile_id.return_value = "full"
    return port


@pytest.fixture
def client(stored_profiles):
    app = FastAPI()
    app.include_router(router)
    register_domain_error_handlers(app)
    app.state.squad_profile = stored_profiles
    llm = AsyncMock()
    llm.refresh_models.return_value = ["m"]
    app.state.llm_port = llm
    return TestClient(app)


def _create_body(skillsets):
    return {
        "name": "Roblox Fixture",
        "agents": [
            {
                "agent_id": "eve",
                "role": "qa",
                "model": "m",
                "serves_roles": ["qa"],
                "skillsets": skillsets,
            }
        ],
    }


def test_creating_a_profile_stores_and_returns_each_agents_skillsets(client, stored_profiles):
    resp = client.post("/api/v1/squad-profiles", json=_create_body(["fixture-qa", "second"]))

    assert resp.status_code == 201, resp.text
    (stored,) = stored_profiles.create_profile.call_args[0]
    assert stored.agents[0].skillsets == ("fixture-qa", "second")
    assert resp.json()["agents"][0]["skillsets"] == ["fixture-qa", "second"]


def test_a_skillset_declared_twice_is_refused_at_the_route(client, stored_profiles):
    resp = client.post("/api/v1/squad-profiles", json=_create_body(["fixture-qa", "fixture-qa"]))

    assert resp.status_code == 422
    assert "skillset declared more than once: fixture-qa" in resp.text
    stored_profiles.create_profile.assert_not_called()


@pytest.mark.parametrize(
    ("skillsets", "expected"),
    [
        (["fixture-qa", ""], "a skillset id must not be empty"),
        (["  "], "a skillset id must not be empty"),
        (["a", "b", "a"], "skillset declared more than once: a"),
    ],
)
def test_a_malformed_skillsets_list_is_named_by_agent(skillsets, expected):
    agents = [
        {"agent_id": "neo", "role": "dev", "model": "m", "serves_roles": ["dev"]},
        {
            "agent_id": "eve",
            "role": "qa",
            "model": "m",
            "serves_roles": ["qa"],
            "skillsets": skillsets,
        },
    ]

    assert validate_agent_entries(agents) == [f"agents[1]: {expected}"]


def test_a_disabled_agent_keeps_its_skillsets_and_an_unknown_id_is_not_the_profiles_error():
    """Whether a skillset exists is cycle preflight's question, on the routed agent (§9). A
    profile may name one this deployment doesn't hold."""
    agents = [
        {
            "agent_id": "eve",
            "role": "qa",
            "model": "m",
            "enabled": False,
            "skillsets": ["not-installed-here"],
        },
    ]

    assert validate_agent_entries(agents) == []


@pytest.mark.parametrize(
    "written",
    ["skillsets: fixture-qa", "skillsets: [fixture-qa, '']", "skillsets: {fixture-qa: 1}"],
    ids=["a bare id", "an empty id", "a mapping"],
)
async def test_a_skillsets_value_that_is_not_a_list_of_ids_is_refused_by_profile_and_agent(
    tmp_path, written
):
    """Bug caught: a lenient read. ``tuple("fixture-qa")`` is ten one-letter skillsets, so the
    squad loads, and is later refused at cycle creation for lacking a skillset its own profile
    names in plain sight."""
    path = tmp_path / "squad-profiles.yaml"
    path.write_text(
        "profiles:\n"
        "  - profile_id: fixture\n"
        "    name: Fixture\n"
        "    agents:\n"
        f"      - {{agent_id: eve, role: qa, model: m, serves_roles: [qa], {written}}}\n"
    )

    with pytest.raises(
        ValueError, match="squad profile 'fixture': agent 'eve' declares `skillsets`"
    ):
        await ConfigSquadProfile(path).get_profile("fixture")


def test_a_stored_row_with_a_malformed_skillsets_value_is_refused_not_reinterpreted():
    adapter = PostgresSquadProfile.__new__(PostgresSquadProfile)
    row = {
        "profile_id": "fixture",
        "name": "Fixture",
        "description": "",
        "version": 1,
        "agents": [
            {
                "agent_id": "eve",
                "role": "qa",
                "model": "m",
                "serves_roles": ["qa"],
                "skillsets": "x",
            }
        ],
        "created_at": _NOW,
    }

    with pytest.raises(ValueError, match="agent 'eve' declares `skillsets` as 'x'"):
        adapter._row_to_profile(row)
