"""Behavioral verification of correction-loop patches (#389).

After a ``patch`` correction, the executor used to re-dispatch the failed
task to "re-run the check" (#374). For generative tasks that re-dispatch
does not re-run the *check* — it re-runs the *generator*, which re-rolls
the artifacts from scratch and discards the repair. Field evidence
(cyc_6841d75f167c, #389): every repair passed validation, every re-roll
reintroduced the defect, and the correction budget starved on one task.

This module keeps #374's principle — the verdict is the re-executed check,
never an LLM judgment — but re-runs the failed task's typed acceptance
criteria directly against the repaired artifacts. Pure evaluation
(criteria + artifacts → verdict); no dispatch, no I/O beyond a temp
workspace for the check evaluators.

The executor treats the three verdicts as:
    PASSED       — accept the patched artifacts as the task's outputs.
    FAILED       — repair didn't satisfy the contract; re-enter correction.
    UNVERIFIABLE — checks can't run here (no typed criteria, evaluator
                   error, malformed criterion); fall back to the pre-#389
                   re-dispatch path. Conservative: worst case is the old
                   behavior, never a false accept.
"""

from __future__ import annotations

import json
import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from squadops.cycles.acceptance_evaluation import (
    evaluate_criterion,
    split_acceptance_criteria,
)
from squadops.cycles.bound_scaffold_record import BoundScaffoldRecord
from squadops.cycles.emission_integrity import (
    unresolved_import_summary,
    unresolved_imports,
)
from squadops.cycles.implementation_plan import TypedCheck
from squadops.cycles.verification_integrity import ResultStatus
from squadops.cycles.write_authorization import WriteAuthorization

logger = logging.getLogger(__name__)

# Verdict vocabulary (module constants, not an enum — matches the
# correction_path string convention of the surrounding loop).
PATCH_PASSED = "passed"
PATCH_FAILED = "failed"
PATCH_UNVERIFIABLE = "unverifiable"

# Unverifiable *reasons* that mean "no structural evidence is possible for this
# task" — as opposed to "an evaluator broke". The distinction is load-bearing at
# patch acceptance: a frontend test task's checks all skip by design (Python-AST
# checks, non-Python file), so structural verification can never speak, and the
# behavioral retest (#456) is the only evidence there will ever be. Fail-closed
# on THESE reasons is not caution — it is a deterministic repair deadlock
# (pf-47: 4 repairs rejected unheard; pf-49: same signature).
REASON_NO_EXECUTED_BLOCKING_CHECKS = "no_executed_blocking_checks"
REASON_NO_TYPED_CRITERIA = "no_typed_criteria"
STRUCTURALLY_UNEVALUABLE_REASONS = frozenset(
    {REASON_NO_EXECUTED_BLOCKING_CHECKS, REASON_NO_TYPED_CRITERIA}
)


#: Where a verification row was executed. The verifier runs in runtime-api; a row the
#: repair evaluated in its own container arrives with ``agent:<role>`` (#1229).
EXECUTED_IN_RUNTIME_API = "runtime-api"


@dataclass(frozen=True)
class PatchCheckRecord:
    """One typed criterion's outcome against the patched workspace."""

    check: str
    severity: str
    status: str  # CheckOutcome status: passed | failed | error | skipped
    description: str = ""
    reason: str | None = None
    actual: Any = None
    #: The criterion's params — the identity a row from another environment is matched on.
    params: dict[str, Any] | None = None
    #: Which environment executed this row (#1229).
    executed_in: str = EXECUTED_IN_RUNTIME_API

    def to_check_row(self) -> dict[str, Any]:
        """Render in the handler-emitted ``checks`` row shape.

        The ``acceptance:`` prefix and ``status`` key are what
        ``normalize_task_checks`` (§6.1) keys on, so a patch-verified task
        records the same executed evidence a first-try pass would.
        """
        return {
            "check": f"acceptance:{self.check}",
            "severity": self.severity,
            "description": self.description,
            "status": self.status,
            "reason": self.reason,
            "params": self.params,
            "executed_in": self.executed_in,
            "actual": self.actual,
            "passed": not (self.severity == "error" and self.status in {"failed", "error"}),
            "patch_verified": True,
        }


