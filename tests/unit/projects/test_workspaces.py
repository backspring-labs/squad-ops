"""A Project's source in the sandbox, and its inherited baseline (SIP-0112 §8.2.2, FR-20; E.4.2).

Contract 3's seeding half and IR-9's shape, against the shared fixture end to end:
- the real managed clone (``GitSourceRepository``, through a configured local root);
- the real sandbox workspace store (``WorkspaceStore``: X-1's origin, X-2's bytes and modes,
  X-3a's disposable copy).

The one stand-in runs each declared check as a local process inside X-3a's disposable copy, where
the service would run it in a container. What it must produce is what the fixture recorded: the
inherited baseline, and a mapping that names the fixture's own revision and tree.
"""

from __future__ import annotations

import asyncio
import dataclasses
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

import pytest

from adapters.tools.git_source import GitSourceRepository
from squadops.cycles.models import Project, ProjectStateConflictError
from squadops.projects.development_configuration import parse_configuration
from squadops.projects.models import ProjectLifecycleStatus, ProjectSource
from squadops.projects.registration import LocatorPolicy
from squadops.projects.workspaces import SandboxUnavailable, capture_inherited_baseline
from squadops.sandbox.models import CommandOutcome
from squadops.sandbox.workspace import WorkspaceStore
from tests.fixtures.shared_contract.repository import build_repository, recorded


class _LocalSandbox:
    """Seeds through the real store; runs a declared check, after its setup, as local processes
    in X-3a's copy."""

    def __init__(self, root: Path) -> None:
        self.store = WorkspaceStore(root)
        self.ran: list[tuple[str, ...]] = []

    async def seed_workspace(self, workspace_id, files, *, origin, executable=(), created_at=None):
        return self.store.seed(workspace_id, files, origin=origin, executable=executable)

    async def run_declared_command(
        self, *, revision, command, working_dir=".", setup=(), timeout_seconds=None,
        findings_reader=None,
    ):  # fmt: skip
        self.ran.append(tuple(command))
        with self.store.disposable_copy(revision.cycle_id, revision.revision_id) as copy:
            started = time.monotonic()
            for step in setup:
                await asyncio.to_thread(subprocess.run, list(step), cwd=copy, check=True)
            done = await asyncio.to_thread(
                subprocess.run,
                list(command),
                cwd=copy / working_dir,
                capture_output=True,
                text=True,
            )
        return _Run(
            ran=True,
            outcome=CommandOutcome.EXITED,
            exit_code=done.returncode,
            duration_seconds=time.monotonic() - started,
            stdout_tail=done.stdout[-500:],
            stderr_tail=done.stderr[-500:],
            image_identity="python:3.12-slim",
            environment_contract_id="python3",
            unavailable_reason=None,
        )


@dataclasses.dataclass
class _Run:
    ran: bool
    outcome: str
    exit_code: int | None
    duration_seconds: float
    stdout_tail: str
    stderr_tail: str
    image_identity: str
    environment_contract_id: str
    unavailable_reason: str | None
    stdout_truncated: bool = False
    stderr_truncated: bool = False


class _Registry:
    def __init__(self, project, configuration):
        self.project, self.configuration = project, configuration
        self.mappings, self.baseline = [], None

    async def get_project(self, project_id):
        return self.project

    async def get_development_configuration(self, project_id, revision=None):
        return self.configuration

    async def record_source_mapping(self, mapping):
        self.mappings.append(mapping)

    async def record_inherited_baseline(self, baseline, **kwargs):
        self.baseline = baseline
        return baseline, False


@pytest.fixture
def world(tmp_path):
    repo = build_repository(tmp_path / "sources" / "tally")
    project = Project(
        project_id="prj-tally",
        name="Tally",
        description="",
        created_at=datetime(2026, 10, 18, tzinfo=UTC),
        lifecycle_status=ProjectLifecycleStatus.READY,
        source=ProjectSource(
            repo_uri=str(repo.path), base_ref="refs/heads/main", contribution_mode="review_request"
        ),
        development_baseline_commit=repo.second_commit,
    )
    configuration = parse_configuration(recorded("development_configuration", "valid"))
    clones = GitSourceRepository(
        tmp_path / "cache",
        LocatorPolicy.of([], [str(tmp_path / "sources")]),
        timeout_seconds=60,
        committer_name="SquadOps",
        committer_email="squadops@squadops.invalid",
    )
    return repo, _Registry(project, configuration), clones, _LocalSandbox(tmp_path / "cycles")


async def _capture(registry, clones, sandbox):
    return await capture_inherited_baseline(
        "prj-tally",
        registry=registry,
        repository=clones,
        sandbox=sandbox,
        actor="owner",
        idempotency_key="b-1",
    )


async def test_the_fixtures_own_checks_reproduce_its_recorded_inherited_baseline(world):
    """IR-9's shape, and FR-20. Bugs caught: the inherited failure (parse) recorded as anything
    but FAIL inherited; notify, which exits 0 skipped, credited as PASS; a check run against a
    tree other than the pinned, unmodified one."""
    repo, registry, clones, sandbox = world

    baseline, _ = await _capture(registry, clones, sandbox)

    assert baseline.to_document() == recorded("inherited_baseline", "valid")
    assert (
        "python3",
        "-m",
        "unittest",
        "discover",
        "-s",
        "checks",
        "-p",
        "check_notify.py",
    ) not in sandbox.ran
    parse = next(c for c in baseline.checks if c.id == "parse")
    assert (
        parse.evidence["exit_code"] == 1 and "FAILED (failures=1)" in parse.evidence["stderr_tail"]
    )


