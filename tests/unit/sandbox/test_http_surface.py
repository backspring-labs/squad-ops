"""Sandbox service HTTP surface + client adapter E2E (SIP-0102 — 102.1 slice d).

The phase exit criterion, in-process: a typed operation travels client →
HTTP API → service core → workspace store and back as a typed semantic
result, via httpx's ASGI transport (no network, no docker).
"""

import httpx
import pytest

from adapters.sandbox.http_client import HttpExecutionSandbox, SandboxServiceError
from squadops.sandbox.api import create_app
from squadops.sandbox.evidence import OperationEvidenceJournal
from squadops.sandbox.models import BuildResult, OperationName, PatchResult
from squadops.sandbox.service import SandboxService
from squadops.sandbox.workspace import WorkspaceStore

TOKEN = "tok-123"
FILES = {"backend/main.py": "print('a')\n"}


@pytest.fixture
def stack(tmp_path):
    root = tmp_path / "cycles"
    store = WorkspaceStore(root)
    journal = OperationEvidenceJournal(root)
    app = create_app(SandboxService(store=store, journal=journal), service_token=TOKEN)

    def client_factory():
        return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://exec")

    sandbox = HttpExecutionSandbox(
        base_url="http://exec", service_token=TOKEN, http_client_factory=client_factory
    )
    return store, journal, app, sandbox, client_factory


def test_create_app_refuses_to_run_unauthenticated(tmp_path):
    """Bug caught: the service booting with no token — an unauthenticated
    privileged surface (§7 item 2/the narrow-port requirement)."""
    root = tmp_path / "cycles"
    service = SandboxService(store=WorkspaceStore(root), journal=OperationEvidenceJournal(root))
    with pytest.raises(ValueError, match="service token"):
        create_app(service, service_token="")


async def test_health_probe_is_unauthenticated(stack):
    """Bug caught: the /health lane accidentally behind auth — operational
    probes must stay tokenless (the repo's one no-auth lane)."""
    _, _, _, _, client_factory = stack
    async with client_factory() as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_missing_bearer_is_401_in_the_resource_envelope(stack):
    """Bug caught: auth bypass, or errors emitted in FastAPI's default
    {"detail": ...} shape instead of the lane-standard {"error": ...}
    envelope the clients parse (#218's exact drift class)."""
    _, _, _, _, client_factory = stack
    async with client_factory() as client:
        response = await client.post("/api/v1/workspaces/cyc_1/seed", json={"files": FILES})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


async def test_seed_and_patch_round_trip_through_the_client(stack):
    """The slice-d exit proof — bug caught: any break in the client → API →
    service → store chain, including rehydration dropping typed fields."""
    store, journal, _, sandbox, _ = stack
    seed = await sandbox.seed_workspace("cyc_1", FILES)
    result = await sandbox.apply_workspace_patch(
        base=seed, files={"backend/main.py": "print('b')\n"}
    )
    assert isinstance(result, PatchResult)
    assert result.ran and result.files_changed == ("backend/main.py",)
    assert store.verify_pinned("cyc_1", result.new_revision_id)
    operations = [e["operation"] for e in journal.read("cyc_1")]
    assert operations == [OperationName.APPLY_WORKSPACE_PATCH]


async def test_backendless_execution_op_rehydrates_as_not_run(stack):
    """Bug caught: the honest not_run posture lost in HTTP transit — a
    backendless service must look identical through the wire."""
    _, _, _, sandbox, _ = stack
    seed = await sandbox.seed_workspace("cyc_1", FILES)
    result = await sandbox.build_frontend(revision=seed)
    assert isinstance(result, BuildResult)
    assert result.ran is False
    assert isinstance(result.diagnostics, tuple)


async def test_unknown_operation_is_rejected_typed_only(stack):
    """Bug caught: §7 item 2 violation — anything shell-shaped slipping
    through the operations endpoint."""
    _, _, _, sandbox, client_factory = stack
    seed = await sandbox.seed_workspace("cyc_1", FILES)
    async with client_factory() as client:
        response = await client.post(
            "/api/v1/workspaces/cyc_1/operations",
            json={"operation": "run_shell", "revision": seed.to_dict(), "params": {}},
            headers={"Authorization": f"Bearer {TOKEN}"},
        )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "UNKNOWN_OPERATION"


async def test_conflicts_surface_with_their_own_codes(stack):
    """Bug caught: 409-class violations (double-seed, stale patch) collapsed
    into generic errors the caller cannot route on."""
    store, _, _, sandbox, _ = stack
    seed = await sandbox.seed_workspace("cyc_1", FILES)
    with pytest.raises(SandboxServiceError) as excinfo:
        await sandbox.seed_workspace("cyc_1", {"other.py": "x"})
    assert excinfo.value.status_code == 409
    (store.workspace_dir("cyc_1") / "backend/main.py").write_text("drift", encoding="utf-8")
    with pytest.raises(SandboxServiceError) as excinfo:
        await sandbox.apply_workspace_patch(base=seed, files={"backend/main.py": "x"})
    assert excinfo.value.status_code == 409


async def test_revision_cycle_mismatch_is_rejected(stack):
    """Bug caught: an operation smuggled onto another cycle's workspace by
    addressing cycle A with cycle B's revision."""
    _, _, _, sandbox, client_factory = stack
    seed = await sandbox.seed_workspace("cyc_1", FILES)
    async with client_factory() as client:
        response = await client.post(
            "/api/v1/workspaces/cyc_OTHER/operations",
            json={
                "operation": OperationName.BUILD_FRONTEND,
                "revision": seed.to_dict(),
                "params": {},
            },
            headers={"Authorization": f"Bearer {TOKEN}"},
        )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "CYCLE_MISMATCH"
