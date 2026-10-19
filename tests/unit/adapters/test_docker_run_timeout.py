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

    def __init__(self, *, run_times_out: bool, kill_stderr: bytes = b"", run_exit: int = 0) -> None:
        self.commands: list[list[str]] = []
        self.inputs: list[bytes | None] = []
        self._run_times_out = run_times_out
        self._kill_stderr = kill_stderr
        self._run_exit = run_exit

    async def __call__(self, argv, *, cwd, timeout, env=None, stdin=None):
        self.commands.append(list(argv))
        self.inputs.append(stdin)
        if argv[1] == "run":
            if self._run_times_out:
                return BoundedRun(None, b"", b"")
            return BoundedRun(self._run_exit, b"ok", b"exec failed" if self._run_exit else b"")
        if argv[1] == "kill":
            return BoundedRun(1 if self._kill_stderr else 0, b"", self._kill_stderr)
        if argv[1] == "rm":
            return BoundedRun(0, b"", b"")
        raise AssertionError(f"unexpected docker command {argv}")

    def run_name(self) -> str:
        [run] = [c for c in self.commands if c[1] == "run"]
        return run[run.index("--name") + 1]

    def killed(self) -> list[str]:
        return [c[2] for c in self.commands if c[1] == "kill"]

    def removed(self) -> list[str]:
        return [c[-1] for c in self.commands if c[1] == "rm"]


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
        app_network=None,
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


@pytest.mark.parametrize("given", [b'{"pages": ["/"]}', None], ids=["an-input", "none"])
async def test_a_runs_input_reaches_the_container_on_its_stdin_and_only_then(docker, given):
    """SIP-0113 A3 (#2416): the evaluator receives its request on its input, never on a mounted
    path. Bug caught: the input dropped, so the evaluator reads nothing and fails every page; or
    ``-i`` passed to every run, so a run that reads stdin waits on a pipe nobody closes."""
    fake = docker(run_times_out=False)

    await DockerAdapter().run(ContainerSpec(image="i", timeout_seconds=5, stdin=given))

    [run] = [c for c in fake.commands if c[1] == "run"]
    assert fake.inputs == [given]
    if given is None:
        assert "-i" not in run
    else:
        assert run.index("-i") < run.index("i")  # a docker option, so before the image


async def test_a_container_already_gone_still_reports_the_timeout(docker):
    """``--rm`` may have removed it between the timeout and the kill. Bug caught: that ordinary
    race turning the timeout the caller must hear into a different error."""
    fake = docker(run_times_out=True, kill_stderr=b"Error: No such container: squadops-run-x")

    with pytest.raises(ToolContainerError, match="timed out after 5"):
        await DockerAdapter().run(ContainerSpec(image="i", timeout_seconds=5))

    assert fake.killed() == [fake.run_name()]


@pytest.mark.parametrize("given", [None, "squadops-app-cyc_1-abc"], ids=["generated", "the-specs"])
async def test_a_detached_start_that_times_out_is_removed_by_its_name(docker, given):
    """#2451 part 4 (the MacBook lane's note on #2450). Bug caught: a ``docker run -d`` that
    outlives its limit leaving an unnamed container nobody can find, holding its port and its
    copy; or a spec's own name, the one the app network addresses, not used."""
    fake = docker(run_times_out=True)
    spec = ContainerSpec(image="sandbox:pinned", command=["serve"], timeout_seconds=1, name=given)

    with pytest.raises(ToolContainerError, match="timed out"):
        await DockerAdapter().run_detached(spec)

    name = fake.run_name()
    assert name == (given or name) and name.startswith("squadops-app-")
    assert fake.removed() == [name]


@pytest.mark.parametrize("exit_code", [125, 126, 127])
async def test_a_detached_start_that_exits_non_zero_is_removed_by_its_name(docker, exit_code):
    """The MacBook lane's review of #2460. Bug caught: a ``docker run -d`` that created its
    container and then failed (125 to 127) leaving a named container behind, which the next
    start under that name collides with."""
    fake = docker(run_times_out=False, run_exit=exit_code)

    with pytest.raises(ToolContainerError, match="Failed to start"):
        await DockerAdapter().run_detached(ContainerSpec(image="sandbox:pinned", command=["serve"]))

    assert fake.removed() == [fake.run_name()]
