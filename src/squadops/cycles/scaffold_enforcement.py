"""SIP-0100 frozen-ownership enforcement, shared by every artifact-landing path.

Lifted from ``DispatchedFlowExecutor`` (3.4b) so the correction runner's
repair-emission path can enforce the same scaffold ownership the executor's
regular storage path does — pf-27/pf-30 both showed repairs re-emitting
frozen files un-restored because enforcement lived only on the executor
side. Pure functions: callers emit the returned evidence records as events
and decide what to do with the enforced artifact list.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Per-artifact enforcement dispositions (internal protocol; named so comparison
# sites never carry raw literals that shadow unrelated enums — #380/#559).
_DISP_RESTORE = "restore"
_DISP_DROP = "drop"
_DISP_PASS = "pass"


def _artifact_raw_path(art: dict) -> str | None:
    """The producer-emitted path of an artifact, accepting both the ``{name}`` and ``{path}``
    shapes the two materializers use (SIP-0100 0.1)."""
    return art.get("name") if art.get("name") is not None else art.get("path")


def _is_qa_producer(task_type: str) -> bool:
    """SIP-0100 3.1: QA task types (``qa.test``, ``qa.validate``) are scoped to the QA test
    namespace — they write tests, not the source under test."""
    return task_type.startswith("qa.")


def bound_record_or_none(interface_manifest: Any, run_id: str) -> Any:
    """SIP-0100 2.4: the bound scaffold record (frozen paths + bytes) for a scaffold-bound
    run, or None for unbound/legacy runs (no manifest / non-scaffoldable stack → no
    enforcement, plan §10). Best-effort: a build failure disables enforcement rather than
    failing the run."""
    if interface_manifest is None:
        return None
    try:
        from squadops.capabilities.scaffold import is_scaffoldable_stack
        from squadops.cycles.bound_scaffold_record import build_bound_record

        if not is_scaffoldable_stack(getattr(interface_manifest, "stack", "")):
            return None
        return build_bound_record(
            interface_manifest, run_id=run_id, attempt_id=run_id, created_at=""
        )
    except Exception:
        logger.warning(
            "SIP-0100: could not build bound scaffold record for run %s; frozen-ownership "
            "enforcement disabled for this run",
            run_id,
            exc_info=True,
        )
        return None


def frozen_restore_instruction(record: Any) -> str:
    """Authoritative next-attempt instruction for a restored frozen emission (3.4b restore+signal).

    Injected into the following correction attempt's ``failure_evidence`` (the
    ``scaffold_enforcement`` key) so the analyzer and repair are TOLD the edit was rejected
    instead of silently fighting the restore — the same deterministic-instruction pattern
    interface-drift uses. Mirrors ``interface_conformance``'s generated instructions."""
    path = record.normalized_path or record.attempted_path
    return (
        f"`{path}` is scaffold-frozen and canonical; a prior repair's edit to it was "
        "rejected and the scaffold bytes restored. Do NOT re-emit this file — implement "
        "the fix in the writable fill slots instead."
    )


