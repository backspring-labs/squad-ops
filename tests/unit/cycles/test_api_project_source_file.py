"""A registered product's file at the Project's integrated commit (#2855): what the crew's Campaign
drafting reads a product's goals through, and the commit its card states."""

import subprocess
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from adapters.tools.git_source import GitSourceRepository
from squadops.api.error_handlers import register_domain_error_handlers
from squadops.api.routes.cycles.projects import router
from squadops.cycles.models import Project
from squadops.projects.models import ProjectSource
from squadops.projects.registration import LocatorPolicy

pytestmark = [pytest.mark.domain_orchestration]

NOW = datetime(2026, 11, 1, 12, 0, 0, tzinfo=UTC)
PROJECT = "prj-almanac"


def _git(cwd, *args) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def _commit(repo, goals: str) -> str:
    (repo / "docs").mkdir(exist_ok=True)
    (repo / "docs" / "goals.md").write_text(goals)
    _git(repo, "add", "-A")
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@t.invalid", "commit", "-q", "-m", "goals")
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def product(tmp_path):
    """A product whose goals moved on upstream after the Project last integrated it."""
    repo = tmp_path / "sources" / "almanac"
    repo.mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")
    integrated = _commit(repo, "# Almanac\n\n1. Plant by season.\n")
    _commit(repo, "# Almanac\n\n1. Plant by season.\n2. Harvest log.\n")
    return repo, integrated


def _project(source: bool = True, integrated: str | None = None) -> Project:
    return Project(
        project_id=PROJECT,
        name="Almanac",
        description="",
        created_at=NOW,
        source=ProjectSource("file:///almanac", "refs/heads/main", "review_request")
        if source
        else None,
        integrated_upstream_commit=integrated,
    )


@pytest.fixture
def client(tmp_path, product):
    repo, _ = product
    clones = GitSourceRepository(
        tmp_path / "cache",
        LocatorPolicy.of([], [str(tmp_path / "sources")]),
        timeout_seconds=60,
        committer_name="SquadOps",
        committer_email="squadops@squadops.invalid",
    )
    app = FastAPI()
    app.include_router(router)
    register_domain_error_handlers(app)
    app.state.project_registry = AsyncMock()
    app.state.source_repository = clones
    test_client = TestClient(app)
    return test_client, clones, repo


async def _synced(clones, repo) -> None:
    await clones.sync(PROJECT, str(repo), "refs/heads/main")


async def test_the_goals_are_read_at_the_integrated_commit_not_upstreams_head(client, product):
    """Bug caught: the draft reads the branch head, so its card shows goals the Campaign never
    works from (a Campaign resolves ``repo:file:…@current`` at the integrated commit)."""
    test_client, clones, repo = client
    _, integrated = product
    await _synced(clones, repo)
    test_client.app.state.project_registry.get_project.return_value = _project(
        integrated=integrated
    )

    resp = test_client.get(
        f"/api/v1/projects/{PROJECT}/source-file", params={"path": "docs/goals.md"}
    )

    assert resp.status_code == 200
    assert resp.json() == {
        "project_id": PROJECT,
        "path": "docs/goals.md",
        "commit": integrated,
        "content": "# Almanac\n\n1. Plant by season.\n",
    }


@pytest.mark.parametrize(
    ("project", "path", "status", "code"),
    [
        (lambda c: _project(source=False), "docs/goals.md", 404, "SOURCE_FILE_NOT_FOUND"),
        (lambda c: _project(integrated=None), "docs/goals.md", 409, "SOURCE_NOT_INTEGRATED"),
        (lambda c: _project(integrated=c), "docs/missing.md", 404, "SOURCE_FILE_NOT_FOUND"),
        (lambda c: _project(integrated=c), "../../etc/passwd", 422, "VALIDATION_ERROR"),
    ],
    ids=["sample application", "never synced", "no such file", "outside the tree"],
)
async def test_a_file_that_cant_be_read_is_refused_by_name(
    client, product, project, path, status, code
):
    """Bugs caught: a missing goals file answered as empty content (the draft would go ahead on
    nothing), a path escaping the clone read from the host, and an unsynced Project read at a
    default commit."""
    test_client, clones, repo = client
    _, integrated = product
    await _synced(clones, repo)
    test_client.app.state.project_registry.get_project.return_value = project(integrated)

    resp = test_client.get(f"/api/v1/projects/{PROJECT}/source-file", params={"path": path})

    assert resp.status_code == status
    assert resp.json()["detail"]["error"]["code"] == code
