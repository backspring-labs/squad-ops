"""Quality baselines: Lighthouse and axe per declared page, and #1937's lint over the evaluated
tree (SIP-0113 §4.2, phase 1; #2416).

They're measured by the evaluator's image (A2), on the instance the scenarios read, after it is
ready and before any scenario has written to it. So every tree is measured in the same state.
Reporting-only: no row, gate or prompt reads a reading.

A reading is one of three:
- **measured:** each declared page carries its scores, or the error that kept it from being scored.
  A page that answered an error, or painted nothing, is never scored.
- **not applicable:** the Project serves no pages.
- **not measured:** something kept the measure from running. The reason says what.

Neither of the last two is evidence. Neither counts in any rate, and neither ever reads as a
baseline held (§4.2).

Lint reads the tree as delivered, whatever the start did, by #1937's rule sets (``LintReading``).
Only a scaffold stack's tree has them: a declared Project's lint is not measured, unless it is a
greenfield product made from a scaffold blueprint, which its derived profile names (§10l). Its own
linter is never read in their place.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

#: Lighthouse's categories, by the key the reading keeps for each.
LIGHTHOUSE_CATEGORIES = ("performance", "accessibility", "best_practices")
#: axe's violation impacts, most severe first.
AXE_IMPACTS = ("critical", "serious", "moderate", "minor")
#: §10y: a page's failing ids, by list. Lighthouse's accessibility and best-practices audits (the
#: environment's apart), and axe's violated rules. Performance has none: its weighted audits are
#: its metrics, which score continuously.
FAILING_LISTS = ("accessibility", "best_practices", "environment", "axe")
#: §10y: the lists whose errored audits are recorded apart: Lighthouse's.
ERRORED_LISTS = ("accessibility", "best_practices", "environment")
#: Each Lighthouse list, by the category whose score nulls it: a null category's list is null,
#: never empty, since an errored audit in it is neither passing nor failing.
_LIST_CATEGORY = {
    "accessibility": "accessibility",
    "best_practices": "best_practices",
    "environment": "best_practices",
}

Ids = tuple[str, ...]


class QualityStatus(StrEnum):
    MEASURED = "measured"
    NOT_APPLICABLE = "not_applicable"
    NOT_MEASURED = "not_measured"


class NotMeasured(StrEnum):
    """Why a measure that applies didn't run."""

    #: No runner: the sandbox service wasn't reached, or isn't wired.
    NO_RUNNER = "no_runner"
    #: The app didn't start, so there was no instance to measure.
    START_FAILED = "start_failed"
    #: The Project couldn't be started: no start declaration, or none the runner reads.
    NO_START_DECLARATION = "no_start_declaration"
    #: The start declares an evaluation secret no approval releases (SIP-0112 Q40, contract 7), so
    #: nothing was started (SIP-0113 §10l).
    SECRET_NOT_AVAILABLE = "secret_not_available"
    #: #1937's rule sets exist only for the scaffold stacks: a declared Project's lint is never
    #: read unless the product follows a scaffold blueprint (§10l), and the product's own linter is
    #: never used in its place (§4.2).
    NOT_A_SCAFFOLD_STACK = "not_a_scaffold_stack"
    #: The derived profile at the unit's pin couldn't be read, so whether the product was made from
    #: a scaffold blueprint isn't known, and its lint isn't read (§10l; the second review of
    #: #2788, P3-6). Never ``not_a_scaffold_stack``, which would claim to know.
    PROFILE_UNREADABLE = "profile_unreadable"
    #: The delivery declares no page without a parameter, so none can be loaded as is.
    NO_DECLARED_PAGE = "no_declared_page"
    #: Not on the sandbox's app network (a host run), where the evaluator can't reach the app.
    NO_APP_NETWORK = "no_app_network"
    #: The app's UI never answered.
    UI_NOT_READY = "ui_not_ready"
    #: The evaluator's image isn't on the box.
    EVALUATOR_ABSENT = "evaluator_absent"
    #: The evaluator ran and failed, or answered something it shouldn't.
    EVALUATOR_FAILED = "evaluator_failed"
    #: §10j, §10n: the seeded reading's. The Project declares no quality seed
    #: (``config/quality_seeds.yaml``).
    NO_SEED = "no_seed"
    #: The delivery's interface can take no record of the seed (``campaigns.seed_plan``).
    SEED_REFUSED = "seed_refused"
    #: The app refused every record the seed sent, so nothing was seeded to measure.
    SEED_FAILED = "seed_failed"


