"""An increment's acceptance on a repository-backed product's own runner, in the sandbox (SIP-0109
§24cd point 6, §24bv point 3, §8.1–§8.4).

A sample application's increment is judged in the qa role's container, where its stack's runner
lives (``qa.evaluate_increment``). A repository-backed product's toolchain exists only in the
sandbox, where its declared commands run (SIP-0102 X-3a), so its increment is judged there,
runtime-side, at its delivery (§24cd point 6). The decisions are the same module's
(``acceptance``): only the runs differ.

- **The trees** are the accepted tree, the campaign branch's head as checked out, and the
  candidate, the head with the squad's changes on it (§24bv point 3). Each is given as the sandbox
  is given a tree: a checkout, and the changes on it.
- **Each overlay is a revision of its tree** (§24cd point 6). It is seeded in a workspace of its
  own as the tree's revision (the head's checkout, then the candidate's changes), and the overlay
  is cut on it as ``acceptance_assembly``: the tree's product files, without the tree's own test
  files, plus one criterion's bundle (``evaluator_trees.candidate_verifier_overlay``, §7.4). So
  the overlay's parent revision is exactly the tree it overlays, and the candidate's revision is
  the one delivery verified.
- **The product's test files** are what the derived profile classes as tests (contract 8's
  ``files.test`` and ``files.test_support``, matched on the whole path), and the criterion files
  the framework placed (§24cj). Every other tracked file is the product's (``ProductTestSurface``).
- **A criterion's bundle** is its placed test file, the test files it imports, the package markers
  its directories need, and its runner's support files (§24bv point 3: "frozen with the
  test-support files the profile names"). Its invocation is its runner's one-file argv, the file
  named in it (H.6's ``{path}`` and ``{name}``): frozen with it, and run as frozen (§8.1).
- **Each run** is that one file, on one overlay, as a check runs: in the configuration's working
  directory, after its install and build steps (H.6), read by the runner's test-id reader.
- **A new criterion** discriminates by ``discrimination_on_runner``: its file run alone on the
  baseline-evaluator overlay and on the candidate (§8.2). A runner with no test-id reader is
  never run for it, and the criterion is unread: blocked, never unmet (§24ci (a)).
- **A frozen criterion** holds by ``held_on_runner``: its bundle run alone on the candidate-verifier
  overlay (§8.1). ``frozen_on_runner`` is that half alone, which a rebase's verification calls
  with the rebased head as its tree (§24cd point 5).
- **A route** the profile names (§24bv point 3) is rendered on the candidate started from the
  product's declared start (``execution.product_routes``, §24co), and its result is handed in.
"""

from __future__ import annotations

import logging
import posixpath
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Any

from squadops.campaigns.acceptance import (
    Discrimination,
    DiscriminationReason,
    FrozenResult,
    RouteResult,
    discrimination_on_runner,
    held_on_runner,
    increment_acceptance,
)
from squadops.campaigns.acceptance_run import (
    FrozenCriterion,
    IncrementEvaluation,
    NewCriterion,
    changed_verifiers_blocked,
)
from squadops.campaigns.evaluator_trees import (
    BundleIncomplete,
    FileTree,
    Overlay,
    VerifierBundle,
    candidate_verifier_overlay,
    freeze_bundle,
)

if TYPE_CHECKING:
    from squadops.sandbox.findings import FindingsReading
    from squadops.sandbox.models import WorkspaceRevision

logger = logging.getLogger(__name__)

#: The two sides a criterion's file is run on (§8.2): the baseline-evaluator overlay, and the
#: candidate-verifier overlay.
BASELINE, CANDIDATE = "baseline", "candidate"


class CandidateNotDelivered(RuntimeError):
    """The candidate the sandbox cut isn't the one delivery verified: nothing is judged on it."""


# =============================================================================
# The product's test files, and a criterion's bundle
# =============================================================================


