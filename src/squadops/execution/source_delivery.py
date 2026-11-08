"""A source-backed run's delivery: its candidate, verified and captured (SIP-0112 E.4.3; FR-06,
FR-20; contract 3).

Once the plan's tasks are done, the run's change to the product is known. It is delivered in
three steps:
1. **The candidate.** The pinned commit's tree is seeded into a sandbox workspace
   (``git_checkout``, mapped ``seeded``). The squad's accepted changes are applied to it as one
   patch (``agent_patch``), cutting the candidate revision. Its ID is checked against the one
   the run computes from the same content, so the tree verified is the tree delivered.
2. **Verification.** The product's own checks run against the candidate through X-3a. They are
   attributed against the inherited baseline, which must be the one at the pinned commit and
   Development Configuration revision (squadops.projects.verification). A repository-backed
   Campaign's increment pinned at a head an earlier increment's promotion made is attributed
   against that increment's accepted verification instead (SIP-0109 §24bv point 3).
3. **Capture,** for an accepted candidate. The revision is read back from the sandbox, committed
   in the managed clone on the pinned commit (``refs/squadops/<cycle>/<run>``), and read back
   from Git to the same tree identity. It is mapped ``captured``, and the commit's patch is
   kept as the run's ``patch_export`` contribution.

**A regressed candidate gets one repair round** (#2613, SIP-0112 H.20). The executor routes it
into the correction chain the plan's own failures take (analyze, decide, repair), spending the
run's correction budget, with ``regression_failure`` as the failed result: the blocking checks as
the product's runner read them. The repaired candidate is delivered again, and its verification
names the one it repairs (``RepairOf``): each check that blocked there must now execute and pass.
A second regression, a round that repairs nothing, or a spent budget fails the run with the
verification's summary.

The squad's change is the files its source and test authors produced, at their latest accepted
content, that differ from the checkout's, and the checkout's files they removed (#2612, SIP-0112
H.23). A removal is applied to the candidate as the patch's ``None`` for its path, and named in
the verification's ``changed_paths`` like a write. A file it rewrites keeps the checkout's CRLF
line endings when the original used them throughout. A run's own documents (plans, reports) are
never part of the product. On a repository-backed increment, the files its change request placed
for the framework (the page loaders its page criteria's tests import, #2799) are laid over the
squad's change, as the framework writes them, whatever the squad emitted at their paths.
"""

from __future__ import annotations

import json
import logging
import posixpath
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import PurePosixPath
from typing import Any
from uuid import uuid4

from squadops.campaigns.evaluator_trees import FileTree
from squadops.cycles.deletions import is_deletion
from squadops.cycles.delivered_tree import WORKSPACE_ARTIFACT_TYPES
from squadops.cycles.emission_integrity import EMISSION_STATUS_FAILED
from squadops.cycles.models import ArtifactRef, Cycle
from squadops.cycles.patch_verification import EVIDENCE_ARTIFACT_TYPES
from squadops.cycles.task_outcome import TaskOutcome
from squadops.cycles.task_plan import REPAIR_TASK_TYPES
from squadops.cycles.vault_reads import retrieve_or_absent
from squadops.cycles.verification_integrity import ResultStatus
from squadops.execution.product_suite import PRODUCT_RUNNER
from squadops.projects.baseline import FAIL, InheritedBaseline
from squadops.projects.checkout import SOURCE_CHECKOUT
from squadops.projects.configuration import baseline_tree
from squadops.projects.contribution import capture_ref
from squadops.projects.models import CheckoutTree
from squadops.projects.verification import (
    ACCEPTED,
    REGRESSED,
    SOURCE_VERIFICATION_FILENAME,
    SOURCE_VERIFICATION_TYPE,
    RegressionBaselineInvalid,
    RepairOf,
    SourceVerification,
    attributed,
    previous_verification_baseline,
    why_blocking,
)
from squadops.projects.workspaces import (
    CAPTURED,
    SourceMapping,
    delivery_workspace,
    run_checks,
    seed_project_tree,
)
from squadops.sandbox.models import RevisionOrigin, WorkspaceRevision, content_bytes
from squadops.tasks.models import TaskEnvelope, TaskResult, TaskResultStatus
from squadops.tasks.task_types import authors_qa_suite, authors_source

