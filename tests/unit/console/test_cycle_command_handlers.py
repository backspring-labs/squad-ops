"""Tests for console command handler registry and handler functions."""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import APIRouter
from pydantic import BaseModel, Field

from tests.unit.console.console_settings import compose_settings


class CommandExecuteRequestBody(BaseModel):
    """The pinned shell's body for ``POST /api/commands/execute``, field for field: Continuum
    v1.0.2 (``console/continuum.lock``, sha ``43369054``), ``src/continuum/adapters/web/api.py:78-84``.
    Unknown keys are dropped, as pydantic's default has it there too (#2903's ``params``). Module
    level because FastAPI resolves a route's annotations against the module's globals, and this
    module postpones its annotations."""

    command_id: str
    args: dict[str, Any] = Field(default_factory=dict)
    dry_run: bool = False
    confirmed: bool = False


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
    # #2431: the console requires every setting compose gives it.
    with patch.dict(os.environ, compose_settings()):
        return importlib.import_module("main")


class TestCommandHandlerRegistry:
    """Verify COMMAND_HANDLERS maps all expected command IDs."""

    def test_registry_has_12_handlers(self):
        main = _load_main()
        assert len(main.COMMAND_HANDLERS) == 12

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
            "squadops.revise_goal_set",
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


class TestReviseGoalSetHandler:
    """SIP-0115 slice 4 (#2887): the goals panel's edit. Bug caught: the API's 409, a revision
    written first by someone else, reaching the panel as anything but that refusal with its
    status and its envelope, so the panel can't say plainly what happened."""

    async def test_a_stale_revision_is_relayed_with_the_apis_status_and_envelope(self):
        main = _load_main()
        envelope = (
            '{"detail": {"error": {"code": "STALE_GOAL_SET_REVISION", "message": '
            "\"Project p-1's goal set is at revision 3; revision 3 doesn't follow it\", "
            '"details": null}}}'
        )
        mock_resp = MagicMock(status_code=409, text=envelope)

        with patch.object(main, "_api_request", new_callable=AsyncMock, return_value=mock_resp):
            result = await main.squadops_revise_goal_set(
                {"project_id": "p-1", "expected_revision": 2, "reason": "r", "goal_set": {}}, {}
            )

        assert result == {"error": envelope, "status_code": 409}


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