@dataclass(frozen=True)
class PatchVerification:
    """Aggregate verdict over all typed criteria.

    ``workspace_revision_id`` (#734 Slice A): the content-addressed id of the
    exact workspace mapping the criteria evaluated against — None only on the
    early returns that never materialized a workspace.
    """

    status: str  # PATCH_PASSED | PATCH_FAILED | PATCH_UNVERIFIABLE
    checks: tuple[PatchCheckRecord, ...] = ()
    reason: str | None = None
    workspace_revision_id: str | None = None
    #: #1229: blocking criteria whose verdict came from the repair's own execution,
    #: because this environment could not execute them. Zero when everything that
    #: decided ran here.
    decided_by_agent: int = 0


def rebase_artifact_paths(
    artifacts: list[dict[str, Any]], expected_paths: list[str] | tuple[str, ...]
) -> list[dict[str, Any]]:
    """Deterministically re-home a repair artifact onto its expected path (#507).

    Repair handlers re-derive the layout from prose and can emit the right file
    under the wrong directory (roll cyc_22b14aeda70f: every repair landed
    ``app/routes.py`` while the scaffold, contract, and typed checks target
    ``backend/routes.py``) — the overlay then appends a net-new file instead of
    superseding, typed patch verification runs against the un-patched original,
    and a content-correct, QA-validated repair is discarded by re-dispatch. The
    target path is not the model's to choose: when an emitted ``name`` is not an
    expected path and exactly one expected path shares its basename, the entry
    is rewritten to that path. Ambiguous or unmatched names pass through
    unchanged (conservative — never a false re-home).
    """
    expected = [p for p in expected_paths if isinstance(p, str) and p]
    by_base: dict[str, list[str]] = {}
    for p in expected:
        by_base.setdefault(Path(p).name, []).append(p)
    out: list[dict[str, Any]] = []
    for art in artifacts:
        name = art.get("name")
        if isinstance(name, str) and name and name not in expected:
            candidates = by_base.get(Path(name).name, [])
            if len(candidates) == 1 and candidates[0] != name:
                logger.info("patch_rebase: repair artifact %r re-homed to %r", name, candidates[0])
                art = {**art, "name": candidates[0]}
        out.append(art)
    return out


def overlay_artifacts(
    base: list[dict[str, Any]] | None, patches: list[dict[str, Any]] | None
) -> list[dict[str, Any]]:
    """Merge artifact dicts by ``name``; a patch supersedes the base entry.

    Order: base order preserved, net-new patch files appended in patch order.
    Entries without a usable ``name`` are dropped (they can't land in a
    workspace anyway).
    """
    merged: dict[str, dict[str, Any]] = {}
    for art in list(base or []) + list(patches or []):
        name = art.get("name")
        if isinstance(name, str) and name:
            merged[name] = art
    return list(merged.values())


#: Artifact types that are EVIDENCE about a task's own run — a report of what the
#: suite did, a typed-check evaluation — rather than work product. They describe one
#: execution and are wrong the moment a later execution of the same task supersedes it.
EVIDENCE_ARTIFACT_TYPES: frozenset[str] = frozenset({"test_report", "typed_check_evaluation"})


@dataclass(frozen=True)
class EvidenceSupersession:
    """What :func:`supersede_evidence_artifacts` did, for the log line."""

    artifacts: list[dict[str, Any]]
    replaced: tuple[str, ...] = ()
    dropped: tuple[str, ...] = ()