@dataclass(frozen=True)
class PageMeasure:
    """One page's scores: Lighthouse's three categories (0 to 1) and axe's violations by impact.
    A page that couldn't be scored has neither, and says why in ``error``.

    §10y's finer reading (the evaluator's ``-7`` on) sits beside them, reporting-only. A page
    measured earlier has none of it, and reads as not having it, never as zero. ``lighthouse``'s
    ``best_practices`` stays Lighthouse's raw score, read with the sandbox's plain HTTP;
    ``best_practices_app`` is the same category without the environment's audits."""

    path: str
    lighthouse: Mapping[str, float | None] | None = None
    axe: Mapping[str, int] | None = None
    error: str | None = None
    #: §10n ruling 4: a seeded page's ``path`` is its key, the route and the record that filled it
    #: (``/runs/{id}#partial``), and ``url`` the address it was loaded at, which differs on every
    #: instance. ``None`` on an unseeded page, whose path is its address.
    url: str | None = None
    #: §10y: axe's violating nodes by impact, one per (rule, element) pair, each under its own.
    axe_nodes: Mapping[str, int] | None = None
    #: §10y: the failing ids by ``FAILING_LISTS``, each sorted; a Lighthouse list is ``None`` when
    #: its category scored null.
    failing: Mapping[str, Ids | None] | None = None
    #: §10y: the weighted audits that errored, by ``ERRORED_LISTS``. Never compared.
    errored: Mapping[str, Ids] | None = None
    #: §10y: best practices without the environment's audits; ``None`` when its category scored
    #: null, no weight remained, or the recomputation failed its invariant (``..._error`` says).
    best_practices_app: float | None = None
    best_practices_app_error: str | None = None

    @property
    def finer(self) -> bool:
        """Whether the page carries §10y's finer reading: a scored page measured on ``-7`` on."""
        return self.axe_nodes is not None

    def as_dict(self) -> dict[str, Any]:
        finer = (
            {
                "axe_nodes": dict(self.axe_nodes or {}),
                "failing": {k: _listed(v) for k, v in (self.failing or {}).items()},
                "errored": {k: list(v) for k, v in (self.errored or {}).items()},
                "best_practices_app": self.best_practices_app,
                "best_practices_app_error": self.best_practices_app_error,
            }
            if self.finer
            else {}
        )
        return {
            "path": self.path,
            "lighthouse": dict(self.lighthouse) if self.lighthouse is not None else None,
            "axe": dict(self.axe) if self.axe is not None else None,
            "error": self.error,
            **({"url": self.url} if self.url is not None else {}),
            **finer,
        }

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> PageMeasure:
        failing, errored = d.get("failing"), d.get("errored")
        return cls(
            path=d["path"],
            lighthouse=d.get("lighthouse"),
            axe=d.get("axe"),
            error=d.get("error"),
            url=d.get("url"),
            axe_nodes=d.get("axe_nodes"),
            failing=(
                {k: tuple(v) if v is not None else None for k, v in failing.items()}
                if failing is not None
                else None
            ),
            errored={k: tuple(v) for k, v in errored.items()} if errored is not None else None,
            best_practices_app=d.get("best_practices_app"),
            best_practices_app_error=d.get("best_practices_app_error"),
        )


def _listed(ids: Ids | None) -> list[str] | None:
    return list(ids) if ids is not None else None


