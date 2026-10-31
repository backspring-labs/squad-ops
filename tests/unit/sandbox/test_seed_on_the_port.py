"""Seeding is on ``ExecutionSandboxPort`` (#2451's consumer, SIP-0112's E.4.2): a caller typed
against the port seeds through any of its three implementations and gets the same revision."""

from __future__ import annotations

import httpx
import pytest

from adapters.sandbox.http_client import HttpExecutionSandbox
from squadops.ports.sandbox import ExecutionSandboxPort
from squadops.sandbox.api import create_app
from squadops.sandbox.evidence import OperationEvidenceJournal
from squadops.sandbox.models import RevisionOrigin
from squadops.sandbox.noop import NoOpExecutionSandbox
from squadops.sandbox.service import SandboxService
from squadops.sandbox.workspace import WorkspaceStore

CHECKOUT = {"run.sh": "#!/bin/sh\necho ok\n", "assets/logo.png": b"\x89PNG\r\n\x1a\n\x00"}


def _service(tmp_path) -> SandboxService:
    root = tmp_path / "cycles"
    return SandboxService(store=WorkspaceStore(root), journal=OperationEvidenceJournal(root))


def _client(tmp_path) -> HttpExecutionSandbox:
    app = create_app(_service(tmp_path), service_token="t")
    return HttpExecutionSandbox(
        base_url="http://sandbox",
        service_token="t",
        http_client_factory=lambda: httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://sandbox"
        ),
    )


async def _seed(sandbox: ExecutionSandboxPort):
    return await sandbox.seed_workspace(
        "cyc_1", CHECKOUT, origin=RevisionOrigin.GIT_CHECKOUT, executable=("run.sh",)
    )


async def test_every_implementation_cuts_the_same_revision_for_the_same_checkout(tmp_path):
    """Bug caught: one implementation dropping the executable bit or a binary file, or the noop
    cutting another ID, so a caller typed against the port records a revision the service never
    holds."""
    in_process = await _seed(_service(tmp_path / "a"))
    over_http = await _seed(_client(tmp_path / "b"))
    unconfigured = await _seed(NoOpExecutionSandbox())

    assert in_process == over_http == unconfigured
    assert in_process.origin == RevisionOrigin.GIT_CHECKOUT


async def test_the_noop_stores_nothing_and_runs_nothing_on_what_it_seeded():
    """The noop never raises, and never claims what it didn't do. Bug caught: a noop seed that
    reads as a workspace something then ran against."""
    sandbox = NoOpExecutionSandbox()
    revision = await _seed(sandbox)

    result = await sandbox.run_declared_command(revision=revision, command=("sh", "run.sh"))

    assert (result.ran, result.unavailable_reason) == (False, "execution sandbox not configured")


async def test_a_released_workspace_is_gone_through_every_implementation_and_its_journal_is_kept(
    tmp_path,
):
    """#2473. Bug caught: a workspace the runtime API seeded (an inherited baseline, a source-backed
    run's tree) kept on the sandbox root for ever, or released only through the service and not the
    HTTP client a deploy calls; a second release failing the consumer's teardown; or the release
    taking the operation journal with it, which shares the cycle's directory."""
    root = tmp_path / "cycles"
    for n, sandbox in enumerate((_service(tmp_path), _client(tmp_path)), start=1):
        revision = await _seed(sandbox)
        await sandbox.run_declared_command(revision=revision, command=("sh", "run.sh"))

        await sandbox.release_workspace("cyc_1")
        await sandbox.release_workspace("cyc_1")

        assert sorted(p.name for p in (root / "cyc_1").iterdir()) == ["evidence"]
        assert WorkspaceStore(root).latest_revision("cyc_1") is None
        assert [e["operation"] for e in OperationEvidenceJournal(root).read("cyc_1")] == [
            "run_declared_command"
        ] * n
    await NoOpExecutionSandbox().release_workspace("cyc_1")


@pytest.mark.parametrize(("cycle_id", "status"), [("..", 404), ("cyc.1", 400), ("cyc 1", 400)])
async def test_releasing_a_workspace_by_an_id_outside_the_pattern_is_refused(
    tmp_path, cycle_id, status
):
    """Bug caught: a crafted id deleting outside its workspace: ``..`` normalized away before the
    route, or an id the store's pattern refuses answered 500, never deleting anything."""
    from adapters.sandbox.http_client import SandboxServiceError

    service = _service(tmp_path)
    await _seed(service)
    with pytest.raises(SandboxServiceError) as refused:
        await _client(tmp_path).release_workspace(cycle_id)

    assert refused.value.status_code == status
    assert (tmp_path / "cycles" / "cyc_1").exists()