def _classed(path: str, glob: str) -> bool:
    """Contract 8's rule for ``files.test``: an ``fnmatch`` glob on the whole path. ``[`` is
    literal, as the change request's globs read it (#2512)."""
    return fnmatch(path, glob.replace("[", "[[]"))


@dataclass(frozen=True)
class ProductTestSurface:
    """Which of a product's files are its tests (§24bv point 3, contract 8): what the derived
    profile classes as a test or test-support file, and the criterion files the framework placed.
    ``config_files`` are one runner's support files, which its criteria's bundles are frozen with.
    The same ``is_test`` and ``config_files`` a stack's ``TestSurface`` answers, so the overlays
    and the bundle are ``evaluator_trees``' own."""

    __test__ = False  # not a pytest class

    globs: tuple[str, ...]
    placed: frozenset[str] = frozenset()
    config_files: tuple[str, ...] = ()

    @classmethod
    def of(cls, profile: Any, placed: Iterable[str], runner: Any = None) -> ProductTestSurface:
        return cls(
            globs=(*profile.test_files, *profile.test_support_files),
            placed=frozenset(placed),
            config_files=tuple(runner.support_files) if runner is not None else (),
        )

    def for_runner(self, runner: Any) -> ProductTestSurface:
        return ProductTestSurface(self.globs, self.placed, tuple(runner.support_files))

    def is_test(self, path: str) -> bool:
        return (
            path in self.placed
            or path in self.config_files
            or any(_classed(path, g) for g in self.globs)
        )


def single_file_argv(runner: Any, test_path: str) -> tuple[str, ...]:
    """The runner's one-file argv with ``test_path`` named in it (H.6): ``{path}`` is the file's
    repository-relative path, ``{name}`` its name. Raises ``ValueError`` for a runner that can't
    be scoped to one file, which placement never hosts a criterion on (§24cj item 5)."""
    if runner.single_file_argv is None:
        raise ValueError(f"{runner.runner} can't be run on one file (runner_not_scopable)")
    name = PurePosixPath(test_path).name
    return tuple(
        a.replace("{path}", test_path).replace("{name}", name) for a in runner.single_file_argv
    )


def _package_markers(test_path: str, tree: FileTree, surface: ProductTestSurface) -> dict:
    """The ``__init__.py`` of each directory a Python test file lies under, where the tree has one
    and it is a test file (§8.1: what the test requires to import as it was written). Without it a
    test under a package directory imports as a top-level module, and the product it tests may not
    be on its path. A marker the surface leaves to the product stays in every overlay anyway."""
    if not test_path.endswith(".py"):
        return {}
    markers = {}
    directory = posixpath.dirname(test_path)
    while directory:
        marker = f"{directory}/__init__.py"
        content = tree.get(marker)
        if content is not None and surface.is_test(marker):
            markers[marker] = content
        directory = posixpath.dirname(directory)
    return markers


def freeze_product_bundle(
    criterion_id: str, tree: FileTree, test_path: str, surface: ProductTestSurface, runner: Any
) -> VerifierBundle:
    """A criterion's bundle on a product (§8.1, §24bv point 3), frozen from ``tree``: its test
    file and the test files it imports (``evaluator_trees.freeze_bundle``), the package markers it
    needs, and ``runner``'s support files, with the runner's one-file argv as its invocation.

    Raises:
        BundleIncomplete: The test file, or a test file it imports, isn't in ``tree``.
        ValueError: ``runner`` can't be run on one file.
    """
    surface = surface.for_runner(runner)
    argv = single_file_argv(runner, test_path)
    bundle = freeze_bundle(criterion_id, tree, test_path, surface, argv)
    markers = _package_markers(test_path, tree, surface)
    if not markers:
        return bundle
    return VerifierBundle(
        criterion_id, FileTree.of({**bundle.files.as_dict(), **markers}), bundle.invocation
    )


# =============================================================================
# The trees, and one run on one overlay
# =============================================================================


