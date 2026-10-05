"""#2006: each deploy's credentials are its own.

What bugs would these catch?
- A new deploy written with a value the repository commits, which is the defect: every
  bootstrapped deploy shared fifteen of them (the v2.0.0 records scan).
- A deploy that predates #2006 given new values on its next deploy, so its services, which still
  hold the old ones, lock themselves out (Postgres applies a password only at initdb).
- A value ``.env`` holds being changed by a deploy. Rotation is deliberate, never a side effect.
- A secret file that disagrees with ``.env``, which is the agents-cannot-authenticate shape of
  #326 and #371.
"""

from __future__ import annotations

import importlib.util
import json
import stat
import sys
from pathlib import Path

import pytest

from squadops.bootstrap.setup.checks import check_deploy_credentials
from squadops.bootstrap.setup.credentials import (
    REGISTRY,
    load_registry,
    plan,
    problems,
    rotation_targets,
    value_from_secret_file,
)

_REPO = Path(__file__).resolve().parents[4]
REGISTRY_ROWS = load_registry()
COMMITTED = {v for c in REGISTRY_ROWS for v in c["committed"]}
_DSN = next(c for c in REGISTRY_ROWS if c["env"] == "KEYCLOAK_DB_PASSWORD")


def _counter():
    n = iter(range(1000))
    return lambda: f"generated-{next(n)}"


def test_a_new_deploy_generates_every_credential_and_commits_none():
    decided = plan(REGISTRY_ROWS, {}, {}, existing=False, new_value=_counter())

    assert set(decided.env_updates) == {c["env"] for c in REGISTRY_ROWS}
    assert {how for _v, how in decided.env_updates.values()} == {"generated"}
    assert not COMMITTED & {v for v, _how in decided.env_updates.values()}
    # Every secret file is derived from the value .env got, through its format.
    value = decided.env_updates["KEYCLOAK_DB_PASSWORD"][0]
    assert decided.secret_writes["secrets/keycloak_db_dsn.txt"] == (
        f"postgresql://keycloak:{value}@postgres:5432/keycloak"
    )


def test_an_existing_deploy_adopts_what_it_runs_with_and_generates_only_what_it_never_had():
    """The secret file it already has wins over the registry's legacy value; a credential with no
    legacy value (the sandbox token, which had no home) is generated."""
    held = {"secrets/keycloak_admin_password.txt": "kept-admin\n"}

    decided = plan(REGISTRY_ROWS, {}, held, existing=True, new_value=_counter())

    assert decided.env_updates["KEYCLOAK_ADMIN_PASSWORD"] == ("kept-admin", "adopted")
    assert decided.env_updates["LANGFUSE_SALT"] == ("mysalt", "adopted")
    assert decided.env_updates["SQUADOPS_SANDBOX_SERVICE_TOKEN"][1] == "generated"
    # The adopted file already holds what .env now says: it is not rewritten.
    assert "secrets/keycloak_admin_password.txt" not in decided.secret_writes


def test_a_value_env_holds_is_never_changed_and_its_secret_file_follows_it():
    env = {c["env"]: f"own-{c['env']}" for c in REGISTRY_ROWS}
    held = {
        "secrets/db_password.txt": "own-POSTGRES_PASSWORD\n",  # bootstrap's `cut` newline
        "secrets/rabbitmq_password.txt": "stale",
    }

    decided = plan(REGISTRY_ROWS, env, held, existing=True, new_value=_counter())

    assert decided.env_updates == {}
    assert "secrets/db_password.txt" not in decided.secret_writes
    assert decided.secret_writes["secrets/rabbitmq_password.txt"] == "own-RABBITMQ_PASSWORD"


@pytest.mark.parametrize(
    ("content", "value"),
    [
        ("postgresql://keycloak:s3cret@postgres:5432/keycloak\n", "s3cret"),
        ("postgresql://other:s3cret@postgres:5432/keycloak", None),
    ],
    ids=["its-own-format", "a-different-dsn"],
)
def test_a_secret_file_is_read_back_through_its_format(content, value):
    assert value_from_secret_file(_DSN, content) == value


def test_the_doctor_names_each_credential_missing_or_committed(tmp_path):
    env = {c["env"]: f"own-{c['env']}" for c in REGISTRY_ROWS}
    env["LANGFUSE_SALT"] = "mysalt"
    del env["GRAFANA_ADMIN_PASSWORD"]
    (tmp_path / ".env").write_text("".join(f"{k}={v}\n" for k, v in env.items()))

    found = problems(REGISTRY_ROWS, env)
    result = check_deploy_credentials(tmp_path / ".env")

    assert [line.split(" ")[0] for line in found] == ["LANGFUSE_SALT", "GRAFANA_ADMIN_PASSWORD"]
    assert result.passed is False
    assert result.detail.splitlines() == found


def test_the_doctor_passes_a_deploy_holding_only_its_own(tmp_path):
    (tmp_path / ".env").write_text("".join(f"{c['env']}=own-{c['env']}\n" for c in REGISTRY_ROWS))

    assert check_deploy_credentials(tmp_path / ".env").passed is True


