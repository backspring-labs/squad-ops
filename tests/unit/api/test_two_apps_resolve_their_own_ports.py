"""#1448: two runtime apps in one process each resolve their own ports.

What bug would this catch? The one #1448 was filed for: ``deps.py`` held every port in a
process-wide registry, so a second ``create_app`` overwrote the first's ports and a route served by
one app read the other's. Entered at the routes, through the real ``create_app`` (the slots it
starts at ``None``), with a distinct fake port on each app.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from squadops.cycles.models import Project

pytestmark = [pytest.mark.domain_api]


def _config():
    """The runtime app's test config — the CLI integration suite's, so the two can't drift."""
    from tests.unit.cli.test_integration import _test_config

    return _test_config()


def _registry(project_id: str) -> AsyncMock:
    registry = AsyncMock()
    registry.list_projects.return_value = [
        Project(
            project_id=project_id, name=project_id, description="", created_at=datetime.now(UTC)
        )
    ]
    return registry


def test_each_app_serves_its_own_port_and_an_unwired_app_says_so():
    from squadops.api.runtime.main import create_app

    first, second, unwired = create_app(_config()), create_app(_config()), create_app(_config())
    first.state.project_registry = _registry("from_the_first_app")
    second.state.project_registry = _registry("from_the_second_app")

    # Not entered as a context manager: the routes, without the lifespan's connections.
    assert [p["project_id"] for p in TestClient(first).get("/api/v1/projects").json()] == [
        "from_the_first_app"
    ]
    assert [p["project_id"] for p in TestClient(second).get("/api/v1/projects").json()] == [
        "from_the_second_app"
    ]
    with pytest.raises(RuntimeError, match="ProjectRegistryPort not configured"):
        TestClient(unwired).get("/api/v1/projects")
