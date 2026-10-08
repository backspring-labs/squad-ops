"""Tests for console command handler registry and handler functions."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import APIRouter

# The console main.py imports from continuum and auth_bff which aren't installed
# in the test environment. We inject stubs so we can import the command handler
# registry and individual handler functions.

_docker_dir = str(Path(__file__).parents[3] / "console" / "app")


@pytest.fixture(autouse=True)
def _stub_continuum_and_bff():
    """Inject stub modules for continuum and auth_bff so main.py can be imported.

    #198: the two ``router`` attributes are real ``APIRouter`` instances, not
    ``MagicMock``s. FastAPI 0.136 added ``assert not router._contains_router(self)`` to
    ``include_router``, and a ``MagicMock`` answers *any* attribute call with a truthy
    object — so ``include_router(<MagicMock>)`` fails that assertion with "Cannot include
    an APIRouter instance that already includes this router", which reads like a router
    cycle and is not one. Twenty-six tests here failed that way on fastapi >= 0.136 while
    the console app itself imported clean.

    A stub standing in for a type the code under test inspects has to be that type. This
    is the general shape, not a FastAPI quirk: the next library assertion on a stubbed
    object fails the same way, and a ``MagicMock`` will satisfy it in whichever direction
    is wrong.
    """
    stubs = {}
    # #2082: restore exactly what was here before, rather than removing it. Another console
    # file imports the real ``auth_bff`` and puts console/app on the path at collection; a
    # teardown that popped both broke that file's later ``import main`` in this run order.
    stubbed = (
        "continuum",
        "continuum.app",
        "continuum.app.runtime",
        "continuum.adapters",
        "continuum.adapters.web",
        "continuum.adapters.web.api",
        "auth_bff",
        "main",
    )
    prior_modules = {name: sys.modules.get(name) for name in stubbed}
    path_added = _docker_dir not in sys.path

    # Stub continuum hierarchy
    for mod_name in (
        "continuum",
        "continuum.app",
        "continuum.app.runtime",
        "continuum.adapters",
        "continuum.adapters.web",
        "continuum.adapters.web.api",
    ):
        stub = MagicMock()
        stubs[mod_name] = stub
        sys.modules[mod_name] = stub

    # A real router, mounted for real: main.py calls app.include_router() on it.
    stubs["continuum.adapters.web.api"].router = APIRouter(prefix="/api/registry")

    # Stub auth_bff — same rule for its router.
    auth_bff_stub = MagicMock()
    auth_bff_stub.router = APIRouter(prefix="/auth")
    auth_bff_stub.configure = MagicMock()
    auth_bff_stub.session_access_token = AsyncMock(return_value=None)
    stubs["auth_bff"] = auth_bff_stub
    sys.modules["auth_bff"] = auth_bff_stub

    # Add console/app to sys.path so main.py can be found
    if path_added:
        sys.path.insert(0, _docker_dir)

    yield

    for name, prior in prior_modules.items():
        if prior is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = prior
    if path_added and _docker_dir in sys.path:
        sys.path.remove(_docker_dir)


def _load_main():
    """Import (or re-import) the console main module."""
    if "main" in sys.modules:
        del sys.modules["main"]
    return importlib.import_module("main")


class TestCommandHandlerRegistry:
    """Verify COMMAND_HANDLERS maps all expected command IDs."""

    def test_registry_has_11_handlers(self):
        main = _load_main()
        assert len(main.COMMAND_HANDLERS) == 11

    def test_registry_contains_all_expected_keys(self):
        main = _load_main()
        expected = {
            "squadops.health_check",
            "squadops.create_cycle",
            "squadops.create_run",
            "squadops.cancel_cycle",
            "squadops.cancel_run",
            "squadops.gate_approve",
            "squadops.gate_reject",
            "squadops.ingest_artifact",
            "squadops.set_baseline",
            "squadops.download_artifact",
            "squadops.set_active_profile",
        }
        assert set(main.COMMAND_HANDLERS.keys()) == expected

    def test_all_handlers_are_callable(self):
        main = _load_main()
        for command_id, handler in main.COMMAND_HANDLERS.items():
            assert callable(handler), f"Handler for {command_id} is not callable"


class TestCreateCycleHandler:
    """Test the create_cycle command handler."""

    async def test_calls_api_with_project_id(self):
        main = _load_main()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"cycle_id": "c123"}

        with patch.object(main, "_api_request", new_callable=AsyncMock, return_value=mock_resp):
            result = await main.squadops_create_cycle({"project_id": "proj1"}, {})

        assert result == {"cycle_id": "c123"}

    async def test_returns_error_on_failure(self):
        main = _load_main()
        mock_resp = MagicMock()
        mock_resp.status_code = 422
        mock_resp.text = "Validation error"

        with patch.object(main, "_api_request", new_callable=AsyncMock, return_value=mock_resp):
            result = await main.squadops_create_cycle({"project_id": "proj1"}, {})

        assert result["error"] == "Validation error"
        assert result["status_code"] == 422


class TestCreateRunHandler:
    """Test the create_run command handler."""

    async def test_calls_api_with_project_and_cycle_id(self):
        main = _load_main()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"run_id": "r123"}

        with patch.object(
            main, "_api_request", new_callable=AsyncMock, return_value=mock_resp
        ) as mock_req:
            result = await main.squadops_create_run(
                {
                    "project_id": "proj1",
                    "cycle_id": "c1",
                },
                {},
            )

        assert result == {"run_id": "r123"}
        call_args = mock_req.call_args
        assert "/projects/proj1/cycles/c1/runs" in call_args[0][1]

    async def test_excludes_path_params_from_body(self):
        main = _load_main()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {}

        with patch.object(
            main, "_api_request", new_callable=AsyncMock, return_value=mock_resp
        ) as mock_req:
            await main.squadops_create_run(
                {
                    "project_id": "proj1",
                    "cycle_id": "c1",
                    "extra_field": "value",
                },
                {},
            )

        body = mock_req.call_args[1]["json"]
        assert "project_id" not in body
        assert "cycle_id" not in body
        assert body["extra_field"] == "value"


class TestCancelHandlers:
    """Test the cancel cycle/run command handlers."""

    async def test_cancel_cycle_calls_correct_url(self):
        main = _load_main()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status": "cancelled"}

        with patch.object(
            main, "_api_request", new_callable=AsyncMock, return_value=mock_resp
        ) as mock_req:
            result = await main.squadops_cancel_cycle(
                {
                    "project_id": "proj1",
                    "cycle_id": "c1",
                },
                {},
            )

        assert result == {"status": "cancelled"}
        call_args = mock_req.call_args
        assert "/projects/proj1/cycles/c1/cancel" in call_args[0][1]

    async def test_cancel_run_calls_correct_url(self):
        main = _load_main()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status": "cancelled"}

        with patch.object(
            main, "_api_request", new_callable=AsyncMock, return_value=mock_resp
        ) as mock_req:
            result = await main.squadops_cancel_run(
                {
                    "project_id": "proj1",
                    "cycle_id": "c1",
                    "run_id": "r1",
                },
                {},
            )

        assert result == {"status": "cancelled"}
        call_args = mock_req.call_args
        assert "/projects/proj1/cycles/c1/runs/r1/cancel" in call_args[0][1]

    async def test_cancel_run_returns_error_on_failure(self):
        main = _load_main()
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.text = "Run not found"

        with patch.object(main, "_api_request", new_callable=AsyncMock, return_value=mock_resp):
            result = await main.squadops_cancel_run(
                {
                    "project_id": "proj1",
                    "cycle_id": "c1",
                    "run_id": "r1",
                },
                {},
            )

        assert result["error"] == "Run not found"
        assert result["status_code"] == 404


class TestSetActiveProfileHandler:
    """Test the set_active_profile command handler."""

    async def test_calls_correct_url(self):
        main = _load_main()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"profile_id": "full"}

        with patch.object(
            main, "_api_request", new_callable=AsyncMock, return_value=mock_resp
        ) as mock_req:
            result = await main.squadops_set_active_profile(
                {
                    "profile_id": "full",
                },
                {},
            )

        assert result == {"profile_id": "full"}
        call_args = mock_req.call_args
        assert "/api/v1/squad-profiles/active" in call_args[0][1]


class TestCreateCycleBodyCleaning:
    """Test that URL-path params are excluded from request bodies."""

    async def test_create_cycle_excludes_project_id_from_body(self):
        main = _load_main()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {}

        with patch.object(
            main, "_api_request", new_callable=AsyncMock, return_value=mock_resp
        ) as mock_req:
            await main.squadops_create_cycle(
                {
                    "project_id": "proj1",
                    "squad_profile_id": "full",
                },
                {},
            )

        body = mock_req.call_args[1]["json"]
        assert "project_id" not in body
        assert body["squad_profile_id"] == "full"


class TestGateHandlers:
    """Test the gate approve/reject command handlers."""

    async def test_gate_approve_sends_approved_decision(self):
        main = _load_main()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"decision": "approved"}

        with patch.object(
            main, "_api_request", new_callable=AsyncMock, return_value=mock_resp
        ) as mock_req:
            await main.squadops_gate_approve(
                {
                    "project_id": "p1",
                    "cycle_id": "c1",
                    "run_id": "r1",
                    "gate_name": "plan-review",
                },
                {},
            )

        call_args = mock_req.call_args
        assert call_args[1]["json"] == {"decision": "approved"}

    async def test_gate_reject_sends_rejected_decision(self):
        main = _load_main()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"decision": "rejected"}

        with patch.object(
            main, "_api_request", new_callable=AsyncMock, return_value=mock_resp
        ) as mock_req:
            await main.squadops_gate_reject(
                {
                    "project_id": "p1",
                    "cycle_id": "c1",
                    "run_id": "r1",
                    "gate_name": "plan-review",
                },
                {},
            )

        call_args = mock_req.call_args
        assert call_args[1]["json"] == {"decision": "rejected"}


class TestIngestArtifactHandler:
    """Test the ingest_artifact command handler (multipart form data)."""

    async def test_sends_multipart_form_data(self):
        main = _load_main()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"artifact_id": "a123"}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)

        with (
            patch.object(main, "_api_client", mock_client),
        ):
            result = await main.squadops_ingest_artifact(
                {
                    "project_id": "proj1",
                    "content": "hello world",
                    "filename": "hello.py",
                    "artifact_type": "source",
                    "media_type": "text/x-python",
                },
                {},
            )

        assert result == {"artifact_id": "a123"}
        call_kwargs = mock_client.post.call_args[1]
        assert "files" in call_kwargs
        assert "data" in call_kwargs
        assert call_kwargs["data"]["artifact_type"] == "source"
        assert call_kwargs["data"]["filename"] == "hello.py"

    async def test_supports_base64_content(self):
        import base64

        main = _load_main()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"artifact_id": "a456"}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)

        b64 = base64.b64encode(b"binary content").decode()

        with (
            patch.object(main, "_api_client", mock_client),
        ):
            result = await main.squadops_ingest_artifact(
                {
                    "project_id": "proj1",
                    "content_base64": b64,
                    "filename": "data.bin",
                    "artifact_type": "config",
                    "media_type": "application/octet-stream",
                },
                {},
            )

        assert result == {"artifact_id": "a456"}
        call_kwargs = mock_client.post.call_args[1]
        # file tuple: (filename, bytes, media_type)
        file_tuple = call_kwargs["files"]["file"]
        assert file_tuple[1] == b"binary content"

    async def test_returns_error_on_failure(self):
        main = _load_main()
        mock_resp = MagicMock()
        mock_resp.status_code = 413
        mock_resp.text = "File too large"

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)

        with (
            patch.object(main, "_api_client", mock_client),
        ):
            result = await main.squadops_ingest_artifact(
                {
                    "project_id": "proj1",
                    "content": "x",
                },
                {},
            )

        assert result["error"] == "File too large"
        assert result["status_code"] == 413


class TestDownloadArtifactHandler:
    """Test the download_artifact command handler (binary response)."""

    async def test_returns_base64_encoded_content(self):
        import base64

        main = _load_main()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"file bytes here"
        mock_resp.headers = {"content-type": "text/x-python"}

        with patch.object(main, "_api_request", new_callable=AsyncMock, return_value=mock_resp):
            result = await main.squadops_download_artifact({"artifact_id": "a789"}, {})

        assert result["artifact_id"] == "a789"
        assert result["content_type"] == "text/x-python"
        assert result["size_bytes"] == 15
        assert base64.b64decode(result["content_base64"]) == b"file bytes here"

    async def test_returns_error_on_404(self):
        main = _load_main()
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.text = "Artifact not found"

        with patch.object(main, "_api_request", new_callable=AsyncMock, return_value=mock_resp):
            result = await main.squadops_download_artifact({"artifact_id": "missing"}, {})

        assert result["error"] == "Artifact not found"
        assert result["status_code"] == 404


class TestSetBaselineHandler:
    """Test the set_baseline command handler."""

    async def test_calls_correct_url(self):
        main = _load_main()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"baseline_id": "b1"}

        with patch.object(
            main, "_api_request", new_callable=AsyncMock, return_value=mock_resp
        ) as mock_req:
            result = await main.squadops_set_baseline(
                {
                    "project_id": "proj1",
                    "artifact_type": "source",
                    "artifact_id": "a1",
                },
                {},
            )

        assert result == {"baseline_id": "b1"}
        call_args = mock_req.call_args
        assert "/projects/proj1/baseline/source" in call_args[0][1]

    async def test_excludes_path_params_from_body(self):
        main = _load_main()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {}

        with patch.object(
            main, "_api_request", new_callable=AsyncMock, return_value=mock_resp
        ) as mock_req:
            await main.squadops_set_baseline(
                {
                    "project_id": "proj1",
                    "artifact_type": "source",
                    "artifact_id": "a1",
                },
                {},
            )

        body = mock_req.call_args[1]["json"]
        assert "project_id" not in body
        assert "artifact_type" not in body
        assert body["artifact_id"] == "a1"


class TestCommandsRunAsTheirCaller:
    """#2068: a command reaches the runtime API with its caller's own authorization, never a
    credential of the console's, so the API applies that user's role (the owner's ruling: a
    service account would have let every console user act with its role).

    Entered at the console app, through the command route's middleware, with a stand-in for
    Continuum's route that runs the handler as Continuum does: in its own task, under
    ``wait_for``. Bugs caught: a console credential coming back; the caller's session not
    consulted; the authorization not reaching the handler's task.
    """

    @staticmethod
    def _client(main, seen):
        import asyncio

        import httpx
        from fastapi.testclient import TestClient

        def runtime_api(request):
            seen.append(request.headers.get("authorization"))
            return httpx.Response(200, json={"ok": True})

        main._api_client = httpx.AsyncClient(
            transport=httpx.MockTransport(runtime_api), base_url="http://runtime-api:8001"
        )

        async def continuum_command_route():
            cancel = main.squadops_cancel_cycle({"project_id": "p", "cycle_id": "c"}, {})
            return await asyncio.wait_for(cancel, timeout=5)

        main.app.add_api_route(main.COMMAND_ROUTE, continuum_command_route, methods=["POST"])
        return TestClient(main.app)

    @pytest.mark.parametrize(
        ("header", "session_token", "sent"),
        [
            (None, "user-token", "Bearer user-token"),
            ("Bearer from-the-browser", "user-token", "Bearer from-the-browser"),
            (None, None, None),
        ],
        ids=["their-session", "their-own-header", "neither-so-the-api-refuses"],
    )
    def test_a_command_carries_its_callers_authorization(self, header, session_token, sent):
        main = _load_main()
        seen: list[str | None] = []
        client = self._client(main, seen)
        client.cookies.set("session_id", "s-1")

        with patch.object(main, "session_access_token", AsyncMock(return_value=session_token)):
            resp = client.post(
                main.COMMAND_ROUTE, headers={"Authorization": header} if header else {}
            )

        assert resp.status_code == 200
        assert seen == [sent]

    def test_a_proxied_call_carries_its_callers_session_token(self):
        main = _load_main()
        seen: list[str | None] = []
        client = self._client(main, seen)
        client.cookies.set("session_id", "s-1")

        with patch.object(main, "session_access_token", AsyncMock(return_value="user-token")):
            client.get("/api/v1/projects")

        assert seen == ["Bearer user-token"]


class TestConfigJsEndpoint:
    """Test the /config.js endpoint."""

    async def test_config_js_contains_public_urls(self):
        main = _load_main()
        from fastapi.testclient import TestClient

        client = TestClient(main.app, raise_server_exceptions=False)
        resp = client.get("/config.js")
        assert resp.status_code == 200
        assert "application/javascript" in resp.headers["content-type"]
        assert "window.__SQUADOPS_CONFIG__" in resp.text
        assert "window.squadops.apiFetch" in resp.text
