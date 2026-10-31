"""Runtime-api application logging configuration (#427).

The bug: the runtime-api container emitted only uvicorn access logs, so the
in-process executor's application logs — including a run's terminal exception —
never reached stdout and every failure was a black box. ``configure_logging``
attaches a named stdout handler to the root logger so those logs surface.
"""

from __future__ import annotations

import io
import logging

import pytest

from squadops.api.runtime.logging_setup import _HANDLER_NAME, configure_logging

pytestmark = [pytest.mark.domain_api]


@pytest.fixture(autouse=True)
def _restore_root_logging():
    """Save/restore the global root logger so these tests can't leak handlers or a
    mutated level into the rest of the suite."""
    root = logging.getLogger()
    saved_handlers = root.handlers[:]
    saved_level = root.level
    yield
    root.handlers[:] = saved_handlers
    root.setLevel(saved_level)


def _our_handlers() -> list[logging.Handler]:
    return [h for h in logging.getLogger().handlers if getattr(h, "name", None) == _HANDLER_NAME]


def test_attaches_a_named_stdout_handler_at_info_by_default(monkeypatch):
    monkeypatch.delenv("SQUADOPS_LOG_LEVEL", raising=False)
    configure_logging()
    handlers = _our_handlers()
    assert len(handlers) == 1
    assert isinstance(handlers[0], logging.StreamHandler)
    assert handlers[0].level == logging.INFO
    assert logging.getLogger().level == logging.INFO


def test_level_from_env(monkeypatch):
    monkeypatch.setenv("SQUADOPS_LOG_LEVEL", "debug")  # case-insensitive
    configure_logging()
    assert logging.getLogger().level == logging.DEBUG
    assert _our_handlers()[0].level == logging.DEBUG


def test_explicit_level_arg_overrides_env(monkeypatch):
    monkeypatch.setenv("SQUADOPS_LOG_LEVEL", "DEBUG")
    configure_logging(level="WARNING")
    assert logging.getLogger().level == logging.WARNING


def test_unknown_level_falls_back_to_info_not_crash(monkeypatch):
    # a bad env value must never crash the process at import or silently disable logging
    monkeypatch.setenv("SQUADOPS_LOG_LEVEL", "NOT_A_LEVEL")
    configure_logging()
    assert logging.getLogger().level == logging.INFO


def test_idempotent_reuses_handler_and_updates_level(monkeypatch):
    monkeypatch.delenv("SQUADOPS_LOG_LEVEL", raising=False)
    configure_logging()
    configure_logging(level="ERROR")  # second call — re-import / re-assert
    handlers = _our_handlers()
    assert len(handlers) == 1  # no duplicate stacked on root
    assert handlers[0].level == logging.ERROR


def test_squadops_logger_message_reaches_the_stream(monkeypatch):
    # the functional guarantee: an application log actually lands on our handler
    monkeypatch.delenv("SQUADOPS_LOG_LEVEL", raising=False)
    configure_logging()
    buf = io.StringIO()
    _our_handlers()[0].setStream(buf)
    logging.getLogger("squadops.cycles.executor").info("run failed: CycleError boom")
    assert "run failed: CycleError boom" in buf.getvalue()


def test_below_level_message_is_suppressed(monkeypatch):
    monkeypatch.delenv("SQUADOPS_LOG_LEVEL", raising=False)
    configure_logging(level="WARNING")
    buf = io.StringIO()
    _our_handlers()[0].setStream(buf)
    logging.getLogger("squadops.x").info("chatty")  # below WARNING
    logging.getLogger("squadops.x").warning("important")
    out = buf.getvalue()
    assert "chatty" not in out
    assert "important" in out


class TestTheAuditSinkIsSeparate:
    """#560: audit records are a compliance surface and leave the application stream —
    to their own rotating file when a path is configured, unchanged (stdout) when not."""

    def test_with_a_path_audit_records_land_in_the_file_and_not_on_stdout(
        self, tmp_path, monkeypatch, capsys
    ):
        from squadops.api.runtime.logging_setup import AUDIT_LOGGER_NAME, configure_audit_sink

        path = tmp_path / "audit" / "runtime-api.jsonl"
        handler = configure_audit_sink(str(path))
        audit = logging.getLogger(AUDIT_LOGGER_NAME)
        audit.info('{"event": "login", "user": "ada"}')
        handler.flush()
        assert path.read_text().strip() == '{"event": "login", "user": "ada"}'
        assert audit.propagate is False
        assert configure_audit_sink(str(path)) is handler, "idempotent on the same path"

    def test_without_a_path_nothing_changes_and_boot_says_so_once(self, caplog):
        from squadops.api.runtime.logging_setup import AUDIT_LOGGER_NAME, configure_audit_sink

        audit = logging.getLogger(AUDIT_LOGGER_NAME)
        for h in list(audit.handlers):
            audit.removeHandler(h)
        audit.propagate = True
        with caplog.at_level(logging.WARNING):
            assert configure_audit_sink(None) is None
        assert "SQUADOPS_AUDIT_LOG_PATH" in caplog.text
        assert audit.propagate is True

    def test_third_party_chatter_is_demoted(self, monkeypatch):
        monkeypatch.delenv("SQUADOPS_AUDIT_LOG_PATH", raising=False)
        configure_logging()
        assert logging.getLogger("httpx").level == logging.WARNING
        assert logging.getLogger("httpcore").level == logging.WARNING


