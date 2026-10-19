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


class _ScriptedToken:
    """The admin-token endpoint answering each request in turn: a status code, ``"refused"``, or
    the token; with a clock the retry's pauses advance."""

    def __init__(self, answers):
        self.answers, self.calls, self.now = list(answers), 0, 0.0

    def __call__(self, base_url, admin, password):
        import urllib.error

        self.calls += 1
        answer = self.answers.pop(0) if self.answers else self.last
        self.last = answer
        if answer == "refused":
            raise urllib.error.URLError("Connection refused")
        if isinstance(answer, int):
            raise urllib.error.HTTPError(base_url, answer, "Bad Request", None, None)
        return answer

    def sleep(self, seconds):
        self.now += seconds


@pytest.mark.parametrize(
    ("answers", "calls"),
    [([400, 400, "t"], 3), ([503, "t"], 2), (["refused", "t"], 2)],
    ids=["pool-recovering", "starting", "not-listening"],
)
def test_the_sync_waits_out_a_keycloak_that_is_recovering(monkeypatch, capsys, answers, calls):
    """#2426, entered at the sync's ``main``, as the deploy runs it. Bug caught: the 2026-10-18
    MacBook deploy recreated Postgres under a running Keycloak, whose first token request drew a
    dead pooled connection and was answered 400; the sync gave up at once, and the realms went
    without the exports' new clients and roles."""
    token = _ScriptedToken(answers)
    monkeypatch.setenv("KEYCLOAK_ADMIN_PASSWORD", "x")
    monkeypatch.setattr(sync, "admin_token", token)
    monkeypatch.setattr(sync, "_clock", lambda: token.now)
    monkeypatch.setattr(sync, "_sleep", token.sleep)
    monkeypatch.setattr(sync, "_request", lambda *a, **k: (404, {}))
    monkeypatch.setattr(sync, "sync_export", lambda base_url, tok, export: f"synced with {tok}")

    assert sync.main([str(_ROOT / "infra" / "auth" / "squadops-realm.json")]) == 0

    assert token.calls == calls
    captured = capsys.readouterr()
    assert "synced with t" in captured.out
    assert "retrying" in captured.err


