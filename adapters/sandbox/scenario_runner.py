"""The scenario runner in the sandbox service (SIP-0113 §4.1, A3; X-3b; #2414, #2421).

One evaluation is one call:
1. the evaluated tree's files are checked against their ``FileTree.identity``;
2. they are written to a disposable copy under the sandbox root, executable bits included;
3. the copy is started, by the product's own declaration or by its stack's environment contract;
4. once it is ready, and before any scenario writes to it, the evaluator's image measures its
   declared pages with Lighthouse and axe, on the app network (§4.2, #2416);
5. each scenario's steps run from the service, outside the app's process;
6. the app stops and the copy is removed, whatever happened;
7. #1937's lint reads the tree as delivered, in the evaluator's image with no network, whatever the
   start did (§4.2, #2416).

Nothing a scenario caused reaches a workspace, a revision or a commit (contract 3). The steps
are held in memory for the call, never written, and never in a result.

The posture is the sandbox's own (§7 items 9–10): caps dropped, no new privileges, the copy's
owner's uid, and resource limits. Setup gets the dependency network, as an install does. The
app gets the bridge it needs to publish its one port to loopback.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import shlex
import shutil
import time
import uuid
from collections.abc import Callable, Collection, Mapping, Sequence
from pathlib import Path
from typing import Any

import httpx

from adapters.sandbox.placement import address, placement
from squadops.campaigns.evaluator_trees import FileTree
from squadops.campaigns.seed_plan import SeedPlan, SeedRecord, fill
from squadops.capabilities.delivered_lint import (
    RUFF_ARGS,
    eslint_findings,
    eslint_runner_source,
    lintable,
    linted_counts,
    ruff_findings,
    tools_reading,
)
from squadops.ports.scenarios import ScenarioRunnerPort
from squadops.ports.tools.container import ContainerPort
from squadops.sandbox.environment import get_environment_contract
from squadops.sandbox.models import OperationName, content_bytes, declared_argv
from squadops.sandbox.workspace import WorkspaceEscapeError, tree_path, working_directory
from squadops.scenarios.quality import (
    LintReading,
    NotMeasured,
    QualityReading,
    QualityStatus,
    evaluator_pages,
)
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
        api_port: int,
        api_path: str,
        ui_port: int | None,
        ui_serve: tuple[str, ...],
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
        # Where scenarios reach the API (#2421): the declared http_base, or the stack's own
        # prefix on its app port. Readiness stays on ``port``.
        self.api_port, self.api_path = api_port, api_path
        # Where its pages are served (#2416), and what serves them beside the app when it doesn't.
        self.ui_port, self.ui_serve = ui_port, ui_serve

    @property
    def ports(self) -> tuple[int, ...]:
        ui = () if self.ui_port is None else (self.ui_port,)
        return tuple(dict.fromkeys((self.port, self.api_port, *ui)))

    @property
    def argv(self) -> tuple[str, ...]:
        """The start, and beside it what serves the built pages when the app doesn't."""
        if not self.ui_serve:
            return self.start
        return ("sh", "-c", f"{shlex.join(self.start)} & exec {shlex.join(self.ui_serve)}")


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
        evaluator_image: str,
        evaluator_timeout_seconds: float = 300.0,
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
        # SIP-0113 A2 (#2416): Lighthouse and axe run in a container of this image, on the app
        # network beside the app, with nothing of the app's environment.
        self._evaluator_image = evaluator_image
        self._evaluator_timeout = evaluator_timeout_seconds

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
        pages: Sequence[str],
        seed: SeedPlan | None = None,
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
        # §10n ruling 8: the seeded instance starts from the copy as setup left it, snapshotted
        # before the first instance starts, so nothing the scenarios write reaches its reading.
        snapshot = copy.with_name(f"{copy.name}-seeded") if seed is not None else None
        timings: dict[str, float] = {}
        try:
            self._write_copy(copy, tree, executable)
            evaluation = await self._evaluate(
                copy, tree_identity, start, scenarios, environment, pages, started,
                snapshot=snapshot, timings=timings,
            )  # fmt: skip
            if seed is not None and snapshot is not None and evaluation.started:
                seeded = await self._seeded(snapshot, start, seed, environment, timings)
                evaluation = dataclasses.replace(evaluation, quality_seeded=seeded)
        finally:
            shutil.rmtree(copy, ignore_errors=True)
            if snapshot is not None:
                shutil.rmtree(snapshot, ignore_errors=True)
        evaluation = dataclasses.replace(evaluation, lint=await self._lint(tree, declared))
        return _redacted(evaluation, environment.values())

    async def _lint(
        self, tree: Mapping[str, bytes | str], declared: DeclaredStart | None
    ) -> LintReading:
        """#1937's lint over the tree as delivered (§4.2, #2416). The evaluator's image runs the
        tools with no network; the files, #1937's ruff command and its ESLint runner go on its
        input, so each has one source. Only a blueprint's tree has #1937's rule sets."""
        if declared is not None:
            return LintReading.not_measured(NotMeasured.NOT_A_SCAFFOLD_STACK)
        if not await self._container.has_image(self._evaluator_image):
            return LintReading.not_measured(NotMeasured.EVALUATOR_ABSENT, self._evaluator_image)
        files = lintable(tree)
        request = {
            "lint": {
                "files": files,
                "ruff_args": list(RUFF_ARGS),
                "eslint_runner": eslint_runner_source(),
            }
        }
        try:
            run = await self._container.run(
                ContainerSpec(
                    image=self._evaluator_image,
                    network="none",
                    timeout_seconds=self._evaluator_timeout,
                    memory_limit=self._limits[0],
                    cpu_limit=self._limits[1],
                    pids_limit=self._limits[2],
                    cap_drop_all=True,
                    no_new_privileges=True,
                    stdin=json.dumps(request).encode("utf-8"),
                )
            )
        except ToolContainerError as e:
            return LintReading.not_measured(NotMeasured.EVALUATOR_FAILED, str(e))
        if run.exit_code != 0:
            tail = "\n".join((run.stdout + run.stderr).splitlines()[-_TAIL_LINES:])
            return LintReading.not_measured(
                NotMeasured.EVALUATOR_FAILED, f"exited {run.exit_code}: {tail}"
            )
        try:
            answer = json.loads(run.stdout.strip().splitlines()[-1])["lint"]
            ruff, eslint = answer["ruff"], answer["eslint"]
            ran = {
                "ruff": ruff_findings(
                    (ruff["exit"], ruff["stdout"], ruff["stderr"]), ruff["version"], answer["root"]
                )
                if ruff
                else None,
                "eslint": eslint_findings((eslint["exit"], eslint["stdout"], eslint["stderr"]))
                if eslint
                else None,
            }
        except (ValueError, IndexError, KeyError, TypeError) as e:
            return LintReading.not_measured(NotMeasured.EVALUATOR_FAILED, f"its answer: {e}")
        return LintReading(
            QualityStatus.MEASURED,
            reading=tools_reading(linted_counts(files), ran),
            evaluator=self._evaluator_image,
        )

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
                declared.api_port if declared.api_port is not None else declared.port,
                declared.api_path,
                declared.ui_port,
                (),  # a product serves its own pages, at its ui_base
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
            contract.app_port,
            contract.api_prefix,
            contract.ui_port,
            contract.ui_serve,
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

    async def _evaluate(
        self, copy, identity, start, scenarios, environment, pages, started, *, snapshot=None,
        timings=None,
    ):  # fmt: skip
        try:
            await self._setup(copy, start)
            if snapshot is not None:
                taken = time.monotonic()
                shutil.copytree(copy, snapshot, symlinks=True)
                if timings is not None:
                    timings["snapshot_s"] = round(time.monotonic() - taken, 3)
            env = (("HOME", "/tmp"), *sorted(environment.items()))
            try:
                container_id = await self._container.run_detached(
                    spec := self._spec(
                        copy,
                        start.argv,
                        start.working_dir,
                        env=env,
                        **placement(self._app_network, "eval", start.ports),
                    )
                )
            except ToolContainerError as e:
                raise _StartFailed(f"the start could not run: {e}") from e
            try:
                runs, quality = await self._serve(container_id, spec, start, scenarios, pages)
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
            quality=quality,
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
        pages: Sequence[str],
    ) -> tuple[tuple[ScenarioRun, ...], QualityReading]:
        try:
            host, port = await address(self._container, container_id, spec, start.port)
            api_host, api_port = await address(self._container, container_id, spec, start.api_port)
        except ToolContainerError as e:
            raise _StartFailed(f"the app published no port {start.ports}: {e}") from e
        base = f"http://{host}:{port}"
        api = f"http://{api_host}:{api_port}{start.api_path}"
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
        # §4.2: measured before any scenario writes to the instance, so every tree is measured
        # in the same state.
        quality = await self._quality(spec, start, pages)
        async with self._http() as client:

            async def send(request: HttpRequest) -> HttpResponse:
                try:
                    response = await client.request(
                        request.method,
                        api + request.path,
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

            return tuple([await run_scenario(scenario, send) for scenario in scenarios]), quality

    async def _quality(
        self, spec: ContainerSpec, start: _Start, pages: Sequence[str]
    ) -> QualityReading:
        """Lighthouse and axe on the declared ``pages`` (§4.2, #2416), by the evaluator's image on
        the app network. Anything that keeps it from running is ``not_measured``, with why."""
        if not pages or start.ui_port is None:
            return QualityReading.not_measured(NotMeasured.NO_DECLARED_PAGE)
        if spec.network is None or not spec.name:
            return QualityReading.not_measured(NotMeasured.NO_APP_NETWORK)
        if not await self._container.has_image(self._evaluator_image):
            return QualityReading.not_measured(NotMeasured.EVALUATOR_ABSENT, self._evaluator_image)
        base = f"http://{spec.name}:{start.ui_port}"
        if not await self._ui_answers(base, start.ready_timeout):
            return QualityReading.not_measured(
                NotMeasured.UI_NOT_READY,
                f"nothing answered at {base} within {start.ready_timeout:g}s",
            )
        request = {"base_url": base, "pages": list(pages)}
        try:
            run = await self._container.run(
                ContainerSpec(
                    image=self._evaluator_image,
                    network=spec.network,
                    timeout_seconds=self._evaluator_timeout,
                    memory_limit=self._limits[0],
                    cpu_limit=self._limits[1],
                    pids_limit=self._limits[2],
                    cap_drop_all=True,
                    no_new_privileges=True,
                    stdin=json.dumps(request).encode("utf-8"),
                )
            )
        except ToolContainerError as e:
            return QualityReading.not_measured(NotMeasured.EVALUATOR_FAILED, str(e))
        if run.exit_code != 0:
            tail = "\n".join((run.stdout + run.stderr).splitlines()[-_TAIL_LINES:])
            return QualityReading.not_measured(
                NotMeasured.EVALUATOR_FAILED, f"exited {run.exit_code}: {tail}"
            )
        try:
            measured = evaluator_pages(json.loads(run.stdout.strip().splitlines()[-1]), pages)
        except (ValueError, IndexError, KeyError, TypeError, AttributeError) as e:
            return QualityReading.not_measured(NotMeasured.EVALUATOR_FAILED, str(e))
        return QualityReading(
            QualityStatus.MEASURED, pages=measured, evaluator=self._evaluator_image
        )

    async def _seeded(
        self,
        snapshot: Path,
        start: _Start,
        plan: SeedPlan,
        environment: Mapping[str, str],
        timings: dict[str, float],
    ) -> QualityReading:
        """§10j, §10n ruling 8: the tree started a second time, from setup's snapshot, after the
        first instance is torn down; seeded through its own API; measured on every page the plan
        names; and torn down. Whatever keeps it from a reading is the seeded reading's *not
        measured*, and never touches the scenarios' record."""
        began = time.monotonic()
        env = (("HOME", "/tmp"), *sorted(environment.items()))
        try:
            container_id = await self._container.run_detached(
                spec := self._spec(
                    snapshot,
                    start.argv,
                    start.working_dir,
                    env=env,
                    **placement(self._app_network, "eval-seeded", start.ports),
                )
            )
        except ToolContainerError as e:
            return QualityReading.not_measured(
                NotMeasured.START_FAILED, f"the seeded instance could not start: {e}"
            )
        try:
            return await self._seed_and_measure(container_id, spec, start, plan, timings, began)
        except Exception as e:  # noqa: BLE001 — the seeded reading never takes the scenarios' down
            return QualityReading.not_measured(
                NotMeasured.EVALUATOR_FAILED, f"the seeded instance: {type(e).__name__}: {e}"
            )
        finally:
            await self._teardown(container_id)

    async def _seed_and_measure(
        self,
        container_id: str,
        spec: ContainerSpec,
        start: _Start,
        plan: SeedPlan,
        timings: dict[str, float],
        began: float,
    ) -> QualityReading:
        host, port = await address(self._container, container_id, spec, start.port)
        api_host, api_port = await address(self._container, container_id, spec, start.api_port)
        if not await self._ready(f"http://{host}:{port}", host, port, start):
            return QualityReading.not_measured(
                NotMeasured.START_FAILED,
                f"the seeded instance wasn't ready within {start.ready_timeout:g}s",
            )
        timings["start_s"] = round(time.monotonic() - began, 3)
        seeding = time.monotonic()
        # §10n ruling 8: to the app's own address and each path as the manifest writes it, never
        # through the scenarios' API prefix.
        base = f"http://{api_host}:{api_port}"
        async with self._http() as client:
            outcomes = [await _seed_record(client, base, record) for record in plan.records]
        timings["seed_s"] = round(time.monotonic() - seeding, 3)
        ids = {o["label"]: o["id"] for o in outcomes if o.get("seeded")}
        account: dict[str, Any] = {
            "version": plan.version,
            "records": outcomes,
            "unfilled": [list(u) for u in plan.unfilled]
            + [
                [f"{p.route}#{p.record}", "seed_failed"]
                for p in plan.pages
                if p.record and p.record not in ids
            ],
            "notes": list(plan.notes) + [f"{label}: {why}" for label, why in plan.refused],
            "durations": timings,
        }
        if not ids:
            return QualityReading(
                QualityStatus.NOT_MEASURED,
                reason=NotMeasured.SEED_FAILED,
                detail="; ".join(f"{o['label']}: {o['failed']}" for o in outcomes),
                seed=account,
            )
        asked = [
            (page, fill(page.route, page.segment, ids[page.record]) if page.record else page.route)
            for page in plan.pages
            if page.record is None or page.record in ids
        ]
        measuring = time.monotonic()
        reading = await self._quality(spec, start, [url for _, url in asked])
        timings["measure_s"] = round(time.monotonic() - measuring, 3)
        timings["total_s"] = round(time.monotonic() - began, 3)
        by_url = {p.path: p for p in reading.pages}
        # §10n ruling 4: each page under its key, route and record, with the address it loaded at.
        keyed = tuple(
            dataclasses.replace(by_url[url], path=page.key, url=url if page.record else None)
            for page, url in asked
            if url in by_url
        )
        return dataclasses.replace(reading, pages=keyed, seed=account)

    async def _ui_answers(self, base: str, timeout: float) -> bool:
        """Whether anything answers at the UI's base: any HTTP answer, since the preview server
        refuses a name it doesn't know (the evaluator itself reaches it by IP)."""
        deadline = time.monotonic() + timeout
        async with self._http() as client:
            while True:
                try:
                    await client.get(base + "/")
                    return True
                except (httpx.HTTPError, OSError):
                    pass
                if time.monotonic() >= deadline:
                    return False
                await asyncio.sleep(self._poll)

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


async def _seed_record(client: httpx.AsyncClient, base: str, record: SeedRecord) -> dict[str, Any]:
    """One record written through the app's own API (§10j): its create, whose response gives its
    id, then each member action on that id. A request that fails voids this record only (§10n
    ruling 7), and the request and status are kept; a body is never kept."""

    async def send(method: str, path: str, body: Mapping[str, Any]) -> httpx.Response | str:
        try:
            response = await client.request(method, base + path, json=dict(body))
        except httpx.HTTPError as e:
            return f"{method} {path}: {type(e).__name__}"
        if response.status_code >= 300:
            return f"{method} {path} answered {response.status_code}"
        return response

    created = await send(record.create.method, record.create.path, record.create.json)
    if isinstance(created, str):
        return {"label": record.label, "seeded": False, "failed": created}
    try:
        ident = str(created.json()["id"])
    except (ValueError, KeyError, TypeError):
        return {
            "label": record.label,
            "seeded": False,
            "failed": f"{record.create.method} {record.create.path} answered no id",
        }
    for member in record.members:
        joined = await send(member.method, fill(member.path, member.segment, ident), member.json)
        if isinstance(joined, str):
            return {"label": record.label, "seeded": False, "failed": joined}
    return {"label": record.label, "seeded": True, "id": ident, "members": len(record.members)}


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

    def scrubbed(reading: QualityReading | None) -> QualityReading | None:
        # §10n ruling 8: a reading's detail is an evaluator's or a seed's free text too.
        if reading is None:
            return None
        seed = reading.seed
        if seed is not None:
            seed = {
                **seed,
                "records": [
                    {**r, "failed": scrub(r["failed"])} if "failed" in r else r
                    for r in seed.get("records", ())
                ],
            }
        return dataclasses.replace(reading, detail=scrub(reading.detail), seed=seed)

    return dataclasses.replace(
        evaluation,
        start_detail=scrub(evaluation.start_detail),
        startup_diagnostics=tuple(scrub(line) or "" for line in evaluation.startup_diagnostics),
        runs=tuple(dataclasses.replace(run, detail=scrub(run.detail)) for run in evaluation.runs),
        quality=scrubbed(evaluation.quality),
        quality_seeded=scrubbed(evaluation.quality_seeded),
    )
