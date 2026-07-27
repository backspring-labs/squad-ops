"""ContainerBackend one-shot ops (SIP-0102 §7 items 3/4/9/10 — 102.1 slice c1)."""

import pytest

from adapters.sandbox.container_backend import ContainerBackend
from squadops.ports.tools.container import ContainerPort
from squadops.sandbox.models import (
    OperationName,
    OperationStatus,
    RevisionOrigin,
    is_deliverable_failure,
)
from squadops.sandbox.workspace import WorkspaceStore, WorkspaceStoreError
from squadops.tools.exceptions import ToolContainerError
from squadops.tools.models import ContainerResult, ContainerSpec

FILES = {"backend/main.py": "print('a')\n"}
COMMANDS = {
    OperationName.INSTALL_DEPENDENCIES: ("pip", "install", "-r", "requirements.txt"),
    OperationName.BUILD_FRONTEND: ("npm", "run", "build"),
    OperationName.RUN_BACKEND_TESTS: ("pytest", "-q"),
}


class FakeContainer(ContainerPort):
    def __init__(self, result: ContainerResult | None = None, error: Exception | None = None):
        self.specs: list[ContainerSpec] = []
        self._result = result or ContainerResult(
            container_id="", exit_code=0, stdout="ok\n", stderr=""
        )
        self._error = error

    async def run(self, spec: ContainerSpec) -> ContainerResult:
        self.specs.append(spec)
        if self._error is not None:
            raise self._error
        return self._result

    async def stop(self, container_id: str) -> None:  # pragma: no cover - unused
        pass

    async def logs(self, container_id: str, tail: int | None = None) -> str:  # pragma: no cover
        return ""

    async def health(self) -> dict:  # pragma: no cover - unused
        return {"healthy": True}

    async def run_detached(self, spec: ContainerSpec) -> str:
        self.specs.append(spec)
        return "cid-detached"

    async def resolve_host_port(self, container_id: str, container_port: int) -> int:
        return 49999


@pytest.fixture
def store(tmp_path):
    return WorkspaceStore(tmp_path / "cycles")


@pytest.fixture
def seeded(store):
    return store.seed("cyc_1", FILES, origin=RevisionOrigin.SCAFFOLD_SEED)


def _backend(container, store, commands=COMMANDS):
    return ContainerBackend(
        container=container, store=store, image="sandbox:pinned", operation_commands=commands
    )


class TestHardenedSpecRendering:
    async def test_build_runs_hardened_and_network_denied(self, store, seeded):
        """Bug caught: a sandbox container running with default (soft) docker
        settings — §7 items 9–10 are acceptance-grade, not adapter defaults."""
        container = FakeContainer()
        await _backend(container, store).build_frontend(revision=seeded)
        spec = container.specs[0]
        assert spec.image == "sandbox:pinned"
        assert spec.command == list(COMMANDS[OperationName.BUILD_FRONTEND])
        assert spec.volumes == ((str(store.workspace_dir("cyc_1")), "/workspace"),)
        assert spec.working_dir == "/workspace"
        assert spec.network == "none"
        assert spec.cap_drop_all and spec.no_new_privileges
        assert spec.memory_limit and spec.cpu_limit and spec.pids_limit

    async def test_install_gets_deps_egress_build_does_not(self, store, seeded):
        """Bug caught: egress polarity flipped — installs starved of the
        network they need, or builds granted egress they must not have."""
        container = FakeContainer()
        backend = _backend(container, store)
        await backend.install_dependencies(revision=seeded)
        await backend.build_frontend(revision=seeded)
        assert container.specs[0].network == "bridge"
        assert container.specs[1].network == "none"


class TestOutcomeClassification:
    async def test_zero_exit_is_success_with_image_identity(self, store, seeded):
        """Bug caught: §7 item 4 — a result without its image identity cannot
        support the evidence pinning 102.4 renders verdicts from."""
        result = await _backend(FakeContainer(), store).run_backend_tests(revision=seeded)
        assert result.ran and result.status == OperationStatus.SUCCEEDED
        assert result.image_identity == "sandbox:pinned"
        assert result.exit_code == 0

    async def test_environment_contract_id_rides_every_result(self, store, seeded):
        """Bug caught: §7 item 4's second half — results without the contract
        identity cannot prove which environment declaration they ran under."""
        backend = ContainerBackend(
            container=FakeContainer(),
            store=store,
            image="sandbox:pinned",
            operation_commands=COMMANDS,
            environment_contract_id="env-123",
        )
        one_shot = await backend.run_backend_tests(revision=seeded)
        assert one_shot.environment_contract_id == "env-123"
        stop = await backend.stop_application(revision=seeded, cleanup_handle="h1")
        assert stop.environment_contract_id == "env-123"

    async def test_nonzero_exit_is_a_deliverable_failure(self, store, seeded):
        """Bug caught: a failing build not routed to application correction."""
        container = FakeContainer(
            result=ContainerResult(container_id="", exit_code=2, stdout="", stderr="boom")
        )
        result = await _backend(container, store).build_frontend(revision=seeded)
        assert result.status == OperationStatus.FAILED
        assert result.exit_classification == "nonzero_exit"
        assert is_deliverable_failure(result)
        assert "boom" in result.diagnostics[-1]

    async def test_timeout_is_a_deliverable_failure_not_environment(self, store, seeded):
        """Bug caught: a hung application laundered as environment-unavailable
        — it would escape correction budget forever (inverse of roll-4)."""
        container = FakeContainer(error=ToolContainerError("Docker command timed out after 600s"))
        result = await _backend(container, store).build_frontend(revision=seeded)
        assert result.ran is True
        assert result.status == OperationStatus.FAILED
        assert result.exit_classification == "timeout"

    async def test_daemon_failure_is_environment_unavailable(self, store, seeded):
        """Bug caught: the roll-4 class — an unreachable docker daemon
        recorded as a FAILED deliverable, taking `patch` and burning budget."""
        container = FakeContainer(error=ToolContainerError("Docker command failed: no daemon"))
        result = await _backend(container, store).build_frontend(revision=seeded)
        assert result.ran is False
        assert result.status == OperationStatus.NOT_RUN
        assert "daemon" in result.unavailable_reason
        assert not is_deliverable_failure(result)


class TestContractAndPinning:
    async def test_unprovided_operation_is_explicit_not_run(self, store, seeded):
        """Bug caught: advertised-vs-provided drift resolved by guessing a
        command instead of surfacing the environment-contract gap."""
        result = await _backend(FakeContainer(), store, commands={}).build_frontend(revision=seeded)
        assert result.ran is False
        assert "provides no command" in result.unavailable_reason

    async def test_drifted_tree_refuses_to_execute(self, store, seeded):
        """Bug caught: §7 item 3 violation — executing against content that is
        not the declared revision, producing evidence about nothing."""
        (store.workspace_dir("cyc_1") / "backend/main.py").write_text("drift", encoding="utf-8")
        with pytest.raises(WorkspaceStoreError, match="does not match declared"):
            await _backend(FakeContainer(), store).build_frontend(revision=seeded)

    async def test_start_without_provided_command_is_explicit_not_run(self, store, seeded):
        """Bug caught: a runtime unit booted with a guessed start command when
        the environment declared none — the advertised-vs-provided rule
        applies to the runtime unit exactly as to the build runner."""
        result = await _backend(FakeContainer(), store).start_application(revision=seeded)
        assert result.ran is False
        assert result.status == OperationStatus.NOT_RUN
        assert "provides no command" in result.unavailable_reason