logger = logging.getLogger(__name__)

SOURCE_PATCH_TYPE = "source_patch"
SOURCE_PATCH_FILENAME = "source_change.patch"


class SourceDeliveryRefused(RuntimeError):
    """A source-backed run whose change can't be verified or captured, with the reason."""


@dataclass(frozen=True)
class SourceDelivery:
    verification: SourceVerification
    artifact_ids: tuple[str, ...]
    captured_commit: str | None = None
    #: The pinned commit's tree the candidate was built on, and the squad's changes to it: the
    #: two trees a repository-backed increment's acceptance is judged on (SIP-0109 §24cd point 6).
    #: A removed file's change is ``None`` (#2612).
    head: CheckoutTree | None = None
    changes: Mapping[str, bytes | None] = field(default_factory=dict)


def squad_changes(
    stored_artifacts: list[tuple[str, ArtifactRef]],
    contents: Mapping[str, bytes],
    checkout: Mapping[str, bytes],
) -> tuple[dict[str, bytes | None], tuple[str, ...]]:
    """The product files the squad changed, added or removed: each path's latest accepted content
    from a source or test author, where it differs from the checkout's, and ``None`` for a
    checkout file whose latest accepted entry is a removal (#2612). ``contents`` maps artifact ID
    to its bytes. Also the paths an author emitted that aren't the product's files, which the
    candidate leaves out and the verification record names. A removal of a path the checkout
    doesn't hold removes only what the squad wrote there, and is named with them."""
    directories = {str(parent) for path in checkout for parent in PurePosixPath(path).parents}
    directories.discard(".")
    latest: dict[str, str] = {}
    left_out: set[str] = set()
    for art_id, ref in stored_artifacts:
        producer = ref.metadata.get("producing_task_type", "")
        # As the executor's own resolution reads the workspace: a failed emission is never
        # input, and a repair candidate is unaccepted until it is re-stored as the task's own.
        if ref.metadata.get("emission_status") == EMISSION_STATUS_FAILED:
            continue
        if producer in REPAIR_TASK_TYPES or producer == SOURCE_CHECKOUT:
            continue
        if not (authors_source(producer) or authors_qa_suite(producer)):
            continue
        # #2591: a task's own records (its test report, its typed-check evaluation) are the
        # squad's evidence, never the product's files (FR-19).
        if ref.artifact_type in EVIDENCE_ARTIFACT_TYPES:
            continue
        if is_deletion(ref):
            if ref.filename in checkout:
                latest[ref.filename] = art_id
            else:
                latest.pop(ref.filename, None)
                left_out.add(ref.filename)
            continue
        if _is_product_file(ref, checkout, directories):
            latest[ref.filename] = art_id
        else:
            left_out.add(ref.filename)
    removed = {art_id for art_id, ref in stored_artifacts if is_deletion(ref)}
    changes: dict[str, bytes | None] = {}
    for path, art_id in sorted(latest.items()):
        if art_id in removed:
            changes[path] = None
            continue
        content = _line_endings_of(checkout.get(path), contents[art_id])
        if checkout.get(path) != content:
            changes[path] = content
    return changes, tuple(sorted(left_out - set(latest)))


def with_framework_files(
    changes: Mapping[str, bytes | None],
    placed: Mapping[str, bytes],
    checkout: Mapping[str, bytes],
) -> dict[str, bytes | None]:
    """The squad's ``changes`` with the framework's ``placed`` files over them (#2799): each one
    written where the checkout doesn't hold it as it is, and the squad's own change at its path
    dropped where it does. So the candidate holds every placed file as the framework wrote it,
    whatever the squad emitted there."""
    merged = dict(changes)
    for path, content in placed.items():
        if checkout.get(path) == content:
            merged.pop(path, None)
        else:
            merged[path] = content
    return merged


