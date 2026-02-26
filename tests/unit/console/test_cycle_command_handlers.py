"""Tests for console command handler registry and handler functions."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# The console main.py imports from continuum and auth_bff which aren't installed
# in the test environment. We inject stubs so we can import the command handler
# registry and individual handler functions.

_docker_dir = str(Path(__file__).parents[3] / "console" / "app")


@pytest.fixture(autouse=True)
def _stub_continuum_and_bff():
    """Inject stub modules for continuum and auth_bff so main.py can be imported."""
    stubs = {}

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

    # Stub auth_bff
    auth_bff_stub = MagicMock()
    auth_bff_stub.router = MagicMock()
    auth_bff_stub.configure = MagicMock()
    stubs["auth_bff"] = auth_bff_stub
    sys.modules["auth_bff"] = auth_bff_stub

    # Add console/app to sys.path so main.py can be found
    if _docker_dir not in sys.path:
        sys.path.insert(0, _docker_dir)

    yield

    # Cleanup
    for mod_name in stubs:
        sys.modules.pop(mod_name, None)
    sys.modules.pop("main", None)
    if _docker_dir in sys.path:
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
        mock_resp.json.return_value = {"profile_id": "full-squad"}

        with patch.object(
            main, "_api_request", new_callable=AsyncMock, return_value=mock_resp
        ) as mock_req:
            result = await main.squadops_set_active_profile(
                {
                    "profile_id": "full-squad",
                },
                {},
            )

        assert result == {"profile_id": "full-squad"}
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
                    "squad_profile_id": "full-squad",
                },
                {},
            )

        body = mock_req.call_args[1]["json"]
        assert "project_id" not in body
        assert body["squad_profile_id"] == "full-squad"


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
            patch.object(main, "_get_service_token", new_callable=AsyncMock, return_value="tok"),
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
            patch.object(main, "_get_service_token", new_callable=AsyncMock, return_value=""),
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
            patch.object(main, "_get_service_token", new_callable=AsyncMock, return_value=""),
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


class TestServiceTokenManagement:
    """Test the service token caching logic."""

    async def test_returns_empty_when_no_secret(self):
        main = _load_main()
        main.SERVICE_CLIENT_SECRET = ""
        main._service_token = None
        main._service_token_expires_at = 0
        token = await main._get_service_token()
        assert token == ""

    async def test_returns_cached_token_when_valid(self):
        import time

        main = _load_main()
        main._service_token = "cached-token"
        main._service_token_expires_at = time.time() + 300
        token = await main._get_service_token()
        assert token == "cached-token"


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
