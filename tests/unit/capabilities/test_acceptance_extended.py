"""
Unit tests for async acceptance check methods (SIP-0070 Phase 1.3).

Tests:
- http_status: mock httpx → PASS, FAIL, connection error, timeout
- process_running: mock subprocess → running, not running, healthy, unhealthy, not found
- json_schema: valid PASS, invalid FAIL, missing document
- command_exit_code: exit 0 PASS, exit 1 FAIL, timeout, cwd security, env, truncation
- evaluate_async: per-check timeout enforcement
- evaluate_all_async: no short-circuit, suite timeout SKIP, suite_outcome = FAIL
"""

import asyncio
import json

import pytest

from squadops.capabilities.acceptance import AcceptanceCheckEngine
from squadops.capabilities.models import (
    AcceptanceCheck,
    AcceptanceContext,
    CheckType,
)

pytestmark = [pytest.mark.domain_pulse_checks]


@pytest.fixture
def temp_chroot(tmp_path):
    chroot = tmp_path / "chroot"
    chroot.mkdir()
    return chroot


@pytest.fixture
def engine(temp_chroot):
    return AcceptanceCheckEngine(temp_chroot)


@pytest.fixture
def ctx(temp_chroot):
    return AcceptanceContext(
        run_root=str(temp_chroot),
        cycle_id="cyc-001",
        workload_id="wl-001",
        run_id="run-001",
    )


def _make_fake_proc(stdout=b"", stderr=b"", returncode=0):
    """Create a fake process object with async communicate()."""

    class FakeProc:
        def __init__(self):
            self.returncode = returncode

        async def communicate(self):
            return stdout, stderr

    return FakeProc()


# =========================================================================
# http_status tests
# =========================================================================


class TestHttpStatus:
    async def test_pass(self, engine, ctx, monkeypatch):
        """http_status PASS when status matches."""
        import httpx

        class FakeResponse:
            status_code = 200

        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def get(self, url, **kwargs):
                return FakeResponse()

        monkeypatch.setattr(httpx, "AsyncClient", FakeClient)

        check = AcceptanceCheck(
            check_type=CheckType.HTTP_STATUS,
            target="",
            url="http://localhost:8000/health",
            expected_status=200,
        )
        result = await engine.evaluate_async(check, ctx)
        assert result.passed is True
        assert result.actual_value == 200

    async def test_fail_wrong_status(self, engine, ctx, monkeypatch):
        """http_status FAIL when status mismatches."""
        import httpx

        class FakeResponse:
            status_code = 500

        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def get(self, url, **kwargs):
                return FakeResponse()

        monkeypatch.setattr(httpx, "AsyncClient", FakeClient)

        check = AcceptanceCheck(
            check_type=CheckType.HTTP_STATUS,
            target="",
            url="http://localhost:8000/health",
            expected_status=200,
        )
        result = await engine.evaluate_async(check, ctx)
        assert result.passed is False
        assert "500" in result.error

    async def test_connection_error(self, engine, ctx, monkeypatch):
        """http_status FAIL on connection error."""
        import httpx

        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def get(self, url, **kwargs):
                raise httpx.ConnectError("refused")

        monkeypatch.setattr(httpx, "AsyncClient", FakeClient)

        check = AcceptanceCheck(
            check_type=CheckType.HTTP_STATUS,
            target="",
            url="http://localhost:8000/health",
            expected_status=200,
        )
        result = await engine.evaluate_async(check, ctx)
        assert result.passed is False
        assert "Connection error" in result.error

    async def test_timeout(self, engine, ctx, monkeypatch):
        """http_status FAIL on timeout."""
        import httpx

        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def get(self, url, **kwargs):
                raise httpx.TimeoutException("timed out")

        monkeypatch.setattr(httpx, "AsyncClient", FakeClient)

        check = AcceptanceCheck(
            check_type=CheckType.HTTP_STATUS,
            target="",
            url="http://localhost:8000/health",
            expected_status=200,
        )
        result = await engine.evaluate_async(check, ctx)
        assert result.passed is False
        assert "timed out" in result.error.lower()


# =========================================================================
# process_running tests
# =========================================================================


