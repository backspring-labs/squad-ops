"""#2451 part 4 (the owner's ruling, 2026-10-18): the sandbox service starts apps on an internal,
no-egress network, by container name with no host port, named to it by a required
``SQUADOPS__SANDBOX__APP_NETWORK``."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from squadops.sandbox.main import build_app
from squadops.tools.exceptions import ToolContainerError
from tests.unit.sandbox.test_container_backend_runtime import RuntimeFakeContainer

_COMPOSE = Path(__file__).resolve().parents[3] / "docker-compose.yml"


@pytest.fixture
def service_env(monkeypatch, tmp_path):
    for key in list(os.environ):
        if key.startswith(("SQUADOPS__SANDBOX__", "SQUADOPS__SECRETS__")):
            monkeypatch.delenv(key)
    monkeypatch.setenv("SQUADOPS__SANDBOX__PROVIDER", "docker")
    monkeypatch.setenv("SQUADOPS__SANDBOX__WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("SQUADOPS__SANDBOX__SERVICE_TOKEN", "t")
    return monkeypatch


def test_a_docker_service_with_no_app_network_refuses_to_start(service_env):
    """Required where it is read (#1568). Bug caught: a deployed service that starts and then
    publishes every app to a loopback it can't reach, each start failing as "not ready"."""
    with pytest.raises(ValueError, match="SQUADOPS__SANDBOX__APP_NETWORK"):
        build_app()


def test_the_env_reaches_the_runtime_unit_through_the_services_root(service_env):
    """The wiring test: entered at ``build_app``, the service's composition root, with the env
    compose writes; asserted at the container spec of a start through the service's HTTP surface.
    Bug caught: the variable read but never handed to the backend, so apps still publish to
    loopback inside the deploy."""
    service_env.setenv("SQUADOPS__SANDBOX__APP_NETWORK", "squadops-sandbox-apps")
    container = RuntimeFakeContainer(detach_error=ToolContainerError("stop here"))
    service_env.setattr("adapters.sandbox.factory.DockerAdapter", lambda: container)
    client = TestClient(build_app())
    auth = {"Authorization": "Bearer t"}

    seeded = client.post(
        "/api/v1/workspaces/cyc_1/seed", json={"files": {"app.py": "x\n"}}, headers=auth
    ).json()
    client.post(
        "/api/v1/workspaces/cyc_1/operations",
        json={"operation": "start_application", "revision": seeded, "params": {}},
        headers=auth,
    )

    [spec] = container.specs
    assert (spec.network, spec.publish_ports) == ("squadops-sandbox-apps", ())


def test_compose_puts_the_service_on_an_internal_network_named_as_it_reads_it():
    """Bug caught: a network compose prefixes with the project's name, so the name the service
    reads matches no network; one with a route out, so an app holding the evaluation secrets can
    reach the internet; or another service joining it, which can then reach every app."""
    compose = yaml.safe_load(_COMPOSE.read_text())
    network = compose["networks"]["sandbox-apps"]
    joined = {
        name
        for name, service in compose["services"].items()
        if "sandbox-apps" in (service.get("networks") or [])
    }

    assert network["internal"] is True
    assert joined == {"sandbox-service"}
    service_env = compose["services"]["sandbox-service"]["environment"]
    assert service_env["SQUADOPS__SANDBOX__APP_NETWORK"] == network["name"]