async def placed_framework_files(cycle: Cycle, vault: Any) -> dict[str, bytes]:
    """#2799: the framework's files a repository-backed increment's change request placed: the
    page loaders its page criteria's tests import. Laid over the squad's change at delivery
    (``with_framework_files``), so the candidate verified, captured and judged holds them as the
    framework wrote them, and the bundles frozen from it carry them. Empty for every other run,
    and for a change request that placed none."""
    # deferred (cycle): campaigns.increment_tree loads the cycles package, which loads this one
    from squadops.campaigns.increment_tree import (
        approved_change_request,
        increment_basis,
        increment_page_loader_files,
    )

    basis = increment_basis(cycle.resolved_config())
    if basis is None or not basis.evaluated_at_delivery:
        return {}
    try:
        document = await approved_change_request(vault, cycle)
        files = increment_page_loader_files(document) if document is not None else {}
    except ValueError as e:
        # The acceptance after delivery would refuse it too: nothing is judged unread.
        raise SourceDeliveryRefused(
            f"the increment's approved change request can't be read for the files it placed: {e}"
        ) from e
    return {p: c.encode("utf-8") for p, c in files.items()}


def _is_product_file(
    ref: ArtifactRef, checkout: Mapping[str, bytes], directories: set[str]
) -> bool:
    """Source, tests and configuration are the product's. A document is when it edits one of the
    product's files or sits in one of its directories (a README, docs/usage.md); a new one at the
    root, beside nothing of the product's, is the squad's own (its notes, its warnings)."""
    if ref.artifact_type in WORKSPACE_ARTIFACT_TYPES:
        return True
    path = ref.filename
    return path in checkout or posixpath.dirname(path) in directories


def _line_endings_of(original: bytes | None, emitted: bytes) -> bytes:
    if not original or b"\r\n" not in original or original.count(b"\n") != original.count(b"\r\n"):
        return emitted
    return emitted.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")


def regression_subject(plan: Sequence[TaskEnvelope]) -> TaskEnvelope | None:
    """The task a regression's repair round is about (#2613): the plan's last source author,
    whose envelope carries the write grant and workspace a repair of the product's code works
    under; in a plan that authors only tests, its last suite author. ``None`` for a plan that
    authors neither, which delivers nothing."""
    for authors in (authors_source, authors_qa_suite):
        found = [e for e in plan if authors(e.task_type)]
        if found:
            return found[-1]
    return None


def regression_failure(task_id: str, verification: SourceVerification) -> TaskResult:
    """A regressed verification as the failed result the correction chain reads (#2613, H.20).

    Each blocking check is a failed row as the product's own runner read it, in the sandbox after
    the Development Configuration's setup: its id, exit code and output tails, and why it blocks.
    Nothing here is read again in an agent's image, which lacks the product's dependencies
    (#2913). An inherited failure isn't the run's to repair, and is named only in the summary.

    Raises:
        ValueError: ``verification`` didn't regress, so there is nothing to repair.
    """
    if verification.verdict != REGRESSED:
        raise ValueError(f"verification reads {verification.verdict!r}: there's no regression")
    rows = []
    for check in verification.checks:
        if check.id not in verification.blocking:
            continue
        evidence = check.evidence or {}
        row: dict[str, Any] = {
            "check": check.id,
            "passed": False,
            "executed": True,
            "status": ResultStatus.FAILED,
            "judged_on": PRODUCT_RUNNER,
            "attribution": check.attribution,
            "reason": why_blocking(check),
            "exit_code": evidence.get("exit_code"),
            "stdout_tail": evidence.get("stdout_tail") or "",
            "stderr_tail": evidence.get("stderr_tail") or "",
        }
        if check.read:
            row["read"] = dict(check.read)
        rows.append(row)
    environment = ", ".join(f"{k} {v}" for k, v in sorted(verification.environment.items()))
    inherited = [
        c.id for c in verification.checks if c.result == FAIL and c.id not in verification.blocking
    ]
    summary = (
        f"the product's own checks, on its runner ({environment}), after the plan: "
        f"{verification.summary()}"
        + (
            f"; failing before the run too, not its to repair: {', '.join(inherited)}"
            if inherited
            else ""
        )
        + f". The run changed: {', '.join(verification.changed_paths)}"
    )
    return TaskResult(
        task_id=task_id,
        status=TaskResultStatus.FAILED,
        outputs={
            "outcome_class": TaskOutcome.SEMANTIC_FAILURE,
            "summary": summary,
            "validation_result": {
                "passed": False,
                "summary": summary,
                "missing_components": [],
                "checks": rows,
            },
            "artifacts": [],
        },
        error=summary,
        outcome_class=TaskOutcome.SEMANTIC_FAILURE,
    )