class TestProcessRunning:
    async def test_running(self, engine, ctx, monkeypatch):
        """process_running PASS when container is running."""
        state_json = json.dumps({"Running": True}).encode()

        async def fake_create(*args, **kwargs):
            return _make_fake_proc(stdout=state_json)

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)

        check = AcceptanceCheck(
            check_type=CheckType.PROCESS_RUNNING,
            target="",
            container_name="my-app",
        )
        result = await engine.evaluate_async(check, ctx)
        assert result.passed is True

    async def test_not_running(self, engine, ctx, monkeypatch):
        """process_running FAIL when container is stopped."""
        state_json = json.dumps({"Running": False}).encode()

        async def fake_create(*args, **kwargs):
            return _make_fake_proc(stdout=state_json)

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)

        check = AcceptanceCheck(
            check_type=CheckType.PROCESS_RUNNING,
            target="",
            container_name="my-app",
        )
        result = await engine.evaluate_async(check, ctx)
        assert result.passed is False
        assert "not running" in result.error

    async def test_unhealthy(self, engine, ctx, monkeypatch):
        """process_running FAIL when container is running but unhealthy."""
        state_json = json.dumps(
            {
                "Running": True,
                "Health": {"Status": "unhealthy"},
            }
        ).encode()

        async def fake_create(*args, **kwargs):
            return _make_fake_proc(stdout=state_json)

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)

        check = AcceptanceCheck(
            check_type=CheckType.PROCESS_RUNNING,
            target="",
            container_name="my-app",
        )
        result = await engine.evaluate_async(check, ctx)
        assert result.passed is False
        assert "unhealthy" in result.error

    async def test_healthy(self, engine, ctx, monkeypatch):
        """process_running PASS when container is running and healthy."""
        state_json = json.dumps(
            {
                "Running": True,
                "Health": {"Status": "healthy"},
            }
        ).encode()

        async def fake_create(*args, **kwargs):
            return _make_fake_proc(stdout=state_json)

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)

        check = AcceptanceCheck(
            check_type=CheckType.PROCESS_RUNNING,
            target="",
            container_name="my-app",
        )
        result = await engine.evaluate_async(check, ctx)
        assert result.passed is True
        assert result.actual_value["health"] == "healthy"

    async def test_container_not_found(self, engine, ctx, monkeypatch):
        """process_running FAIL when container doesn't exist."""

        async def fake_create(*args, **kwargs):
            return _make_fake_proc(stderr=b"No such container", returncode=1)

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)

        check = AcceptanceCheck(
            check_type=CheckType.PROCESS_RUNNING,
            target="",
            container_name="nonexistent",
        )
        result = await engine.evaluate_async(check, ctx)
        assert result.passed is False
        assert "not found" in result.error.lower()


# =========================================================================
# json_schema tests
# =========================================================================


class TestJsonSchema:
    async def test_valid_document(self, engine, ctx, temp_chroot):
        """json_schema PASS when document validates against schema."""
        doc = temp_chroot / "output" / "report.json"
        doc.parent.mkdir(parents=True)
        doc.write_text(json.dumps({"name": "test", "version": 1}))

        schema = temp_chroot / "schemas" / "report.schema.json"
        schema.parent.mkdir(parents=True)
        schema.write_text(
            json.dumps(
                {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "version": {"type": "integer"},
                    },
                    "required": ["name", "version"],
                }
            )
        )

        check = AcceptanceCheck(
            check_type=CheckType.JSON_SCHEMA,
            target="output/report.json",
            schema="schemas/report.schema.json",
        )
        result = await engine.evaluate_async(check, ctx)
        assert result.passed is True

    async def test_invalid_document(self, engine, ctx, temp_chroot):
        """json_schema FAIL when document fails validation."""
        doc = temp_chroot / "output" / "report.json"
        doc.parent.mkdir(parents=True)
        doc.write_text(json.dumps({"name": 123}))

        schema = temp_chroot / "schemas" / "report.schema.json"
        schema.parent.mkdir(parents=True)
        schema.write_text(
            json.dumps(
                {
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                    "required": ["name"],
                }
            )
        )

        check = AcceptanceCheck(
            check_type=CheckType.JSON_SCHEMA,
            target="output/report.json",
            schema="schemas/report.schema.json",
        )
        result = await engine.evaluate_async(check, ctx)
        assert result.passed is False
        assert "Schema validation failed" in result.error

    async def test_missing_document(self, engine, ctx, temp_chroot):
        """json_schema FAIL when document doesn't exist."""
        schema = temp_chroot / "schemas" / "report.schema.json"
        schema.parent.mkdir(parents=True)
        schema.write_text(json.dumps({"type": "object"}))

        check = AcceptanceCheck(
            check_type=CheckType.JSON_SCHEMA,
            target="output/missing.json",
            schema="schemas/report.schema.json",
        )
        result = await engine.evaluate_async(check, ctx)
        assert result.passed is False
        assert "not found" in result.error.lower()


