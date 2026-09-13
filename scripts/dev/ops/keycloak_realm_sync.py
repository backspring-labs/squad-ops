#!/usr/bin/env python3
"""Re-sync the realm exports into Keycloak realms that already exist (#372).

Keycloak's ``--import-realm`` imports a realm only when it does not exist yet; every
later change to ``infra/auth/squadops-realm*.json`` — a new client, a role, a mapper —
silently never reaches an environment whose realm is already in the Keycloak DB (#326's
``squadops-agent`` client was the first casualty). This runs after Keycloak is healthy in
the deploy: for every export the compose mounts, if its realm exists, ``partialImport``
the export with ``ifResourceExists=SKIP`` — idempotent and non-destructive (adds what is
missing, leaves existing resources and users alone).

stdlib only, so any deploy pipeline can call it. Usage:

    keycloak_realm_sync.py [--base-url http://localhost:8180] [--admin admin]
                           [--password-file secrets/keycloak_admin_password.txt] EXPORT...
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

#: What a partial import carries. Users are deliberately absent: a realm export's users
#: are dev seeds, and re-importing them would be the one destructive thing this can do.
PARTIAL_IMPORT_SECTIONS = ("clients", "roles", "groups", "identityProviders", "clientScopes")


def partial_import_payload(export: dict) -> dict:
    """The body ``POST /admin/realms/{realm}/partialImport`` takes, from a realm export."""
    payload: dict = {"ifResourceExists": "SKIP"}
    for section in PARTIAL_IMPORT_SECTIONS:
        if export.get(section):
            payload[section] = export[section]
    return payload


def admin_token(base_url: str, admin: str, password: str) -> str:
    body = urllib.parse.urlencode(
        {
            "grant_type": "password",
            "client_id": "admin-cli",
            "username": admin,
            "password": password,
        }
    ).encode()
    req = urllib.request.Request(
        f"{base_url}/realms/master/protocol/openid-connect/token",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.load(resp)["access_token"]


def _request(base_url: str, token: str, method: str, path: str, body: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{base_url}{path}",
        data=data,
        method=method,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as exc:
        return exc.code, None


def sync_export(base_url: str, token: str, export_path: Path) -> str:
    """One export: skip a realm Keycloak does not have (``--import-realm`` owns first
    creation), else partial-import and report what was added / skipped."""
    export = json.loads(export_path.read_text())
    realm = export["realm"]
    status, _ = _request(base_url, token, "GET", f"/admin/realms/{realm}")
    if status == 404:
        return f"{export_path.name}: realm {realm!r} does not exist yet — left to --import-realm"
    if status != 200:
        return f"{export_path.name}: realm {realm!r} lookup returned {status}"
    status, result = _request(
        base_url,
        token,
        "POST",
        f"/admin/realms/{realm}/partialImport",
        partial_import_payload(export),
    )
    if status != 200 or not isinstance(result, dict):
        return f"{export_path.name}: partialImport of {realm!r} returned {status}"
    return (
        f"{export_path.name}: realm {realm!r} synced — added {result.get('added', 0)}, "
        f"skipped {result.get('skipped', 0)}, overwritten {result.get('overwritten', 0)}"
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("exports", nargs="+", type=Path)
    ap.add_argument(
        "--base-url", default=os.environ.get("KEYCLOAK_BASE_URL", "http://localhost:8180")
    )
    ap.add_argument("--admin", default=os.environ.get("KEYCLOAK_ADMIN", "admin"))
    ap.add_argument(
        "--password-file", type=Path, default=Path("secrets/keycloak_admin_password.txt")
    )
    args = ap.parse_args(argv)
    password = os.environ.get("KEYCLOAK_ADMIN_PASSWORD") or (
        args.password_file.read_text().strip() if args.password_file.exists() else ""
    )
    if not password:
        print(
            "keycloak_realm_sync: no admin password (KEYCLOAK_ADMIN_PASSWORD or --password-file)",
            file=sys.stderr,
        )
        return 2
    try:
        token = admin_token(args.base_url, args.admin, password)
    except (urllib.error.URLError, KeyError, ValueError) as exc:
        print(f"keycloak_realm_sync: admin token failed: {exc}", file=sys.stderr)
        return 1
    for export in args.exports:
        print(sync_export(args.base_url, token, export))
    return 0


if __name__ == "__main__":
    sys.exit(main())
