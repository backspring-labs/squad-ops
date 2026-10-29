"""What the scenario runner takes and gives (SIP-0113 §4.1; X-3b; #2414, #2421).

The runner stands an evaluated tree up in a disposable copy, by its ``FileTree.identity``, never
by a sandbox revision (SIP-0112 contract 3). It runs a suite's scenarios against it and discards
it.

- **A blueprint Project starts by its stack's environment contract,** with transport-level
  readiness (#520/#622).
- **Any other Project starts by its start declaration** (contract 7), read here into a
  ``DeclaredStart``. Readiness is a 2xx from the declared target.

This SIP never infers how to start a product from a sample application.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import urlsplit

from squadops.scenarios.evaluation import BlockedReason
from squadops.scenarios.quality import LintReading, QualityReading
from squadops.scenarios.steps import ScenarioRun


class RunnerUnavailable(Exception):
    """The deploy runs no scenario runner, or can't reach it: every applicable scenario is
    ``blocked_unverified``, reason ``no_runner``, never passed (§4.1)."""


class StartUndeclared(ValueError):
    """No start declaration, or one that breaks contract 7's schema: every scenario is
    ``blocked_unverified``, reason ``no_start_declaration`` (SIP-0112 §8.2.1). E.4.2 validates
    each revision when it is recorded, so a stored one reaching here malformed is a defect there.
    """

    reason = BlockedReason.NO_START_DECLARATION


class SecretUnavailable(ValueError):
    """A start that declares an evaluation secret no approval record releases (SIP-0112 Q40,
    contract 7): it isn't resolved, and every scenario is ``blocked_unverified``, reason
    ``secret_not_available``. The owner's per-Project approval is #2421's, unbuilt in 2.5, so no
    declared secret is resolved yet."""

    reason = BlockedReason.SECRET_NOT_AVAILABLE


class ReadinessUnsupported(ValueError):
    """A valid readiness kind this runner doesn't check: ``command``, whose target the contract
    names as a string and not an argv. Every scenario is ``blocked_unverified``, ``no_runner``."""

    reason = BlockedReason.NO_RUNNER


class ReadinessKind:
    """Contract 7's readiness kinds (SIP-0112 §8.2.1). The runner checks ``http`` (a 2xx from
    the target) and ``tcp`` (a connection to its port)."""

    HTTP = "http"
    TCP = "tcp"
    COMMAND = "command"
    CHECKED = frozenset({HTTP, TCP})
    ALL = frozenset({HTTP, TCP, COMMAND})


@dataclass(frozen=True)
class DeclaredStart:
    """A product's own start (contract 7): setup argvs, then the start argv, in the copy. The
    port is the one the product listens on inside it. Readiness is a 2xx from ``ready_path``
    (``http``) or a connection to the port (``tcp``). ``configuration_revision`` is the
    Development Configuration revision the declaration came from, recorded on the evaluation."""

    start: tuple[str, ...]
    port: int
    ready_kind: str
    ready_path: str
    ready_timeout_seconds: float
    setup: tuple[tuple[str, ...], ...] = ()
    working_dir: str = "."
    configuration_revision: int | None = None
    #: The declared ``http_base`` entry point (#2421): the port and path scenarios reach the API
    #: at. ``None`` when the Project declares no ``http_base``; then no ``http_endpoint`` scenario
    #: applies (``evaluate.declared_surfaces``).
    api_port: int | None = None
    api_path: str = ""
    #: The declared ``ui_base`` entry point (#2416): where its pages are served, measured by
    #: Lighthouse and axe. ``None`` when the Project declares no ``ui_base``: it has no pages.
    ui_port: int | None = None
    ui_path: str = ""

    def __post_init__(self) -> None:
        if self.ready_kind not in ReadinessKind.CHECKED:
            raise ReadinessUnsupported(f"no runner for readiness {self.ready_kind!r}")

    def as_dict(self) -> dict[str, Any]:
        return {
            "start": list(self.start),
            "port": self.port,
            "ready_kind": self.ready_kind,
            "ready_path": self.ready_path,
            "ready_timeout_seconds": self.ready_timeout_seconds,
            "setup": [list(s) for s in self.setup],
            "working_dir": self.working_dir,
            "configuration_revision": self.configuration_revision,
            "api_port": self.api_port,
            "api_path": self.api_path,
            "ui_port": self.ui_port,
            "ui_path": self.ui_path,
        }

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> DeclaredStart:
        return cls(
            start=tuple(d["start"]),
            port=int(d["port"]),
            ready_kind=str(d["ready_kind"]),
            ready_path=str(d["ready_path"]),
            ready_timeout_seconds=float(d["ready_timeout_seconds"]),
            setup=tuple(tuple(s) for s in d.get("setup", ())),
            working_dir=str(d.get("working_dir", ".")),
            configuration_revision=d.get("configuration_revision"),
            api_port=d.get("api_port"),
            api_path=str(d.get("api_path", "")),
            ui_port=d.get("ui_port"),
            ui_path=str(d.get("ui_path", "")),
        )


def _argv(value: Any, where: str) -> tuple[str, ...]:
    if not isinstance(value, list | tuple) or not value:
        raise StartUndeclared(f"{where} is an argv, a list of strings, never one string: {value!r}")
    if not all(isinstance(a, str) and a for a in value):
        raise StartUndeclared(f"{where} is a list of non-empty strings: {value!r}")
    return tuple(value)


def _working_directory(value: Any) -> str:
    path = PurePosixPath(str(value).strip() or ".")
    if path.is_absolute() or ".." in path.parts:
        raise StartUndeclared(f"working_directory {value!r} is a path inside the repository")
    return str(path)


def _entry_points(entry_points: Any) -> tuple[Mapping[str, Any], ...]:
    """Contract 7's entry points, each a known kind with a url. It declares at least one."""
    if not isinstance(entry_points, list | tuple) or not entry_points:
        raise StartUndeclared(
            "the declaration names no entry_points: contract 7 declares at least one"
        )
    for entry in entry_points:
        if not isinstance(entry, Mapping) or entry.get("kind") not in _ENTRY_KINDS:
            raise StartUndeclared(
                f"an entry point is a kind of {sorted(_ENTRY_KINDS)} and a url: {entry!r}"
            )
    return tuple(entry_points)