class TestRoutineSuccessesLeaveTheAccessLog:
    """#2425: a heartbeat or health probe answered 2xx is recorded elsewhere (the agent's
    ``last_heartbeat``, Docker's health history), so its access line is dropped; a failed one,
    and every other request, is still logged."""

    @pytest.fixture(autouse=True)
    def _access_logger_restored(self):
        from squadops.api.runtime.logging_setup import ACCESS_LOGGER_NAME

        access = logging.getLogger(ACCESS_LOGGER_NAME)
        saved = (access.filters[:], access.handlers[:], access.level, access.propagate)
        yield
        access.filters[:], access.handlers[:] = saved[0], saved[1]
        access.setLevel(saved[2])
        access.propagate = saved[3]

    def test_the_quieted_requests_are_the_apps_own_heartbeat_and_health_routes(self):
        """Read off the runtime app's route table, as ``create_app`` registers it. Bug caught: a
        route moved or renamed while the quiet list kept the old path, so every heartbeat is back
        in the log, or the list naming a route the app does not serve."""
        from fastapi.routing import APIRoute

        from squadops.api.routes.agent_status import create_or_update_agent_status
        from squadops.api.runtime.main import ROUTINE_ACCESS, create_app, health_check
        from tests.unit.cli.test_integration import _test_config

        app = create_app(_test_config())
        served = {
            (method, route.path)
            for route in app.routes
            if isinstance(route, APIRoute)
            and route.endpoint in (create_or_update_agent_status, health_check)
            for method in route.methods
        }
        assert served == set(ROUTINE_ACCESS)

    async def test_a_served_request_keeps_its_line_only_when_it_is_news(self, monkeypatch):
        """Entered at a real uvicorn server, whose startup logging config is applied after the
        filter is installed, as the runtime API's ``--factory`` start does, with the set the
        runtime names. Bugs caught: uvicorn's dictConfig dropping the filter, or a uvicorn whose
        access record no longer carries (client, method, path, version, status), either of which
        puts every heartbeat back in the log; and a filter that also swallows a failed heartbeat
        or another route."""
        import asyncio
        import socket

        import httpx
        import uvicorn
        from fastapi import FastAPI, Response

        from squadops.api.routes.agent_status import HEARTBEAT_PATH
        from squadops.api.runtime.logging_setup import ACCESS_LOGGER_NAME, quiet_routine_successes
        from squadops.api.runtime.main import HEALTH_PATH, ROUTINE_ACCESS

        monkeypatch.delenv("SQUADOPS_LOG_LEVEL", raising=False)
        monkeypatch.delenv("SQUADOPS_AUDIT_LOG_PATH", raising=False)
        configure_logging()
        quiet_routine_successes(ROUTINE_ACCESS)

        app = FastAPI()
        answer = {"status": 200}

        @app.post(HEARTBEAT_PATH)
        async def heartbeat() -> Response:
            return Response(status_code=answer["status"])

        @app.get(HEALTH_PATH)
        async def health() -> dict:
            return {"status": "healthy"}

        @app.get("/api/v1/cycles")
        async def cycles() -> list:
            return []

        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(app, lifespan="off"))
        lines: list[str] = []

        class _Capture(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                lines.append(record.getMessage())

        logging.getLogger(ACCESS_LOGGER_NAME).addHandler(_Capture())
        serving = asyncio.create_task(server.serve(sockets=[sock]))
        try:
            while not server.started:
                await asyncio.sleep(0.01)
            async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}") as client:
                await client.post(HEARTBEAT_PATH)
                await client.get(HEALTH_PATH)
                await client.get("/api/v1/cycles")
                answer["status"] = 503
                await client.post(HEARTBEAT_PATH)
        finally:
            server.should_exit = True
            await serving
            sock.close()

        assert [line.split(" - ", 1)[1] for line in lines] == [
            '"GET /api/v1/cycles HTTP/1.1" 200',
            '"POST /api/v1/agents/status HTTP/1.1" 503',
        ]

    @pytest.mark.parametrize(
        ("args", "root_level", "kept"),
        [
            (("c", "POST", "/api/v1/agents/status", "1.1", 204), logging.INFO, False),
            (("c", "POST", "/api/v1/agents/status", "1.1", 204), logging.DEBUG, True),
            (("c", "GET", "/health?verbose=1", "1.1", 200), logging.INFO, True),
            (("c", "GET", "/health", "1.1", 301), logging.INFO, True),
            (("an access line of another shape",), logging.INFO, True),
        ],
        ids=["heartbeat-ok", "at-debug", "other-path", "redirect", "other-shape"],
    )
    def test_the_filter_drops_only_a_routine_success_below_debug(self, args, root_level, kept):
        """Bugs caught: DEBUG not bringing the lines back for a heartbeat investigation; a
        probe with a query string, a non-2xx answer or an unfamiliar record being dropped."""
        from squadops.api.runtime.logging_setup import RoutineSuccessFilter

        quiet = RoutineSuccessFilter({("POST", "/api/v1/agents/status"), ("GET", "/health")})
        logging.getLogger().setLevel(root_level)
        record = logging.makeLogRecord({"msg": "%s", "args": args})
        assert quiet.filter(record) is kept