def supersede_evidence_artifacts(
    patched: list[dict[str, Any]] | None, retest_artifacts: list[dict[str, Any]] | None
) -> EvidenceSupersession:
    """After a PASSING retest, the failed task's own evidence must not be re-stored (#1111).

    An accepted patch re-stores ``patched`` under the repaired task's id. That list is the
    failed result's artifacts overlaid with the repair — so it still carries the failed run's
    ``test_report.md`` and ``typed_check_evaluation_*.json``, written seconds after the retest
    stored its passing report under its own id. Last-writer-wins: the first artifact a triage
    opens for the task says the tests failed on a run whose verdict is ``accepted``, and on
    1.6.5 FastAPI+React roll 1 the next round's analyzer read exactly that and re-diagnosed a
    defect the repair had already fixed.

    Evidence artifacts (:data:`EVIDENCE_ARTIFACT_TYPES`) in ``patched`` are replaced by the
    retest's same-named artifact when it produced one, and dropped otherwise — the corrected
    result carries the retest's fresh ``test_result`` and validation rows, so a stale
    evaluation file adds nothing but the wrong answer. Work product is untouched, and the
    retest's own suite files are never added here: they are stored under the retest's id.
    """
    fresh: dict[str, dict[str, Any]] = {}
    for art in retest_artifacts or []:
        name = art.get("name")
        if isinstance(name, str) and name and art.get("type") in EVIDENCE_ARTIFACT_TYPES:
            fresh[name] = art
    kept: list[dict[str, Any]] = []
    replaced: list[str] = []
    dropped: list[str] = []
    for art in patched or []:
        if art.get("type") not in EVIDENCE_ARTIFACT_TYPES:
            kept.append(art)
            continue
        name = art.get("name")
        if isinstance(name, str) and name in fresh:
            kept.append(fresh[name])
            replaced.append(name)
        else:
            dropped.append(str(name))
    return EvidenceSupersession(kept, tuple(replaced), tuple(dropped))


@dataclass(frozen=True)
class MaterializeResult:
    """Outcome of a unified ``materialize`` (SIP-0100 2.2)."""

    written: tuple[str, ...] = ()
    # (original path, reason code) when a bound authorization rejected the response.
    rejected: tuple[tuple[str, str], ...] = ()
    authorized: bool = True  # False only when a passed authorization forbade the response


def _artifact_name(art: dict) -> Any:
    """The workspace-relative path from either artifact shape — ``{name}``
    (materialize_artifacts) or ``{path}`` (test_runner). SIP-0100 0.1 found the two
    materializers used different shapes; 2.2 unifies them here."""
    return art.get("name") if art.get("name") is not None else art.get("path")


def materialize(
    artifacts: list[dict],
    workspace_root: Path | str,
    *,
    authorization: WriteAuthorization | None = None,
) -> MaterializeResult:
    """The single workspace materializer for BOTH artifact shapes (SIP-0100 2.2 — the one seam
    0.1's inventory said must exist).

    When ``authorization`` is given, the COMPLETE emitted set is authorized BEFORE any write
    (response-atomic, D5): a forbidden or ambiguous path rejects the whole response and writes
    nothing (authorize→materialize, never materialize→restore — plan §3). Without authorization
    (unbound/legacy) it writes everything with path-safety only, byte-identical to the pre-SIP
    behavior. Path-safety (absolute / workspace-escape) always applies; the typed-check
    evaluators keep their own ``_safe_resolve`` chroot on top.
    """
    workspace_root = Path(workspace_root)
    if authorization is not None:
        names = [n for a in artifacts if isinstance((n := _artifact_name(a)), str) and n]
        decision = authorization.authorize_response(names)
        if not decision.allowed:
            return MaterializeResult(
                rejected=tuple((p, str(d)) for p, d in decision.violations), authorized=False
            )

    root_resolved = workspace_root.resolve()
    written: list[str] = []
    for art in artifacts:
        name = _artifact_name(art)
        content = art.get("content", "")
        if not isinstance(name, str) or not name:
            continue
        if Path(name).is_absolute():
            continue
        target = (workspace_root / name).resolve()
        try:
            target.relative_to(root_resolved)
        except ValueError:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            target.write_bytes(content)
        else:
            target.write_text(str(content), encoding="utf-8")
        written.append(name)
    return MaterializeResult(written=tuple(written))


def materialize_artifacts(artifacts: list[dict], workspace_root: Path) -> None:
    """Backward-compatible ``{name}``-shape entry point — delegates to ``materialize`` with no
    authorization (today's write-everything-with-path-safety behavior). Ownership-enforcing
    callers call ``materialize(..., authorization=...)`` directly (SIP-0100 2.4)."""
    materialize(artifacts, workspace_root)


