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
