"""An increment's acceptance: discrimination, accumulated acceptance, route rendering (SIP-0109
§8.1–§8.3; #1707, #1796).

Pure decisions over runner results, read from the test runner's own rows
(``squadops.capabilities.handlers.test_runner``: ``{file, title, messages, line, suite_level}``)
— no second classifier of what a failure means:
- **a test fails for the intended reason** when its row is a test's own assertion: not a
  suite-level row (collection, transform or import death), and not a defect the suite raised in
  its own frame before any application code ran (``suite_defects``). New behaviour is tested
  through the running app's surface, so a missing module is setup, never discrimination (§8.2);
- **a new criterion is met** when at least one test in its own file fails on the baseline-
  evaluator overlay for the intended reason and passes on the candidate (§8.2);
- **a frozen criterion holds** when its bundle ran on the candidate-verifier overlay and no test
  of it failed. A missing bundle, or a run that never executed, is ``blocked_unverified``, never a
  pass (§8.1);
- **a route renders** when every test id its view declares appears on the booted candidate (§8.3).

The increment is accepted only when everything holds; blocked when anything could not be read;
rejected otherwise.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum


@dataclass(frozen=True)
class TreeRun:
    """One runner execution on one tree, in the runner's own terms."""

    executed: bool
    failures: tuple[dict, ...] = ()
    suite_defects: tuple[dict, ...] = ()
    uncollected: tuple[str, ...] = ()

    @classmethod
    def from_runner(cls, result) -> TreeRun:
        """From a ``RunTestsResult``."""
        return cls(
            executed=bool(result.executed),
            failures=tuple(result.test_failures),
            suite_defects=tuple(result.suite_defects),
            uncollected=tuple(getattr(result, "uncollected_test_files", ()) or ()),
        )

    def failed_titles(self, path: str) -> set[str]:
        return {str(r.get("title", "")) for r in self.failures if r.get("file") == path}

    def suite_died(self, path: str) -> bool:
        return any(r.get("file") == path and r.get("suite_level") for r in self.failures)

    def collected(self, path: str) -> bool:
        return self.executed and path not in self.uncollected and not self.suite_died(path)


def is_behavioural(row: Mapping, suite_defects: tuple[dict, ...]) -> bool:
    """A test's own assertion failure: neither a suite-level death nor a defect the suite raised
    in its own frame (§8.2)."""
    if row.get("suite_level"):
        return False
    key = (row.get("file"), row.get("title"))
    return not any((d.get("file"), d.get("title")) == key for d in suite_defects)


# =============================================================================
# §8.2: a new criterion's discrimination
# =============================================================================


class DiscriminationReason(StrEnum):
    DISCRIMINATES = "discriminates"
    NOT_RUN = "not_run"
    NO_BASELINE_FAILURE = "no_baseline_failure"
    ONLY_SETUP_FAILURES = "only_setup_failures"
    FAILS_ON_CANDIDATE = "fails_on_candidate"


@dataclass(frozen=True)
class Discrimination:
    criterion_id: str
    met: bool
    reason: DiscriminationReason
    #: The titles that fail on the baseline as assertions and pass on the candidate.
    discriminating: tuple[str, ...] = ()


def discrimination(
    criterion_id: str, test_path: str, baseline: TreeRun, candidate: TreeRun
) -> Discrimination:
    """§8.2 for one new criterion, judged on its own file ``test_path`` (§8.1).

    ``baseline`` and ``candidate`` are runs of **that file alone** (§8.4: results are per
    criterion). Run together, one file's collection error abandons the whole pytest session, and
    every other criterion would read as never having failed — measured on the real runner while
    building this.
    """
    if not (
        baseline.collected(test_path) or baseline.suite_died(test_path)
    ) or not candidate.collected(test_path):
        return Discrimination(criterion_id, False, DiscriminationReason.NOT_RUN)
    rows = [r for r in baseline.failures if r.get("file") == test_path]
    if not rows:
        return Discrimination(criterion_id, False, DiscriminationReason.NO_BASELINE_FAILURE)
    behavioural = {
        str(r.get("title", "")) for r in rows if is_behavioural(r, baseline.suite_defects)
    }
    if not behavioural:
        return Discrimination(criterion_id, False, DiscriminationReason.ONLY_SETUP_FAILURES)
    passing = behavioural - candidate.failed_titles(test_path)
    if not passing:
        return Discrimination(criterion_id, False, DiscriminationReason.FAILS_ON_CANDIDATE)
    return Discrimination(
        criterion_id, True, DiscriminationReason.DISCRIMINATES, tuple(sorted(passing))
    )


# =============================================================================
# §8.1: accumulated acceptance of the frozen criteria
# =============================================================================


class Held(StrEnum):
    """Whether a frozen criterion (or a declared route) held on the candidate. Its own words, not
    the check vocabulary's ``passed``/``failed``: a criterion holds or breaks."""

    HELD = "held"
    BROKEN = "broken"
    BLOCKED_UNVERIFIED = "blocked_unverified"