@dataclass(frozen=True)
class SandboxTree:
    """A tree as the sandbox is given it: a commit's checkout (its files and executable bits),
    and the squad's changes on it, for a candidate (§24bv point 3). The accepted tree, the
    branch's head, has none."""

    files: Mapping[str, bytes]
    executable: frozenset[str] = frozenset()
    changes: Mapping[str, bytes] = field(default_factory=dict)

    @property
    def content(self) -> dict[str, bytes]:
        return {**self.files, **self.changes}

    @property
    def file_tree(self) -> FileTree:
        return FileTree.of(self.content)


@dataclass(frozen=True)
class RunnerSetup:
    """Where a runner's argvs run (H.6): as a check does, in the configuration's working
    directory, after its install and build steps."""

    working_directory: str = "."
    setup: tuple[tuple[str, ...], ...] = ()

    @classmethod
    def of(cls, commands: Any) -> RunnerSetup:
        return cls(str(commands.working_directory), tuple(commands.check_setup))


@dataclass(frozen=True)
class OverlayRun:
    """One bundle's run on one overlay: what §8.4 keys a result by (the criterion, its side and
    the overlay's identity), the sandbox revision it ran on, and how it ended."""

    criterion_id: str
    side: str
    overlay_identity: str
    revision_id: str | None
    argv: tuple[str, ...]
    reader: str | None
    exit_code: int | None
    reading: FindingsReading | None
    #: Why the command never reached an exit, when it didn't: the sandbox's own words.
    unexecuted: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "criterion_id": self.criterion_id,
            "side": self.side,
            "overlay_identity": self.overlay_identity,
            "revision_id": self.revision_id,
            "argv": list(self.argv),
            "reader": self.reader,
            "exit_code": self.exit_code,
            "unexecuted": self.unexecuted,
            "reading": self.reading.as_dict() if self.reading is not None else None,
        }


def _stages(tree: SandboxTree, overlay: Overlay) -> list[tuple[str, dict, str]]:
    """Each revision an overlay is cut through, as ``(stage, patch, revision id)``: the checkout,
    the candidate (the squad's changes, none for the accepted tree) and the overlay. Each id is
    what the content names (``compute_revision_id``, contract 3), with the executable bits a
    patch keeps: a file keeps its mode, and a deleted one drops out."""
    # deferred (pair): squadops.sandbox imports this package at load (its API's seed plan)
    from squadops.sandbox.models import compute_revision_id

    def named(files: Mapping[str, bytes]) -> str:
        return compute_revision_id(files, tree.executable & files.keys())

    content, target = tree.content, overlay.tree.as_dict()
    return [
        ("checkout", dict(tree.files), named(tree.files)),
        ("candidate", dict(tree.changes), named(content)),
        ("overlay", _patch_to(content, target), named(target)),
    ]


def _patch_to(current: Mapping[str, bytes], target: Mapping[str, bytes]) -> dict:
    """The patch that turns ``current`` into ``target``: each file written that differs, and each
    one ``target`` lacks deleted."""
    patch: dict[str, bytes | None] = {p: c for p, c in target.items() if current.get(p) != c}
    patch.update({p: None for p in current if p not in target})
    return patch


