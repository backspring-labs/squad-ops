"""Reading a pinned revision's content through the port (contract 3; SIP-0112's E.4.3 captures a
change back from it): from the live tree only while it matches its pin, as a disposable copy is
taken."""

from __future__ import annotations

import httpx
import pytest

from adapters.sandbox.http_client import HttpExecutionSandbox, SandboxServiceError
from squadops.ports.sandbox import ExecutionSandboxPort
from squadops.sandbox.api import create_app
from squadops.sandbox.evidence import OperationEvidenceJournal
from squadops.sandbox.models import RevisionOrigin, WorkspaceRevision
from squadops.sandbox.noop import NoOpExecutionSandbox
from squadops.sandbox.service import SandboxService
from squadops.sandbox.workspace import StaleBaseRevisionError, WorkspaceStore

CHECKOUT = {
    "run.sh": "#!/bin/sh\necho ok\n",
    "crlf.txt": "a\r\nb\r\n",
    "assets/logo.png": b"\x89PNG\r\n\x1a\n\x00\xff",
}


@pytest.fixture
def service(tmp_path) -> SandboxService:
    root = tmp_path / "cycles"
    return SandboxService(store=WorkspaceStore(root), journal=OperationEvidenceJournal(root))


def _client(service: SandboxService) -> HttpExecutionSandbox:
    app = create_app(service, service_token="t")
    return HttpExecutionSandbox(
        base_url="http://sandbox",
        service_token="t",
        http_client_factory=lambda: httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://sandbox"
        ),
    )


async def _seed(sandbox: ExecutionSandboxPort) -> WorkspaceRevision:
    return await sandbox.seed_workspace(
        "cyc_1", CHECKOUT, origin=RevisionOrigin.GIT_CHECKOUT, executable=("run.sh",)
    )


@pytest.mark.parametrize("over", ["http", "in-process"])
async def test_a_revision_reads_back_exactly_as_it_was_seeded(service, over):
    """Bug caught: a binary file decoded as text, a ``\\r\\n`` normalized, or an executable bit
    dropped on the way back, so E.4.3 captures a change the product's repository never made."""
    sandbox = _client(service) if over == "http" else service
    seeded = await _seed(sandbox)

    content = await sandbox.read_workspace_revision(seeded)

    assert content.revision == seeded
    assert dict(content.files) == CHECKOUT
    assert content.executable == {"run.sh"}


@pytest.mark.parametrize("moved", ["a-file-edited", "a-patch-applied"])
async def test_a_tree_that_no_longer_matches_its_pin_returns_nothing(service, moved):
    """Contract 3. Bug caught: a read of whatever the live tree now holds, labelled with a revision
    that names other content, so a capture mixes two revisions."""
    seeded = await _seed(service)
    if moved == "a-file-edited":
        (service._store.workspace_dir("cyc_1") / "run.sh").write_text("drift", encoding="utf-8")
    else:
        await service.apply_workspace_patch(base=seeded, files={"run.sh": "#!/bin/sh\necho 2\n"})

    with pytest.raises(StaleBaseRevisionError):
        await service.read_workspace_revision(seeded)
    with pytest.raises(SandboxServiceError, match="409"):
        await _client(service).read_workspace_revision(seeded)


async def test_a_revision_the_cycle_never_held_is_not_found(service):
    """Bug caught: an unknown revision answered with an empty tree, read as a product with no
    files."""
    await _seed(service)
    unknown = WorkspaceRevision(revision_id="0" * 64, cycle_id="cyc_1", origin="git_checkout")

    with pytest.raises(SandboxServiceError, match="404"):
        await _client(service).read_workspace_revision(unknown)


async def test_the_noop_holds_nothing_to_read():
    """Bug caught: an unconfigured sandbox answering a read with an empty tree, read as a capture
    of a product with no files."""
    sandbox = NoOpExecutionSandbox()
    revision = await _seed(sandbox)

    with pytest.raises(StaleBaseRevisionError, match="not configured"):
        await sandbox.read_workspace_revision(revision)