class TestTheBodyThePluginsPost:
    """#2903/#2904: a plugin posts ``{command_id, args}`` and, when the bus asks, the same body
    with ``confirmed: true`` (``console/continuum-plugins/shared/commands.js``). Entered at the
    console app's command route, through its middleware, with a stand-in for the pinned shell's
    route (Continuum v1.0.2, sha ``43369054``; the test env has no ``continuum``,
    ``_stub_continuum_and_bff``): the body model's four fields and defaults
    (``adapters/web/api.py:78-84``), a ``confirm``-level command answered ``pending`` until
    ``confirmed`` (``app/command_bus.py:293-303``), the handler called with ``args`` (``:357``) in
    its own task under ``wait_for``, and an exception answered 200 ``failed`` (``:401-421``). The
    danger levels are the plugins' own manifests'.

    Bugs caught: a handler reading its arguments from anywhere but the ``args`` dict the bus hands
    it; the args a plugin sends being ones its handler doesn't take (the old ``params`` body
    reached every handler as ``{}``); a confirm-level command running on the first post.
    """

    #: The args each plugin sends, verbatim from its source.
    GATE = {"project_id": "p-1", "cycle_id": "c-1", "run_id": "r-1", "gate_name": "plan_review"}
    GATE_PATH = "/api/v1/projects/p-1/cycles/c-1/runs/r-1/gates/plan_review"
    #: The goals panel's revision body: every key of the API's ``GoalSetRevisionRequest``.
    GOAL_SET_REVISION = {
        "expected_revision": 2,
        "reason": "Move the export item first",
        "idempotency_key": "console-goals-k-1",
        "goal_set": {"goal": "A reading log", "backlog": []},
    }

    @staticmethod
    def _danger_levels() -> dict[str, str]:
        import tomllib

        plugins = Path(__file__).parents[3] / "console" / "continuum-plugins"
        return {
            command["id"]: command.get("danger_level", "safe")
            for manifest in plugins.glob("squadops.*/plugin.toml")
            for command in tomllib.loads(manifest.read_text(encoding="utf-8"))
            .get("contributions", {})
            .get("command", [])
        }

    @classmethod
    def _client(cls, main, seen: list):
        import asyncio
        import json

        import httpx
        from fastapi.testclient import TestClient

        def runtime_api(request: httpx.Request) -> httpx.Response:
            if request.headers.get("content-type", "").startswith("multipart/"):
                body = request.content.decode()
            else:
                body = json.loads(request.content) if request.content else None
            seen.append((request.method, request.url.path, body))
            return httpx.Response(200, json={"id": "made"})

        main._api_client = httpx.AsyncClient(
            transport=httpx.MockTransport(runtime_api), base_url="http://runtime-api:8001"
        )
        levels = cls._danger_levels()

        async def continuum_command_route(body: CommandExecuteRequestBody) -> dict:
            level = levels[body.command_id]
            answer = {"command_id": body.command_id, "danger_level": level, "result": {}}
            if level in ("confirm", "danger") and not body.confirmed:
                return {**answer, "status": "pending", "requires_confirmation": True}
            handler = main.COMMAND_HANDLERS[body.command_id]
            try:
                result = await asyncio.wait_for(handler(body.args, {}), timeout=5)
            except Exception as e:  # the bus's own catch (command_bus.py:401)
                return {**answer, "status": "failed", "error": str(e)}
            return {**answer, "status": "success", "result": result}

        main.app.add_api_route(main.COMMAND_ROUTE, continuum_command_route, methods=["POST"])
        return TestClient(main.app)

    @pytest.mark.parametrize(
        ("command_id", "args", "sent"),
        [
            (
                "squadops.gate_approve",
                GATE,
                ("POST", GATE_PATH, {"decision": "approved"}),
            ),
            (
                "squadops.create_cycle",
                {"project_id": "p-1", "squad_profile_id": "full", "prd_ref": "a-1"},
                (
                    "POST",
                    "/api/v1/projects/p-1/cycles",
                    {"squad_profile_id": "full", "prd_ref": "a-1"},
                ),
            ),
        ],
        ids=["GateDecisionCard", "CycleCreateModal"],
    )
    def test_the_args_a_plugin_posts_reach_its_handler_and_the_runtime_api(
        self, command_id, args, sent
    ):
        main = _load_main()
        seen: list = []
        client = self._client(main, seen)

        resp = client.post(main.COMMAND_ROUTE, json={"command_id": command_id, "args": args})

        assert resp.status_code == 200
        assert resp.json()["status"] == "success", resp.json()
        assert resp.json()["result"] == {"id": "made"}
        assert seen == [sent]

    def test_the_prd_a_plugin_posts_reaches_the_runtime_api_as_a_file(self):
        main = _load_main()
        seen: list = []
        client = self._client(main, seen)
        # CycleCreateModal's ingest, verbatim.
        args = {
            "project_id": "p-1",
            "filename": "prd.md",
            "artifact_type": "documentation",
            "media_type": "text/markdown",
            "content": "# A product\n",
        }

        resp = client.post(
            main.COMMAND_ROUTE, json={"command_id": "squadops.ingest_artifact", "args": args}
        )

        assert resp.json()["status"] == "success", resp.json()
        [(method, path, form)] = seen
        assert (method, path) == ("POST", "/api/v1/projects/p-1/artifacts/ingest")
        assert 'filename="prd.md"' in form and "# A product" in form

    @pytest.mark.parametrize(
        ("command_id", "args", "sent"),
        [
            (
                "squadops.gate_reject",
                GATE,
                ("POST", GATE_PATH, {"decision": "rejected"}),
            ),
            (
                "squadops.set_active_profile",
                {"profile_id": "full"},
                ("POST", "/api/v1/squad-profiles/active", {"profile_id": "full"}),
            ),
            (
                # GoalsPanel's edit, as `goals.js`'s `revisionArgs` builds it.
                "squadops.revise_goal_set",
                {"project_id": "p-1", **GOAL_SET_REVISION},
                ("POST", "/api/v1/projects/p-1/goal-set/revisions", GOAL_SET_REVISION),
            ),
        ],
        ids=["GateDecisionCard-reject", "ProjectsProfiles", "GoalsPanel"],
    )
    def test_a_confirm_level_command_runs_only_on_the_re_post_with_confirmed(
        self, command_id, args, sent
    ):
        main = _load_main()
        seen: list = []
        client = self._client(main, seen)
        body = {"command_id": command_id, "args": args}

        asked = client.post(main.COMMAND_ROUTE, json=body).json()

        assert (asked["status"], asked["requires_confirmation"]) == ("pending", True)
        assert asked["danger_level"] == "confirm"
        assert seen == [], "nothing ran: the bus asked first"

        confirmed = client.post(main.COMMAND_ROUTE, json={**body, "confirmed": True}).json()

        assert confirmed["status"] == "success", confirmed
        assert seen == [sent]

    def test_the_old_body_reaches_the_handler_as_nothing_and_the_bus_answers_200_failed(self):
        """#2903's shape: ``params`` is not a field of the body, so it is dropped."""
        main = _load_main()
        seen: list = []
        client = self._client(main, seen)

        resp = client.post(
            main.COMMAND_ROUTE, json={"command_id": "squadops.gate_approve", "params": self.GATE}
        )

        assert resp.status_code == 200
        assert resp.json()["status"] == "failed"
        assert "project_id" in resp.json()["error"]
        assert seen == []


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