@dataclass(frozen=True)
class RunnerAcceptance:
    """Runs a criterion's bundle on an overlay, in the sandbox (§24cd point 6).

    ``workspace_prefix`` names every workspace this evaluation seeds: one per overlay, released
    before it is seeded (an earlier attempt's, after a restart) and after its run. ``candidate``
    is the candidate's revision as delivery verified it, when the caller has it: a candidate the
    sandbox cuts otherwise is refused (``CandidateNotDelivered``)."""

    sandbox: Any
    profile: Any
    setup: RunnerSetup
    workspace_prefix: str
    verified_candidate_revision: str | None = None

    async def run(
        self,
        *,
        criterion_id: str,
        side: str,
        tree: SandboxTree,
        overlay: Overlay,
        argv: tuple[str, ...],
        reader: str | None,
    ) -> OverlayRun:
        """One bundle's file run on one overlay. The command runs only on the overlay itself
        (§24cl item 13): each revision cut on the way, the checkout, the candidate and the overlay,
        must be the one its content names, and the run must report that revision. Otherwise
        nothing ran on the overlay, and the run is unexecuted, with why: never a result.

        Raises:
            CandidateNotDelivered: The candidate's content isn't the one delivery verified.
        """
        # deferred (pair): squadops.sandbox imports this package at load (its API's seed plan)
        from squadops.sandbox.findings import FindingsReading

        # deferred (pair): as above
        from squadops.sandbox.models import CommandOutcome, RevisionOrigin

        stages = _stages(tree, overlay)
        expected = self.verified_candidate_revision
        if tree.changes and expected is not None and stages[1][2] != expected:
            raise CandidateNotDelivered(
                f"the candidate's content is revision {stages[1][2]}, and delivery verified "
                f"{expected}: the tree judged isn't the tree delivered"
            )
        workspace_id = f"{self.workspace_prefix}{overlay.identity[:12]}"

        def unexecuted(why: str, revision_id: str | None) -> OverlayRun:
            return OverlayRun(
                criterion_id, side, overlay.identity, revision_id, argv, reader, None, None, why
            )

        await self.sandbox.release_workspace(workspace_id)
        try:
            revision = await self.sandbox.seed_workspace(
                workspace_id,
                dict(tree.files),
                origin=RevisionOrigin.GIT_CHECKOUT,
                executable=tree.executable,
            )
            if revision.revision_id != stages[0][2]:
                return unexecuted(
                    f"the sandbox seeded {revision.revision_id}, not the checkout "
                    f"{stages[0][2]}: the overlay wasn't assembled",
                    revision.revision_id,
                )
            for name, files, want in stages[1:]:
                if not files:
                    continue
                origin = (
                    RevisionOrigin.AGENT_PATCH
                    if name == "candidate"
                    else RevisionOrigin.ACCEPTANCE_ASSEMBLY
                )
                patched = await self._patched(revision, files, origin)
                if patched is None or patched.revision_id != want:
                    cut = patched.revision_id if patched is not None else "nothing"
                    return unexecuted(
                        f"the {name} patch cut {cut}, not {want}: the overlay wasn't assembled, so "
                        "nothing ran on it",
                        revision.revision_id,
                    )
                revision = patched
            result = await self.sandbox.run_declared_command(
                revision=revision,
                command=argv,
                working_dir=self.setup.working_directory,
                setup=self.setup.setup,
                findings_reader=reader,
            )
        finally:
            await self._release(workspace_id, raising=sys.exc_info()[0] is None)
        if result.workspace_revision_id != revision.revision_id:
            return unexecuted(
                f"the command ran on revision {result.workspace_revision_id}, not the overlay "
                f"{revision.revision_id}",
                revision.revision_id,
            )
        exited = result.ran and result.outcome == CommandOutcome.EXITED
        return OverlayRun(
            criterion_id=criterion_id,
            side=side,
            overlay_identity=overlay.identity,
            revision_id=revision.revision_id,
            argv=argv,
            reader=reader,
            exit_code=result.exit_code if exited else None,
            reading=FindingsReading.from_dict(result.findings) if result.findings else None,
            unexecuted=None
            if exited
            else (getattr(result, "unavailable_reason", None) or result.outcome or "not run"),
        )

    async def _patched(
        self, base: WorkspaceRevision, files: dict, origin: str
    ) -> WorkspaceRevision | None:
        """The revision a patch cut, or ``None`` when it wasn't applied (a sandbox that runs
        nothing applies nothing, SIP-0102 §4.4)."""
        # deferred (pair): squadops.sandbox imports this package at load (its API's seed plan)
        from squadops.sandbox.models import WorkspaceRevision

        patched = await self.sandbox.apply_workspace_patch(base=base, files=files, origin=origin)
        if not patched.ran:
            return None
        moved = patched.new_revision_id != base.revision_id
        return WorkspaceRevision(
            revision_id=patched.new_revision_id,
            cycle_id=base.cycle_id,
            origin=origin if moved else base.origin,
            # A patch that changed nothing is its base again: the caller holds it to its content.
            parent_revision_id=base.revision_id if moved else base.parent_revision_id,
        )

    async def _release(self, workspace_id: str, *, raising: bool) -> None:
        """An overlay's teardown. When the run itself failed, its error is the one a caller
        needs, so a release that fails too is logged rather than raised over it."""
        try:
            await self.sandbox.release_workspace(workspace_id)
        except Exception:
            if raising:
                raise
            logger.warning("acceptance workspace %s not released", workspace_id, exc_info=True)


