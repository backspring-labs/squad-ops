"""The realm re-sync reaches existing realms without touching what is there (#372)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location(
    "keycloak_realm_sync", _ROOT / "scripts" / "dev" / "ops" / "keycloak_realm_sync.py"
)
sync = importlib.util.module_from_spec(_spec)
sys.modules["keycloak_realm_sync"] = sync
_spec.loader.exec_module(sync)


def test_the_payload_carries_the_shipped_sections_and_never_users():
    export = {
        "realm": "squadops-dev",
        "clients": [{"clientId": "squadops-agent"}],
        "roles": {"realm": [{"name": "agent"}]},
        "users": [{"username": "dev-seed"}],
        "groups": [],
    }
    payload = sync.partial_import_payload(export)
    assert payload["ifResourceExists"] == "SKIP"
    assert payload["clients"] == [{"clientId": "squadops-agent"}]
    assert payload["roles"] == {"realm": [{"name": "agent"}]}
    assert "users" not in payload and "groups" not in payload


@pytest.mark.parametrize("export_name", ["squadops-realm.json", "squadops-realm-local.json"])
def test_every_mounted_export_yields_a_payload_with_its_clients(export_name):
    export = json.loads((_ROOT / "infra" / "auth" / export_name).read_text())
    payload = sync.partial_import_payload(export)
    assert {c["clientId"] for c in payload["clients"]} >= {"squadops-agent"}


def test_a_missing_realm_is_left_to_import_realm_and_an_existing_one_is_partially_imported(
    tmp_path, monkeypatch
):
    export = tmp_path / "r.json"
    export.write_text(json.dumps({"realm": "squadops-dev", "clients": [{"clientId": "c"}]}))
    calls: list[tuple[str, str]] = []

    def fake_request(base_url, token, method, path, body=None):
        calls.append((method, path))
        if method == "GET":
            return (404 if "missing" in base_url else 200), None
        assert body["ifResourceExists"] == "SKIP" and body["clients"] == [{"clientId": "c"}]
        return 200, {"added": 1, "skipped": 3, "overwritten": 0}

    monkeypatch.setattr(sync, "_request", fake_request)
    assert "left to --import-realm" in sync.sync_export("http://missing", "t", export)
    assert calls == [("GET", "/admin/realms/squadops-dev")]
    calls.clear()
    line = sync.sync_export("http://kc", "t", export)
    assert "added 1, skipped 3" in line
    assert calls == [
        ("GET", "/admin/realms/squadops-dev"),
        ("POST", "/admin/realms/squadops-dev/partialImport"),
    ]


def test_no_password_is_a_refusal_not_a_blank_login(tmp_path, monkeypatch):
    monkeypatch.delenv("KEYCLOAK_ADMIN_PASSWORD", raising=False)
    assert sync.main([str(tmp_path / "x.json"), "--password-file", str(tmp_path / "nope")]) == 2


class _Keycloak:
    """The admin API's answers for one client, and the requests made of it."""

    def __init__(self, current_secret):
        self.current_secret = current_secret
        self.calls = []

    def __call__(self, base_url, token, method, path, body=None):
        self.calls.append((method, path, body))
        if method == "GET" and "/clients?" in path:
            return 200, [{"id": "c-1", "clientId": "squadops-agent", "enabled": True}]
        if method == "GET" and path.endswith("/client-secret"):
            return 200, {"type": "secret", "value": self.current_secret}
        if method == "PUT":
            return 204, None
        return 404, None


@pytest.mark.parametrize(
    ("current", "puts", "said"),
    [
        ("squadops-agent-secret", 1, "secret set from .env"),
        ("own-agent-secret", 0, "secret already the deploy's"),
    ],
    ids=["the-export-seed-is-replaced", "the-deploys-own-is-left-alone"],
)
def test_a_client_secret_is_brought_to_the_deploys_own(monkeypatch, current, puts, said):
    """#2006: a realm the export created holds the export's seed secret, which every deploy
    shared. Bug caught: the seed left in place, or a client re-written on every deploy."""
    keycloak = _Keycloak(current)
    monkeypatch.setattr(sync, "_request", keycloak)

    out = sync.set_client_secret(
        "http://kc", "tok", "squadops-local", "squadops-agent", "own-agent-secret"
    )

    put = [body for method, _path, body in keycloak.calls if method == "PUT"]
    assert len(put) == puts and out.endswith(said)
    if put:
        assert put[0]["secret"] == "own-agent-secret" and put[0]["clientId"] == "squadops-agent"


