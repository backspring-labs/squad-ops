"""Every agent container keeps its memory store on a volume of its own (#2112).

An agent opens its store at ``/app/data/memory_db`` (``squadops.agents.entrypoint``, the
``MEMORY_DB_PATH`` default). A service with no volume there keeps the store in the container's
writable layer, and every recreation (a rebuild, a deploy) empties it. Three agents shipped that
way: han was added in 1.8.1 without the mount the other five had.
"""

from __future__ import annotations

import pathlib

import pytest
import yaml

_STORE = "/app/data/memory_db"
_AGENT_DOCKERFILE = "agents/Dockerfile"


def _compose() -> dict:
    path = pathlib.Path(__file__).resolve().parents[3] / "docker-compose.yml"
    return yaml.safe_load(path.read_text())


def _is_agent(service: dict) -> bool:
    build = service.get("build")
    return isinstance(build, dict) and build.get("dockerfile") == _AGENT_DOCKERFILE


def _memory_volume_problems(compose: dict) -> list[str]:
    """What keeps an agent's store off a volume of its own: no named volume at the store path,
    one no top-level ``volumes:`` declares, one another agent also mounts, or a
    ``MEMORY_DB_PATH`` that moves the store away from the mount."""
    declared = set((compose.get("volumes") or {}).keys())
    owners: dict[str, list[str]] = {}
    problems = []
    for name, service in (compose.get("services") or {}).items():
        if not _is_agent(service):
            continue
        env = service.get("environment") or {}
        if isinstance(env, dict) and "MEMORY_DB_PATH" in env:
            problems.append(f"{name}: MEMORY_DB_PATH moves the store off {_STORE}")
        mounted = [
            spec.split(":")[0]
            for spec in service.get("volumes") or []
            if isinstance(spec, str) and spec.split(":")[1:2] == [_STORE]
        ]
        if not mounted:
            problems.append(f"{name}: nothing is mounted at {_STORE}")
            continue
        volume = mounted[0]
        if volume.startswith((".", "/")):
            problems.append(f"{name}: {volume} is a bind mount, not a named volume")
        elif volume not in declared:
            problems.append(f"{name}: {volume} is not declared under the top-level volumes")
        owners.setdefault(volume, []).append(name)
    problems += [
        f"{volume} is mounted by {', '.join(names)}"
        for volume, names in owners.items()
        if len(names) > 1
    ]
    return problems


def test_every_agent_keeps_its_memory_store_on_a_volume_of_its_own():
    """Bug caught: an agent service added without the store's volume (#2112), or two agents
    sharing one store."""
    compose = _compose()
    agents = [name for name, service in compose["services"].items() if _is_agent(service)]

    assert len(agents) >= 8, f"the eight agent services are built from {_AGENT_DOCKERFILE}"
    assert _memory_volume_problems(compose) == []


def _agent(volumes=None, environment=None) -> dict:
    service = {"build": {"dockerfile": _AGENT_DOCKERFILE}}
    if volumes is not None:
        service["volumes"] = volumes
    if environment is not None:
        service["environment"] = environment
    return service


@pytest.mark.parametrize(
    ("services", "declared", "expected"),
    [
        pytest.param(
            {"eve": _agent()},
            [],
            ["eve: nothing is mounted at /app/data/memory_db"],
            id="no mount (#2112)",
        ),
        pytest.param(
            {"eve": _agent(["/var/run/docker.sock:/var/run/docker.sock"])},
            [],
            ["eve: nothing is mounted at /app/data/memory_db"],
            id="other mounts only",
        ),
        pytest.param(
            {"eve": _agent(["eve_memory_data:/app/data/memory_db"])},
            [],
            ["eve: eve_memory_data is not declared under the top-level volumes"],
            id="undeclared volume",
        ),
        pytest.param(
            {"eve": _agent(["./data/eve:/app/data/memory_db"])},
            [],
            ["eve: ./data/eve is a bind mount, not a named volume"],
            id="bind mount",
        ),
        pytest.param(
            {
                "eve": _agent(["shared_memory:/app/data/memory_db"]),
                "han": _agent(["shared_memory:/app/data/memory_db"]),
            },
            ["shared_memory"],
            ["shared_memory is mounted by eve, han"],
            id="two agents share a store",
        ),
        pytest.param(
            {
                "eve": _agent(
                    ["eve_memory_data:/app/data/memory_db"],
                    {"MEMORY_DB_PATH": "/tmp/memory_db"},
                )
            },
            ["eve_memory_data"],
            ["eve: MEMORY_DB_PATH moves the store off /app/data/memory_db"],
            id="store moved off the mount",
        ),
    ],
)
def test_a_store_off_a_volume_of_its_own_is_named(services, declared, expected):
    """Bug caught: a check that passes the shapes it exists to refuse."""
    compose = {"services": services, "volumes": {name: {} for name in declared}}

    assert _memory_volume_problems(compose) == expected


def test_a_service_not_built_as_an_agent_needs_no_store():
    """Bug caught: the check reaching the runtime API or a third-party service, which open no
    agent store."""
    compose = {"services": {"postgres": {"image": "postgres:16"}, "runtime-api": {"build": "."}}}

    assert _memory_volume_problems(compose) == []