def verify_frozen_integrity(
    workspace_root: Path | str, record: BoundScaffoldRecord
) -> tuple[str, ...]:
    """SIP-0100 D4: after materialization, every frozen path's on-disk bytes MUST equal the
    bound record's bytes. Returns the frozen paths whose bytes changed or vanished (empty ⇒
    intact). A non-empty result is a **high-severity system fault** (a producer bypass /
    concurrent writer / bug — plan D4/§16), NOT a producer correction — the caller restores and
    stops the attempt."""
    workspace_root = Path(workspace_root)
    faults: list[str] = []
    for fa in record.frozen:
        target = workspace_root / fa.path
        try:
            on_disk = target.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            faults.append(fa.path)
            continue
        if on_disk != fa.content:
            faults.append(fa.path)
    return tuple(faults)


def restore_frozen_files(
    workspace_root: Path | str, record: BoundScaffoldRecord
) -> tuple[str, ...]:
    """SIP-0100 D2: rewrite every frozen path from the bound record's persisted bytes — the
    restoration authority is the bound instance, NEVER a re-run of the (possibly newer) expander.
    Returns the restored paths."""
    workspace_root = Path(workspace_root)
    restored: list[str] = []
    for fa in record.frozen:
        target = workspace_root / fa.path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(fa.content, encoding="utf-8")
        restored.append(fa.path)
    return tuple(restored)


def _coerce_typed_criteria(criteria: list[Any]) -> list[TypedCheck] | None:
    """Extract TypedCheck entries via the shared seam (#420).

    Prose strings are informational and never block — dropped. Returns None
    when any row fails to parse: an unintelligible contract must fall
    back to re-dispatch, not silently verify against a subset of itself.
    """
    split = split_acceptance_criteria(criteria)
    if split.unparseable:
        logger.warning(
            "patch_verification: %d unparseable criteria — unverifiable",
            len(split.unparseable),
        )
        return None
    return list(split.typed)


def _dedupe_file_owned(
    file_owned_criteria: list[TypedCheck] | None, typed: list[TypedCheck]
) -> list[TypedCheck]:
    """Drop file-owned criteria the failed task already carries (by contract id).

    A dev-task repair's task criteria ARE its file's criteria — without this the
    same check evaluates and reports twice on every dev patch.
    """
    task_criterion_ids = {check.id for check in typed if check.id}
    return [
        check
        for check in (file_owned_criteria or [])
        if not (check.id and check.id in task_criterion_ids)
    ]


async def _evaluate_file_owned_gate(
    gate: list[TypedCheck],
    workspace_root: Path,
    *,
    stack: str | None,
    typed_acceptance_enabled: bool,
    command_acceptance_enabled: bool,
) -> tuple[list[PatchCheckRecord], bool]:
    """Evaluate the #870 file-owned criteria; returns (records, any executed blocking failure).

    Monotone by design (see ``verify_patched_artifacts``): only ``severity=error``
    + ``status=failed`` counts as a gate failure — evaluator errors and skips are
    recorded and change nothing, because this environment may lack the stack's
    toolchain and the behavioral retest still covers those checks where it runs.
    """
    records: list[PatchCheckRecord] = []
    failed = False
    for criterion in gate:
        outcome = await evaluate_criterion(
            criterion,
            workspace_root,
            stack=stack,
            typed_acceptance_enabled=typed_acceptance_enabled,
            command_acceptance_enabled=command_acceptance_enabled,
        )
        records.append(
            PatchCheckRecord(
                check=criterion.check,
                severity=criterion.severity,
                status=outcome.status,
                description=criterion.description or "file-owned criterion (#870)",
                reason=outcome.reason,
                actual=outcome.actual,
                params=dict(criterion.params or {}),
            )
        )
        if criterion.severity == "error" and outcome.status == "failed":
            failed = True
    return records, failed


