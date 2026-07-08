"""
Code ↔ realm-export parity guards (#326).

The #270 role→scope bridge only works if every Role constant is backed by a
realm role in the Keycloak exports — a rename or dropped role on either side
silently strips permissions (exactly the class of bug behind #270). These
tests pin the two surfaces together.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from squadops.auth.models import ROLE_SCOPES, Role, Scope

pytestmark = pytest.mark.auth

_REPO_ROOT = Path(__file__).resolve().parents[3]
_AUTH_DIR = _REPO_ROOT / "infra" / "auth"
_REALM_FILES = [
    "squadops-realm.json",
    "squadops-realm-local.json",
    "squadops-realm-cloud.json",
    "squadops-realm-lab.json",
]


def _load(fname: str) -> dict:
    return json.loads((_AUTH_DIR / fname).read_text())


@pytest.mark.parametrize("fname", _REALM_FILES)
class TestRealmParity:
    def test_every_code_role_exists_in_realm(self, fname):
        realm_roles = {r["name"] for r in _load(fname)["roles"]["realm"]}
        missing = set(ROLE_SCOPES) - realm_roles
        assert not missing, (
            f"{fname} lacks realm role(s) {sorted(missing)} that ROLE_SCOPES "
            "maps — tokens carrying them would imply no scopes"
        )

    def test_agent_client_is_confidential_service_account(self, fname):
        """#326: the squadops-agent client must exist, be confidential, and
        have service accounts on — otherwise agent containers cannot acquire
        heartbeat tokens via client credentials."""
        clients = {c["clientId"]: c for c in _load(fname)["clients"]}
        agent = clients.get("squadops-agent")
        assert agent is not None, f"{fname} missing squadops-agent client"
        assert agent["publicClient"] is False
        assert agent["serviceAccountsEnabled"] is True

    def test_agent_client_token_carries_runtime_audience(self, fname):
        """runtime-api validates aud=squadops-runtime; without the audience
        mapper every agent token would be rejected at validation."""
        clients = {c["clientId"]: c for c in _load(fname)["clients"]}
        agent = clients["squadops-agent"]
        audiences = [
            m["config"]["included.client.audience"]
            for m in agent.get("protocolMappers", [])
            if m.get("protocolMapper") == "oidc-audience-mapper"
        ]
        assert "squadops-runtime" in audiences

    def test_agent_service_account_holds_only_agent_role(self, fname):
        """Least privilege: the agent service account gets the agent role and
        nothing else (agents:write only — no cycle/task/admin scopes)."""
        users = {u.get("username"): u for u in _load(fname).get("users", [])}
        svc = users.get("service-account-squadops-agent")
        assert svc is not None, f"{fname} missing agent service-account user"
        assert svc.get("serviceAccountClientId") == "squadops-agent"
        assert svc.get("realmRoles") == ["agent"]


class TestAgentRoleScopes:
    def test_agent_role_implies_exactly_agents_write(self):
        """The agent role must grant agents:write (or heartbeats 403) and
        nothing more (an agent identity must not gain cycle/task/admin
        access if someone fattens the mapping)."""
        assert ROLE_SCOPES[Role.AGENT] == frozenset({Scope.AGENTS_WRITE})
