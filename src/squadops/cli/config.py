"""
CLI configuration loading (SIP-0065 §6.2).

Loads from ~/.config/squadops/config.toml (or $XDG_CONFIG_HOME/squadops/config.toml).
Falls back to defaults if no config file exists.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CLIConfig:
    """CLI configuration with sensible defaults."""

    base_url: str = "http://localhost:8001"
    timeout: int = 30
    auth_mode: str = "token"  # "token" only in v0.9.4
    token_env: str = "SQUADOPS_TOKEN"
    output_format: str = "table"  # "table" | "json"
    tls_verify: bool = True


def _config_dir() -> Path:
    """Resolve config directory respecting XDG_CONFIG_HOME."""
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "squadops"
    return Path.home() / ".config" / "squadops"


def _config_path() -> Path:
    return _config_dir() / "config.toml"


def load_config() -> CLIConfig:
    """Load CLI config from TOML file, falling back to defaults.

    Returns:
        CLIConfig with values from config file merged over defaults.
    """
    path = _config_path()
    if not path.is_file():
        return CLIConfig()

    with open(path, "rb") as f:
        raw = tomllib.load(f)

    kwargs: dict = {}

    # [api] section
    api = raw.get("api", {})
    if "base_url" in api:
        kwargs["base_url"] = api["base_url"]
    if "timeout" in api:
        kwargs["timeout"] = api["timeout"]
    if "tls_verify" in api:
        kwargs["tls_verify"] = api["tls_verify"]

    # [auth] section
    auth = raw.get("auth", {})
    if "mode" in auth:
        kwargs["auth_mode"] = auth["mode"]
    if "token_env" in auth:
        kwargs["token_env"] = auth["token_env"]

    # [output] section
    output = raw.get("output", {})
    if "format" in output:
        kwargs["output_format"] = output["format"]

    return CLIConfig(**kwargs)


def resolve_token(config: CLIConfig, token_flag: str | None = None) -> str | None:
    """Resolve auth token using hierarchy: flag > env var > cached file > None.

    The cached file layer loads ``~/.config/squadops/token.json``, auto-refreshes
    if the access token is expired but a refresh token is available, and persists
    the refreshed token back to disk.

    Args:
        config: CLI configuration.
        token_flag: Explicit --token flag value (highest priority).

    Returns:
        Token string or None if no token found at any level.
    """
    # 1. CLI flag (highest priority)
    if token_flag:
        return token_flag
    # 2. Env var
    env_token = os.environ.get(config.token_env)
    if env_token:
        return env_token
    # 3. Cached token file (with auto-refresh)
    from squadops.cli.auth import (
        is_expired,
        load_cached_token,
        refresh_access_token,
        save_token,
    )

    cached = load_cached_token()
    if cached is not None:
        if not is_expired(cached):
            return cached.access_token
        # Expired — try refresh
        refreshed = refresh_access_token(cached)
        if refreshed is not None:
            save_token(refreshed)
            return refreshed.access_token
    # 4. No token found
    return None