async def _evaluate_task_criteria(
    typed: list[TypedCheck],
    workspace_root: Path,
    records: list[PatchCheckRecord],
    *,
    stack: str | None,
    typed_acceptance_enabled: bool,
    command_acceptance_enabled: bool,
) -> list[tuple[TypedCheck, str]]:
    """Evaluate the failed task's own criteria here, appending rows to *records*.

    Returns ``(criterion, local status)`` per criterion; the verdict is ``_task_verdict``'s,
    over these and whatever the repair executed in its own container (#1229).
    """
    statuses: list[tuple[TypedCheck, str]] = []
    for criterion in typed:
        outcome = await evaluate_criterion(
            criterion,
            workspace_root,
            stack=stack,
            typed_acceptance_enabled=typed_acceptance_enabled,
            command_acceptance_enabled=command_acceptance_enabled,
        )
        records.append(
            PatchCheckRecord(
                check=criterion.check,
                severity=criterion.severity,
                status=outcome.status,
                description=criterion.description or "",
                reason=outcome.reason,
                actual=outcome.actual,
                params=dict(criterion.params or {}),
            )
        )
        statuses.append((criterion, outcome.status))
    return statuses


_EXECUTED = frozenset({ResultStatus.PASSED, ResultStatus.FAILED})


def _criterion_key(check: str, params: Any) -> tuple[str, str]:
    return check, json.dumps(params or {}, sort_keys=True, default=str)


def agent_check_records(agent_checks: Any) -> list[PatchCheckRecord]:
    """The rows a repair evaluated in its own container, as verification records (#1229).

    ``agent_checks`` is the handler's ``repair_typed_checks`` output: ``environment`` and
    the ``acceptance:``-prefixed rows ``_evaluate_typed_acceptance`` banks. Anything that
    is not such a row is ignored — the shape is the handler's, not the transport's.
    """
    # #1256: one entry per repair step of the round (a dev step and a qa step each
    # evaluate in their own environment) — the executor hands the protocol result's
    # sequence; a single handler output still reads as before.
    if isinstance(agent_checks, (list, tuple)):
        return [record for step in agent_checks for record in agent_check_records(step)]
    if not isinstance(agent_checks, dict):
        return []
    environment = str(agent_checks.get("environment") or "agent")
    records: list[PatchCheckRecord] = []
    for row in agent_checks.get("checks") or ():
        if not isinstance(row, dict):
            continue
        name = str(row.get("check") or "")
        if not name.startswith("acceptance:"):
            continue
        records.append(
            PatchCheckRecord(
                check=name[len("acceptance:") :],
                severity=str(row.get("severity") or "error"),
                status=str(row.get("status") or ""),
                description=str(row.get("description") or ""),
                reason=row.get("reason"),
                actual=row.get("actual"),
                params=dict(row.get("params") or {}),
                executed_in=environment,
            )
        )
    return records


def _task_verdict(
    local: list[tuple[TypedCheck, str]], agent: list[PatchCheckRecord]
) -> tuple[bool, int, str | None, int]:
    """RC-9 over both environments: ``(blocking_failure, blocking_passed, evaluator_error,
    decided_by_agent)``.

    Per blocking criterion: an executed failure anywhere rejects — an agent pass never
    overrides a failure that executed here, and vice versa. An executed pass anywhere
    counts as positive evidence. A local evaluator error aborts the verification, as it
    always did, unless the repair executed that very criterion — then the error was this
    environment's, not the patch's. Rows are matched on ``(check, params)``; an agent row
    for another file or another check says nothing about this criterion.
    """
    executed_by_agent = {
        _criterion_key(r.check, r.params): r.status for r in agent if r.status in _EXECUTED
    }
    blocking_failure = False
    blocking_passed = 0
    evaluator_error: str | None = None
    decided_by_agent = 0
    for criterion, status in local:
        if criterion.severity != "error":
            continue
        remote = executed_by_agent.get(_criterion_key(criterion.check, criterion.params))
        if ResultStatus.FAILED in (status, remote):
            blocking_failure = True
        elif ResultStatus.PASSED in (status, remote):
            blocking_passed += 1
        if status not in _EXECUTED and remote in _EXECUTED:
            decided_by_agent += 1
        if status == ResultStatus.ERROR and remote not in _EXECUTED and evaluator_error is None:
            evaluator_error = criterion.check
    return blocking_failure, blocking_passed, evaluator_error, decided_by_agent