def test_the_secrets_come_from_env_by_the_registrys_client_names():
    registry = [
        {"env": "SQUADOPS_AGENT_CLIENT_SECRET", "keycloak_client": "squadops-agent"},
        {"env": "SQUADOPS_RUNTIME_CLIENT_SECRET", "keycloak_client": "squadops-runtime"},
        {"env": "POSTGRES_PASSWORD"},
    ]
    env = {"SQUADOPS_AGENT_CLIENT_SECRET": "a", "POSTGRES_PASSWORD": "p"}

    assert sync.client_secrets(registry, env) == {"squadops-agent": "a"}


class _ServiceAccountRealm:
    """A live realm's admin API for one confidential client whose service-account user holds
    ``held``, with the requests made of it."""

    def __init__(self, held: list[str]):
        self.held = [{"id": f"r-{n}", "name": n} for n in held]
        self.calls: list[tuple[str, str, object]] = []

    def __call__(self, base_url, token, method, path, body=None):
        self.calls.append((method, path, body))
        if method == "GET" and path.endswith("/clients?clientId=squadops-agent"):
            return 200, [{"id": "c-1", "clientId": "squadops-agent"}]
        if method == "GET" and path.endswith("/clients/c-1/service-account-user"):
            return 200, {"id": "u-sa", "username": "service-account-squadops-agent"}
        if method == "GET" and path.endswith("/users/u-sa/role-mappings/realm"):
            return 200, list(self.held)
        if method == "GET" and "/roles/" in path:
            name = path.rsplit("/", 1)[1]
            return 200, {"id": f"r-{name}", "name": name}
        if method == "POST" and path.endswith("/users/u-sa/role-mappings/realm"):
            self.held += body
            return 204, None
        return 404, None


def test_a_service_account_missing_its_declared_role_is_granted_it_and_nothing_else(monkeypatch):
    """#2083, entered at the sync's grant with a realm lacking the mapping (squadops-dev's live
    state, 2026-10-05). Bugs caught: the agents' client token carrying no role, so the runtime
    grants it no scope; or the grant touching anything but the service account's own mappings."""
    export = json.loads((_ROOT / "infra" / "auth" / "squadops-realm.json").read_text())
    declared = sync.declared_service_account_roles(export)
    realm = _ServiceAccountRealm(held=["default-roles-squadops"])
    monkeypatch.setattr(sync, "_request", realm)

    line = sync.grant_service_account_roles(
        "http://kc", "t", "squadops-dev", "squadops-agent", declared["squadops-agent"]
    )

    assert declared == {"squadops-agent": ["agent"]}
    assert "granted ['agent']" in line
    [post] = [c for c in realm.calls if c[0] != "GET"]
    assert post == (
        "POST",
        "/admin/realms/squadops-dev/users/u-sa/role-mappings/realm",
        [{"id": "r-agent", "name": "agent"}],
    )
    assert {r["name"] for r in realm.held} == {"default-roles-squadops", "agent"}


def test_a_service_account_already_holding_its_roles_is_left_alone(monkeypatch):
    realm = _ServiceAccountRealm(held=["agent"])
    monkeypatch.setattr(sync, "_request", realm)

    line = sync.grant_service_account_roles(
        "http://kc", "t", "squadops-dev", "squadops-agent", ["agent"]
    )

    assert "already holds ['agent']" in line
    assert [c for c in realm.calls if c[0] != "GET"] == []


def test_a_human_user_in_the_export_is_never_read_as_a_service_account():
    export = {
        "users": [
            {"username": "squadops-admin", "realmRoles": ["admin"]},
            {
                "username": "service-account-squadops-agent",
                "serviceAccountClientId": "squadops-agent",
                "realmRoles": ["agent"],
            },
        ]
    }

    assert sync.declared_service_account_roles(export) == {"squadops-agent": ["agent"]}


