"""An increment's acceptance, executed (SIP-0109 §8.1–§8.4; #1707).

Step 3 built the trees (``evaluator_trees``) and step 4 the decisions over runner results
(``acceptance``). This runs one through the other, on the stack's own test runner:

- **each new criterion** is frozen into its bundle from the candidate — its test file, the
  test-surface files it imports, the stack's test configuration — and that bundle is run **twice,
  alone**: on the accepted tree's product code (the baseline-evaluator overlay, for this one
  criterion) and on the candidate's. ``discrimination`` reads the two runs. Alone, because one
  file's collection error abandons a whole pytest session (step 4's finding);
- **each frozen criterion's** stored bundle is run alone on the candidate's product code (the
  candidate-verifier overlay); a missing bundle is never run and never passes;
- **each declared route** is read from the rendered test ids the caller collected (the browser
  pass); a page never read is blocked.

The runner is the caller's: the stack's (``run_fullstack_tests``, ``run_node_tests``), so nothing
here knows a stack. Nothing here writes a tree.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass

from squadops.campaigns.acceptance import (
    Discrimination,
    DiscriminationReason,
    FrozenResult,
    Held,
    IncrementAcceptance,
    RouteResult,
    TreeRun,
    accumulated_acceptance,
    discrimination,
    increment_acceptance,
    route_rendering,
)
from squadops.campaigns.evaluator_trees import (
    BundleIncomplete,
    FileTree,
    Overlay,
    TestSurface,
    VerifierBundle,
    candidate_verifier_overlay,
    freeze_bundle,
)

#: The stack's test runner: ``(source_files, test_files) -> RunTestsResult``.
Runner = Callable[[list[dict[str, str]], list[dict[str, str]]], Awaitable[object]]


@dataclass(frozen=True)
class NewCriterion:
    criterion_id: str
    #: The criterion's own test file, in the candidate tree.
    test_path: str


@dataclass(frozen=True)
class FrozenCriterion:
    criterion_id: str
    test_path: str
    #: Its verifier bundle; ``None`` when the bundle is missing or unreadable.
    bundle: VerifierBundle | None


@dataclass(frozen=True)
class IncrementEvaluation:
    acceptance: IncrementAcceptance
    discriminations: tuple[Discrimination, ...]
    frozen: tuple[FrozenResult, ...]
    routes: tuple[RouteResult, ...]
    #: The bundles the new criteria, and the replaced verifiers, were frozen into: what a
    #: promotion freezes for later increments (§8.1).
    new_bundles: Mapping[str, VerifierBundle]


def _runner_files(overlay: Overlay, surface: TestSurface) -> tuple[list[dict], list[dict]]:
    source, tests = [], []
    for path, content in overlay.tree.files:
        entry = {"path": path, "content": content.decode("utf-8")}
        (tests if surface.is_test(path) else source).append(entry)
    return source, tests


async def _run(overlay: Overlay, surface: TestSurface, run: Runner) -> TreeRun:
    return TreeRun.from_runner(await run(*_runner_files(overlay, surface)))


async def evaluate_increment(
    *,
    increment_id: str,
    accepted: FileTree,
    candidate: FileTree,
    surface: TestSurface,
    new: Iterable[NewCriterion],
    frozen: Iterable[FrozenCriterion],
    declared_routes: Mapping[str, tuple[str, ...]],
    rendered: Mapping[str, frozenset[str] | None],
    run: Runner,
    invocation: Iterable[str],
    retired: Iterable[str],
    replaced: Iterable[NewCriterion] = (),
) -> IncrementEvaluation:
    """The increment's acceptance (§8): discrimination, accumulated acceptance, rendering.

    ``replaced`` is each frozen criterion whose verifier the change request replaces, at its own
    test file (§8.1): the old bundle is retired, and the new one is frozen from the candidate and
    run there as a frozen criterion is — it must pass, and nothing discriminates it."""
    invocation = tuple(invocation)
    discriminations, bundles = [], {}
    for criterion in new:
        try:
            bundle = freeze_bundle(
                criterion.criterion_id, candidate, criterion.test_path, surface, invocation
            )
        except BundleIncomplete:
            discriminations.append(
                Discrimination(criterion.criterion_id, False, DiscriminationReason.NOT_RUN)
            )
            continue
        bundles[criterion.criterion_id] = bundle
        on_baseline = await _run(
            candidate_verifier_overlay(accepted, bundle, surface), surface, run
        )
        on_candidate = await _run(
            candidate_verifier_overlay(candidate, bundle, surface), surface, run
        )
        discriminations.append(
            discrimination(criterion.criterion_id, criterion.test_path, on_baseline, on_candidate)
        )

    # §8.1: a criterion the change request retires (or whose verifier it replaces) is no longer
    # frozen, and is not run.
    retired = frozenset(retired)
    frozen = [c for c in frozen if c.criterion_id not in retired]
    runs = {}
    for criterion in frozen:
        if criterion.bundle is not None:
            runs[criterion.criterion_id] = await _run(
                candidate_verifier_overlay(candidate, criterion.bundle, surface), surface, run
            )
    held_by = {
        c.criterion_id: (c.bundle.address if c.bundle else None, c.test_path) for c in frozen
    }
    # §8.1: "the old bundle is retired and the new one frozen." A replacement the candidate does
    # not carry whole has no bundle, and is blocked like a missing one.
    for criterion in replaced:
        try:
            bundle = freeze_bundle(
                criterion.criterion_id, candidate, criterion.test_path, surface, invocation
            )
        except BundleIncomplete:
            held_by[criterion.criterion_id] = (None, criterion.test_path)
            continue
        bundles[criterion.criterion_id] = bundle
        held_by[criterion.criterion_id] = (bundle.address, criterion.test_path)
        runs[criterion.criterion_id] = await _run(
            candidate_verifier_overlay(candidate, bundle, surface), surface, run
        )
    frozen_results = accumulated_acceptance(increment_id, candidate.identity, held_by, runs)
    frozen_results = _changed_verifiers_blocked(frozen_results, frozen, candidate)
    routes = route_rendering(declared_routes, rendered)
    return IncrementEvaluation(
        acceptance=increment_acceptance(tuple(discriminations), frozen_results, routes),
        discriminations=tuple(discriminations),
        frozen=frozen_results,
        routes=routes,
        new_bundles=bundles,
    )


def _changed_verifiers_blocked(
    results: tuple[FrozenResult, ...], frozen: list[FrozenCriterion], candidate: FileTree
) -> tuple[FrozenResult, ...]:
    """§8.1, §19 item 7: a frozen criterion's test file changed in the candidate, without a
    ``retires`` entry, blocks acceptance. Its bundle still runs as frozen — the candidate's
    copy is never what is judged — but a candidate that rewrote a verifier nobody ruled on is
    not accepted on it."""
    changed = {
        c.criterion_id
        for c in frozen
        if c.bundle is not None
        and candidate.get(c.test_path) is not None
        and candidate.get(c.test_path) != c.bundle.files.get(c.test_path)
    }
    return tuple(
        dataclasses.replace(
            r,
            held=Held.BLOCKED_UNVERIFIED,
            detail="its test file changed in the candidate without a retires entry (§8.1)",
        )
        if r.criterion_id in changed
        else r
        for r in results
    )


def evaluation_document(
    evaluation: IncrementEvaluation,
    *,
    increment_id: str,
    accepted: FileTree,
    candidate: FileTree,
    new: Iterable[NewCriterion],
    retired: Iterable[str],
    replaced: Iterable[NewCriterion] = (),
) -> dict:
    """The evaluation as plain data, for the ``increment_evaluation`` artifact the completion hook
    reads (§8.4: every result keyed, the bundles a promotion freezes carried whole)."""
    acceptance = evaluation.acceptance
    replaced = tuple(replaced)
    test_paths = {c.criterion_id: c.test_path for c in (*new, *replaced)}
    return {
        "increment_id": increment_id,
        "accepted_tree": accepted.identity,
        "candidate_tree": candidate.identity,
        "verdict": str(acceptance.verdict),
        "unmet": list(acceptance.unmet),
        "blocked": list(acceptance.blocked),
        "discriminations": [
            {
                "criterion_id": d.criterion_id,
                "met": d.met,
                "reason": str(d.reason),
                "discriminating": list(d.discriminating),
            }
            for d in evaluation.discriminations
        ],
        "frozen": [
            {
                "criterion_id": f.criterion_id,
                "bundle_address": f.bundle_address,
                "held": str(f.held),
                "detail": f.detail,
            }
            for f in evaluation.frozen
        ],
        "routes": [
            {
                "path": r.path,
                "held": str(r.held),
                "missing": list(r.missing),
                "not_shown": list(r.not_shown),
            }
            for r in evaluation.routes
        ],
        # §8.1: the criteria this increment retires — dropped from the frozen set at promotion.
        "retired": sorted(retired),
        # §8.1: of those, the criteria whose verifier was replaced — their new bundles are in
        # ``new_bundles``, frozen at promotion in place of the retired ones.
        "replaced": sorted(c.criterion_id for c in replaced),
        "new_bundles": {
            criterion_id: {
                "address": bundle.address,
                "test_path": test_paths[criterion_id],
                "invocation": list(bundle.invocation),
                "files": {
                    path: content.decode("utf-8", errors="replace")
                    for path, content in bundle.files.files
                },
            }
            for criterion_id, bundle in evaluation.new_bundles.items()
        },
    }


def frozen_criteria_from(
    pinned: Iterable[Mapping], bundles: Mapping[str, Mapping]
) -> tuple[FrozenCriterion, ...]:
    """The frozen criteria an increment's launch pinned (§8.1), each with its stored bundle
    rebuilt. A bundle that is missing, unreadable, or whose content no longer hashes to the
    address it was frozen under is ``None``: never run, and ``blocked_unverified`` (SIP-0096)."""
    frozen = []
    for pin in pinned:
        criterion_id = str(pin["criterion_id"])
        stored = bundles.get(criterion_id)
        bundle = None
        if stored is not None:
            try:
                rebuilt = VerifierBundle(
                    criterion_id,
                    FileTree.of(dict(stored["files"])),
                    tuple(str(a) for a in stored["invocation"]),
                )
            except (KeyError, TypeError):
                rebuilt = None
            if rebuilt is not None and rebuilt.address == pin.get("bundle_address"):
                bundle = rebuilt
        frozen.append(FrozenCriterion(criterion_id, str(pin.get("test_path") or ""), bundle))
    return tuple(frozen)