def _gate_failed_by_agent(gate: list[TypedCheck], agent: list[PatchCheckRecord]) -> bool:
    """#870's rejection power, extended to what the repair executed: a file-owned criterion
    this environment could not run, that failed where it did run, rejects the patch."""
    failed = {
        _criterion_key(r.check, r.params)
        for r in agent
        if r.status == ResultStatus.FAILED and r.severity == "error"
    }
    return any(_criterion_key(c.check, c.params) in failed for c in gate if c.severity == "error")


async def verify_patched_artifacts(
    criteria: list[Any],
    artifacts: list[dict[str, Any]],
    *,
    workspace_files: dict[str, str] | None = None,
    stack: str | None = None,
    typed_acceptance_enabled: bool = True,
    command_acceptance_enabled: bool = True,
    file_owned_criteria: list[TypedCheck] | None = None,
    agent_checks: Any = None,
) -> PatchVerification:
    """Re-run the failed task's typed acceptance criteria against *artifacts*.

    ``agent_checks`` (#1229, the owner's rule B) are the rows the repair evaluated on its
    own patched tree in the agent container — where the stack's toolchain lives. This
    environment re-runs what it can as a cross-check and takes the repair's executed rows
    as the verdict for what it cannot run; ``no_executed_blocking_checks`` fires only when
    neither environment executed a blocking criterion. Before this, runtime-api — which
    has no node — was the only judge, so on the Next.js stack a dev repair could never
    earn a verdict (``cyc_05abfc7c1f00``, three rounds of ``unverifiable``).

    Mirrors the handler-side RC-9 blocking matrix: only ``severity=error``
    criteria can block; ``skipped`` never blocks. Any evaluator ``error`` on
    a blocking criterion makes the whole patch UNVERIFIABLE (the executor
    environment may lack tooling the agent container has — never guess).

    ``workspace_files`` (#643) is the accepted workspace tree the patch lands
    in, materialized FIRST so *artifacts* supersede their own slots. It is a
    verification substrate only — never part of what an accepted patch stores.
    Runtime-level checks (module_imports, the #591 import pre-gate) are
    meaningless without the scaffold siblings the patched file imports.

    ``file_owned_criteria`` (#870) are the contract criteria owned by the files
    the repair rewrote (``resolve_criteria_for_files``) — a repair for a
    qa.test failure is otherwise judged against nothing structural at all
    (roll 12: four re-emitted routes that no longer compiled sailed to the
    retest). The gate is deliberately MONOTONE: an executed blocking failure
    rejects the patch — executed here or, since #1229, in the repair's own
    container — and an evaluator error or skip changes nothing. Gate rows never
    count as positive acceptance evidence — compiling is necessary, not sufficient.
    """
    typed = _coerce_typed_criteria(criteria)
    if typed is None:
        return PatchVerification(status=PATCH_UNVERIFIABLE, reason="unparseable_criteria")
    gate = _dedupe_file_owned(file_owned_criteria, typed)
    agent_records = agent_check_records(agent_checks)
    if not typed and not gate:
        # #1255: carry the rows the repair executed so the verdict — and the executor's
        # ``agent_rows=`` log line — say what the agent did. The builder repair in
        # cyc_c6db3ffc1f4e reported one executed row and this returned none.
        return PatchVerification(
            status=PATCH_UNVERIFIABLE,
            reason=REASON_NO_TYPED_CRITERIA,
            checks=tuple(agent_records),
        )

    records: list[PatchCheckRecord] = []
    # #734 Slice A: name the exact workspace mapping evaluated below — computed
    # from the parameter (the post-filter mapping handed in), never store state.
    from squadops.sandbox.models import compute_revision_id

    revision_id = compute_revision_id(workspace_files or {})
    with tempfile.TemporaryDirectory(prefix="squadops-patch-verify-") as tmpdir:
        workspace_root = Path(tmpdir)
        if workspace_files:
            materialize_artifacts(
                [{"name": name, "content": content} for name, content in workspace_files.items()],
                workspace_root,
            )
        materialize_artifacts(artifacts, workspace_root)

        # #591: typed criteria read one file at a time, so a patch whose imports
        # cannot resolve passes every one of them and is accepted — then the
        # suite fails to collect. pf-37: the repair emitted a coherent
        # models.py/routes.py pair, SIP-0100 restored the frozen models.py, and
        # the surviving routes.py imported seven names it never defined.
        # Deliberately BEFORE the criteria loop: an unimportable workspace makes
        # every downstream verdict meaningless, and this is the one place the
        # restored-plus-repaired combination actually exists.
        unresolved = unresolved_imports(workspace_root)
        if unresolved:
            summary = unresolved_import_summary(unresolved)
            logger.info("patch_verification: unresolved intra-package imports — %s", summary)
            return PatchVerification(
                status=PATCH_FAILED,
                reason=f"unresolved_imports:{summary}",
                workspace_revision_id=revision_id,
            )

        # #870 file-owned gate, BEFORE the task-criteria loop: an executed blocking
        # failure rejects the patch outright; anything else (pass / skip / evaluator
        # error) falls through to the existing logic unchanged, and gate rows never
        # feed ``blocking_passed`` — rejection power only, per the docstring.
        gate_records, gate_failed = await _evaluate_file_owned_gate(
            gate,
            workspace_root,
            stack=stack,
            typed_acceptance_enabled=typed_acceptance_enabled,
            command_acceptance_enabled=command_acceptance_enabled,
        )
        records.extend(gate_records)
        records.extend(agent_records)
        if gate_failed or _gate_failed_by_agent(gate, agent_records):
            return PatchVerification(
                status=PATCH_FAILED,
                checks=tuple(records),
                reason="file_owned_criteria",
                workspace_revision_id=revision_id,
            )
        if not typed:
            # The gate could not reject and the failed task itself has no typed
            # criteria — same structurally-unevaluable verdict as before the gate
            # existed, so the behavioral retest still decides (pf-47/pf-49).
            return PatchVerification(
                status=PATCH_UNVERIFIABLE,
                checks=tuple(records),
                reason=REASON_NO_TYPED_CRITERIA,
                workspace_revision_id=revision_id,
            )

        local = await _evaluate_task_criteria(
            typed,
            workspace_root,
            records,
            stack=stack,
            typed_acceptance_enabled=typed_acceptance_enabled,
            command_acceptance_enabled=command_acceptance_enabled,
        )
        blocking_failure, blocking_passed, evaluator_error, decided_by_agent = _task_verdict(
            local, agent_records
        )
        if evaluator_error is not None:
            # Evaluator couldn't run in this environment and the repair did not run it
            # either — the whole verification is untrustworthy, not just this row.
            return PatchVerification(
                status=PATCH_UNVERIFIABLE,
                checks=tuple(records),
                reason=f"evaluator_error:{evaluator_error}",
                workspace_revision_id=revision_id,
            )

    if blocking_failure:
        return PatchVerification(
            status=PATCH_FAILED,
            checks=tuple(records),
            workspace_revision_id=revision_id,
            decided_by_agent=decided_by_agent,
        )
    if blocking_passed == 0:
        # Every blocking criterion was skipped in BOTH environments (disabled config,
        # unset stack, a toolchain no role provisions). Accepting a patch requires
        # positive executed evidence — "nothing failed because nothing ran" is the
        # false-green shape (§6.2).
        return PatchVerification(
            status=PATCH_UNVERIFIABLE,
            checks=tuple(records),
            reason=REASON_NO_EXECUTED_BLOCKING_CHECKS,
            workspace_revision_id=revision_id,
        )
    return PatchVerification(
        status=PATCH_PASSED,
        checks=tuple(records),
        workspace_revision_id=revision_id,
        decided_by_agent=decided_by_agent,
    )
