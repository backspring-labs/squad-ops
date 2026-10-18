"""The scenario runner in the sandbox service (SIP-0113 §4.1, A3; X-3b; #2414, #2421).

One evaluation is one call:
1. the evaluated tree's files are checked against their ``FileTree.identity``;
2. they are written to a disposable copy under the sandbox root, executable bits included;
3. the copy is started, by the product's own declaration or by its stack's environment contract;
4. each scenario's steps run from the service, over loopback, outside the app's process;
5. the app stops and the copy is removed, whatever happened.

Nothing a scenario caused reaches a workspace, a revision or a commit (contract 3). The steps
are held in memory for the call, never written, and never in a result.

The posture is the sandbox's own (§7 items 9–10): caps dropped, no new privileges, the copy's
owner's uid, and resource limits. Setup gets the dependency network, as an install does. The
app gets the bridge it needs to publish its one port to loopback.
"""

from __future__ import annotations

import asyncio
import shutil
import time
import uuid
from collections.abc import Callable, Collection, Mapping, Sequence
from pathlib import Path
from typing import Any

import httpx

from squadops.campaigns.evaluator_trees import FileTree
from squadops.ports.scenarios import ScenarioRunnerPort
from squadops.ports.tools.container import ContainerPort
from squadops.sandbox.environment import get_environment_contract
from squadops.sandbox.models import OperationName, content_bytes
from squadops.scenarios.runner import DeclaredStart, TreeEvaluation
from squadops.scenarios.steps import HttpRequest, HttpResponse, ScenarioRun, run_scenario
from squadops.tools.exceptions import ToolContainerError
from squadops.tools.models import ContainerSpec

_MOUNT = "/workspace"
_TAIL_LINES = 40


class _StartFailed(Exception):
    def __init__(self, detail: str, diagnostics: tuple[str, ...] = ()) -> None:
        super().__init__(detail)
        self.detail, self.diagnostics = detail, diagnostics


class _Start:
    """How this tree starts: setup argvs, the start argv, its port and readiness."""

    def __init__(
        self,
        setup: tuple[tuple[str, ...], ...],
        start: tuple[str, ...],
        port: int,
        ready_path: str,
        require_2xx: bool,
        ready_timeout: float,
        working_dir: str,
    ) -> None:
        self.setup, self.start, self.port = setup, start, port
        self.ready_path, self.require_2xx, self.ready_timeout = (
            ready_path,
            require_2xx,
            ready_timeout,
        )
        self.working_dir = working_dir