def test_the_sync_grants_a_live_realms_service_account_its_declared_role(monkeypatch, capsys):
    """#2083's done-when, entered at the sync's ``main`` with the shipped export and a realm that
    exists and lacks the mapping. Bug caught: the grant written and never called by the sync the
    deploy runs."""
    realm = _ServiceAccountRealm(held=[])

    def answering(base_url, token, method, path, body=None):
        if method == "GET" and path == "/admin/realms/squadops-dev":
            return 200, {"realm": "squadops-dev"}
        if path.endswith("/partialImport"):
            return 200, {"added": 0, "skipped": 9, "overwritten": 0}
        return realm(base_url, token, method, path, body)

    monkeypatch.setenv("KEYCLOAK_ADMIN_PASSWORD", "x")
    monkeypatch.setattr(sync, "admin_token", lambda *a: "t")
    monkeypatch.setattr(sync, "_request", answering)
    monkeypatch.setattr(sync, "client_secrets", lambda registry, env: {})
    monkeypatch.setattr(sync, "user_passwords", lambda registry, env: {})

    assert sync.main([str(_ROOT / "infra" / "auth" / "squadops-realm.json")]) == 0

    assert (
        "squadops-dev/squadops-agent: service account granted ['agent']" in capsys.readouterr().out
    )
    assert {r["name"] for r in realm.held} == {"agent"}


class _UserRealm:
    """A live realm's admin API for one human user, with the requests made of it."""

    def __init__(self, exists: bool = True):
        self.exists = exists
        self.calls: list[tuple[str, str, object]] = []

    def __call__(self, base_url, token, method, path, body=None):
        self.calls.append((method, path, body))
        if method == "GET" and "/users?" in path:
            return 200, ([{"id": "u-admin", "username": "squadops-admin"}] if self.exists else [])
        if method == "PUT" and path.endswith("/users/u-admin/reset-password"):
            return 204, None
        return 404, None


@pytest.mark.parametrize(
    ("holds", "exists", "said", "writes"),
    [
        (True, True, "password already the deploy's", []),
        (
            False,
            True,
            "password set from .env",
            [
                (
                    "PUT",
                    "/admin/realms/squadops-local/users/u-admin/reset-password",
                    {"type": "password", "value": "deploy-own", "temporary": False},
                )
            ],
        ),
        (False, False, "user not found", []),
    ],
)
def test_the_realm_users_password_is_brought_to_the_deploys_own(
    monkeypatch, holds, exists, said, writes
):
    """#2079. Bugs caught: the admin left on the password every realm file committed; a
    non-temporary reset that a password grant then refuses; or a user who already holds the
    deploy's value reset on every deploy."""
    realm = _UserRealm(exists)
    monkeypatch.setattr(sync, "_request", realm)
    monkeypatch.setattr(sync, "holds_password", lambda *a: holds)

    line = sync.set_user_password(
        "http://kc", "t", "squadops-local", "squadops-admin", "deploy-own"
    )

    assert said in line
    assert [c for c in realm.calls if c[0] != "GET"] == writes


def test_the_sync_brings_each_realm_users_password_to_env(monkeypatch, capsys):
    """#2079's wiring, entered at the sync's ``main``: the registry's user password, from .env,
    reaches every synced realm."""
    realm = _UserRealm()

    def answering(base_url, token, method, path, body=None):
        if method == "GET" and path == "/admin/realms/squadops-dev":
            return 200, {"realm": "squadops-dev"}
        if path.endswith("/partialImport"):
            return 200, {"added": 0, "skipped": 9, "overwritten": 0}
        if "/clients?" in path or "/service-account-user" in path or "/role-mappings" in path:
            return 404, None
        return realm(base_url, token, method, path, body)

    monkeypatch.setenv("KEYCLOAK_ADMIN_PASSWORD", "x")
    monkeypatch.setattr(sync, "admin_token", lambda *a: "t")
    monkeypatch.setattr(sync, "_request", answering)
    monkeypatch.setattr(sync, "holds_password", lambda *a: False)
    monkeypatch.setattr(sync, "client_secrets", lambda registry, env: {})
    monkeypatch.setattr(sync, "read_env", lambda path: {"SQUADOPS_ADMIN_PASSWORD": "deploy-own"})

    assert sync.main([str(_ROOT / "infra" / "auth" / "squadops-realm.json")]) == 0

    assert "squadops-dev/squadops-admin: password set from .env" in capsys.readouterr().out
    [put] = [c for c in realm.calls if c[0] == "PUT"]
    assert put[2]["value"] == "deploy-own"


@pytest.mark.parametrize(
    "export_name",
    [
        "squadops-realm.json",
        "squadops-realm-local.json",
        "squadops-realm-cloud.json",
        "squadops-realm-lab.json",
    ],
)
def test_no_realm_export_commits_a_users_password(export_name):
    """#2079. Bug caught: a realm user's password back in an export, so every realm created from
    it signs in with a value anyone with the repository has."""
    export = json.loads((_ROOT / "infra" / "auth" / export_name).read_text())

    assert [u["username"] for u in export.get("users", []) if u.get("credentials")] == []
