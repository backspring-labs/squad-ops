"""#2045: a sandbox run that outlives its limit is killed by name, not left running.

What bug would these catch? The container a timed-out ``docker run`` started kept running after
the operation was recorded ``timeout``. The client was never stopped, and stopping it would not
have stopped the container, which the daemon owns. It held its CPU, memory and workspace mount
while the next operation started. The command's subprocess is faked at the adapter's seam
(``run_bounded``), never the daemon.
"""

from __future__ import annotations

import pytest

from adapters.sandbox.container_backend import ContainerBackend
from adapters.tools import docker as docker_module
from adapters.tools.docker import DockerAdapter
from squadops.core.bounded_run import BoundedRun
from squadops.sandbox.models import OperationName, OperationStatus, RevisionOrigin
from squadops.sandbox.workspace import WorkspaceStore
from squadops.tools.exceptions import ToolContainerError
from squadops.tools.models import ContainerSpec


class _Docker:
    """The docker CLI as ``run_bounded`` would run it: ``run`` outlives its limit or exits, and
    ``kill`` answers as scripted. Records every command."""

    def __init__(self, *, run_times_out: bool, kill_stderr: bytes = b"") -> None:
        self.commands: list[list[str]] = []
        self._run_times_out = run_times_out
        self._kill_stderr = kill_stderr

    async def __call__(self, argv, *, cwd, timeout, env=None):
        self.commands.append(list(argv))
        if argv[1] == "run":
            return BoundedRun(None, b"", b"") if self._run_times_out else BoundedRun(0, b"ok", b"")
        if argv[1] == "kill":
            return BoundedRun(1 if self._kill_stderr else 0, b"", self._kill_stderr)
        raise AssertionError(f"unexpected docker command {argv}")

    def run_name(self) -> str:
        [run] = [c for c in self.commands if c[1] == "run"]
        return run[run.index("--name") + 1]

    def killed(self) -> list[str]:
        return [c[2] for c in self.commands if c[1] == "kill"]


@pytest.fixture
def docker(monkeypatch):
    def install(**script) -> _Docker:
        fake = _Docker(**script)
        monkeypatch.setattr(docker_module, "run_bounded", fake)
        return fake

    return install


async def test_a_sandbox_operation_that_times_out_kills_its_container(docker, tmp_path):
    """Entered at ``ContainerBackend.build_frontend``, the operation the sandbox runs, with the
    real adapter: the operation still reads as a timed-out deliverable, and the container its
    run started, by the name the run gave it, is killed."""
    fake = docker(run_times_out=True)
    store = WorkspaceStore(tmp_path / "cycles")
    revision = store.seed("cyc_1", {"a.py": "x\n"}, origin=RevisionOrigin.SCAFFOLD_SEED)
    backend = ContainerBackend(
        container=DockerAdapter(),
        store=store,
        image="sandbox:pinned",
        operation_commands={OperationName.BUILD_FRONTEND: ("npm", "run", "build")},
    )

    result = await backend.build_frontend(revision=revision)

    assert (result.status, result.exit_classification) == (OperationStatus.FAILED, "timeout")
    assert fake.killed() == [fake.run_name()]
    assert fake.run_name().startswith("squadops-run-")


async def test_a_run_that_finishes_kills_nothing(docker):
    fake = docker(run_times_out=False)

    result = await DockerAdapter().run(ContainerSpec(image="i", timeout_seconds=5))

    assert result.exit_code == 0
    assert fake.killed() == []


async def test_a_container_already_gone_still_reports_the_timeout(docker):
    """``--rm`` may have removed it between the timeout and the kill. Bug caught: that ordinary
    race turning the timeout the caller must hear into a different error."""
    fake = docker(run_times_out=True, kill_stderr=b"Error: No such container: squadops-run-x")

    with pytest.raises(ToolContainerError, match="timed out after 5"):
        await DockerAdapter().run(ContainerSpec(image="i", timeout_seconds=5))

    assert fake.killed() == [fake.run_name()]
