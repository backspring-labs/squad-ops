"""No agent container mounts a store of its own (#2184).

Until 2.5 every agent opened SIP-042's LanceDB store at ``/app/data/memory_db``, and #2112 gave
each one a named volume there so the store outlived a recreation. SIP-0110 §A.4.3 retired the
store: the eight held no record when it was re-inventoried, and #2184 removed it, its port and
the eight volumes. Memory's records are SIP-0110's, in Postgres beside the cycle registry, so an
agent keeps nothing that a recreation could lose.

This guard keeps it so: an agent service mounts no named volume and nothing at the old store
path, sets no ``MEMORY_DB_PATH``, and the file declares no ``*_memory_data`` volume. Bind mounts
of host files (neo's ``docker-compose.yml`` and Docker socket) are not stores.
"""

from __future__ import annotations

import pathlib

import pytest
import yaml

_RETIRED_STORE = "/app/data/memory_db"
_AGENT_DOCKERFILE = "agents/Dockerfile"


def _compose() -> dict:
    path = pathlib.Path(__file__).resolve().parents[3] / "docker-compose.yml"
    return yaml.safe_load(path.read_text())


def _is_agent(service: dict) -> bool:
    build = service.get("build")
    return isinstance(build, dict) and build.get("dockerfile") == _AGENT_DOCKERFILE


def _fields(spec: str) -> list[str]:
    """A short-syntax mount split on its colons, outside any ``${VAR:-default}``."""
    fields, depth, current = [], 0, ""
    for char in spec:
        depth += {"{": 1, "}": -1}.get(char, 0)
        if char == ":" and depth == 0:
            fields.append(current)
            current = ""
        else:
            current += char
    return [*fields, current]


#: The source of a volume compose creates with no name: it persists like a named one.
_ANONYMOUS = "an anonymous volume"


def _mounts(service: dict) -> list[tuple[str, str]]:
    """``(source, target)`` for each of a service's mounts, short or long syntax. A host path is
    its source as written; a volume with no source is ``_ANONYMOUS``."""
    out = []
    for spec in service.get("volumes") or []:
        if isinstance(spec, str):
            fields = _fields(spec)
            out.append((_ANONYMOUS, fields[0]) if len(fields) == 1 else (fields[0], fields[1]))
        elif isinstance(spec, dict):
            source = spec.get("source") or ""
            if spec.get("type", "volume") == "volume" and not source:
                source = _ANONYMOUS
            out.append((source, spec.get("target", "")))
    return out


def _is_volume(source: str) -> bool:
    """A volume, named or anonymous; not a host path (``./x``, ``/x``, ``~/x``, ``${VAR}``)."""
    return bool(source) and not source.startswith((".", "/", "~", "$"))


def _store_problems(compose: dict) -> list[str]:
    """What gives an agent a store of its own."""
    problems = []
    for name, service in (compose.get("services") or {}).items():
        if not _is_agent(service):
            continue
        env = service.get("environment") or {}
        names = env.keys() if isinstance(env, dict) else [e.split("=")[0] for e in env]
        if "MEMORY_DB_PATH" in names:
            problems.append(f"{name}: sets MEMORY_DB_PATH")
        for source, target in _mounts(service):
            if target == _RETIRED_STORE:
                problems.append(f"{name}: mounts {source} at the retired store {_RETIRED_STORE}")
            elif _is_volume(source):
                problems.append(f"{name}: mounts {source} at {target}")
    problems += [
        f"the volume {volume} is declared"
        for volume in (compose.get("volumes") or {})
        if volume.endswith("_memory_data")
    ]
    return problems


def test_no_agent_mounts_a_store():
    """Bug caught: a branch from before #2184 merged or rebased back in with an agent's store
    volume, so a store comes back that nothing reads and the next re-inventory has to account
    for it; or an agent given a volume of its own for state that belongs in Postgres."""
    compose = _compose()
    agents = [name for name, service in compose["services"].items() if _is_agent(service)]

    assert len(agents) >= 8, f"the eight agent services are built from {_AGENT_DOCKERFILE}"
    assert _store_problems(compose) == []


def _agent(volumes=None, environment=None) -> dict:
    service: dict = {"build": {"dockerfile": _AGENT_DOCKERFILE}}
    if volumes is not None:
        service["volumes"] = volumes
    if environment is not None:
        service["environment"] = environment
    return service


@pytest.mark.parametrize(
    ("compose", "expected"),
    [
        pytest.param(
            {"services": {"eve": _agent(["eve_memory_data:/app/data/memory_db"])}},
            ["eve: mounts eve_memory_data at the retired store /app/data/memory_db"],
            id="the #2112 mount restored",
        ),
        pytest.param(
            {"services": {"eve": _agent(["./data/eve:/app/data/memory_db:rw"])}},
            ["eve: mounts ./data/eve at the retired store /app/data/memory_db"],
            id="a bind mount at the store path",
        ),
        pytest.param(
            {"services": {"eve": _agent(["${EVE_DATA:-/srv/eve}:/app/data/memory_db"])}},
            ["eve: mounts ${EVE_DATA:-/srv/eve} at the retired store /app/data/memory_db"],
            id="an interpolated host path at the store path",
        ),
        pytest.param(
            {"services": {"eve": _agent(["eve_state:/app/state"])}},
            ["eve: mounts eve_state at /app/state"],
            id="a named volume elsewhere",
        ),
        pytest.param(
            {"services": {"eve": _agent(["/app/state"])}},
            ["eve: mounts an anonymous volume at /app/state"],
            id="an anonymous volume",
        ),
        pytest.param(
            {
                "services": {
                    "eve": _agent([{"type": "volume", "source": "eve_state", "target": "/s"}])
                }
            },
            ["eve: mounts eve_state at /s"],
            id="long syntax",
        ),
        pytest.param(
            {"services": {"eve": _agent(environment=["MEMORY_DB_PATH=/tmp/memory_db"])}},
            ["eve: sets MEMORY_DB_PATH"],
            id="the store path set in a list environment",
        ),
        pytest.param(
            {"services": {"eve": _agent()}, "volumes": {"eve_memory_data": {}}},
            ["the volume eve_memory_data is declared"],
            id="a store volume declared, unmounted",
        ),
    ],
)
def test_a_store_is_named(compose, expected):
    """Bug caught: a check that passes the shapes it exists to refuse."""
    assert _store_problems(compose) == expected


def test_host_files_and_other_services_are_not_stores():
    """Bug caught: the check refusing neo's bind mounts of the compose file and the Docker socket,
    a ``${VAR}`` host path, or reaching services not built as agents, whose volumes are theirs."""
    compose = {
        "services": {
            "neo": _agent(
                [
                    "./docker-compose.yml:/app/docker-compose.yml",
                    "/var/run/docker.sock:/var/run/docker.sock",
                    "${SQUADOPS_SANDBOX_ROOT:-/tmp/s}:${SQUADOPS_SANDBOX_ROOT:-/tmp/s}",
                ]
            ),
            "postgres": {"image": "postgres:15", "volumes": ["postgres_data:/var/lib/data"]},
        },
        "volumes": {"postgres_data": {}},
    }

    assert _store_problems(compose) == []