@pytest.mark.parametrize(
    ("answers", "calls"),
    [([401], 1), ([400], 1 + sync.TOKEN_RETRY_SECONDS // 3)],
    ids=["wrong-password-at-once", "still-failing-at-the-deadline"],
)
def test_the_sync_fails_when_waiting_cannot_help_or_has_run_out(
    monkeypatch, capsys, answers, calls
):
    """Bugs caught: a wrong password retried for a minute before it is reported, and a Keycloak
    that never recovers retried forever, so the deploy hangs rather than fails."""
    token = _ScriptedToken(answers)
    monkeypatch.setenv("KEYCLOAK_ADMIN_PASSWORD", "x")
    monkeypatch.setattr(sync, "admin_token", token)
    monkeypatch.setattr(sync, "_clock", lambda: token.now)
    monkeypatch.setattr(sync, "_sleep", token.sleep)

    assert sync.main([str(_ROOT / "infra" / "auth" / "squadops-realm.json")]) == 1

    assert token.calls == calls
    assert f"admin token failed: HTTP Error {answers[0]}" in capsys.readouterr().err


# --------------------------------------------------------------------------------------------
# #2464 (the owner's ruling of 2026-10-18): the supervisor, a user a realm created before it lacks
# --------------------------------------------------------------------------------------------


class _RealmLackingAUser:
    """A live realm's admin API with no ``squadops-supervisor`` until one is created, and the
    realm roles ``roles``; with the requests made of it."""

    def __init__(self, *, roles=("campaign-supervisor",), exists=False):
        self.roles, self.users = set(roles), ([{"id": "u-sup"}] if exists else [])
        self.calls: list[tuple[str, str, object]] = []

    def __call__(self, base_url, token, method, path, body=None):
        self.calls.append((method, path, body))
        if method == "GET" and "/users?" in path:
            return 200, list(self.users)
        if method == "GET" and "/roles/" in path:
            name = path.rsplit("/", 1)[1]
            return (200, {"id": f"r-{name}", "name": name}) if name in self.roles else (404, None)
        if method == "POST" and path.endswith("/users"):
            self.users = [{"id": "u-sup", **body}]
            return 201, None
        if method == "POST" and path.endswith("/users/u-sup/role-mappings/realm"):
            return 204, None
        if method == "PUT" and path.endswith("/users/u-sup/reset-password"):
            return 204, None
        return 404, None

    def writes(self):
        return [(m, p, b) for m, p, b in self.calls if m != "GET"]


def _supervisor(export_name: str = "squadops-realm-local.json") -> dict:
    export = json.loads((_ROOT / "infra" / "auth" / export_name).read_text())
    return sync.declared_users(export, {"squadops-supervisor"})["squadops-supervisor"]


def test_a_declared_user_the_realm_lacks_is_created_with_its_roles_and_no_credential(monkeypatch):
    """The Spark's realms predate the supervisor, and ``partialImport`` never carries users. Bug
    caught: the user never reaching an existing realm, so the suite is drafted as the admin; or
    created with no role, or with a password from the export."""
    realm = _RealmLackingAUser()
    monkeypatch.setattr(sync, "_request", realm)

    line = sync.create_missing_user("http://kc", "t", "squadops-local", _supervisor())

    assert line.endswith("user created with ['campaign-supervisor']")
    (_, create_path, created), mapping = realm.writes()
    assert create_path == "/admin/realms/squadops-local/users"
    assert created["username"] == "squadops-supervisor" and created["enabled"] is True
    assert "credentials" not in created and "realmRoles" not in created
    assert mapping == (
        "POST",
        "/admin/realms/squadops-local/users/u-sup/role-mappings/realm",
        [{"id": "r-campaign-supervisor", "name": "campaign-supervisor"}],
    )


@pytest.mark.parametrize(
    ("realm", "said"),
    [
        (_RealmLackingAUser(exists=True), "user exists, left as it is"),
        (_RealmLackingAUser(roles=()), "realm role 'campaign-supervisor' not found"),
    ],
    ids=["it-exists", "its-role-is-missing"],
)
def test_an_existing_user_is_never_changed_and_a_half_made_one_never_left(monkeypatch, realm, said):
    """Bug caught: a deploy rewriting a person's roles back to the export's; or a user created
    before its role is found, left in the realm with no role the next sync would add."""
    monkeypatch.setattr(sync, "_request", realm)

    line = sync.create_missing_user("http://kc", "t", "squadops-local", _supervisor())

    assert said in line
    assert realm.writes() == []


def test_only_a_registry_named_person_is_declared_never_a_seed_or_a_service_account():
    export = {
        "users": [
            {"username": "squadops-supervisor", "realmRoles": ["campaign-supervisor"]},
            {"username": "dev-seed", "realmRoles": ["viewer"]},
            {"username": "service-account-x", "serviceAccountClientId": "x", "realmRoles": ["a"]},
        ]
    }

    assert set(sync.declared_users(export, {"squadops-supervisor", "service-account-x"})) == {
        "squadops-supervisor"
    }


def test_the_sync_creates_the_supervisor_then_gives_it_the_deploys_password(monkeypatch, capsys):
    """The wiring, entered at the sync's ``main`` with the real export and registry: the user is
    created before its password is set, from ``.env``'s value."""
    realm = _RealmLackingAUser()

    def answering(base_url, token, method, path, body=None):
        if method == "GET" and path == "/admin/realms/squadops-local":
            return 200, {"realm": "squadops-local"}
        if path.endswith("/partialImport"):
            return 200, {"added": 0, "skipped": 9, "overwritten": 0}
        if "/clients?" in path or "/service-account-user" in path:
            return 404, None
        return realm(base_url, token, method, path, body)

    monkeypatch.setenv("KEYCLOAK_ADMIN_PASSWORD", "x")
    monkeypatch.setattr(sync, "admin_token", lambda *a: "t")
    monkeypatch.setattr(sync, "_request", answering)
    monkeypatch.setattr(sync, "holds_password", lambda *a: False)
    monkeypatch.setattr(sync, "client_secrets", lambda registry, env: {})
    monkeypatch.setattr(
        sync, "read_env", lambda path: {"SQUADOPS_SUPERVISOR_PASSWORD": "supervisor-own"}
    )

    assert sync.main([str(_ROOT / "infra" / "auth" / "squadops-realm-local.json")]) == 0

    out = capsys.readouterr().out
    assert out.index("squadops-supervisor: user created") < out.index(
        "squadops-supervisor: password set from .env"
    )
    [reset] = [b for m, p, b in realm.calls if m == "PUT"]
    assert reset["value"] == "supervisor-own" and reset["temporary"] is False


@pytest.mark.parametrize(
    "export_name",
    [
        "squadops-realm.json",
        "squadops-realm-local.json",
        "squadops-realm-cloud.json",
        "squadops-realm-lab.json",
    ],
)
def test_every_realms_supervisor_can_draft_a_suite_and_never_approve_one(export_name):
    """D2 as the owner ruled it (2026-10-18): the supervisor drafts, the owner approves. Bug
    caught: the supervisor given a role that approves, so one identity both drafts and approves
    the held-out suite; or a realm with no supervisor, or one that asks the admin for MFA and
    not the supervisor."""
    from squadops.auth.models import Scope, scopes_for_roles

    export = json.loads((_ROOT / "infra" / "auth" / export_name).read_text())
    admin = next(u for u in export["users"] if u["username"] == "squadops-admin")
    roles = set(_supervisor(export_name)["realmRoles"])
    scopes = scopes_for_roles(tuple(roles))

    assert Scope.SCENARIOS_DRAFT in scopes and Scope.SCENARIOS_APPROVE not in scopes
    assert roles - {"campaign-supervisor"} == set(admin["realmRoles"]) & {"mfa-required"}