# =============================================================================
# §8.1 on the product's runner: the frozen criteria
# =============================================================================


async def frozen_on_runner(
    runs: RunnerAcceptance,
    *,
    subject_id: str,
    tree: SandboxTree,
    frozen: Iterable[FrozenCriterion],
    surface: ProductTestSurface,
) -> tuple[tuple[FrozenResult, ...], tuple[OverlayRun, ...]]:
    """Each frozen criterion's bundle run alone on ``tree``'s candidate-verifier overlay, judged by
    ``held_on_runner`` (§8.1), and the runs. ``subject_id`` keys each result: the increment, or the
    rebase whose head ``tree`` is (§24cd point 5).

    A bundle is read by the test-id reader of the runner that holds its file in the profile, and
    by its exit status where none does or the runner has none (H.6's ``per_test_reading``). Its
    invocation is its own, as frozen. A missing bundle is never run, and is
    ``blocked_unverified``."""
    candidate = tree.file_tree
    results: list[FrozenResult] = []
    done: list[OverlayRun] = []
    for criterion in frozen:
        bundle = criterion.bundle
        if bundle is None:
            held, detail = held_on_runner(None, None, None, None)
        else:
            runner = runs.profile.runner_for(criterion.test_path)
            reader = runner.test_ids if runner is not None else None
            run = await runs.run(
                criterion_id=criterion.criterion_id,
                side=CANDIDATE,
                tree=tree,
                overlay=candidate_verifier_overlay(candidate, bundle, surface),
                argv=bundle.invocation,
                reader=reader,
            )
            done.append(run)
            held, detail = held_on_runner(bundle.address, reader, run.exit_code, run.reading)
            if run.exit_code is None and run.unexecuted:
                detail = f"{detail}: {run.unexecuted}"
        results.append(
            FrozenResult(
                subject_id,
                criterion.criterion_id,
                candidate.identity,
                bundle.address if bundle is not None else None,
                held,
                detail,
            )
        )
    return tuple(results), tuple(done)


# =============================================================================
# §8.2 on the product's runner, and the increment's evaluation
# =============================================================================


async def _discriminated(
    runs: RunnerAcceptance,
    criterion: NewCriterion,
    *,
    accepted: SandboxTree,
    candidate: SandboxTree,
    surface: ProductTestSurface,
) -> tuple[Discrimination, VerifierBundle | None, tuple[OverlayRun, ...]]:
    """One new criterion (§8.2): its bundle frozen from the candidate, and its file run alone on
    each side, unless nothing could read it."""
    not_run = Discrimination(criterion.criterion_id, False, DiscriminationReason.NOT_RUN)
    runner = runs.profile.runner_for(criterion.test_path)
    if runner is None or runner.single_file_argv is None:
        # Placement never puts a criterion there (§24cj item 5): the profile moved under it.
        return not_run, None, ()
    try:
        bundle = freeze_product_bundle(
            criterion.criterion_id, candidate.file_tree, criterion.test_path, surface, runner
        )
    except BundleIncomplete:
        return not_run, None, ()
    if runner.test_ids is None:
        # §24ci (a): unread, so nothing is run that could only be read whole.
        return discrimination_on_runner(criterion.criterion_id, None, None, None), bundle, ()
    sides = []
    for side, tree in ((BASELINE, accepted), (CANDIDATE, candidate)):
        sides.append(
            await runs.run(
                criterion_id=criterion.criterion_id,
                side=side,
                tree=tree,
                overlay=candidate_verifier_overlay(tree.file_tree, bundle, surface),
                argv=bundle.invocation,
                reader=runner.test_ids,
            )
        )
    on_baseline, on_candidate = sides
    decided = discrimination_on_runner(
        criterion.criterion_id, runner.test_ids, on_baseline.reading, on_candidate.reading
    )
    return decided, bundle, tuple(sides)