@dataclass(frozen=True)
class FrozenResult:
    """Keyed by (increment, criterion, candidate identity, bundle address): recomputing it is
    idempotent (§8.4)."""

    increment_id: str
    criterion_id: str
    candidate_identity: str
    bundle_address: str | None
    held: Held
    detail: str = ""


def accumulated_acceptance(
    increment_id: str,
    candidate_identity: str,
    frozen: Mapping[str, tuple[str | None, str]],
    runs: Mapping[str, TreeRun | None],
) -> tuple[FrozenResult, ...]:
    """Each frozen criterion on the candidate-verifier overlay with its bundle.

    ``frozen`` maps a criterion id to (its bundle address, its test file); a ``None`` address is
    a bundle that is missing or unreadable. ``runs`` holds the bundle's run on the overlay.
    """
    results = []
    for criterion_id, (address, test_path) in sorted(frozen.items()):
        held, detail = _held(address, test_path, runs.get(criterion_id))
        results.append(
            FrozenResult(increment_id, criterion_id, candidate_identity, address, held, detail)
        )
    return tuple(results)


def _held(address: str | None, test_path: str, run: TreeRun | None) -> tuple[Held, str]:
    if address is None:
        return Held.BLOCKED_UNVERIFIED, "the verifier bundle is missing"
    if run is None or not run.executed:
        return Held.BLOCKED_UNVERIFIED, "the bundle never executed"
    if run.suite_died(test_path) or run.failed_titles(test_path):
        # The frozen test ran against the candidate's product code and did not pass: a broken
        # import of a module the candidate removed is a break, not a skip.
        failed = sorted(run.failed_titles(test_path) - {""}) or ["the suite itself"]
        return Held.BROKEN, ", ".join(failed)
    if test_path in run.uncollected:
        return Held.BLOCKED_UNVERIFIED, "the runner never collected it"
    return Held.HELD, ""


# =============================================================================
# §8.3: every declared route renders
# =============================================================================


@dataclass(frozen=True)
class RouteResult:
    path: str
    held: Held
    missing: tuple[str, ...] = ()


def route_rendering(
    declared: Mapping[str, tuple[str, ...]], rendered: Mapping[str, frozenset[str] | None]
) -> tuple[RouteResult, ...]:
    """Each declared route against the test ids found on its page. ``None`` is a page that was
    never rendered or read, which is blocked, never a pass."""
    results = []
    for path, testids in sorted(declared.items()):
        seen = rendered.get(path)
        if seen is None:
            results.append(RouteResult(path, Held.BLOCKED_UNVERIFIED))
            continue
        missing = tuple(t for t in testids if t not in seen)
        results.append(RouteResult(path, Held.BROKEN if missing else Held.HELD, missing))
    return tuple(results)


# =============================================================================
# The increment's verdict
# =============================================================================


class IncrementVerdict(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    BLOCKED_UNVERIFIED = "blocked_unverified"


@dataclass(frozen=True)
class IncrementAcceptance:
    verdict: IncrementVerdict
    unmet: tuple[str, ...] = field(default_factory=tuple)
    blocked: tuple[str, ...] = field(default_factory=tuple)


def increment_acceptance(
    discriminations: tuple[Discrimination, ...],
    frozen: tuple[FrozenResult, ...],
    routes: tuple[RouteResult, ...],
) -> IncrementAcceptance:
    """Accepted only when every new criterion discriminates, every frozen criterion held and every
    route rendered. Anything unread blocks: ``blocked_unverified`` never reads as accepted
    (SIP-0096), and it outranks a failure only when nothing failed."""
    unmet = [f"criterion {d.criterion_id}: {d.reason}" for d in discriminations if not d.met]
    blocked = [
        f"criterion {d.criterion_id}: not run"
        for d in discriminations
        if d.reason is DiscriminationReason.NOT_RUN
    ]
    unmet = [u for u in unmet if not u.endswith(DiscriminationReason.NOT_RUN)]
    for r in frozen:
        if r.held is Held.BROKEN:
            unmet.append(f"frozen {r.criterion_id}: {r.detail}")
        elif r.held is Held.BLOCKED_UNVERIFIED:
            blocked.append(f"frozen {r.criterion_id}: {r.detail}")
    for r in routes:
        if r.held is Held.BROKEN:
            unmet.append(f"route {r.path}: missing {', '.join(r.missing)}")
        elif r.held is Held.BLOCKED_UNVERIFIED:
            blocked.append(f"route {r.path}: not rendered")
    if unmet:
        return IncrementAcceptance(IncrementVerdict.REJECTED, tuple(unmet), tuple(blocked))
    if blocked:
        return IncrementAcceptance(IncrementVerdict.BLOCKED_UNVERIFIED, (), tuple(blocked))
    return IncrementAcceptance(IncrementVerdict.ACCEPTED)