@dataclass(frozen=True)
class QualityReading:
    """One tree's Lighthouse and axe reading. ``evaluator`` names the image that measured it,
    which is each measure's version (§1.3 of the 2.4 plan: the window records it)."""

    status: QualityStatus
    reason: NotMeasured | None = None
    pages: tuple[PageMeasure, ...] = field(default_factory=tuple)
    evaluator: str | None = None
    detail: str | None = None
    #: §10j, §10n: a seeded reading's account. Its ``version`` (``SeedPlan.version``), each
    #: record's outcome, the pages it couldn't fill, its notes and each phase's duration.
    #: ``None`` on §10f's reading.
    seed: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if (self.status is QualityStatus.NOT_MEASURED) != (self.reason is not None):
            raise ValueError("a reading that isn't measured says why, and only then")
        if self.pages and self.status is not QualityStatus.MEASURED:
            raise ValueError("only a measured reading carries pages")

    @classmethod
    def not_measured(cls, reason: NotMeasured, detail: str | None = None) -> QualityReading:
        return cls(QualityStatus.NOT_MEASURED, reason=reason, detail=detail)

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "reason": self.reason.value if self.reason else None,
            "pages": [p.as_dict() for p in self.pages],
            "evaluator": self.evaluator,
            "detail": self.detail,
            **({"seed": dict(self.seed)} if self.seed is not None else {}),
        }

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> QualityReading:
        return cls(
            status=QualityStatus(d["status"]),
            reason=NotMeasured(d["reason"]) if d.get("reason") else None,
            pages=tuple(PageMeasure.from_dict(p) for p in d.get("pages", ())),
            evaluator=d.get("evaluator"),
            detail=d.get("detail"),
            seed=d.get("seed"),
        )


@dataclass(frozen=True)
class LintReading:
    """One tree's lint by #1937's rule sets (§4.2, #2416): ``reading`` is #1937's own shape
    (``delivered_lint.reading``), counted by rule and by file, with any tool that couldn't run
    named under its ``unavailable``. ``evaluator`` names the image that ran the tools."""

    status: QualityStatus
    reason: NotMeasured | None = None
    reading: Mapping[str, Any] | None = None
    evaluator: str | None = None
    detail: str | None = None

    def __post_init__(self) -> None:
        if self.status is QualityStatus.NOT_APPLICABLE:
            raise ValueError("lint applies to every tree: it is measured, or not measured")
        if (self.status is QualityStatus.NOT_MEASURED) != (self.reason is not None):
            raise ValueError("a reading that isn't measured says why, and only then")
        if (self.status is QualityStatus.MEASURED) != (self.reading is not None):
            raise ValueError("a measured lint carries its reading, and only it")

    @classmethod
    def not_measured(cls, reason: NotMeasured, detail: str | None = None) -> LintReading:
        return cls(QualityStatus.NOT_MEASURED, reason=reason, detail=detail)

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "reason": self.reason.value if self.reason else None,
            "reading": dict(self.reading) if self.reading is not None else None,
            "evaluator": self.evaluator,
            "detail": self.detail,
        }

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> LintReading:
        return cls(
            status=QualityStatus(d["status"]),
            reason=NotMeasured(d["reason"]) if d.get("reason") else None,
            reading=d.get("reading"),
            evaluator=d.get("evaluator"),
            detail=d.get("detail"),
        )


_FINER_KEYS = ("axe_nodes", "failing", "errored", "best_practices_app")


