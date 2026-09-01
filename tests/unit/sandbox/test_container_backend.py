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
    def __init__(
        self,
        result: ContainerResult | None = None,
        error: Exception | None = None,
        image_present: bool | Exception = True,
    ):
        self.specs: list[ContainerSpec] = []
        self._result = result or ContainerResult(
            container_id="", exit_code=0, stdout="ok\n", stderr=""
        )
        self._error = error
        self._image_present = image_present

    async def has_image(self, image: str) -> bool:
        if isinstance(self._image_present, Exception):
            raise self._image_present
        return self._image_present

    async def run(self, spec: ContainerSpec) -> ContainerResult:
        self.specs.append(spec)
        if self._error is not None:
            raise self._error
        return self._result

    async def stop(self, container_id: str) -> None:  # pragma: no cover - unused
        pass

    async def remove(self, container_id: str) -> None:  # pragma: no cover - unused
        pass

    async def state(self, container_id: str) -> tuple[bool, int | None]:  # pragma: no cover
        return (False, 0)

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

    async def test_cache_root_mounts_download_caches_only(self, tmp_path, store, seeded):
        """Bug caught: §7 item 13's structural guarantee broken — mounting
        installed-dependency dirs (site-packages/node_modules) instead of
        download caches would let cached deps substitute for undeclared ones."""
        container = FakeContainer()
        backend = ContainerBackend(
            container=container,
            store=store,
            image="sandbox:pinned",
            operation_commands=COMMANDS,
            cache_root=tmp_path / "caches",
        )
        await backend.install_dependencies(revision=seeded)
        mounts = dict(container.specs[0].volumes)
        # User-neutral mount points (Spark shakedown 2026-07-28): /root/.* paths
        # only resolved while the container ran as root.
        assert mounts[str(tmp_path / "caches" / "pip")] == "/cache/pip"
        assert mounts[str(tmp_path / "caches" / "npm")] == "/cache/npm"
        assert (tmp_path / "caches" / "pip").is_dir()  # pre-created, never root-owned
        assert not any("site-packages" in c or "node_modules" in c for c in mounts.values())

    async def test_no_cache_root_means_no_cache_mounts(self, store, seeded):
        """Bug caught: phantom cache mounts when caching is disabled."""
        container = FakeContainer()
        await _backend(container, store).build_frontend(revision=seeded)
        assert len(container.specs[0].volumes) == 1  # workspace only

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

    @pytest.mark.parametrize(
        ("image_present", "expected"),
        [(True, True), (False, False), (ToolContainerError("no daemon"), None)],
        ids=["present", "absent", "daemon-unreachable"],
    )
    async def test_environment_report_is_honest_about_image_presence(
        self, store, image_present, expected
    ):
        """Bug caught: a daemon outage reported as image-absent (a false
        preflight block) or as present (a false pass) — unverifiable must
        stay None."""
        backend = ContainerBackend(
            container=FakeContainer(image_present=image_present),
            store=store,
            image="sandbox:pinned",
            operation_commands=COMMANDS,
            environment_contract_id="env-123",
        )
        report = await backend.environment_report()
        assert report == {
            "contract_id": "env-123",
            "image": "sandbox:pinned",
            "image_present": expected,
        }

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
        # The probe base dict has its own shape — live-smoke caught it missing.
        probe = await backend.probe_http_endpoint(
            revision=seeded, probe_id="p1", method="GET", path="/x"
        )
        assert probe.environment_contract_id == "env-123"

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


class TestBuildMutatesSource:
    """SIP-0102 §11: a stack whose BUILD rewrites its own source (measured on
    nextjs_ts — `next build` generates `next-env.d.ts` and rewrites `tsconfig.json`)
    can never match its pin after building, so §4.6's verification is enforced only on
    the operation that precedes any build. The canonical stack is unaffected."""

    def _mutating_backend(self, container, store):
        return ContainerBackend(
            container=container,
            store=store,
            image="sandbox:pinned",
            operation_commands=COMMANDS,
            build_mutates_source=True,
        )

    async def test_install_still_refuses_a_drifted_tree(self, store, seeded):
        """The guarantee that survives: the source we declared is the source we built.
        Install runs before any build, so drift there is still a caller error."""
        (store.workspace_dir("cyc_1") / "backend/main.py").write_text("drift", encoding="utf-8")
        with pytest.raises(WorkspaceStoreError, match="does not match declared"):
            await self._mutating_backend(FakeContainer(), store).install_dependencies(
                revision=seeded
            )

    async def test_post_build_operations_tolerate_the_builds_own_writes(self, store, seeded):
        """Bug caught (SIP-0104 window roll 1): the audited app installed and BUILT
        successfully, then boot was refused because the build's own `next-env.d.ts` and
        rewritten `tsconfig.json` no longer matched the pin — asserting an invariant
        that was never true for this stack."""
        (store.workspace_dir("cyc_1") / "next-env.d.ts").write_text("gen", encoding="utf-8")

        # Two post-build operations: neither refuses on the pin. The tests run for real
        # (this fixture provides a test command); start reports NOT_RUN only because the
        # fixture declares no start command — reaching that verdict IS passing the gate.
        tested = await self._mutating_backend(FakeContainer(), store).run_backend_tests(
            revision=seeded
        )
        assert tested.ran is True
        started = await self._mutating_backend(FakeContainer(), store).start_application(
            revision=seeded
        )
        assert "provides no command" in started.unavailable_reason

    async def test_the_canonical_stack_still_verifies_everywhere(self, store, seeded):
        """Default False keeps stack #1 byte-identical: post-build drift still refuses."""
        (store.workspace_dir("cyc_1") / "next-env.d.ts").write_text("gen", encoding="utf-8")
        with pytest.raises(WorkspaceStoreError, match="does not match declared"):
            await _backend(FakeContainer(), store).start_application(revision=seeded)


class TestWorkspaceOwnerUser:
    """Spark shakedown (2026-07-28): with cap_drop_all, root loses DAC_OVERRIDE
    and cannot write a host-owned bind mount on native Linux — the floor smoke
    failed at `python -m venv` in 0.3s. Docker Desktop's virtiofs masked the
    mismatch on Mac. The container must run as the workspace owner."""

    async def test_operations_run_as_the_workspace_owner(self, tmp_path, store, seeded):
        import os

        container = FakeContainer()
        backend = _backend(container, store)
        await backend.install_dependencies(revision=seeded)
        spec = container.specs[0]
        st = os.stat(store.workspace_dir(seeded.cycle_id))
        assert spec.user == f"{st.st_uid}:{st.st_gid}"

    async def test_env_pins_home_and_user_neutral_caches(self, tmp_path, store, seeded):
        container = FakeContainer()
        backend = ContainerBackend(
            container=container,
            store=store,
            image="sandbox:pinned",
            operation_commands=COMMANDS,
            cache_root=tmp_path / "caches",
        )
        await backend.install_dependencies(revision=seeded)
        env = dict(container.specs[0].env)
        # A passwd-less uid resolves $HOME to '/' — npm then writes /.npm and
        # fails; HOME plus explicit cache env decouple caching from identity.
        assert env["HOME"] == "/tmp"
        assert env["PIP_CACHE_DIR"] == "/cache/pip"
        assert env["npm_config_cache"] == "/cache/npm"