def _base(entry_points: tuple[Mapping[str, Any], ...], kind: str) -> tuple[int | None, str]:
    """The first ``kind`` entry point's port and path, ``(None, "")`` when there is none."""
    bases = [e for e in entry_points if e["kind"] == kind]
    if not bases:
        return None, ""
    url = urlsplit(str(bases[0].get("url", "")))
    try:
        port = url.port
    except ValueError as e:
        raise StartUndeclared(f"{kind} {bases[0].get('url')!r}: {e}") from e
    if port is None:
        raise StartUndeclared(f"{kind} {bases[0].get('url')!r} names no port")
    return port, url.path.rstrip("/")


_ENTRY_KINDS = frozenset({"http_base", "ui_base", "other"})


def declared_start(
    declaration: Mapping[str, Any] | None, *, configuration_revision: int
) -> DeclaredStart:
    """A Development Configuration's start declaration (SIP-0112 §8.2.1, contract 7), as the
    runner runs it, from the revision it was recorded in. Its URLs are as the product sees them,
    loopback on its declared port: the runner publishes that port and keeps the path.

    Contract 7's schema is checked here, so a malformed declaration is refused as one, not met
    later as a failed start: an argv is a list of strings (``"python3 -m tally"`` is refused,
    never split), ``install`` and ``build`` are lists of argvs, the working directory stays in
    the repository, and readiness names its timeout."""
    if not declaration or not declaration.get("start"):
        raise StartUndeclared("the Project declares no start")
    start = _argv(declaration["start"], "start")
    setup: list[tuple[str, ...]] = []
    for key in ("install", "build"):
        entries = declaration.get(key) or []
        if not isinstance(entries, list | tuple):
            raise StartUndeclared(f"{key} is a list of argvs: {entries!r}")
        setup += [_argv(argv, f"each {key} step") for argv in entries]
    readiness = declaration.get("readiness")
    if not isinstance(readiness, Mapping):
        raise StartUndeclared("the declaration names no readiness")
    kind = readiness.get("kind")
    if kind not in ReadinessKind.ALL:
        raise StartUndeclared(f"readiness kind {kind!r} is not one of {sorted(ReadinessKind.ALL)}")
    if kind == ReadinessKind.COMMAND:
        raise ReadinessUnsupported(f"no runner for readiness {kind!r}")
    timeout = readiness.get("timeout_seconds")
    if isinstance(timeout, bool) or not isinstance(timeout, int | float) or timeout <= 0:
        raise StartUndeclared(
            f"readiness names its timeout_seconds, a positive number: {timeout!r}"
        )
    raw = str(readiness.get("target", ""))
    target = urlsplit(raw if "://" in raw else f"{kind}://{raw}")
    try:
        port = target.port
    except ValueError as e:
        raise StartUndeclared(f"readiness target {raw!r}: {e}") from e
    if port is None:
        raise StartUndeclared(f"readiness target {raw!r} names no port")
    entry_points = _entry_points(declaration.get("entry_points"))
    api_port, api_path = _base(entry_points, "http_base")
    ui_port, ui_path = _base(entry_points, "ui_base")
    return DeclaredStart(
        start=start,
        port=port,
        ready_kind=kind,
        ready_path=(target.path or "/") if kind == ReadinessKind.HTTP else "",
        ready_timeout_seconds=float(timeout),
        setup=tuple(setup),
        working_dir=_working_directory(declaration.get("working_directory", ".")),
        configuration_revision=configuration_revision,
        api_port=api_port,
        api_path=api_path,
        ui_port=ui_port,
        ui_path=ui_path,
    )