async def deliver_source_change(
    cycle: Cycle,
    run_id: str,
    stored_artifacts: list[tuple[str, ArtifactRef]],
    *,
    vault: Any,
    registry: Any,
    repository: Any,
    sandbox: Any,
    repair_of: RepairOf | None = None,
) -> SourceDelivery:
    """Verify the run's change against the inherited baseline, and capture it when accepted.
    ``repair_of`` is a repaired candidate's regressed verification, whose blocking checks it must
    run and pass (#2613)."""
    context = cycle.source_context
    if context is None:
        raise ValueError(f"cycle {cycle.cycle_id} pins no source: it is not source-backed")
    if repository is None or sandbox is None:
        raise SourceDeliveryRefused(
            "a source-backed run is verified in the sandbox and captured in the managed clone, "
            "and this runtime has " + ("neither" if repository is sandbox else "only one")
        )
    commit = context.pinned_commit
    project = await registry.get_project(cycle.project_id)
    configuration = await registry.get_development_configuration(
        cycle.project_id, context.development_configuration_revision
    )
    baseline, verified_tree = await regression_baseline(cycle, vault, registry)
    checkout = await baseline_tree(
        repository, cycle.project_id, context.repo_uri, project.source.base_ref, commit
    )
    if verified_tree is not None and FileTree.of(checkout.files).identity != verified_tree:
        raise SourceDeliveryRefused(
            f"verification {context.previous_verification_ref} verified tree "
            f"{verified_tree[:12]}, and the head {commit[:12]} the run was built on holds "
            f"{FileTree.of(checkout.files).identity[:12]}: a candidate is compared only with the "
            "checks of the tree it changed (SIP-0109 §24bv point 3)"
        )
    contents = {}
    for art_id, _ref in stored_artifacts:
        _stored, contents[art_id] = await vault.retrieve(art_id)
    changes, left_out = squad_changes(stored_artifacts, contents, checkout.files)
    if not changes:
        named = f"; it left out what isn't the product's: {', '.join(left_out)}" if left_out else ""
        raise SourceDeliveryRefused(f"the run changed no file of the product{named}")
    changes = with_framework_files(
        changes, await placed_framework_files(cycle, vault), checkout.files
    )
    if not changes:
        raise SourceDeliveryRefused(
            "the run changed no file of the product: its one change was a file the framework "
            "places, which the head already holds"
        )
    binary = sorted(
        p for p, c in changes.items() if c is not None and _is_binary(checkout.files.get(p))
    )
    if binary:
        raise SourceDeliveryRefused(
            f"the run wrote text over binary files, which 2.4 doesn't edit: {', '.join(binary)}"
        )

    # #2612: a removed file is absent from the candidate, as the sandbox's patch leaves it.
    candidate_files = {
        **{p: c for p, c in checkout.files.items() if changes.get(p, c) is not None},
        **{p: c for p, c in changes.items() if c is not None},
    }
    tree_identity = FileTree.of(candidate_files).identity
    workspace_id = delivery_workspace(run_id, tree_identity)
    # A resumed run delivers again: an earlier attempt's workspace, its head already that
    # attempt's candidate, is released before seeding, and this one at its teardown, once the
    # capture has read it back (#2473's release; the G4 of #2484).
    await sandbox.release_workspace(workspace_id)
    try:
        seeded = await seed_project_tree(
            project,
            commit,
            workspace_id,
            registry=registry,
            repository=repository,
            sandbox=sandbox,
            cycle_id=cycle.cycle_id,
            tree=checkout,
        )
        patched = await sandbox.apply_workspace_patch(base=seeded, files=changes)
        candidate = WorkspaceRevision(
            revision_id=patched.new_revision_id,
            cycle_id=workspace_id,
            origin=RevisionOrigin.AGENT_PATCH,
            parent_revision_id=seeded.revision_id,
        )
        expected = WorkspaceRevision.cut(
            cycle_id=workspace_id,
            origin=RevisionOrigin.AGENT_PATCH,
            files=candidate_files,
            # a removed file's mode drops out with it, as the sandbox's patch drops it
            executable=frozenset(checkout.executable) & candidate_files.keys(),
        )
        if candidate.revision_id != expected.revision_id:
            raise SourceDeliveryRefused(
                f"the sandbox cut {candidate.revision_id} for the candidate, and its content is "
                f"{expected.revision_id}: the tree it would verify isn't the one the run changed"
            )

        results, environment = await run_checks(sandbox, candidate, configuration.commands)
        verification = SourceVerification(
            project_id=cycle.project_id,
            cycle_id=cycle.cycle_id,
            run_id=run_id,
            baseline_commit=commit,
            development_configuration_revision=configuration.revision,
            candidate_revision_id=candidate.revision_id,
            candidate_tree_identity=tree_identity,
            changed_paths=tuple(sorted(changes)),
            left_out=left_out,
            environment=environment,
            checks=attributed(results, baseline),
            regression_baseline_ref=context.previous_verification_ref,
            repair_of=repair_of,
        )
        ids = [
            await _store(
                vault,
                cycle,
                run_id,
                SOURCE_VERIFICATION_FILENAME,
                json.dumps(verification.to_document(), indent=1).encode(),
                SOURCE_VERIFICATION_TYPE,
                "application/json",
            )
        ]
        if verification.verdict != ACCEPTED:
            return SourceDelivery(verification, tuple(ids), head=checkout, changes=changes)

        new_commit, captured = await _capture(
            cycle, run_id, candidate, commit, verification, repository, sandbox
        )
        if captured != tree_identity:
            raise SourceDeliveryRefused(
                f"the captured commit's tree is {captured}, and the candidate verified is "
                f"{tree_identity}: the commit is not the change that was verified"
            )
        await registry.record_source_mapping(
            SourceMapping(
                project_id=cycle.project_id,
                workspace_id=workspace_id,
                direction=CAPTURED,
                commit=new_commit,
                sandbox_revision_id=candidate.revision_id,
                tree_identity=tree_identity,
                cycle_id=cycle.cycle_id,
                campaign_id=cycle.campaign_id,
            )
        )
        patch = await repository.export_patch(cycle.project_id, new_commit)
        ids.append(
            await _store(
                vault,
                cycle,
                run_id,
                SOURCE_PATCH_FILENAME,
                patch,
                SOURCE_PATCH_TYPE,
                "text/x-patch",
                {"captured_commit": new_commit, "parent_commit": commit},
            )
        )
        return SourceDelivery(
            verification, tuple(ids), captured_commit=new_commit, head=checkout, changes=changes
        )
    finally:
        await _release(sandbox, workspace_id, raising=sys.exc_info()[0] is None)