async def evaluate_on_runner(
    runs: RunnerAcceptance,
    *,
    increment_id: str,
    accepted: SandboxTree,
    candidate: SandboxTree,
    new: Iterable[NewCriterion],
    frozen: Iterable[FrozenCriterion],
    retired: Iterable[str],
    routes: Sequence[RouteResult],
    replaced: Iterable[NewCriterion] = (),
) -> tuple[IncrementEvaluation, tuple[OverlayRun, ...]]:
    """The increment's acceptance on the product's runner (§8, §24cd point 6): discrimination,
    accumulated acceptance and the profile's routes, as ``acceptance_run.evaluate_increment``
    judges a sample application's, and the runs it made. ``routes`` are the profile's routes as
    rendered on the candidate (``execution.product_routes``, §24co): empty where it names none.

    ``replaced`` is each frozen criterion whose verifier the change request replaces, at its own
    test file (§8.1): frozen anew from the candidate and run as a frozen criterion is."""
    new, replaced = tuple(new), tuple(replaced)
    retired = frozenset(retired)
    frozen = tuple(c for c in frozen if c.criterion_id not in retired)
    placed = {c.test_path for c in new} | {c.test_path for c in frozen}
    placed |= {c.test_path for c in replaced}
    surface = ProductTestSurface.of(runs.profile, placed)
    discriminations: list[Discrimination] = []
    bundles: dict[str, VerifierBundle] = {}
    done: list[OverlayRun] = []
    for criterion in new:
        decided, bundle, made = await _discriminated(
            runs, criterion, accepted=accepted, candidate=candidate, surface=surface
        )
        discriminations.append(decided)
        if bundle is not None:
            bundles[criterion.criterion_id] = bundle
        done.extend(made)

    # §8.1: "the old bundle is retired and the new one frozen." A replacement the candidate does
    # not carry whole has no bundle, and is blocked like a missing one.
    renewed = []
    for criterion in replaced:
        runner = runs.profile.runner_for(criterion.test_path)
        bundle = None
        if runner is not None and runner.single_file_argv is not None:
            try:
                bundle = freeze_product_bundle(
                    criterion.criterion_id,
                    candidate.file_tree,
                    criterion.test_path,
                    surface,
                    runner,
                )
            except BundleIncomplete:
                bundle = None
        if bundle is not None:
            bundles[criterion.criterion_id] = bundle
        renewed.append(FrozenCriterion(criterion.criterion_id, criterion.test_path, bundle))
    held, made = await frozen_on_runner(
        runs, subject_id=increment_id, tree=candidate, frozen=(*frozen, *renewed), surface=surface
    )
    done.extend(made)
    held = changed_verifiers_blocked(held, list(frozen), candidate.file_tree)
    routes = tuple(routes)
    return (
        IncrementEvaluation(
            acceptance=increment_acceptance(tuple(discriminations), held, routes),
            discriminations=tuple(discriminations),
            frozen=held,
            routes=routes,
            new_bundles=bundles,
        ),
        tuple(done),
    )


__all__ = [
    "BASELINE",
    "CANDIDATE",
    "CandidateNotDelivered",
    "OverlayRun",
    "ProductTestSurface",
    "RunnerAcceptance",
    "RunnerSetup",
    "SandboxTree",
    "evaluate_on_runner",
    "freeze_product_bundle",
    "frozen_on_runner",
    "single_file_argv",
]
