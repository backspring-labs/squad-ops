"""No squad-side package can reach the held-out scenarios (SIP-0113 §4.1; IR-4; #2413).

A scenario's steps reach the runner, never a squad role: not through a prompt, a task's inputs or
an agent's container. This holds it in the code. The packages that build what a squad agent reads
or runs import neither the scenarios' domain, nor their port, nor their store, and name none of
its tables.

**The database:** no agent's container holds a credential for it (#2457). Until 2.4 every agent
held the runtime API's own (``SQUADOPS__DB__URL`` and the ``db_password`` secret in
``docker-compose.yml``), so a process in one could have read these tables directly. No agent
connects, so the credential is gone rather than narrowed, and a table added later is out of an
agent's reach without a grant to forget.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest
import yaml

pytestmark = [pytest.mark.domain_contracts]

ROOT = Path(__file__).resolve().parents[3]
SQUAD_SIDE = ("agents", "capabilities", "prompts", "execution")
HELD_OUT = ("squadops.scenarios", "squadops.ports.scenarios", "adapters.scenarios")
#: The held-out tables (``infra/migrations/1900_scenario_suites.sql``): a suite's content, steps
#: included, and each campaign's pin.
HELD_OUT_TABLES = ("scenario_suites", "campaign_scenario_suites")


def _imports(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_no_squad_side_module_imports_the_held_out_scenarios():
    """Bug caught: a handler, a prompt or the executor importing the scenario store, the first
    step of a scenario's steps reaching an authoring envelope or a squad task's inputs."""
    reached = sorted(
        f"{path.relative_to(ROOT)} imports {name}"
        for package in SQUAD_SIDE
        for path in (ROOT / "src" / "squadops" / package).rglob("*.py")
        for name in _imports(path)
        if name.startswith(HELD_OUT)
    )
    assert reached == []


def test_the_guard_reads_the_packages_it_names():
    """Bug caught: a renamed package leaving the guard above reading nothing, and passing."""
    for package in SQUAD_SIDE:
        assert any((ROOT / "src" / "squadops" / package).rglob("*.py")), package


def test_no_squad_side_file_names_a_held_out_table():
    """Bug caught: a handler, a prompt or a capability reading a suite's steps with its own SQL,
    past the store and its import guard above."""
    pattern = re.compile(r"\b(" + "|".join(HELD_OUT_TABLES) + r")\b")
    reached = sorted(
        f"{path.relative_to(ROOT)} names {match.group(1)}"
        for package in SQUAD_SIDE
        for path in (ROOT / "src" / "squadops" / package).rglob("*")
        if path.is_file() and path.suffix in {".py", ".md", ".yaml", ".yml", ".sql", ".j2"}
        for match in pattern.finditer(path.read_text(encoding="utf-8", errors="replace"))
    )
    assert reached == []


def test_the_held_out_tables_are_the_migrations_own():
    """Bug caught: a table renamed in the migration, leaving the guard above matching a name no
    longer used, and passing."""
    migration = (ROOT / "infra" / "migrations" / "1900_scenario_suites.sql").read_text()
    created = set(re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)", migration))
    assert created == set(HELD_OUT_TABLES)


def _compose_services() -> dict:
    return yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))["services"]


def _agents(services: dict) -> dict:
    """The squad's agents: every service built from the agents' image."""
    return {
        name: service
        for name, service in services.items()
        if (service.get("build") or {}).get("dockerfile") == "agents/Dockerfile"
    }


def _environment(service: dict) -> dict[str, str]:
    env = service.get("environment") or {}
    if isinstance(env, list):
        return dict(entry.split("=", 1) if "=" in entry else (entry, "") for entry in env)
    return {key: str(value) for key, value in env.items()}


def _secrets(service: dict) -> set[str]:
    return {s if isinstance(s, str) else s["source"] for s in service.get("secrets") or []}


def test_no_agent_container_holds_a_database_credential():
    """Bug caught (#2457): an agent's container holding the runtime API's database credential, so
    a process in it could read a suite's steps from ``scenario_suites`` directly, past the routes
    and both guards above. Each agent's block is copied from the last, which is how all eight
    came to hold it."""
    held = sorted(
        [f"{name}: the db_password secret" for name, s in _agents(_compose_services()).items()
         if "db_password" in _secrets(s)]
        + [f"{name}: {key}" for name, s in _agents(_compose_services()).items()
           for key, value in _environment(s).items()
           if key.startswith("SQUADOPS__DB__") or "postgresql://" in value]
    )  # fmt: skip
    assert held == []


def test_the_compose_guard_reads_every_agent_and_the_runtime_apis_credential():
    """Bug caught: the guard above reading no agent, after a renamed Dockerfile or a changed
    compose shape, and passing. The runtime API holds the credential: the paired control, so
    the guard is known to read secrets and environments where they are."""
    services = _compose_services()
    assert len(_agents(services)) >= 8
    runtime = services["runtime-api"]
    assert "db_password" in _secrets(runtime)
    assert "postgresql://" in _environment(runtime)["SQUADOPS__DB__URL"]
