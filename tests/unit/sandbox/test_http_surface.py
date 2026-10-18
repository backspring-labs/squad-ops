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
from squadops.sandbox.models import (
    BuildResult,
    OperationName,
    PatchResult,
    RevisionOrigin,
    compute_revision_id,
)
from squadops.sandbox.service import SandboxService
from squadops.sandbox.workspace import WorkspaceStore
from tests.fixtures.shared_contract.repository import build_repository, recorded, tracked_files

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
    assert response.json()["environment"] is None  # backendless: nothing to report


async def test_health_carries_the_environment_report(tmp_path):
    """Bug caught: 102.2c's reconciliation evidence not riding /health — the
    cycle-create preflight and doctor would have nothing to reconcile."""
    root = tmp_path / "cycles"

    async def report():
        return {"contract_id": "env-123", "image": "img", "image_present": True}

    service = SandboxService(
        store=WorkspaceStore(root),
        journal=OperationEvidenceJournal(root),
        environment_report=report,
    )
    app = create_app(service, service_token=TOKEN)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://exec"
    ) as client:
        response = await client.get("/health")
    assert response.json()["environment"]["contract_id"] == "env-123"


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


async def test_a_git_checkout_seed_keeps_its_origin_from_the_client_to_disk(stack, tmp_path):
    """X-1 (#2419), contract 3's wiring: the seed Project Lifecycle Management's checkout makes.
    Bug caught: the origin refused at the revision, dropped in transit so the API's default
    files the checkout as a scaffold seed, or unreadable once persisted. Its ID stays the
    content hash, and an agent's patch on it chains from it, as a capture back to Git reads."""
    store, _, _, sandbox, _ = stack
    seed = await sandbox.seed_workspace("cyc_1", FILES, origin=RevisionOrigin.GIT_CHECKOUT)
    patch = await sandbox.apply_workspace_patch(base=seed, files={"backend/main.py": "b = 2\n"})

    persisted = WorkspaceStore(tmp_path / "cycles").get_revision("cyc_1", seed.revision_id)
    assert (seed.origin, persisted) == (RevisionOrigin.GIT_CHECKOUT, seed)
    assert seed.revision_id == compute_revision_id(FILES)
    head = store.latest_revision("cyc_1")
    assert (head.revision_id, head.parent_revision_id) == (patch.new_revision_id, seed.revision_id)


async def test_an_unknown_seed_origin_is_refused_and_writes_nothing(stack):
    """Bug caught: the closed origin set opened to any string at the HTTP surface, or a
    refused seed leaving its files in the live tree for the next seed to inherit."""
    store, _, _, _, client_factory = stack
    async with client_factory() as client:
        response = await client.post(
            "/api/v1/workspaces/cyc_1/seed",
            json={"files": FILES, "origin": "git_clone"},
            headers={"Authorization": f"Bearer {TOKEN}"},
        )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_SEED"
    assert store.current_files("cyc_1") == {}


async def test_the_shared_fixture_seeds_and_captures_to_its_recorded_revisions(stack, tmp_path):
    """X-2 (#2420), contract 3's wiring on the shared fixture (#2407): its Git checkout, binary
    asset included, seeded through the client the runtime API uses, then its verified change
    patched on. Bug caught: bytes lost or mangled on the wire or on disk, or a hashing change,
    so the sandbox's revisions stop equalling the ones the MacBook lane's mapping records."""
    store, _, _, sandbox, _ = stack
    repo = build_repository(tmp_path / "tally")
    first = tracked_files(repo.path, repo.first_commit)
    second = tracked_files(repo.path, repo.second_commit)
    mapping = recorded("workspace_commit_mapping", "valid")
    seeded, captured = mapping["entries"]
    cycle = mapping["cycle_id"]

    seed = await sandbox.seed_workspace(cycle, first, origin=RevisionOrigin.GIT_CHECKOUT)
    change: dict = {p: c for p, c in second.items() if first.get(p) != c}
    change.update(dict.fromkeys(first.keys() - second.keys()))
    patch = await sandbox.apply_workspace_patch(base=seed, files=change)

    assert (seed.revision_id, patch.new_revision_id) == (
        seeded["sandbox_revision_id"],
        captured["sandbox_revision_id"],
    )
    asset = store.workspace_dir(cycle) / "assets" / "mark.png"
    assert asset.read_bytes() == second["assets/mark.png"]
    assert store.verify_pinned(cycle, patch.new_revision_id)


@pytest.mark.parametrize(
    ("body", "why"),
    [
        (
            {"files": {"a.png": "x"}, "binary_files": {"a.png": "eA=="}},
            "both as text and as binary",
        ),
        ({"files": {}, "binary_files": {"a.png": "not base64!"}}, "not valid base64"),
    ],
    ids=["a-path-sent-both-ways", "undecodable-bytes"],
)
async def test_binary_content_the_sandbox_cannot_read_is_refused_at_seeding(stack, body, why):
    """Bug caught: a path sent both as text and as bytes settled by dict order, or undecodable
    bytes seeded as something else."""
    store, _, _, _, client_factory = stack
    async with client_factory() as client:
        response = await client.post(
            "/api/v1/workspaces/cyc_1/seed", json=body, headers={"Authorization": f"Bearer {TOKEN}"}
        )
    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "INVALID_SEED" and why in error["message"]
    assert store.current_files("cyc_1") == {}


@pytest.mark.parametrize(
    ("params", "why"),
    [
        ({"files": {"backend/main.py": "b = 2\n"}, "origin": "warm"}, "unknown revision origin"),
        ({"files": dict(FILES)}, "own parent"),
        ({"files": {}, "binary_files": {"a.png": "not base64!"}}, "not valid base64"),
    ],
    ids=["unknown-origin", "changes-nothing", "undecodable-bytes"],
)
async def test_a_patch_the_store_refuses_is_a_400_and_leaves_the_tree(stack, params, why):
    """Bug caught: a caller's bad patch answered 500, as though the service had failed, where a
    seed's refusal answers 400. The tree stays on its base."""
    store, _, _, sandbox, client_factory = stack
    seed = await sandbox.seed_workspace("cyc_1", FILES)
    async with client_factory() as client:
        response = await client.post(
            "/api/v1/workspaces/cyc_1/operations",
            json={
                "operation": OperationName.APPLY_WORKSPACE_PATCH,
                "revision": seed.to_dict(),
                "params": params,
            },
            headers={"Authorization": f"Bearer {TOKEN}"},
        )
    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "INVALID_PATCH" and why in error["message"]
    assert store.verify_pinned("cyc_1", seed.revision_id)
