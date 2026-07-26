"""ContainerBackend runtime unit (SIP-0102 §7 items 12/14 — 102.1 slice c2)."""

import httpx
import pytest

from adapters.execution.container_backend import ContainerBackend
from squadops.execution.models import (
    OperationName,
    OperationStatus,
    RevisionOrigin,
)
from squadops.execution.workspace import WorkspaceStore
from squadops.ports.tools.container import ContainerPort
from squadops.tools.exceptions import ToolContainerError
from squadops.tools.models import ContainerResult, ContainerSpec

FILES = {"backend/main.py": "app\n"}
COMMANDS = {OperationName.START_APPLICATION: ("uvicorn", "backend.main:app")}


class FakeResponse:
    def __init__(self, status_code: int):
        self.status_code = status_code


class FakeHTTPClient:
    """Async-context client replaying a shared script of responses/errors."""

    def __init__(self, script: list):
        self._script = script

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def request(self, method: str, url: str):
        item = self._script.pop(0) if self._script else FakeResponse(200)
        if isinstance(item, Exception):
            raise item
        return item


class RuntimeFakeContainer(ContainerPort):
    def __init__(
        self, *, detach_error: Exception | None = None, stop_error: Exception | None = None
    ):
        self.specs: list[ContainerSpec] = []
        self.stopped: list[str] = []
        self._detach_error = detach_error
        self._stop_error = stop_error

    async def run(self, spec: ContainerSpec) -> ContainerResult:  # pragma: no cover - unused
        raise AssertionError("runtime unit must not use foreground run")

    async def run_detached(self, spec: ContainerSpec) -> str:
        self.specs.append(spec)
        if self._detach_error is not None:
            raise self._detach_error
        return "cid-app"

    async def resolve_host_port(self, container_id: str, container_port: int) -> int:
        return 49999

    async def stop(self, container_id: str) -> None:
        self.stopped.append(container_id)
        if self._stop_error is not None:
            raise self._stop_error

    async def logs(self, container_id: str, tail: int | None = None) -> str:
        return "boot line 1\nboot line 2"

    async def health(self) -> dict:  # pragma: no cover - unused
        return {"healthy": True}


@pytest.fixture
def store(tmp_path):
    return WorkspaceStore(tmp_path / "cycles")


@pytest.fixture
def seeded(store):
    return store.seed("cyc_1", FILES, origin=RevisionOrigin.SCAFFOLD_SEED)


def _backend(container, store, script):
    return ContainerBackend(
        container=container,
        store=store,
        image="sandbox:pinned",
        operation_commands=COMMANDS,
        readiness_timeout_seconds=0.05,
        poll_interval_seconds=0.01,
        http_client_factory=lambda: FakeHTTPClient(script),
    )


class TestStartApplication:
    async def test_ready_app_yields_endpoints_and_cleanup_handle(self, store, seeded):
        """Bug caught: a started app without endpoint/cleanup handles — probes
        could not reach it and teardown could not converge."""
        container = RuntimeFakeContainer()
        result = await _backend(container, store, [FakeResponse(200)]).start_application(
            revision=seeded
        )
        assert result.ran and result.ready
        assert result.status == OperationStatus.SUCCEEDED
        assert result.endpoints == ("http://127.0.0.1:49999",)
        assert result.cleanup_handle == "cid-app"
        spec = container.specs[0]
        assert spec.publish_ports == (8000,)
        assert spec.cap_drop_all and spec.no_new_privileges

    async def test_never_ready_app_is_stopped_and_fails_with_diagnostics(self, store, seeded):
        """Bug caught: a hung startup leaving an orphan container running, or
        failing without the boot logs the builder needs to correct it."""
        container = RuntimeFakeContainer()
        script = [httpx.ConnectError("refused") for _ in range(50)]
        result = await _backend(container, store, script).start_application(revision=seeded)
        assert result.ran is True
        assert result.status == OperationStatus.FAILED
        assert result.exit_classification == "startup_timeout"
        assert result.ready is False
        assert container.stopped == ["cid-app"]
        assert "boot line 2" in result.startup_diagnostics

    async def test_spawn_failure_is_environment_unavailable(self, store, seeded):
        """Bug caught: the roll-4 class at the runtime unit — a container that
        never started recorded as an application startup failure."""
        container = RuntimeFakeContainer(detach_error=ToolContainerError("no daemon"))
        result = await _backend(container, store, []).start_application(revision=seeded)
        assert result.ran is False
        assert result.status == OperationStatus.NOT_RUN


class TestProbe:
    async def _started(self, store, seeded, script):
        backend = _backend(RuntimeFakeContainer(), store, script)
        start = await backend.start_application(revision=seeded)
        assert start.ready
        return backend

    async def test_probe_before_start_is_not_run(self, store, seeded):
        """Bug caught: probing nothing and recording a verdict about it."""
        backend = _backend(RuntimeFakeContainer(), store, [])
        result = await backend.probe_http_endpoint(
            revision=seeded, probe_id="p1", method="GET", path="/health"
        )
        assert result.ran is False
        assert "not running" in result.unavailable_reason

    @pytest.mark.parametrize(
        ("expected", "observed", "ok"),
        [(200, 200, True), (200, 500, False), (None, 204, True), (None, 503, False)],
        ids=["exact-match", "exact-mismatch", "default-2xx", "default-5xx"],
    )
    async def test_probe_verdicts_follow_expected_status(
        self, store, seeded, expected, observed, ok
    ):
        """Bug caught: probe pass/fail polarity drift — a 500 passing the
        health floor is a false `verified_executable`."""
        backend = await self._started(store, seeded, [FakeResponse(200), FakeResponse(observed)])
        result = await backend.probe_http_endpoint(
            revision=seeded, probe_id="p1", method="GET", path="/health", expected_status=expected
        )
        assert result.ran is True
        assert (result.status == OperationStatus.SUCCEEDED) is ok
        assert result.observed_status_code == observed

    async def test_connection_error_is_an_application_failure(self, store, seeded):
        """Bug caught: an app that died after readiness laundered as
        environment-unavailable — it must stay in the correction budget."""
        backend = await self._started(
            store, seeded, [FakeResponse(200), httpx.ConnectError("refused")]
        )
        result = await backend.probe_http_endpoint(
            revision=seeded, probe_id="p1", method="GET", path="/items"
        )
        assert result.ran is True
        assert result.status == OperationStatus.FAILED
        assert result.exit_classification == "connection_error"


class TestStopApplication:
    async def test_stop_stops_the_container(self, store, seeded):
        """Bug caught: teardown not reaching the runtime — stranded app
        containers accumulating on the host."""
        container = RuntimeFakeContainer()
        backend = _backend(container, store, [FakeResponse(200)])
        start = await backend.start_application(revision=seeded)
        result = await backend.stop_application(
            revision=seeded, cleanup_handle=start.cleanup_handle
        )
        assert result.status == OperationStatus.SUCCEEDED
        assert container.stopped == ["cid-app"]

    async def test_stopping_a_gone_container_converges(self, store, seeded):
        """Bug caught: §7 item 12 violation — teardown of an already-gone
        runtime erroring instead of converging (retry loops forever)."""
        container = RuntimeFakeContainer(
            stop_error=ToolContainerError("Failed to stop container: No such container: cid-app")
        )
        backend = _backend(container, store, [])
        result = await backend.stop_application(revision=seeded, cleanup_handle="cid-app")
        assert result.status == OperationStatus.SUCCEEDED
        assert result.detail == "already stopped"
