"""A service mounts exactly the secrets its configuration reads (#2498, #2457).

Every SquadOps service resolves ``secret://`` references through the ``docker_secret`` provider,
which reads ``/run/secrets/<name>``. A reference with no mount fails the service at start. A mount
with no reference is a credential the process holds and never reads: until 2.4, every agent held
the runtime API's database password (#2457), and every agent and the runtime API held Keycloak's
admin password and database DSN (#2498). An agent's container runs the builds and tests the squad
generates, so a credential there is reachable by whatever that code does.

What a service reads is its own environment's references and, when it loads a deploy profile, any
profile's (the one it loads is chosen at deploy, ``SQUADOPS_PROFILE``).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

pytestmark = [pytest.mark.domain_contracts]

ROOT = Path(__file__).resolve().parents[3]
_REF = re.compile(r"secret://([A-Za-z0-9_]+)")


def _services() -> dict:
    return yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))["services"]


def _environment(service: dict) -> dict[str, str]:
    env = service.get("environment") or {}
    if isinstance(env, list):
        return dict(entry.split("=", 1) if "=" in entry else (entry, "") for entry in env)
    return {key: str(value) for key, value in env.items()}


def _profiles_reference() -> set[str]:
    return {
        name
        for path in (ROOT / "config" / "profiles").glob("*.yaml")
        for name in _REF.findall(path.read_text(encoding="utf-8"))
    }


def _resolving() -> dict[str, tuple[set[str], set[str]]]:
    """Each service that resolves ``secret://`` references: (what it mounts, what it reads)."""
    out = {}
    for name, service in _services().items():
        env = _environment(service)
        if env.get("SQUADOPS__SECRETS__PROVIDER") != "docker_secret":
            continue
        reads = {ref for value in env.values() for ref in _REF.findall(value)}
        if "SQUADOPS_PROFILE" in env:
            reads |= _profiles_reference()
        mounts = {s if isinstance(s, str) else s["source"] for s in service.get("secrets") or []}
        out[name] = (mounts, reads)
    return out


def test_every_service_mounts_exactly_the_secrets_it_reads():
    """Bug caught: a credential mounted into a service that never reads it (the Keycloak admin
    password in eight agents' containers, #2498), or a reference with no mount, which fails the
    service at start."""
    wrong = {
        name: {
            "mounted, never read": sorted(mounts - reads),
            "read, not mounted": sorted(reads - mounts),
        }
        for name, (mounts, reads) in _resolving().items()
        if mounts != reads
    }
    assert wrong == {}


def test_the_guard_reads_the_runtime_api_and_every_agent():
    """Bug caught: the guard above reading no service, after a changed provider name or compose
    shape, and passing on nothing. The runtime API reads the database password: the paired
    control, so the guard is known to see a reference where it is."""
    resolving = _resolving()
    assert len(resolving) >= 9
    assert "db_password" in resolving["runtime-api"][1]