def configured_start(configuration: Any) -> DeclaredStart:
    """A Project's own start (contract 7), from its Development Configuration at the revision
    the unit pinned, as the runner runs it: what the cycle-end hook evaluates with (#2414), and
    what an increment's client routes are rendered on (SIP-0109 §24co). One reading, so the two
    can never start a product differently.

    Raises:
        StartUndeclared: The configuration declares no start, or one contract 7 refuses.
        SecretUnavailable: The start declares an evaluation secret, which nothing resolves yet.
        ReadinessUnsupported: Its readiness is a kind no runner checks.
    """
    # deferred (pair): the projects package reads the sandbox's findings, which load this one
    from squadops.projects.development_configuration import start_document

    declaration = configuration.commands.start
    if declaration is None:
        raise StartUndeclared("the Project declares no start")
    if declaration.evaluation_environment:
        names = ", ".join(name for name, _ in declaration.evaluation_environment)
        raise SecretUnavailable(f"the start declares {names}, and no approval releases it")
    return declared_start(
        start_document(declaration), configuration_revision=configuration.revision
    )


@dataclass(frozen=True)
class RouteRequest:
    """A client route to read on the started tree (SIP-0109 §24co, §8.3): the route as the
    manifest writes it, and, for a parameterized one, its seed (``increment_tree.route_seeds``):
    the create that brings its page into being and the segment the created id fills."""

    route: str
    seed: Mapping[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"route": self.route, "seed": dict(self.seed) if self.seed is not None else None}

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> RouteRequest:
        seed = d.get("seed")
        return cls(route=str(d["route"]), seed=dict(seed) if seed is not None else None)


@dataclass(frozen=True)
class RouteReading:
    """One route's page as the browser read it (SIP-0109 §24co): the path it was read at, and
    the test ids its elements carried. ``testids`` is ``None`` for a page that was never read, with
    why in ``detail``: no path reached it, or nothing read it."""

    route: str
    path: str | None
    testids: tuple[str, ...] | None
    detail: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "route": self.route,
            "path": self.path,
            "testids": list(self.testids) if self.testids is not None else None,
            "detail": self.detail,
        }

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> RouteReading:
        testids = d.get("testids")
        return cls(
            route=str(d["route"]),
            path=d.get("path"),
            testids=tuple(str(t) for t in testids) if testids is not None else None,
            detail=d.get("detail"),
        )


@dataclass(frozen=True)
class TreeEvaluation:
    """One tree's evaluation in the runner. ``started`` False carries why (``start_detail`` and
    the app's own last lines), and then no scenario ran. ``configuration_revision`` names the
    Development Configuration revision that started it, ``None`` for a blueprint."""

    tree_identity: str
    started: bool
    start_detail: str | None = None
    startup_diagnostics: tuple[str, ...] = ()
    runs: tuple[ScenarioRun, ...] = field(default_factory=tuple)
    duration_seconds: float = 0.0
    configuration_revision: int | None = None
    #: Lighthouse and axe on the started instance (#2416). ``None`` when nothing was started.
    quality: QualityReading | None = None
    #: #1937's lint over the tree as delivered (#2416), whatever the start did.
    lint: LintReading | None = None
    #: Lighthouse and axe on a second, seeded instance (§10j, §10n). ``None`` when none was asked.
    quality_seeded: QualityReading | None = None
    #: Each client route asked for, as the browser read it (SIP-0109 §24co). Empty when none was.
    routes: tuple[RouteReading, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "tree_identity": self.tree_identity,
            "started": self.started,
            "start_detail": self.start_detail,
            "startup_diagnostics": list(self.startup_diagnostics),
            "runs": [r.as_dict() for r in self.runs],
            "duration_seconds": self.duration_seconds,
            "configuration_revision": self.configuration_revision,
            "quality": self.quality.as_dict() if self.quality is not None else None,
            "lint": self.lint.as_dict() if self.lint is not None else None,
            "quality_seeded": (
                self.quality_seeded.as_dict() if self.quality_seeded is not None else None
            ),
            "routes": [r.as_dict() for r in self.routes],
        }

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> TreeEvaluation:
        return cls(
            tree_identity=d["tree_identity"],
            started=d["started"],
            start_detail=d.get("start_detail"),
            startup_diagnostics=tuple(d.get("startup_diagnostics", ())),
            # Strict: a key this side doesn't know fails loudly (§10p ruling 7: both sides deploy
            # together). Only the steps' seconds arrive as a list.
            runs=tuple(
                ScenarioRun(**{**r, "step_seconds": tuple(r.get("step_seconds") or ())})
                for r in d.get("runs", ())
            ),
            duration_seconds=d.get("duration_seconds", 0.0),
            configuration_revision=d.get("configuration_revision"),
            quality=QualityReading.from_dict(d["quality"]) if d.get("quality") else None,
            lint=LintReading.from_dict(d["lint"]) if d.get("lint") else None,
            quality_seeded=(
                QualityReading.from_dict(d["quality_seeded"]) if d.get("quality_seeded") else None
            ),
            # A service that predates §24co answers none: each route asked for is then unread.
            routes=tuple(RouteReading.from_dict(r) for r in d.get("routes") or ()),
        )
