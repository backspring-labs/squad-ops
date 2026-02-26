#!/usr/bin/env python3
"""Realm export linter for SIP-0063 Keycloak production hardening.

Validates deployed realm JSON exports against security requirements.
Exit 0 on success, exit 1 with descriptive errors on failure.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# Deployed (non-dev) realm names that the linter validates
_DEPLOYED_REALMS = {"squadops-local", "squadops-lab", "squadops-cloud"}
# Cloud realm requires sslRequired: all; others require external
_CLOUD_REALMS = {"squadops-cloud"}


def lint_realm(realm: dict[str, Any], filename: str) -> list[str]:
    """Validate a single realm export dict. Returns list of error strings."""
    errors: list[str] = []
    realm_name = realm.get("realm", "<unknown>")

    # Determine expected environment from realm name
    is_deployed = realm_name in _DEPLOYED_REALMS
    is_cloud = realm_name in _CLOUD_REALMS

    if not is_deployed:
        errors.append(f"[{filename}] Realm name {realm_name!r} is not a deployed realm — skipping")
        return errors

    # --- Realm name pattern ---
    if not realm_name.startswith("squadops-"):
        errors.append(
            f"[{filename}] Realm name {realm_name!r} does not match expected pattern 'squadops-*'"
        )

    # --- SSL required ---
    ssl_required = realm.get("sslRequired", "none")
    if is_cloud and ssl_required != "all":
        errors.append(f"[{filename}] sslRequired must be 'all' for cloud, got {ssl_required!r}")
    elif not is_cloud and ssl_required != "external":
        errors.append(
            f"[{filename}] sslRequired must be 'external' for deployed realm, got {ssl_required!r}"
        )

    # --- Refresh token rotation ---
    if not realm.get("revokeRefreshToken", False):
        errors.append(f"[{filename}] revokeRefreshToken must be true")
    if realm.get("refreshTokenMaxReuse", -1) != 0:
        errors.append(
            f"[{filename}] refreshTokenMaxReuse must be 0, got {realm.get('refreshTokenMaxReuse', '<missing>')}"
        )

    # --- Events ---
    if not realm.get("eventsEnabled", False):
        errors.append(f"[{filename}] eventsEnabled must be true")
    if not realm.get("adminEventsEnabled", False):
        errors.append(f"[{filename}] adminEventsEnabled must be true")

    # --- Brute force ---
    if not realm.get("bruteForceProtected", False):
        errors.append(f"[{filename}] bruteForceProtected must be true")

    # --- MFA authentication flow ---
    flows = realm.get("authenticationFlows", [])
    flow_aliases = [f.get("alias") for f in flows]
    if "squadops-browser-with-mfa" not in flow_aliases:
        errors.append(f"[{filename}] Missing MFA authentication flow 'squadops-browser-with-mfa'")

    # --- Login theme ---
    login_theme = realm.get("loginTheme")
    if login_theme != "squadops":
        errors.append(f"[{filename}] loginTheme must be 'squadops', got {login_theme!r}")

    # --- Redirect URIs and web origins: no localhost ---
    for client in realm.get("clients", []):
        client_id = client.get("clientId", "<unknown>")
        for uri in client.get("redirectUris", []):
            if "localhost" in uri or "127.0.0.1" in uri:
                errors.append(
                    f"[{filename}] Client {client_id!r} has localhost in redirectUri: {uri!r}"
                )
        for origin in client.get("webOrigins", []):
            if "localhost" in origin or "127.0.0.1" in origin:
                errors.append(
                    f"[{filename}] Client {client_id!r} has localhost in webOrigin: {origin!r}"
                )
        # RP-Initiated Logout requires post.logout.redirect.uris attribute
        if client_id == "squadops-console":
            attrs = client.get("attributes", {})
            post_logout = attrs.get("post.logout.redirect.uris", "")
            if not post_logout:
                errors.append(
                    f"[{filename}] Client {client_id!r} missing"
                    f" attributes.post.logout.redirect.uris"
                )
            elif "localhost" in post_logout or "127.0.0.1" in post_logout:
                errors.append(
                    f"[{filename}] Client {client_id!r} has localhost in"
                    f" post.logout.redirect.uris: {post_logout!r}"
                )

    return errors


def lint_realm_files(file_paths: list[Path]) -> list[str]:
    """Lint multiple realm export files. Returns all errors."""
    all_errors: list[str] = []
    for path in file_paths:
        try:
            with open(path) as f:
                realm = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            all_errors.append(f"[{path.name}] Failed to load: {e}")
            continue
        all_errors.extend(lint_realm(realm, path.name))
    return all_errors


def main() -> int:
    """Entry point: lint deployed realm exports."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    auth_dir = repo_root / "infra" / "auth"

    files = [
        auth_dir / "squadops-realm-staging.json",
        auth_dir / "squadops-realm-lab.json",
        auth_dir / "squadops-realm-prod.json",
    ]

    missing = [f for f in files if not f.exists()]
    if missing:
        for f in missing:
            print(f"ERROR: Realm export not found: {f}")
        return 1

    errors = lint_realm_files(files)
    if errors:
        print(f"Realm lint FAILED — {len(errors)} error(s):")
        for err in errors:
            print(f"  {err}")
        return 1

    print(f"Realm lint PASSED — {len(files)} file(s) validated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