async def regression_baseline(
    cycle: Cycle, vault: Any, registry: Any
) -> tuple[InheritedBaseline, str | None]:
    """What the run's candidate is compared with (FR-20; SIP-0109 §24bv point 3), and the tree
    identity it verified when that isn't the inherited baseline's.

    - **Pinned at the Project's baseline,** or at a campaign branch's head that is the
      calibration record's commit (no ``previous_verification_ref``): the inherited baseline at
      that commit and revision, as a standalone cycle's.
    - **Pinned at a head an increment's promotion made:** that increment's accepted source
      verification, ``previous_verification_ref``, never the Project's baseline, which describes
      a tree the run wasn't built on.

    Delivery runs the product's checks only. The frozen criteria's bundles run in the increment's
    accumulated acceptance (§8.1, §24cd point 6) and in a rebase's verification (§24cd point 5),
    not here. The increment's proposal is shown the same baseline, as the previous increment's
    verification (§24bv point 5, ``product_proposal``), so it reads the result its change is
    compared with."""
    context = cycle.source_context
    assert context is not None
    commit, revision = context.pinned_commit, context.development_configuration_revision
    ref = context.previous_verification_ref
    if ref is None:
        baseline = await registry.get_inherited_baseline(cycle.project_id)
        if (baseline.commit, baseline.development_configuration_revision) != (commit, revision):
            raise SourceDeliveryRefused(
                f"the inherited baseline is at {baseline.commit}, revision "
                f"{baseline.development_configuration_revision}; the run pins {commit}, revision "
                f"{revision}: a candidate is compared only with the baseline of the tree it "
                "changed (FR-20)"
            )
        return baseline, None
    # Contract 1's reader holds a verification to a campaign branch's pin (``parse_source_context``).
    got = await retrieve_or_absent(vault, ref)
    if got is None or getattr(got[0], "artifact_type", None) != SOURCE_VERIFICATION_TYPE:
        raise SourceDeliveryRefused(
            f"the campaign branch's head {commit[:12]} names verification {ref}, and the vault "
            "holds no source verification there: the increment has no regression baseline "
            "(SIP-0109 §24bv point 3)"
        )
    try:
        document = json.loads(got[1])
    except ValueError:
        document = None
    try:
        return previous_verification_baseline(
            document, ref=ref, project_id=cycle.project_id, commit=commit, revision=revision
        )
    except RegressionBaselineInvalid as e:
        raise SourceDeliveryRefused(f"no regression baseline (SIP-0109 §24bv point 3): {e}") from e


