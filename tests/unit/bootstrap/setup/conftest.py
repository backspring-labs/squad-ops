"""Fixtures for bootstrap profile tests (SIP-0081)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml


@pytest.fixture()
def tmp_profile_dir(tmp_path: Path) -> Path:
    """Return a temporary directory for bootstrap profile YAML files."""
    d = tmp_path / "profiles"
    d.mkdir()
    return d


def _write_profile(directory: Path, name: str, data: dict) -> Path:
    """Write a profile YAML file and return its path."""
    path = directory / f"{name}.yaml"
    path.write_text(yaml.dump(data, default_flow_style=False), encoding="utf-8")
    return path


@pytest.fixture()
def valid_profile_data() -> dict:
    """Return a fully populated valid profile dict."""
    return {
        "schema_version": 1,
        "name": "test-profile",
        "description": "A test profile",
        "platform": {
            "os": "darwin",
            "min_version": "14.0",
        },
        "python": {
            "version": "3.11",
            "manager": "pyenv",
            "extras": [],
            "test_deps": "tests/requirements.txt",
        },
        "system_deps": [
            {
                "name": "git",
                "check": "git --version",
                "install": "brew",
                "package": "git",
                "required": True,
            },
        ],
        "docker_services": [
            {
                "name": "postgres",
                "healthcheck": "tcp",
                "port": 5432,
                "timeout_seconds": 30,
            },
        ],
        "ollama_models": [
            {"name": "qwen2.5:7b", "required": True},
        ],
        "deployment_profile": "dev",
        "squad_profile": "full-squad",
    }


@pytest.fixture()
def minimal_profile_data() -> dict:
    """Return a minimal valid profile dict (only required fields)."""
    return {
        "schema_version": 1,
        "name": "minimal",
        "platform": {"os": "linux"},
        "python": {"version": "3.11", "manager": "system"},
    }


@pytest.fixture()
def write_profile(tmp_profile_dir: Path):
    """Factory fixture to write a profile YAML file."""

    def _writer(name: str, data: dict) -> Path:
        return _write_profile(tmp_profile_dir, name, data)

    return _writer