def enforce_frozen_ownership(
    artifacts: list[dict], bound_record: Any, envelope: Any
) -> tuple[list[dict], list[Any]]:
    """SIP-0100 2.4: a producer must not overwrite a scaffold-frozen file. Any emitted artifact
    whose normalized path is frozen has its content RESTORED to the bound record's bytes (D2
    restoration authority — never re-derive), so the producer cannot clobber the scaffold
    (pf-26). The attempt is recorded (not silent). Non-frozen artifacts pass through unchanged.

    Restore (not response-atomic reject) is the deliberate first enforcement: the current squad
    still re-emits frozen files, so a reject would break every bind-mode build; restore is
    non-breaking and correct.

    SIP-0100 3.3: each enforcement produces a structured ``ScaffoldIntegrityEvidence`` record
    (returned alongside the artifacts). Pure — the caller emits it as an
    ``artifact.ownership_enforced`` event + structured log — so enforcement stays testable and
    3.4 can drive the compliance counter off the returned records.

    SIP-0100 3.1: a **QA** producer is additionally scoped to its own namespace. A QA emission
    of a path writable in principle but owned by another producer's slot (e.g. dev's
    ``routes.py``) is **dropped** — the owning producer's version stays; QA cannot rewrite the
    source under test to agree with its own test (the pf-26 class, one step past ``main.py``).
    QA emissions in its namespace, and undeclared paths (deliverables like ``test_report.md``),
    pass through. Non-QA producers are unaffected here (frozen-restore only)."""
    from squadops.cycles.scaffold_integrity_evidence import (
        frozen_restore_evidence,
        unauthorized_slot_evidence,
    )
    from squadops.cycles.write_authorization import (
        AuthzDecision,
        WorkspaceOwnership,
        WriteAuthorization,
        WriteGrant,
        normalize_ws_path,
    )

    frozen = {
        n: fa.content for fa in bound_record.frozen if (n := normalize_ws_path(fa.path)) is not None
    }
    # A QA producer gets a namespace-scoped grant; the 2.1 authorization classes decide whether
    # a non-frozen emission is inside its lane (allow), another producer's slot (drop), or
    # undeclared (allow — could be a deliverable, §4.6 undeclared-reject stays gated on 3.4).
    qa_authz = None
    if _is_qa_producer(envelope.task_type):
        ownership = WorkspaceOwnership.from_record(bound_record)
        grant = WriteGrant.for_qa(envelope.task_type, ownership)
        qa_authz = WriteAuthorization(ownership, grant)

    # Classify first so each evidence record can report how many sibling artifacts in the SAME
    # response were left untouched (per-artifact disposition — restore/drop keep the rest; a
    # response-atomic reject would not — that difference is exactly what the field captures).
    norms = [
        normalize_ws_path(raw) if isinstance(raw := _artifact_raw_path(art), str) else None
        for art in artifacts
    ]

    def _disposition(art: dict, norm: str | None) -> str:
        if norm is not None and norm in frozen:
            return _DISP_RESTORE
        if qa_authz is not None and (
            qa_authz.authorize(_artifact_raw_path(art) or "")
            == AuthzDecision.FORBIDDEN_UNAUTHORIZED
        ):
            return _DISP_DROP
        return _DISP_PASS

    dispositions = [_disposition(art, norm) for art, norm in zip(artifacts, norms, strict=True)]
    siblings_retained = sum(1 for d in dispositions if d == _DISP_PASS)

    enforced: list[dict] = []
    evidence: list[Any] = []
    for art, norm, disposition in zip(artifacts, norms, dispositions, strict=True):
        if disposition == _DISP_RESTORE:
            evidence.append(
                frozen_restore_evidence(
                    producer_task_id=envelope.task_id,
                    producer_task_type=envelope.task_type,
                    record=bound_record,
                    attempted_path=_artifact_raw_path(art) or norm,
                    normalized_path=norm,
                    attempted_content=art.get("content"),
                    siblings_retained=siblings_retained,
                )
            )
            enforced.append({**art, "content": frozen[norm]})  # restore scaffold bytes (D2)
        elif disposition == _DISP_DROP:
            evidence.append(
                unauthorized_slot_evidence(
                    producer_task_id=envelope.task_id,
                    producer_task_type=envelope.task_type,
                    record=bound_record,
                    attempted_path=_artifact_raw_path(art) or (norm or ""),
                    normalized_path=norm,
                    attempted_content=art.get("content"),
                    siblings_retained=siblings_retained,
                )
            )
            # dropped: NOT appended — the owning producer's already-stored version stays.
        else:
            enforced.append(_restore_fill_slot_ownership(art, norm, bound_record, envelope))
    return enforced, evidence


def _restore_fill_slot_ownership(
    art: dict, norm: str | None, bound_record: Any, envelope: Any
) -> dict:
    """Hold the scaffold-owned parts of a *fill slot* in place (pf-40).

    A frozen file is restored wholesale; a fill slot cannot be, because rewriting it is the
    producer's job. But the slot's decorators and signatures are scaffold-owned — the stub
    says so in its own header — and pf-40 showed that saying so is not enough: the producer
    replaced ``@router.post("/runs", response_model=RunEvent, status_code=201)`` with
    ``@router.post("/runs")``, so the app answered 200 against a contract demanding 201 and
    the run was rejected for it, on the very deploy that had just fixed the scaffold to emit
    201.

    Only ``status_code`` is put back — see ``fill_slot_integrity`` for why the rest is
    reported rather than rewritten. No seed (older bound records) means no enforcement, and
    a non-Python or unparseable artifact passes through untouched.
    """
    if norm is None or norm not in set(bound_record.fill_slots) or not norm.endswith(".py"):
        return art
    seed = bound_record.fill_seed_bytes(norm)
    content = art.get("content")
    if not seed or not isinstance(content, str):
        return art

    from squadops.cycles.fill_slot_integrity import (
        divergence_summary,
        restore_declared_status_codes,
    )

    corrected, divergences = restore_declared_status_codes(seed, content)
    if divergences:
        logger.warning(
            "SIP-0100 fill_slot_integrity: task=%s path=%s %s",
            getattr(envelope, "task_id", "?"),
            norm,
            divergence_summary(divergences),
        )
    return art if corrected == content else {**art, "content": corrected}
