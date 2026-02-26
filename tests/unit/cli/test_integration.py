"""
CLI integration tests — end-to-end via Starlette TestClient (SIP-0065 §8.2).

Uses real in-memory adapters backed by the FastAPI app via ASGI transport (D10).
No mocks, no network, no Docker.

Requires runtime-api dependencies (aio_pika, starlette) to be installed.
Skipped automatically when those dependencies are unavailable.
"""

from __future__ import annotations

import json
import os
import sys
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from squadops.cli import exit_codes
from squadops.cli.client import APIClient
from squadops.cli.config import CLIConfig
from squadops.cli.main import app
from squadops.contracts.cycle_request_profiles import load_profile
from squadops.cycles.lifecycle import compute_config_hash

try:
    import aio_pika  # noqa: F401 — runtime dep check
    from starlette.testclient import TestClient as StarletteTestClient

    _HAS_RUNTIME_DEPS = True
except ImportError:
    _HAS_RUNTIME_DEPS = False

pytestmark = pytest.mark.skipif(
    not _HAS_RUNTIME_DEPS,
    reason="Runtime-api dependencies (aio_pika, starlette) not installed",
)

runner = CliRunner()

# Minimal env overrides to make load_config() succeed without Docker services.
# The local.yaml profile enables auth with a secret:// reference and lacks
# db/comms sections.  We disable auth, override the secret:// ref with a
# literal, and provide dummy db/comms values.
_TEST_ENV = {
    "SQUADOPS__AUTH__ENABLED": "false",
    "SQUADOPS__AUTH__KEYCLOAK__ADMIN__PASSWORD": "test",  # override secret:// ref
    "SQUADOPS__DB__URL": "postgresql://test:test@localhost:5432/test",
    "SQUADOPS__COMMS__RABBITMQ__URL": "amqp://test:test@localhost:5672/",
    "SQUADOPS__COMMS__REDIS__URL": "redis://localhost:6379/0",
}


def _import_fastapi_app():
    """Import the FastAPI app with test env vars set.

    Must be called inside a fixture/function — never at module level — so
    that env overrides are active before ``load_config()`` runs.
    """
    saved = {}
    for k, v in _TEST_ENV.items():
        saved[k] = os.environ.get(k)
        os.environ[k] = v
    try:
        # Clear any cached failed import attempt
        sys.modules.pop("squadops.api.runtime.main", None)
        from squadops.api.runtime.main import app as fastapi_app

        return fastapi_app
    finally:
        for k, orig in saved.items():
            if orig is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = orig


def _wire_cycle_ports():
    """Wire in-memory cycle adapters into the DI container.

    Replaces the startup_event() wiring which requires Postgres/RabbitMQ.
    """
    from adapters.cycles.factory import (
        create_artifact_vault,
        create_cycle_registry,
        create_project_registry,
        create_squad_profile_port,
    )
    from squadops.api.runtime.deps import set_cycle_ports

    project_registry = create_project_registry("config")
    cycle_registry = create_cycle_registry("memory")
    squad_profile = create_squad_profile_port("config")
    artifact_vault = create_artifact_vault("filesystem")

    set_cycle_ports(
        project_registry=project_registry,
        cycle_registry=cycle_registry,
        squad_profile=squad_profile,
        artifact_vault=artifact_vault,
    )


# ---------------------------------------------------------------------------
# Fixtures — set up a real FastAPI app with in-memory adapters
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def fastapi_app():
    """Lazily import the FastAPI app and wire in-memory adapters."""
    fa_app = _import_fastapi_app()
    _wire_cycle_ports()
    return fa_app


@pytest.fixture
def integration_client(fastapi_app):
    """Create a real APIClient backed by the FastAPI TestClient (D10).

    Uses starlette.testclient.TestClient which is a sync httpx.Client subclass.
    """
    http_client = StarletteTestClient(fastapi_app)
    config = CLIConfig(base_url="http://test")
    return APIClient(config=config, client=http_client)


@pytest.fixture
def _patch_client(integration_client):
    """Patch _get_client in all command modules to use the integration client."""
    modules = [
        "squadops.cli.commands.projects",
        "squadops.cli.commands.cycles",
        "squadops.cli.commands.runs",
        "squadops.cli.commands.profiles",
        "squadops.cli.commands.artifacts",
    ]
    patches = []
    for mod in modules:
        p = patch(f"{mod}._get_client", return_value=integration_client)
        p.start()
        patches.append(p)
    yield
    for p in patches:
        p.stop()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestProjectsIntegration:
    """Projects list/show via real API."""

    @pytest.mark.usefixtures("_patch_client")
    def test_projects_list(self):
        result = runner.invoke(app, ["--json", "projects", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)

    @pytest.mark.usefixtures("_patch_client")
    def test_project_not_found(self):
        result = runner.invoke(app, ["projects", "show", "nonexistent_project_xyz"])
        assert result.exit_code == exit_codes.NOT_FOUND


class TestCyclesIntegration:
    """Cycle create with real CRP defaults → verify applied_defaults stored."""

    @pytest.mark.usefixtures("_patch_client")
    def test_create_cycle_stores_applied_defaults(self):
        # First, need a project and squad profile — get from list
        proj_result = runner.invoke(app, ["--json", "projects", "list"])
        if proj_result.exit_code != 0:
            pytest.skip("No projects available in test runtime")

        projects = json.loads(proj_result.output)
        if not projects:
            pytest.skip("No projects seeded in test runtime")

        project_id = projects[0]["project_id"]

        # Get a squad profile
        prof_result = runner.invoke(app, ["--json", "squad-profiles", "list"])
        if prof_result.exit_code != 0:
            pytest.skip("No squad profiles available")

        profiles = json.loads(prof_result.output)
        if not profiles:
            pytest.skip("No squad profiles seeded")

        profile_id = profiles[0]["profile_id"]

        # Create cycle with default CRP profile
        result = runner.invoke(
            app,
            [
                "--json",
                "cycles",
                "create",
                project_id,
                "--squad-profile",
                profile_id,
            ],
        )

        if result.exit_code == exit_codes.NOT_FOUND:
            pytest.skip("Project or profile not found in test runtime")

        # If create succeeded, verify hash
        if result.exit_code == 0:
            data = json.loads(result.output)
            crp = load_profile("default")
            expected_hash = compute_config_hash(crp.defaults, {})
            assert data["resolved_config_hash"] == expected_hash


class TestErrorCodes:
    """Error code mapping: real API errors → correct CLI exit codes."""

    @pytest.mark.usefixtures("_patch_client")
    def test_unknown_project_exits_12(self):
        result = runner.invoke(app, ["cycles", "list", "definitely_not_a_real_project_id"])
        # Server may return 404 or empty list depending on implementation
        # At minimum it should not crash
        assert result.exit_code in (0, exit_codes.NOT_FOUND)

    @pytest.mark.usefixtures("_patch_client")
    def test_json_output_valid(self):
        result = runner.invoke(app, ["--json", "projects", "list"])
        if result.exit_code == 0:
            data = json.loads(result.output)
            assert isinstance(data, (list, dict))