def evaluator_pages(answer: Mapping[str, Any], asked: Sequence[str]) -> tuple[PageMeasure, ...]:
    """The evaluator's answer, one measure per page asked for, in that order. Refused unless it
    names exactly those pages, each with its scores or its error, never both. A scored page
    carries §10y's finer reading, the runner's evaluator being ``-7`` or later: one without it is
    refused, never read as zero."""
    pages = answer.get("pages")
    if not isinstance(pages, list) or [p.get("path") for p in pages] != list(asked):
        raise ValueError(f"the evaluator answered for other pages than {list(asked)}")
    measured = []
    for page in pages:
        error = page.get("error")
        lighthouse, axe = page.get("lighthouse"), page.get("axe")
        if error is not None and (lighthouse is not None or axe is not None):
            raise ValueError(f"page {page['path']}: scored and in error at once")
        if error is None and (lighthouse is None or axe is None):
            raise ValueError(f"page {page['path']}: neither scored nor in error")
        if error is not None:
            if any(page.get(k) is not None for k in _FINER_KEYS):
                raise ValueError(f"page {page['path']}: a finer reading of a page in error")
            measured.append(PageMeasure(page["path"], error=error))
            continue
        lighthouse = {k: lighthouse.get(k.replace("_", "-")) for k in LIGHTHOUSE_CATEGORIES}
        axe = {k: int(axe.get(k, 0)) for k in AXE_IMPACTS}
        measured.append(_finer(page, lighthouse, axe))
    return tuple(measured)


def _ids(value: Any, where: str) -> Ids:
    if not isinstance(value, list) or not all(isinstance(i, str) for i in value):
        raise ValueError(f"{where}: a list of ids, not {value!r}")
    return tuple(sorted(set(value)))


def _finer(page: Mapping[str, Any], lighthouse: dict, axe: dict) -> PageMeasure:
    """A scored page's measure, with §10y's finer reading. Refused when it lacks a key, or when a
    list says something its category's score doesn't: a list of a null category, or a null list
    of a scored one."""
    path = page["path"]
    missing = [k for k in _FINER_KEYS if k not in page]
    if missing:
        raise ValueError(f"page {path}: no {', '.join(missing)}, which -7's evaluator reads")
    nodes, failing, errored = page["axe_nodes"], page["failing"], page["errored"]
    if not isinstance(nodes, Mapping) or sorted(nodes) != sorted(AXE_IMPACTS):
        raise ValueError(f"page {path}: axe_nodes by {list(AXE_IMPACTS)}, not {nodes!r}")
    if not isinstance(failing, Mapping) or sorted(failing) != sorted(FAILING_LISTS):
        raise ValueError(f"page {path}: failing by {list(FAILING_LISTS)}, not {failing!r}")
    if not isinstance(errored, Mapping) or sorted(errored) != sorted(ERRORED_LISTS):
        raise ValueError(f"page {path}: errored by {list(ERRORED_LISTS)}, not {errored!r}")
    lists: dict[str, Ids | None] = {}
    for name in FAILING_LISTS:
        category = _LIST_CATEGORY.get(name)
        null = category is not None and lighthouse[category] is None
        if (failing[name] is None) != null:
            raise ValueError(
                f"page {path}: failing.{name} is {failing[name]!r} and its category scored "
                f"{lighthouse.get(category) if category else 'nothing'}"
            )
        lists[name] = None if null else _ids(failing[name], f"page {path}: failing.{name}")
    app, app_error = page["best_practices_app"], page.get("best_practices_app_error")
    if app is not None and (lighthouse["best_practices"] is None or app_error is not None):
        raise ValueError(f"page {path}: best_practices_app {app} beside a null category or error")
    return PageMeasure(
        path,
        lighthouse,
        axe,
        axe_nodes={k: int(nodes[k]) for k in AXE_IMPACTS},
        failing=lists,
        errored={k: _ids(errored[k], f"page {path}: errored.{k}") for k in ERRORED_LISTS},
        best_practices_app=app,
        best_practices_app_error=app_error,
    )


_PARAMETER_MARKS = (":", "{", "*", "[")


def measurable_pages(routes: Sequence[str]) -> tuple[str, ...]:
    """The declared routes a page can be loaded at as is: those with no parameter (``/runs/:id``,
    ``/runs/{id}``, ``/runs/[id]``) or wildcard. In the order declared, each once."""
    return tuple(
        dict.fromkeys(
            r for r in routes if r.startswith("/") and not any(m in r for m in _PARAMETER_MARKS)
        )
    )