def _script():
    path = _REPO / "scripts" / "dev" / "ops" / "deploy_credentials.py"
    spec = importlib.util.spec_from_file_location("deploy_credentials_script", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_ensure_fills_empty_lines_in_place_appends_the_rest_and_locks_the_secret_files(tmp_path):
    """Entered at ``ensure``, what bootstrap and every deploy call: .env.example's empty
    ``KEY=`` lines are filled where they stand, the rest appended, and each secret file is
    written owner-only."""
    (tmp_path / "infra").mkdir()
    (tmp_path / "infra" / "deploy_credentials.json").write_text(REGISTRY.read_text())
    (tmp_path / ".env").write_text("SQUADOPS_PROFILE=local\nPOSTGRES_PASSWORD=\n")

    decided = _script().ensure(tmp_path, existing=False, dry_run=False)

    lines = (tmp_path / ".env").read_text().splitlines()
    assert lines[:2] == [
        "SQUADOPS_PROFILE=local",
        f"POSTGRES_PASSWORD={decided.env_updates['POSTGRES_PASSWORD'][0]}",
    ]
    assert sum(1 for line in lines if line.startswith("POSTGRES_PASSWORD=")) == 1
    secret = tmp_path / "secrets" / "db_password.txt"
    assert secret.read_text() == decided.env_updates["POSTGRES_PASSWORD"][0]
    assert stat.S_IMODE(secret.stat().st_mode) == 0o600
    # A second run changes nothing.
    assert _script().ensure(tmp_path, existing=True, dry_run=False).env_updates == {}


def test_every_credential_names_what_it_authenticates_and_its_committed_values():
    """The registry is read by bash, a stdlib script and the doctor; a row missing a field
    fails one of them at a deploy rather than here."""
    rows = json.loads(REGISTRY.read_text())["credentials"]
    assert rows and all(
        {"env", "what", "secret_file", "legacy", "committed"} <= set(r) for r in rows
    )
    assert len({r["env"] for r in rows}) == len(rows)


@pytest.mark.parametrize(
    ("only", "keep", "expected"),
    [
        ((), (), ["POSTGRES_PASSWORD", "LANGFUSE_SALT"]),
        ((), ("LANGFUSE_SALT",), ["POSTGRES_PASSWORD"]),
        (("GRAFANA_ADMIN_PASSWORD",), (), ["GRAFANA_ADMIN_PASSWORD"]),
    ],
    ids=["every-committed-one", "the-owner-keeps-the-salt", "a-named-one-even-if-its-own"],
)
def test_a_rotation_replaces_the_committed_or_the_named(only, keep, expected):
    env = {c["env"]: f"own-{c['env']}" for c in REGISTRY_ROWS}
    env.update(POSTGRES_PASSWORD="squadops-dev", LANGFUSE_SALT="mysalt")

    assert rotation_targets(REGISTRY_ROWS, env, only=only, keep=keep) == expected


@pytest.mark.parametrize("field", ["only", "keep"])
def test_a_rotation_naming_no_credential_is_refused(field):
    """Bug caught: a typo in --keep reads as "keep nothing", rotating the one the owner said not
    to (or in --only, as rotating nothing)."""
    with pytest.raises(ValueError, match="LANGFUSE_SLAT"):
        rotation_targets(REGISTRY_ROWS, {}, **{field: ("LANGFUSE_SLAT",)})


def test_rotate_keeps_the_previous_env_and_changes_only_the_targets(tmp_path):
    (tmp_path / "infra").mkdir()
    (tmp_path / "infra" / "deploy_credentials.json").write_text(REGISTRY.read_text())
    before = "".join(f"{c['env']}=own-{c['env']}\n" for c in REGISTRY_ROWS).replace(
        "LANGFUSE_SALT=own-LANGFUSE_SALT", "LANGFUSE_SALT=mysalt"
    )
    (tmp_path / ".env").write_text(before)

    rotated = _script().rotate(tmp_path, only=(), keep=(), dry_run=False)

    after = (tmp_path / ".env").read_text().splitlines()
    [backup] = tmp_path.glob(".env.pre-rotation-*")
    assert rotated == ["LANGFUSE_SALT"]
    assert backup.read_text() == before and stat.S_IMODE(backup.stat().st_mode) == 0o600
    changed = [a for a, b in zip(after, before.splitlines(), strict=True) if a != b]
    assert [line.split("=")[0] for line in changed] == ["LANGFUSE_SALT"]
    assert changed[0] != "LANGFUSE_SALT=mysalt"


def test_a_deploy_whose_container_is_gone_still_counts_as_existing(tmp_path, monkeypatch):
    """Bug caught: after ``docker compose down`` the Postgres container is gone and its volume is
    not. Read as a new deploy, the next ``ensure`` would generate a Keycloak admin password and an
    agent secret the running realm does not hold, and lock the box out."""
    script = _script()
    (tmp_path / "infra").mkdir()
    (tmp_path / "infra" / "deploy_credentials.json").write_text(REGISTRY.read_text())
    monkeypatch.setattr(
        script.subprocess, "run", lambda *a, **k: script.subprocess.CompletedProcess(a, 1)
    )

    assert script.deploy_exists(tmp_path) is False
    (tmp_path / "secrets").mkdir()
    (tmp_path / "secrets" / "agent_client_secret.txt").write_text("held")
    assert script.deploy_exists(tmp_path) is True