# =========================================================================
# command_exit_code tests
# =========================================================================


class TestCommandExitCode:
    async def test_exit_0_pass(self, engine, ctx, monkeypatch):
        """command_exit_code PASS when exit code matches expected (0)."""

        async def fake_create(*args, **kwargs):
            return _make_fake_proc(stdout=b"ok\n")

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)

        check = AcceptanceCheck(
            check_type=CheckType.COMMAND_EXIT_CODE,
            target="",
            command=("echo", "test"),
        )
        result = await engine.evaluate_async(check, ctx)
        assert result.passed is True
        assert result.actual_value == 0

    async def test_exit_1_fail(self, engine, ctx, monkeypatch):
        """command_exit_code FAIL when exit code != expected."""

        async def fake_create(*args, **kwargs):
            return _make_fake_proc(stderr=b"error\n", returncode=1)

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)

        check = AcceptanceCheck(
            check_type=CheckType.COMMAND_EXIT_CODE,
            target="",
            command=("false",),
        )
        result = await engine.evaluate_async(check, ctx)
        assert result.passed is False
        assert "exit code" in result.error.lower()

    async def test_timeout(self, engine, ctx, monkeypatch):
        """command_exit_code FAIL on command timeout."""

        async def fake_create(*args, **kwargs):
            class SlowProc:
                returncode = None

                async def communicate(self):
                    raise TimeoutError()

            return SlowProc()

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)

        check = AcceptanceCheck(
            check_type=CheckType.COMMAND_EXIT_CODE,
            target="",
            command=("sleep", "999"),
        )
        result = await engine.evaluate_async(check, ctx, max_check_seconds=0.1)
        assert result.passed is False
        assert "timed out" in result.error.lower()

    async def test_relative_cwd_resolved(self, engine, ctx, temp_chroot, monkeypatch):
        """command_exit_code resolves cwd relative to chroot."""
        captured_kwargs = {}

        async def fake_create(*args, **kwargs):
            captured_kwargs.update(kwargs)
            return _make_fake_proc()

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)

        subdir = temp_chroot / "workspace"
        subdir.mkdir()

        check = AcceptanceCheck(
            check_type=CheckType.COMMAND_EXIT_CODE,
            target="",
            command=("ls",),
            cwd="workspace",
        )
        result = await engine.evaluate_async(check, ctx)
        assert result.passed is True
        assert captured_kwargs["cwd"] == str(temp_chroot / "workspace")

    async def test_env_allowlist_only(self, engine, ctx, monkeypatch):
        """command_exit_code passes only declared env vars + safe PATH."""
        captured_kwargs = {}

        async def fake_create(*args, **kwargs):
            captured_kwargs.update(kwargs)
            return _make_fake_proc()

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)

        check = AcceptanceCheck(
            check_type=CheckType.COMMAND_EXIT_CODE,
            target="",
            command=("echo",),
            env=(("MY_VAR", "hello"),),
        )
        result = await engine.evaluate_async(check, ctx)
        assert result.passed is True
        env = captured_kwargs["env"]
        assert env["MY_VAR"] == "hello"
        assert env["PATH"] == engine._SAFE_PATH
        # Host env should NOT leak
        assert "HOME" not in env

    async def test_truncation_metadata(self, engine, ctx, monkeypatch):
        """command_exit_code populates truncation metadata when output exceeds limit (D20)."""
        big_output = b"x" * 200

        async def fake_create(*args, **kwargs):
            return _make_fake_proc(stdout=big_output, stderr=b"small")

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)

        check = AcceptanceCheck(
            check_type=CheckType.COMMAND_EXIT_CODE,
            target="",
            command=("echo",),
        )
        result = await engine.evaluate_async(check, ctx, max_output_bytes=100)
        assert result.passed is True
        assert result.metadata["truncated"] is True
        assert result.metadata["stdout_bytes"] == 200
        assert result.metadata["stderr_bytes"] == 5
        assert result.metadata["stdout_truncated"] is True
        assert result.metadata["stderr_truncated"] is False

    async def test_command_not_found(self, engine, ctx, monkeypatch):
        """command_exit_code FAIL when command doesn't exist."""

        async def fake_create(*args, **kwargs):
            raise FileNotFoundError("not found")

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)

        check = AcceptanceCheck(
            check_type=CheckType.COMMAND_EXIT_CODE,
            target="",
            command=("nonexistent_cmd",),
        )
        result = await engine.evaluate_async(check, ctx)
        assert result.passed is False
        assert "not found" in result.error.lower()


