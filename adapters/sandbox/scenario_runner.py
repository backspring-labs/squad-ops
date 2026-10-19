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
import dataclasses
import shutil
import time
import uuid
from collections.abc import Callable, Collection, Mapping, Sequence
from pathlib import Path
from typing import Any

import httpx

from adapters.sandbox.placement import address, placement
from squadops.campaigns.evaluator_trees import FileTree
from squadops.ports.scenarios import ScenarioRunnerPort
from squadops.ports.tools.container import ContainerPort
from squadops.sandbox.environment import get_environment_contract
from squadops.sandbox.models import OperationName, content_bytes, declared_argv
from squadops.sandbox.workspace import WorkspaceEscapeError, tree_path, working_directory
from squadops.scenarios.runner import DeclaredStart, ReadinessKind, TreeEvaluation
from squadops.scenarios.steps import HttpRequest, HttpResponse, ScenarioRun, run_scenario
from squadops.tools.exceptions import ToolContainerError
from squadops.tools.models import ContainerSpec

_MOUNT = "/workspace"
_TAIL_LINES = 40
_REDACTED = "[redacted]"
#: How long a tcp readiness connection must stay open to be the app's, not the port proxy's.
_TCP_SETTLE_SECONDS = 0.25


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
        ready_kind: str,
        ready_path: str,
        require_2xx: bool,
        ready_timeout: float,
        working_dir: str,
        configuration_revision: int | None,
    ) -> None:
        self.setup, self.start, self.port = setup, start, port
        self.ready_kind, self.ready_path, self.require_2xx, self.ready_timeout = (
            ready_kind,
            ready_path,
            require_2xx,
            ready_timeout,
        )
        self.working_dir = working_dir
        self.configuration_revision = configuration_revision


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
        app_network: str | None,
    ) -> None:
        # #2451 part 4 (the MacBook lane's review of #2460): the app, which holds the evaluation
        # secrets, runs on the app network by name with no host port and no route out. ``None``, as
        # on a host run, publishes to loopback.
        self._app_network = app_network
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
        for rel in tree:
            try:
                tree_path(rel)  # the tree is a squad's files: no key writes outside the copy
            except WorkspaceEscapeError as e:
                raise ValueError(str(e)) from e
        start = self._start_for(stack, declared)
        started = time.monotonic()
        copy = self._root / "evaluations" / uuid.uuid4().hex
        try:
            self._write_copy(copy, tree, executable)
            evaluation = await self._evaluate(
                copy, tree_identity, start, scenarios, environment, started
            )
        finally:
            shutil.rmtree(copy, ignore_errors=True)
        return _redacted(evaluation, environment.values())

    def _start_for(self, stack: str | None, declared: DeclaredStart | None) -> _Start:
        if declared is not None:
            # X-3a's own rules again, where the argvs run: the declaration's reader is on the
            # other side of the wire, and this side never runs what it hasn't checked.
            try:
                setup = tuple(declared_argv(argv) for argv in declared.setup)
                argv = declared_argv(declared.start)
                workdir = working_directory(declared.working_dir) or "."
            except (ValueError, WorkspaceEscapeError) as e:
                raise ValueError(f"the start declaration: {e}") from e
            return _Start(
                setup,
                argv,
                declared.port,
                declared.ready_kind,
                declared.ready_path,
                True,
                declared.ready_timeout_seconds,
                workdir,
                declared.configuration_revision,
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
            ReadinessKind.HTTP,
            "/",
            False,
            self._blueprint_ready_timeout,
            ".",
            None,
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
                    spec := self._spec(
                        copy,
                        start.start,
                        start.working_dir,
                        env=env,
                        **placement(self._app_network, "eval", (start.port,)),
                    )
                )
            except ToolContainerError as e:
                raise _StartFailed(f"the start could not run: {e}") from e
            try:
                runs = await self._serve(container_id, spec, start, scenarios)
            finally:
                await self._teardown(container_id)
        except _StartFailed as failed:
            return TreeEvaluation(
                identity,
                started=False,
                start_detail=failed.detail,
                startup_diagnostics=failed.diagnostics,
                duration_seconds=round(time.monotonic() - started, 3),
                configuration_revision=start.configuration_revision,
            )
        return TreeEvaluation(
            identity,
            started=True,
            runs=runs,
            duration_seconds=round(time.monotonic() - started, 3),
            configuration_revision=start.configuration_revision,
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
        self,
        container_id: str,
        spec: ContainerSpec,
        start: _Start,
        scenarios: Sequence[Mapping[str, Any]],
    ) -> tuple[ScenarioRun, ...]:
        try:
            host, port = await address(self._container, container_id, spec, start.port)
        except ToolContainerError as e:
            raise _StartFailed(f"the app published no port {start.port}: {e}") from e
        base = f"http://{host}:{port}"
        if not await self._ready(base, host, port, start):
            try:
                logs = await self._container.logs(container_id)
            except ToolContainerError:
                logs = ""
            raise _StartFailed(
                f"not ready at {start.ready_path or f'port {start.port}'} "
                f"within {start.ready_timeout:g}s",
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

    async def _ready(self, base: str, host: str, port: int, start: _Start) -> bool:
        deadline = time.monotonic() + start.ready_timeout
        async with self._http() as client:
            while True:
                if await self._answers(client, base, host, port, start):
                    return True
                if time.monotonic() >= deadline:
                    return False
                await asyncio.sleep(self._poll)

    async def _answers(
        self, client: httpx.AsyncClient, base: str, host: str, port: int, start: _Start
    ) -> bool:
        if start.ready_kind == ReadinessKind.TCP:
            return await _tcp_answers(host, port, connect_timeout=self._poll + 1.0)
        try:
            response = await client.get(base + start.ready_path)
        except (httpx.HTTPError, OSError):
            return False  # connection refused while the app boots is expected
        return not start.require_2xx or 200 <= response.status_code < 300


async def _tcp_answers(host: str, port: int, *, connect_timeout: float) -> bool:
    """A connection the app holds. Docker's port proxy accepts on the published port as soon as the
    container starts, and closes at once, sending nothing, while nothing listens behind it (read
    live on the Spark, 2026-10-18). So a connection counts only if it stays open, or the app speaks
    first."""
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=connect_timeout
        )
    except (OSError, TimeoutError):
        return False  # nothing listens yet while the app boots
    try:
        return bool(await asyncio.wait_for(reader.read(1), timeout=_TCP_SETTLE_SECONDS))
    except TimeoutError:
        return True  # held open and silent: the app's own listener
    except OSError:
        return False
    finally:
        writer.close()


def _redacted(evaluation: TreeEvaluation, secrets: Collection[str]) -> TreeEvaluation:
    """The evaluation with every resolved secret's value replaced in its free text (Q40: never in a
    log, a record or an agent's input). An app may log its environment, or answer with a token, and
    the start's detail, its last lines and each step's detail are returned as written. Only those
    are scrubbed: a short secret (``pass``) must not rewrite a result (``passed``), an identity or
    a scenario id (the MacBook lane's review of #2450). Longest first, so a value that contains
    another is replaced whole."""
    values = sorted({v for v in secrets if v}, key=len, reverse=True)
    if not values:
        return evaluation

    def scrub(text: str | None) -> str | None:
        if text is None:
            return None
        for secret in values:
            text = text.replace(secret, _REDACTED)
        return text

    return dataclasses.replace(
        evaluation,
        start_detail=scrub(evaluation.start_detail),
        startup_diagnostics=tuple(scrub(line) or "" for line in evaluation.startup_diagnostics),
        runs=tuple(dataclasses.replace(run, detail=scrub(run.detail)) for run in evaluation.runs),
    )
