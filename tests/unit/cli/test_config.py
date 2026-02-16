"""
Unit tests for CLI config loading (SIP-0065 §6.2).
"""

import time
from unittest.mock import patch

from squadops.cli.auth import CachedToken, save_token
from squadops.cli.config import CLIConfig, load_config, resolve_token


class TestCLIConfigDefaults:
    """Default config values."""

    def test_default_base_url(self):
        cfg = CLIConfig()
        assert cfg.base_url == "http://localhost:8001"

    def test_default_timeout(self):
        assert CLIConfig().timeout == 30

    def test_default_auth_mode(self):
        assert CLIConfig().auth_mode == "token"

    def test_default_token_env(self):
        assert CLIConfig().token_env == "SQUADOPS_TOKEN"

    def test_default_output_format(self):
        assert CLIConfig().output_format == "table"

    def test_default_tls_verify(self):
        assert CLIConfig().tls_verify is True


class TestLoadConfig:
    """Config loading from TOML files."""

    def test_falls_back_to_defaults_when_no_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        cfg = load_config()
        assert cfg.base_url == "http://localhost:8001"
        assert cfg.timeout == 30

    def test_loads_from_toml(self, tmp_path, monkeypatch):
        config_dir = tmp_path / "squadops"
        config_dir.mkdir()
        config_file = config_dir / "config.toml"
        config_file.write_text(
            '[api]\nbase_url = "http://prod:9000"\ntimeout = 60\n'
            '[auth]\nmode = "token"\ntoken_env = "MY_TOKEN"\n'
            '[output]\nformat = "json"\n'
        )
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        cfg = load_config()
        assert cfg.base_url == "http://prod:9000"
        assert cfg.timeout == 60
        assert cfg.token_env == "MY_TOKEN"
        assert cfg.output_format == "json"

    def test_respects_xdg_config_home(self, tmp_path, monkeypatch):
        custom_xdg = tmp_path / "custom_xdg"
        config_dir = custom_xdg / "squadops"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "config.toml"
        config_file.write_text('[api]\nbase_url = "http://xdg:1234"\n')
        monkeypatch.setenv("XDG_CONFIG_HOME", str(custom_xdg))
        cfg = load_config()
        assert cfg.base_url == "http://xdg:1234"

    def test_partial_config_merges_with_defaults(self, tmp_path, monkeypatch):
        config_dir = tmp_path / "squadops"
        config_dir.mkdir()
        (config_dir / "config.toml").write_text("[api]\ntimeout = 99\n")
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        cfg = load_config()
        assert cfg.timeout == 99
        assert cfg.base_url == "http://localhost:8001"  # default preserved

    def test_tls_verify_false(self, tmp_path, monkeypatch):
        config_dir = tmp_path / "squadops"
        config_dir.mkdir()
        (config_dir / "config.toml").write_text("[api]\ntls_verify = false\n")
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        cfg = load_config()
        assert cfg.tls_verify is False


class TestResolveToken:
    """Auth token resolution — D4 hierarchy: flag > env var > config."""

    def test_flag_wins_over_env(self, monkeypatch):
        monkeypatch.setenv("SQUADOPS_TOKEN", "env_token")
        cfg = CLIConfig()
        token = resolve_token(cfg, token_flag="flag_token")
        assert token == "flag_token"

    def test_env_var_when_no_flag(self, monkeypatch):
        monkeypatch.setenv("SQUADOPS_TOKEN", "env_token")
        cfg = CLIConfig()
        token = resolve_token(cfg)
        assert token == "env_token"

    def test_custom_token_env(self, monkeypatch):
        monkeypatch.setenv("MY_CUSTOM_TOKEN", "custom_val")
        cfg = CLIConfig(token_env="MY_CUSTOM_TOKEN")
        token = resolve_token(cfg)
        assert token == "custom_val"

    def test_none_when_no_token_at_any_level(self, monkeypatch, tmp_path):
        monkeypatch.delenv("SQUADOPS_TOKEN", raising=False)
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        cfg = CLIConfig()
        token = resolve_token(cfg)
        assert token is None


class TestResolveTokenCachedFile:
    """Cached token file layer in resolve_token hierarchy."""

    def test_returns_cached_token_when_valid(self, tmp_path, monkeypatch):
        monkeypatch.delenv("SQUADOPS_TOKEN", raising=False)
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        save_token(
            CachedToken(
                access_token="cached_access",
                refresh_token="ref",
                expires_at=time.time() + 300,
                token_endpoint="http://kc/token",
                client_id="cli",
                grant_type="password",
            )
        )
        token = resolve_token(CLIConfig())
        assert token == "cached_access"

    def test_env_var_wins_over_cached_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SQUADOPS_TOKEN", "env_token")
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        save_token(
            CachedToken(
                access_token="cached_access",
                refresh_token=None,
                expires_at=time.time() + 300,
                token_endpoint="http://kc/token",
                client_id="cli",
                grant_type="password",
            )
        )
        assert resolve_token(CLIConfig()) == "env_token"

    def test_expired_token_triggers_refresh(self, tmp_path, monkeypatch):
        monkeypatch.delenv("SQUADOPS_TOKEN", raising=False)
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        save_token(
            CachedToken(
                access_token="old",
                refresh_token="ref",
                expires_at=time.time() - 100,
                token_endpoint="http://kc/token",
                client_id="cli",
                grant_type="password",
            )
        )
        refreshed = CachedToken(
            access_token="refreshed_access",
            refresh_token="new_ref",
            expires_at=time.time() + 300,
            token_endpoint="http://kc/token",
            client_id="cli",
            grant_type="password",
        )
        with patch("squadops.cli.auth.refresh_access_token", return_value=refreshed):
            token = resolve_token(CLIConfig())
        assert token == "refreshed_access"

    def test_expired_no_refresh_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.delenv("SQUADOPS_TOKEN", raising=False)
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        save_token(
            CachedToken(
                access_token="old",
                refresh_token=None,
                expires_at=time.time() - 100,
                token_endpoint="http://kc/token",
                client_id="cli",
                grant_type="password",
            )
        )
        assert resolve_token(CLIConfig()) is None

    def test_refresh_failure_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.delenv("SQUADOPS_TOKEN", raising=False)
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        save_token(
            CachedToken(
                access_token="old",
                refresh_token="ref",
                expires_at=time.time() - 100,
                token_endpoint="http://kc/token",
                client_id="cli",
                grant_type="password",
            )
        )
        with patch("squadops.cli.auth.refresh_access_token", return_value=None):
            assert resolve_token(CLIConfig()) is None
