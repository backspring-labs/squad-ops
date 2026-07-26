"""NoOp sandbox default (SIP-0102, phase 102.1 slice a).

The unconfigured default must be honestly not-run for every operation and must
never raise — this is the parity floor the inert-to-merge guarantee rests on.
"""

from squadops.sandbox.models import OperationStatus, RevisionOrigin, WorkspaceRevision
from squadops.sandbox.noop import NoOpExecutionSandbox

REV = WorkspaceRevision.cut(
    cycle_id="cyc_1",
    origin=RevisionOrigin.SCAFFOLD_SEED,
    files={"backend/main.py": "print('a')\n"},
)


async def test_every_operation_returns_not_run_without_raising():
    """Bug caught: a port method left abstract or raising in the default
    adapter — an unconfigured stack would crash instead of keeping today's
    in-process behavior."""
    sandbox = NoOpExecutionSandbox()
    results = [
        await sandbox.install_dependencies(revision=REV),
        await sandbox.build_frontend(revision=REV),
        await sandbox.run_backend_tests(revision=REV),
        await sandbox.start_application(revision=REV),
        await sandbox.probe_http_endpoint(
            revision=REV, probe_id="p1", method="GET", path="/health"
        ),
        await sandbox.stop_application(revision=REV, cleanup_handle="h1"),
        await sandbox.apply_workspace_patch(base=REV, files={"backend/main.py": "x"}),
        await sandbox.read_build_diagnostics(revision=REV),
    ]
    for result in results:
        assert result.ran is False
        assert result.status == OperationStatus.NOT_RUN
        assert result.unavailable_reason
        assert result.workspace_revision_id == REV.revision_id


async def test_noop_patch_leaves_the_base_revision_untouched():
    """Bug caught: the NoOp path minting a new revision id for a patch it never
    applied — evidence would pin content that does not exist."""
    sandbox = NoOpExecutionSandbox()
    result = await sandbox.apply_workspace_patch(base=REV, files={"backend/main.py": "changed"})
    assert result.new_revision_id == REV.revision_id
    assert result.files_changed == ()