async def _release(sandbox: Any, workspace_id: str, *, raising: bool) -> None:
    """A delivery's teardown. When the delivery itself failed, its error is the one a caller
    needs, so a release that fails too is logged rather than raised over it."""
    try:
        await sandbox.release_workspace(workspace_id)
    except Exception:
        if raising:
            raise
        logger.warning(
            "delivery workspace %s not released after a failed delivery", workspace_id,
            exc_info=True,
        )  # fmt: skip


async def _capture(
    cycle: Cycle,
    run_id: str,
    candidate: WorkspaceRevision,
    parent: str,
    verification: SourceVerification,
    repository: Any,
    sandbox: Any,
) -> tuple[str, str]:
    """Commit the candidate as the sandbox holds it; return the commit and the tree identity
    Git holds for it."""
    content = await sandbox.read_workspace_revision(candidate)
    files = {path: content_bytes(c) for path, c in content.files.items()}
    commit = await repository.commit_tree(
        cycle.project_id,
        parent=parent,
        files=files,
        executable=content.executable,
        ref=capture_ref(cycle.cycle_id, run_id),
        message=_message(cycle, run_id, parent, verification),
    )
    committed = await repository.tree_at(cycle.project_id, commit)
    return commit, FileTree.of(committed.files).identity


def _message(cycle: Cycle, run_id: str, parent: str, verification: SourceVerification) -> str:
    changed = verification.changed_paths
    shown = ", ".join(changed[:5]) + (f" and {len(changed) - 5} more" if len(changed) > 5 else "")
    return (
        f"SquadOps cycle {cycle.cycle_id}: {shown}\n\n"
        f"Developed by a SquadOps squad in run {run_id}, from {parent}.\n"
        f"The product's own checks: {verification.summary()}.\n"
    )


def _is_binary(content: bytes | None) -> bool:
    if content is None:
        return False
    try:
        content.decode("utf-8")
    except UnicodeDecodeError:
        return True
    return False


async def _store(
    vault: Any,
    cycle: Cycle,
    run_id: str,
    filename: str,
    content: bytes,
    artifact_type: str,
    media_type: str,
    metadata: dict[str, Any] | None = None,
) -> str:
    ref = ArtifactRef(
        artifact_id=f"art_{uuid4().hex[:12]}",
        project_id=cycle.project_id,
        cycle_id=cycle.cycle_id,
        run_id=run_id,
        artifact_type=artifact_type,
        filename=filename,
        content_hash=sha256(content).hexdigest(),
        size_bytes=len(content),
        media_type=media_type,
        created_at=datetime.now(UTC),
        metadata={"source_delivery": True, **(metadata or {})},
    )
    await vault.store(ref, content)
    return ref.artifact_id