class ContainerScenarioRunner(ScenarioRunnerPort):
    def __init__(
        self,
        *,
        container: ContainerPort,
        root: Path,
        image: str,
        install_network: str = "bridge",
        memory_limit: str = "2g",
        cpu_limit: float = 2.0,
        pids_limit: int = 512,
        timeout_seconds: float = 600.0,
        blueprint_ready_timeout_seconds: float = 60.0,
        poll_interval_seconds: float = 0.5,
        http_client_factory: Callable[[], httpx.AsyncClient] | None = None,
    ) -> None:
        self._container = container
        self._root = Path(root)
        self._image = image
        self._install_network = install_network
        self._limits = (memory_limit, cpu_limit, pids_limit)
        self._timeout = timeout_seconds
        self._blueprint_ready_timeout = blueprint_ready_timeout_seconds
        self._poll = poll_interval_seconds
        self._http = http_client_factory or (lambda: httpx.AsyncClient(timeout=10.0))

    async def evaluate_tree(
        self,
        *,
        tree: Mapping[str, bytes | str],
        tree_identity: str,
        executable: Collection[str],
        stack: str | None,
        declared: DeclaredStart | None,
        scenarios: Sequence[Mapping[str, Any]],
        environment: Mapping[str, str],
    ) -> TreeEvaluation:
        built = FileTree.of(tree).identity
        if built != tree_identity:
            raise ValueError(f"the tree hashes to {built}, not its declared {tree_identity}")
        missing = sorted(set(executable) - set(tree))
        if missing:
            raise ValueError(f"executable paths the tree doesn't carry: {missing}")
        start = self._start_for(stack, declared)
        started = time.monotonic()
        copy = self._root / "evaluations" / uuid.uuid4().hex
        try:
            self._write_copy(copy, tree, executable)
            return await self._evaluate(copy, tree_identity, start, scenarios, environment, started)
        finally:
            shutil.rmtree(copy, ignore_errors=True)

    def _start_for(self, stack: str | None, declared: DeclaredStart | None) -> _Start:
        if declared is not None:
            return _Start(
                declared.setup,
                declared.start,
                declared.port,
                declared.ready_path,
                True,
                declared.ready_timeout_seconds,
                declared.working_dir,
            )
        if not stack:
            raise ValueError("a tree with no start declaration names its stack")
        contract = get_environment_contract(stack)
        commands = contract.commands()
        setup = tuple(
            commands[op]
            for op in (OperationName.INSTALL_DEPENDENCIES, OperationName.BUILD_FRONTEND)
            if op in commands
        )
        return _Start(
            setup,
            commands[OperationName.START_APPLICATION],
            contract.app_port,
            "/",
            False,
            self._blueprint_ready_timeout,
            ".",
        )

    @staticmethod
    def _write_copy(copy: Path, tree: Mapping[str, bytes | str], executable: Collection[str]):
        for rel, content in tree.items():
            target = copy / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content_bytes(content))
            if rel in executable:
                target.chmod(target.stat().st_mode | 0o111)
        copy.mkdir(parents=True, exist_ok=True)

    def _spec(self, copy: Path, argv: tuple[str, ...], workdir: str, **kw: Any) -> ContainerSpec:
        st = copy.stat()
        memory, cpu, pids = self._limits
        inside = _MOUNT if workdir in ("", ".") else f"{_MOUNT}/{workdir.strip('/')}"
        return ContainerSpec(
            image=self._image,
            command=list(argv),
            env=kw.pop("env", (("HOME", "/tmp"),)),
            volumes=((str(copy), _MOUNT),),
            working_dir=inside,
            timeout_seconds=self._timeout,
            memory_limit=memory,
            cpu_limit=cpu,
            pids_limit=pids,
            cap_drop_all=True,
            no_new_privileges=True,
            user=f"{st.st_uid}:{st.st_gid}",
            **kw,
        )

    async def _evaluate(self, copy, identity, start, scenarios, environment, started):
        try:
            await self._setup(copy, start)
            env = (("HOME", "/tmp"), *sorted(environment.items()))
            try:
                container_id = await self._container.run_detached(
                    self._spec(
                        copy, start.start, start.working_dir, env=env, publish_ports=(start.port,)
                    )
                )
            except ToolContainerError as e:
                raise _StartFailed(f"the start could not run: {e}") from e
            try:
                runs = await self._serve(container_id, start, scenarios)
            finally:
                await self._teardown(container_id)
        except _StartFailed as failed:
            return TreeEvaluation(
                identity,
                started=False,
                start_detail=failed.detail,
                startup_diagnostics=failed.diagnostics,
                duration_seconds=round(time.monotonic() - started, 3),
            )
        return TreeEvaluation(
            identity, started=True, runs=runs, duration_seconds=round(time.monotonic() - started, 3)
        )

    async def _setup(self, copy: Path, start: _Start) -> None:
        for number, argv in enumerate(start.setup, start=1):
            try:
                run = await self._container.run(
                    self._spec(copy, argv, start.working_dir, network=self._install_network)
                )
            except ToolContainerError as e:
                raise _StartFailed(f"setup step {number} could not run: {e}") from e
            if run.exit_code != 0:
                tail = tuple((run.stdout + run.stderr).splitlines()[-_TAIL_LINES:])
                raise _StartFailed(f"setup step {number} exited {run.exit_code}", tail)

    async def _serve(
        self, container_id: str, start: _Start, scenarios: Sequence[Mapping[str, Any]]
    ) -> tuple[ScenarioRun, ...]:
        try:
            host_port = await self._container.resolve_host_port(container_id, start.port)
        except ToolContainerError as e:
            raise _StartFailed(f"the app published no port {start.port}: {e}") from e
        base = f"http://127.0.0.1:{host_port}"
        if not await self._ready(base + start.ready_path, start):
            try:
                logs = await self._container.logs(container_id)
            except ToolContainerError:
                logs = ""
            raise _StartFailed(
                f"not ready at {start.ready_path} within {start.ready_timeout:g}s",
                tuple(logs.splitlines()[-_TAIL_LINES:]),
            )
        async with self._http() as client:

            async def send(request: HttpRequest) -> HttpResponse:
                try:
                    response = await client.request(
                        request.method,
                        base + request.path,
                        json=request.json,
                        headers=dict(request.headers or {}),
                    )
                except httpx.HTTPError as e:
                    raise ConnectionError(str(e)) from e
                try:
                    body: Any = response.json()
                except ValueError:
                    body = response.text
                return HttpResponse(response.status_code, body)

            return tuple([await run_scenario(scenario, send) for scenario in scenarios])

    async def _teardown(self, container_id: str) -> None:
        for step in (self._container.stop, self._container.remove):
            try:
                await step(container_id)
            except ToolContainerError:
                pass  # teardown converges: the container may already be gone

    async def _ready(self, url: str, start: _Start) -> bool:
        deadline = time.monotonic() + start.ready_timeout
        async with self._http() as client:
            while True:
                try:
                    response = await client.get(url)
                    if not start.require_2xx or 200 <= response.status_code < 300:
                        return True
                except (httpx.HTTPError, OSError):
                    pass  # connection refused while the app boots is expected
                if time.monotonic() >= deadline:
                    return False
                await asyncio.sleep(self._poll)
