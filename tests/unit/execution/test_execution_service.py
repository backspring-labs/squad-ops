"""ExecutionService core (SIP-0102 §4.3/§4.4 — phase 102.1 slice b)."""

import pytest

from squadops.execution.evidence import OperationEvidenceJournal
from squadops.execution.models import (
    BuildResult,
    OperationName,
    OperationStatus,
)
from squadops.execution.noop import NoOpExecutionSandbox
from squadops.execution.service import ExecutionService
from squadops.execution.workspace import StaleBaseRevisionError, WorkspaceStore

FILES = {"backend/main.py": "print('a')\n"}


class StubBackend(NoOpExecutionSandbox):
    """Backend double: build succeeds; everything else stays NoOp."""

    async def build_frontend(self, *, revision):
        return BuildResult(
            operation=OperationName.BUILD_FRONTEND,
            workspace_revision_id=revision.revision_id,
            status=OperationStatus.SUCCEEDED,
            ran=True,
            warning_count=2,
        )


@pytest.fixture
def parts(tmp_path):
    root = tmp_path / "cycles"
    return WorkspaceStore(root), OperationEvidenceJournal(root)


async def test_patch_flows_through_store_and_is_journaled(parts):
    """Bug caught: a patch mutating the tree without evidence, or evidence
    without mutation — the two must be one motion."""
    store, journal = parts
    service = ExecutionService(store=store, journal=journal)
    seed = service.seed_workspace("cyc_1", FILES)
    result = await service.apply_workspace_patch(
        base=seed, files={"backend/main.py": "print('b')\n"}
    )
    assert result.ran and result.status == OperationStatus.SUCCEEDED
    assert store.verify_pinned("cyc_1", result.new_revision_id)
    entries = journal.read("cyc_1")
    assert [e["operation"] for e in entries] == [OperationName.APPLY_WORKSPACE_PATCH]
    assert entries[0]["new_revision_id"] == result.new_revision_id


async def test_stale_patch_raises_and_leaves_no_evidence_or_revision(parts):
    """Bug caught: a rejected patch minting a revision or journal entry —
    failed authority checks must leave no trace claiming success."""
    store, journal = parts
    service = ExecutionService(store=store, journal=journal)
    seed = service.seed_workspace("cyc_1", FILES)
    (store.workspace_dir("cyc_1") / "backend/main.py").write_text("drift", encoding="utf-8")
    with pytest.raises(StaleBaseRevisionError):
        await service.apply_workspace_patch(base=seed, files={"backend/main.py": "x"})
    assert journal.read("cyc_1") == ()
    assert store.latest_revision("cyc_1") == seed


async def test_backendless_execution_is_not_run_but_journaled(parts):
    """Bug caught: an unconfigured backend either claiming failure (roll-4)
    or skipping the journal — a request that reached the service is evidence
    even when the environment cannot execute it."""
    store, journal = parts
    service = ExecutionService(store=store, journal=journal, backend=None)
    seed = service.seed_workspace("cyc_1", FILES)
    result = await service.build_frontend(revision=seed)
    assert result.ran is False
    assert result.status == OperationStatus.NOT_RUN
    entry = journal.read("cyc_1")[0]
    assert entry["status"] == OperationStatus.NOT_RUN
    assert entry["unavailable_reason"]


async def test_backend_results_pass_through_and_are_journaled(parts):
    """Bug caught: the service rewriting or dropping backend semantics on the
    way through — the journaled result must be the returned result."""
    store, journal = parts
    service = ExecutionService(store=store, journal=journal, backend=StubBackend())
    seed = service.seed_workspace("cyc_1", FILES)
    result = await service.build_frontend(revision=seed)
    assert result.ran is True
    assert result.warning_count == 2
    entry = journal.read("cyc_1")[0]
    assert entry["warning_count"] == 2
    assert entry["status"] == OperationStatus.SUCCEEDED