async def test_each_check_runs_after_the_install_its_configuration_declares(world):
    """#2468's review. Bug caught: the checks run with no setup, so a product whose checks need
    their dependencies installed records every check FAIL inherited, a missing step recorded as
    the product's state."""
    repo, registry, clones, sandbox = world
    doc = recorded("development_configuration", "valid")
    commands = doc["configuration"]["technical"]["commands"]
    commands["install"] = [["python3", "-c", "open('installed.flag', 'w').close()"]]
    commands["checks"] = [
        {
            "id": "installed",
            "argv": [
                "python3",
                "-c",
                "import os, sys; sys.exit(not os.path.exists('installed.flag'))",
            ],
        }
    ]
    registry.configuration = parse_configuration(doc)

    baseline, _ = await _capture(registry, clones, sandbox)

    [check] = baseline.checks
    assert (check.id, check.result) == ("installed", "PASS")


async def test_the_seed_is_mapped_by_all_three_of_its_identifiers(world):
    """Contract 3's seeding half. Bugs caught: the sandbox revision recorded as a commit or the
    reverse; a revision ID that differs from the one the fixture recorded for this tree, which
    would mean the seed carried a different tree (a byte, a line ending or a mode lost)."""
    repo, registry, clones, sandbox = world

    await _capture(registry, clones, sandbox)

    [mapping] = registry.mappings
    captured = recorded("workspace_commit_mapping", "valid")["entries"][1]
    assert (mapping.direction, mapping.commit) == ("seeded", repo.second_commit)
    assert mapping.sandbox_revision_id == captured["sandbox_revision_id"]
    assert mapping.tree_identity == captured["tree_identity"]


async def test_a_configuration_recorded_at_another_commit_is_refused(world):
    """FR-21: commands validated against another commit are revalidated before they're relied
    on. Bug caught: a baseline captured with checks recorded for an older tree."""
    repo, registry, clones, sandbox = world
    registry.configuration = parse_configuration(
        recorded("development_configuration", "stale_commit")
    )

    with pytest.raises(ProjectStateConflictError, match="record a revision at the baseline"):
        await _capture(registry, clones, sandbox)
    assert sandbox.ran == [] and registry.baseline is None


async def test_no_sandbox_client_records_nothing(world):
    repo, registry, clones, _ = world

    with pytest.raises(SandboxUnavailable):
        await _capture(registry, clones, None)
    assert registry.baseline is None and registry.mappings == []


@pytest.mark.parametrize("bound", [600.0, 120.0], ids=["the-default", "a-deploys-own"])
async def test_a_declared_runs_request_waits_for_every_step_the_service_bounds(
    world, tmp_path, bound
):
    """#2586, entered at ``capture_inherited_baseline``, the live caller, through the real client
    to the real service and backend; only the container is a stand-in. Bugs caught:
    - the request ending at the client's 30 s while the product's install still runs, so no
      product with a real install can be baselined or have its change verified;
    - the service bounding each step by another number than the one the client waited on;
    - every other operation's 30 s lengthened with it."""
    import json

    import httpx

    from adapters.sandbox.container_backend import ContainerBackend
    from adapters.sandbox.http_client import HttpExecutionSandbox
    from squadops.projects.development_configuration import parse_technical
    from squadops.sandbox.api import create_app
    from squadops.sandbox.evidence import OperationEvidenceJournal
    from squadops.sandbox.service import SandboxService
    from tests.unit.sandbox.test_container_backend import _WritingContainer

    _repo, registry, clones, local = world
    *_, commands = parse_technical(
        {"project_type": "web_application", "target": "web",
         "commands": {"install": [["python3", "-m", "venv", ".venv"],
                                  [".venv/bin/pip", "install", "-r", "requirements.txt"],
                                  ["npm", "--prefix", "frontend", "install"]],
                      "checks": [{"id": "tests", "argv": [".venv/bin/python", "-m", "pytest"]}]}}
    )  # fmt: skip
    registry.configuration = dataclasses.replace(registry.configuration, commands=commands)
    store = local.store
    backend = ContainerBackend(
        app_network=None, container=_WritingContainer(), store=store, image="sandbox:pinned",
        operation_commands={},
    )  # fmt: skip
    app = create_app(
        SandboxService(
            store=store, journal=OperationEvidenceJournal(tmp_path / "cycles"), backend=backend
        ),
        service_token="tok",
    )
    seen: list = []

    class _Recording(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            seen.append((request.url.path, request.extensions.get("timeout"), request.content))
            return await httpx.ASGITransport(app=app).handle_async_request(request)

    sandbox = HttpExecutionSandbox(
        base_url="http://exec",
        service_token="tok",
        http_client_factory=lambda: httpx.AsyncClient(transport=_Recording(), timeout=30.0),
        command_timeout_seconds=bound,
    )

    baseline, _ = await _capture(registry, clones, sandbox)

    [(_, seeded, _)] = [s for s in seen if s[0].endswith("/seed")]
    [(_, waited, body)] = [s for s in seen if s[0].endswith("/operations")]
    assert [c.id for c in baseline.checks] == ["tests"]
    assert waited["read"] == 4 * bound + 60.0 and waited["connect"] == 10.0  # 3 installs + check
    assert json.loads(body)["params"]["timeout_seconds"] == bound
    assert seeded["read"] == 30.0