# =========================================================================
# evaluate_async dispatch tests
# =========================================================================


class TestEvaluateAsync:
    async def test_sync_check_type_delegates(self, engine, ctx, temp_chroot):
        """Sync check types are handled by the sync evaluate() path."""
        target = temp_chroot / "exists.txt"
        target.write_text("content")

        check = AcceptanceCheck(
            check_type=CheckType.FILE_EXISTS,
            target="exists.txt",
        )
        result = await engine.evaluate_async(check, ctx)
        assert result.passed is True


# =========================================================================
# evaluate_all_async tests
# =========================================================================


class TestEvaluateAllAsync:
    async def test_no_short_circuit(self, engine, ctx, temp_chroot):
        """evaluate_all_async evaluates all checks even if some fail."""
        exists = temp_chroot / "exists.txt"
        exists.write_text("content")

        checks = (
            AcceptanceCheck(check_type=CheckType.FILE_EXISTS, target="missing.txt"),
            AcceptanceCheck(check_type=CheckType.FILE_EXISTS, target="exists.txt"),
            AcceptanceCheck(check_type=CheckType.FILE_EXISTS, target="missing2.txt"),
        )
        report = await engine.evaluate_all_async(checks, ctx)
        assert len(report.results) == 3
        assert report.results[0].passed is False
        assert report.results[1].passed is True
        assert report.results[2].passed is False
        assert report.all_passed is False

    async def test_suite_timeout_skips_remaining(self, engine, ctx, temp_chroot):
        """When suite timeout is exceeded, remaining checks are SKIPPED (D18)."""
        exists = temp_chroot / "exists.txt"
        exists.write_text("content")

        checks = (
            AcceptanceCheck(check_type=CheckType.FILE_EXISTS, target="exists.txt"),
            AcceptanceCheck(check_type=CheckType.FILE_EXISTS, target="exists.txt"),
            AcceptanceCheck(check_type=CheckType.FILE_EXISTS, target="exists.txt"),
        )
        # Use 0s suite timeout — all checks should be skipped
        report = await engine.evaluate_all_async(checks, ctx, max_suite_seconds=0.0)
        skipped = [r for r in report.results if r.reason_code == "suite_timeout"]
        assert len(skipped) >= 1

    async def test_suite_timeout_marks_fail(self, engine, ctx, temp_chroot):
        """Suite with timeout SKIP has all_passed = False (D18: incomplete evidence)."""
        exists = temp_chroot / "exists.txt"
        exists.write_text("content")

        checks = (
            AcceptanceCheck(check_type=CheckType.FILE_EXISTS, target="exists.txt"),
            AcceptanceCheck(check_type=CheckType.FILE_EXISTS, target="exists.txt"),
        )
        report = await engine.evaluate_all_async(checks, ctx, max_suite_seconds=0.0)
        # SKIPPED checks are not passed, so all_passed must be False
        assert report.all_passed is False

    async def test_all_pass(self, engine, ctx, temp_chroot):
        """All passing checks → all_passed True."""
        f1 = temp_chroot / "f1.txt"
        f2 = temp_chroot / "f2.txt"
        f1.write_text("content")
        f2.write_text("content")

        checks = (
            AcceptanceCheck(check_type=CheckType.FILE_EXISTS, target="f1.txt"),
            AcceptanceCheck(check_type=CheckType.NON_EMPTY, target="f2.txt"),
        )
        report = await engine.evaluate_all_async(checks, ctx)
        assert report.all_passed is True
