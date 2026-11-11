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

On a repository-backed product's own runner (SIP-0109 §24bv point 3), the same two decisions
read each run by the runner's test-id reader (``squadops.sandbox.findings``) instead of the
stack's rows: ``discrimination_on_runner`` and ``held_on_runner``. A runner with no test-id reader
reads no criterion as discriminating (§24ci (a)).

A scenario criterion (SIP-0117 R3.7, #3044) is read from its operation's assertion records
instead: ``discrimination_on_scenario`` and ``held_on_scenario``. A reading counts only for the
frozen digest and the revision being judged (#3053).
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

from squadops.remote_execution.models import (
    AssertionOutcome,
    OperationStatus,
    ReadingSide,
    Scenario,
)
from squadops.remote_execution.scenario import BaselineVerdict, baseline_verdict

if TYPE_CHECKING:
    from squadops.sandbox.findings import FindingsReading


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
    #: §24ci (a): on a product's runner that names no test one by one, discrimination is unread.
    NO_TEST_ID_READER = "no_test_id_reader"


#: The reasons a criterion's discrimination couldn't be read at all: blocked, never unmet.
_UNREAD = (DiscriminationReason.NOT_RUN, DiscriminationReason.NO_TEST_ID_READER)


@dataclass(frozen=True)
class Discrimination:
    criterion_id: str
    met: bool
    reason: DiscriminationReason
    #: The titles that fail on the baseline as assertions and pass on the candidate.
    discriminating: tuple[str, ...] = ()
    #: #2849: on ``no_baseline_failure``, whether the file's tests passed on the candidate too, so
    #: the criterion describes behaviour the change keeps (a preservation check), not one it broke.
    candidate_passed: bool = False
    #: Why, in words, when it isn't met: which reading was unread and why (#3053).
    detail: str = ""


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
        return Discrimination(
            criterion_id,
            False,
            DiscriminationReason.NO_BASELINE_FAILURE,
            candidate_passed=not candidate.failed_titles(test_path),
        )
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
# §8.2 on a repository-backed product's own runner (SIP-0109 §24bv point 3, §24ci (a))
# =============================================================================

#: §24ci (a): the exception classes that say a test failed before reaching what it asserts, by
#: each test-id reader. The import family, and what the sample applications' stacks read as a
#: suite's own defect (``test_runner._OWN_FRAME_SHAPES``: NameError, ReferenceError). Every
#: ``ERROR`` key (a setup, teardown or collection failure, a suite that never loaded) is setup
#: whatever its class, and a failure whose class wasn't read is never read as the test's own.
SETUP_CLASSES: Mapping[str, frozenset[str]] = {
    "pytest": frozenset({"ImportError", "ModuleNotFoundError", "SyntaxError", "NameError"}),
    "vitest": frozenset({"SyntaxError", "ReferenceError"}),
}


def _intended(reading: FindingsReading) -> set[str]:
    """The failing keys of ``reading`` that are a test's own failure: a ``FAILED`` key whose
    class was read and is no setup class."""
    # deferred (pair): squadops.sandbox imports this package at load (its API's seed plan)
    from squadops.sandbox.findings import FAILED

    setup = SETUP_CLASSES.get(reading.reader, frozenset())
    return {
        key
        for key in reading.counts
        if key.startswith(f"{FAILED} ")
        and reading.classes.get(key) is not None
        and reading.classes[key] not in setup
    }


def discrimination_on_runner(
    criterion_id: str,
    test_ids: str | None,
    baseline: FindingsReading | None,
    candidate: FindingsReading | None,
) -> Discrimination:
    """§8.2 for one new criterion on a product's own runner: its test file run alone on the
    baseline-evaluator overlay and on the candidate, each read by ``test_ids``, the runner's
    test-id reader in the derived profile (H.6).

    - **No test-id reader:** unread, and so never accepted as discriminating (§24ci (a)). A
      whole-file reading would count a file that fails to import on the baseline.
    - **A run unread** (none, unreadable, another reader, or a candidate that ran fewer tests):
      not run.
    - **A candidate run that doesn't show its tests ran** (SIP-0096: only executed-and-passed
      credits; SIP-0109 §24cl item 13): a test it skipped, or one expected to fail, isn't failing,
      and isn't passing either. A reading that names no pass count shows nothing: not run.
    - **Otherwise** it discriminates when a test fails on the baseline for the intended reason
      (``_intended``) and doesn't fail on the candidate."""
    # deferred (pair): squadops.sandbox imports this package at load (its API's seed plan)
    from squadops.sandbox.findings import FAILED, comparable

    if test_ids is None:
        return Discrimination(criterion_id, False, DiscriminationReason.NO_TEST_ID_READER)
    if (
        baseline is None
        or candidate is None
        or baseline.reader != test_ids
        or comparable(baseline, candidate) is not None
        or not ran_every_test(candidate)
    ):
        return Discrimination(criterion_id, False, DiscriminationReason.NOT_RUN)
    if not baseline.counts:
        return Discrimination(
            criterion_id,
            False,
            DiscriminationReason.NO_BASELINE_FAILURE,
            candidate_passed=not candidate.counts,
        )
    intended = _intended(baseline)
    if not intended:
        return Discrimination(criterion_id, False, DiscriminationReason.ONLY_SETUP_FAILURES)
    passing = intended - set(candidate.counts)
    if not passing:
        return Discrimination(criterion_id, False, DiscriminationReason.FAILS_ON_CANDIDATE)
    tests = tuple(sorted(key.removeprefix(f"{FAILED} ") for key in passing))
    return Discrimination(criterion_id, True, DiscriminationReason.DISCRIMINATES, tests)


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


def ran_every_test(reading: FindingsReading) -> bool:
    """Whether every test a readable run collected ran to an outcome: it passed or it failed
    (SIP-0096: only executed-and-passed credits; §24cl item 13). A skipped test, or one expected to
    fail, did neither. A reading that names no pass count can't show it."""
    if reading.passed is None or reading.collected is None:
        return False
    return reading.passed + sum(reading.counts.values()) >= reading.collected


#: §24cl item 13: why a frozen criterion read by exit status alone holds nothing.
NO_READER_EXIT_ZERO = (
    "its test file exited 0, and its runner names no test, so nothing shows a test ran "
    "(read whole: no test-id reader)"
)


def held_on_runner(
    address: str | None,
    test_ids: str | None,
    exit_code: int | None,
    reading: FindingsReading | None,
) -> tuple[Held, str]:
    """§8.1 for one frozen criterion on a product's own runner: its bundle's test file run alone
    on the candidate-verifier overlay. It holds only on evidence that its tests ran and passed
    (SIP-0096: only executed-and-passed credits; §24cl item 13).

    - **With a test-id reader,** read by it. Any failing test breaks it. Unread, no test run, or a
      test that didn't run to a pass (skipped, or expected to fail) is blocked.
    - **Without one,** by the file's exit status (H.6's ``per_test_reading``). A non-zero exit
      breaks it: the frozen test ran against the candidate's code and didn't pass. Exit 0 is
      blocked, never held: unittest's discovery exits 0 when every test was skipped, so a whole-file
      pass is no evidence that a test ran. That is §24ci (a)'s rule for discrimination, applied
      to holding."""
    if address is None:
        return Held.BLOCKED_UNVERIFIED, "the verifier bundle is missing"
    if exit_code is None:
        return Held.BLOCKED_UNVERIFIED, "the bundle never executed"
    if test_ids is None:
        if exit_code == 0:
            return Held.BLOCKED_UNVERIFIED, NO_READER_EXIT_ZERO
        return Held.BROKEN, f"its test file exited {exit_code} (read whole: no test-id reader)"
    if reading is None or not reading.readable or reading.reader != test_ids:
        why = reading.reason if reading is not None and reading.reason else "no reading"
        return Held.BLOCKED_UNVERIFIED, f"its run is unread: {why}"
    if reading.counts:
        return Held.BROKEN, ", ".join(sorted(k.partition(" ")[2] for k in reading.counts))
    if not reading.collected:
        return Held.BLOCKED_UNVERIFIED, "the runner ran none of its tests"
    if not ran_every_test(reading):
        if reading.passed is None:
            return Held.BLOCKED_UNVERIFIED, "its reading doesn't say how many of its tests passed"
        missing = reading.collected - reading.passed
        return (
            Held.BLOCKED_UNVERIFIED,
            f"{missing} of its {reading.collected} tests didn't run to a pass (skipped, or "
            "expected to fail)",
        )
    return Held.HELD, ""


# =============================================================================
# §8.1/§8.2 on a frozen scenario's assertion records (SIP-0117 R3.7; #3053)
# =============================================================================


def credited_outcomes(
    reading: Mapping | None, frozen: Scenario, revision: str, side: ReadingSide
) -> tuple[dict[str, AssertionOutcome] | None, str]:
    """Each declared assertion's outcome in ``reading`` (a ``remote_operation_assertions``
    document), or ``None`` and why it can't be credited.

    A reading counts only for the scenario that was frozen, on the revision being judged and the
    side it is read for (#3044 §4); ``revision`` is ``scenario.staged_revision`` over the files
    the judged tree put on the request. One for another digest or revision counts for nothing: an
    edit after freezing, or a run of an older tree, is never this tree's evidence. A declared
    assertion with no record is ``missing``, never a pass.
    """
    if reading is None:
        return None, f"no {side} reading"
    if reading.get("side") != side:
        return None, f"the reading is the {reading.get('side') or 'unnamed'} side's, not the {side}"
    scenario = reading.get("scenario") or {}
    if scenario.get("digest") != frozen.digest:
        return None, (
            f"the reading ran scenario {scenario.get('digest') or 'with no digest'}, and the "
            f"frozen one is {frozen.digest}"
        )
    if reading.get("source_revision") != revision:
        return None, (
            f"the reading is of revision {reading.get('source_revision') or 'unnamed'}, and the "
            f"{side} judged is {revision}"
        )
    status = reading.get("status")
    if status != OperationStatus.COMPLETED:
        why = reading.get("reason") or "no reason given"
        return None, f"the operation is {status or 'unread'}: {why}"
    # What was declared is the frozen scenario's: the digest matched, so it is the reading's too.
    declared = frozen.assertions
    if frozen.named_assertion not in declared:
        return None, f"the frozen scenario declares no assertion {frozen.named_assertion!r}"
    recorded: dict[str, AssertionOutcome] = {}
    for record in reading.get("assertions") or ():
        try:
            recorded[str(record.get("assertion_id"))] = AssertionOutcome(record.get("outcome"))
        except ValueError:
            return None, f"a record's outcome {record.get('outcome')!r} is no assertion outcome"
    return {a: recorded.get(a, AssertionOutcome.MISSING) for a in declared}, ""


def _unexecuted(outcomes: Mapping[str, AssertionOutcome]) -> list[str]:
    return [f"{a} ({o})" for a, o in sorted(outcomes.items()) if not o.executed]


def _failed(outcomes: Mapping[str, AssertionOutcome]) -> list[str]:
    return sorted(a for a, o in outcomes.items() if o is AssertionOutcome.FAILED)


def discrimination_on_scenario(
    criterion_id: str,
    frozen: Scenario,
    baseline_revision: str,
    candidate_revision: str,
    baseline: Mapping | None,
    candidate: Mapping | None,
) -> Discrimination:
    """§8.2 for a new scenario criterion: its named assertion executed and failed on the
    baseline, with every precondition passing, and every declared assertion executed and passed
    on the candidate. Each reading is credited only for the frozen digest and its own side's
    revision; anything unread is ``not_run``, never unmet."""
    outcomes, why = credited_outcomes(baseline, frozen, baseline_revision, ReadingSide.BASELINE)
    if outcomes is None:
        return Discrimination(criterion_id, False, DiscriminationReason.NOT_RUN, detail=why)
    verdict, why = baseline_verdict(outcomes, frozen.named_assertion)
    if verdict is BaselineVerdict.BLOCKED:
        return Discrimination(criterion_id, False, DiscriminationReason.NOT_RUN, detail=why)
    if verdict is BaselineVerdict.PRECONDITION_FAILS:
        return Discrimination(
            criterion_id, False, DiscriminationReason.ONLY_SETUP_FAILURES, detail=why
        )
    on_candidate, candidate_why = credited_outcomes(
        candidate, frozen, candidate_revision, ReadingSide.CANDIDATE
    )
    if verdict is BaselineVerdict.PASSES_ON_BASELINE:
        return Discrimination(
            criterion_id,
            False,
            DiscriminationReason.NO_BASELINE_FAILURE,
            candidate_passed=on_candidate is not None
            and all(o is AssertionOutcome.PASSED for o in on_candidate.values()),
            detail=why,
        )
    if on_candidate is None:
        return Discrimination(
            criterion_id, False, DiscriminationReason.NOT_RUN, detail=candidate_why
        )
    failed = _failed(on_candidate)
    if failed:
        return Discrimination(
            criterion_id,
            False,
            DiscriminationReason.FAILS_ON_CANDIDATE,
            detail="fail on the candidate: " + ", ".join(failed),
        )
    unexecuted = _unexecuted(on_candidate)
    if unexecuted:
        return Discrimination(
            criterion_id,
            False,
            DiscriminationReason.NOT_RUN,
            detail="didn't execute on the candidate: " + ", ".join(unexecuted),
        )
    return Discrimination(
        criterion_id, True, DiscriminationReason.DISCRIMINATES, (frozen.named_assertion,)
    )


def held_on_scenario(frozen: Scenario, revision: str, reading: Mapping | None) -> tuple[Held, str]:
    """§8.1 for an earlier increment's scenario, replayed on this candidate: it holds when every
    assertion it declares executed and passed on this revision. A failure breaks it, a
    precondition's as much as the named one's (the world it relied on is gone). An unread
    reading, or one with an assertion that didn't execute, is blocked, never held."""
    outcomes, why = credited_outcomes(reading, frozen, revision, ReadingSide.CANDIDATE)
    if outcomes is None:
        return Held.BLOCKED_UNVERIFIED, why
    failed = _failed(outcomes)
    if failed:
        return Held.BROKEN, ", ".join(failed)
    unexecuted = _unexecuted(outcomes)
    if unexecuted:
        return Held.BLOCKED_UNVERIFIED, "didn't execute: " + ", ".join(unexecuted)
    return Held.HELD, ""


# =============================================================================
# §8.3: every declared route renders
# =============================================================================


@dataclass(frozen=True)
class RouteResult:
    path: str
    held: Held
    #: The root anchor, when the page did not render it.
    missing: tuple[str, ...] = ()
    #: The view's other declared anchors this reading did not show — state-dependent (a list's
    #: rows on an empty list, an error banner): recorded, not judged (§24p).
    not_shown: tuple[str, ...] = ()
    #: A parameterized route no seed brings into being (#2398): blocked because nothing could
    #: reach its page, not because a page was read and failed.
    unseeded: bool = False
    #: Why a blocked route wasn't read, when its reader says (SIP-0109 §24co: a product's routes,
    #: read in the sandbox). Empty for a sample application's, whose reasons are logged.
    detail: str = ""


def route_rendering(
    declared: Mapping[str, tuple[str, ...]],
    rendered: Mapping[str, frozenset[str] | None],
    *,
    unseeded: Collection[str],
) -> tuple[RouteResult, ...]:
    """Each declared route against the test ids found on its page (§8.3): it renders when its
    view's ROOT anchor does — the first declared id, stamped on the view's container (#659).

    Not every declared id: a view's anchors include states that exclude each other (a list's
    rows and its empty state; a form and its error), so one reading of a correct page never shows
    them all — the first live reading failed a correct app that way (§24p). The rest are recorded
    as ``not_shown``. ``None`` is a page that was never rendered or read: blocked, never a pass.
    ``unseeded`` names the routes of those that nothing could reach (``unseeded_routes``)."""
    results = []
    for path, testids in sorted(declared.items()):
        seen = rendered.get(path)
        if seen is None:
            results.append(RouteResult(path, Held.BLOCKED_UNVERIFIED, unseeded=path in unseeded))
            continue
        root, rest = (testids[0], testids[1:]) if testids else (None, ())
        missing = (root,) if root is not None and root not in seen else ()
        not_shown = tuple(t for t in rest if t not in seen)
        results.append(RouteResult(path, Held.BROKEN if missing else Held.HELD, missing, not_shown))
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
    #: #2849: new criteria the accepted tree already met and the candidate still meets, kept as
    #: preservation checks beside criteria that discriminate, rather than rejecting the increment.
    preserved: tuple[str, ...] = field(default_factory=tuple)


def preserved_criteria(discriminations: tuple[Discrimination, ...]) -> tuple[str, ...]:
    """#2849 (SIP-0109 §24ct): the new criteria an increment keeps as preservation checks. Each
    passed on the accepted tree and on the candidate, and at least one other new criterion
    discriminates, so the increment still shows the change it was proposed for. When none
    discriminates, nothing is kept: the increment is rejected, and row 16 tells the next proposal
    which criteria were already met."""
    if not any(d.met for d in discriminations):
        return ()
    return tuple(
        d.criterion_id
        for d in discriminations
        if d.reason is DiscriminationReason.NO_BASELINE_FAILURE and d.candidate_passed
    )


def increment_acceptance(
    discriminations: tuple[Discrimination, ...],
    frozen: tuple[FrozenResult, ...],
    routes: tuple[RouteResult, ...],
) -> IncrementAcceptance:
    """Accepted only when every new criterion discriminates, every frozen criterion held and every
    route rendered. Anything unread blocks: ``blocked_unverified`` never reads as accepted
    (SIP-0096), and it outranks a failure only when nothing failed."""
    preserved = preserved_criteria(discriminations)
    unmet = [
        f"criterion {d.criterion_id}: {d.reason}" + (f" ({d.detail})" if d.detail else "")
        for d in discriminations
        if not d.met and d.reason not in _UNREAD and d.criterion_id not in preserved
    ]
    blocked = [
        f"criterion {d.criterion_id}: "
        + ("not run" if d.reason is DiscriminationReason.NOT_RUN else "its runner names no test")
        + (f": {d.detail}" if d.detail else "")
        for d in discriminations
        if d.reason in _UNREAD
    ]
    for r in frozen:
        if r.held is Held.BROKEN:
            unmet.append(f"frozen {r.criterion_id}: {r.detail}")
        elif r.held is Held.BLOCKED_UNVERIFIED:
            blocked.append(f"frozen {r.criterion_id}: {r.detail}")
    for route in routes:
        if route.held is Held.BROKEN:
            unmet.append(f"route {route.path}: missing {', '.join(route.missing)}")
        elif route.unseeded:
            blocked.append(f"route {route.path}: not read, no seed brings its page into being")
        elif route.held is Held.BLOCKED_UNVERIFIED:
            why = f": {route.detail}" if route.detail else ""
            blocked.append(f"route {route.path}: not rendered{why}")
    if unmet:
        return IncrementAcceptance(IncrementVerdict.REJECTED, tuple(unmet), tuple(blocked))
    if blocked:
        return IncrementAcceptance(
            IncrementVerdict.BLOCKED_UNVERIFIED, (), tuple(blocked), preserved=preserved
        )
    return IncrementAcceptance(IncrementVerdict.ACCEPTED, preserved=preserved)
