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
_DISP_DROP_FROZEN = "drop_frozen"
_DISP_DROP_SHELL = "drop_shell"
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


# #649: source suffixes a builder may not author. Assembly re-packages accepted
# code; net-new source is how fay-7's uninstructed start.py entered the tree
# (import-time RuntimeError in every test workspace, unrepairable — dev-scoped
# repairs never touch builder artifacts). Docs/reports pass through.
_BUILDER_FORBIDDEN_SOURCE_SUFFIXES = (".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs")


def _is_builder_producer(task_type: str) -> bool:
    """#649: builder task types are scoped to re-packaging the declared fill surface."""
    return task_type.startswith("builder.")


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


def _producer_grants(envelope: Any, bound_record: Any) -> tuple[Any, Any]:
    """The (qa, builder) write authorizations for this producer, or (None, None).

    A QA producer gets a namespace-scoped grant; the 2.1 authorization classes decide
    whether a non-frozen emission is inside its lane (allow), another producer's slot
    (drop), or undeclared (allow — could be a deliverable; §4.6 undeclared-reject stays
    gated on 3.4). #649: a builder producer gets a fill-surface grant — net-new SOURCE
    and QA-namespace writes drop with evidence; undeclared non-source paths (handoff
    docs, reports) remain deliverables and pass.
    """
    from squadops.cycles.write_authorization import (
        WorkspaceOwnership,
        WriteAuthorization,
        WriteGrant,
    )

    qa_authz = None
    if _is_qa_producer(envelope.task_type):
        ownership = WorkspaceOwnership.from_record(bound_record)
        qa_authz = WriteAuthorization(ownership, WriteGrant.for_qa(envelope.task_type, ownership))
    builder_authz = None
    if _is_builder_producer(envelope.task_type):
        ownership = WorkspaceOwnership.from_record(bound_record)
        builder_authz = WriteAuthorization(
            ownership, WriteGrant.for_builder(envelope.task_type, ownership)
        )
    return qa_authz, builder_authz


def _shell_map(bound_record: Any) -> dict[str, Any]:
    """SIP-0104 P4: the region-frozen verification-scaffold shells, keyed by normalized
    path — mutable slot bodies inside a frozen, hash-verified spine. Content-based and
    role-independent: the rule is what the bytes are, not who emitted them (§4.3's "any
    role, any locus"). Empty for unopted stacks and pre-P4 bound records (no region
    enforcement; the file-level rules are unchanged)."""
    from squadops.cycles.write_authorization import normalize_ws_path

    scaffold_record = getattr(bound_record, "verification_scaffold", None)
    if scaffold_record is None:
        return {}
    return {
        n: shell
        for shell in scaffold_record.files
        if (n := normalize_ws_path(shell.path)) is not None
    }


def _shell_verdict(shell: Any, art: dict) -> tuple[str, str] | None:
    """The region verdict for one emission against its bound shell, or None = legal."""
    from squadops.capabilities.verification_scaffold_fill import (
        SHELL_VIOLATION_REGION,
        shell_emission_violation,
    )

    content = art.get("content")
    if not isinstance(content, str):
        return (SHELL_VIOLATION_REGION, "non-text emission for a shell path")
    return shell_emission_violation(shell, content)


def enforcement_instruction(record: Any) -> str | None:
    """The next-attempt carry instruction for an enforcement record, or None.

    One selector for both call sites (executor + correction runner), keyed on the
    violation code so the vocabulary and its transports cannot drift apart.
    """
    from squadops.cycles.task_outcome import ContractComplianceViolation

    if record.violation_code == ContractComplianceViolation.FROZEN_PATH_EMISSION:
        return frozen_emission_instruction(record)
    if record.violation_code in (
        ContractComplianceViolation.SCAFFOLD_REGION_VIOLATION,
        ContractComplianceViolation.PROHIBITED_FILL_EMISSION,
    ):
        return shell_emission_instruction(record)
    return None


def shell_emission_instruction(record: Any) -> str:
    """Authoritative next-attempt instruction for a rejected shell emission (SIP-0104 P4).

    The region-level counterpart of :func:`frozen_emission_instruction`, on the same carry
    transport: the next repair attempt must be TOLD the spine is frozen and verified, or it
    fights enforcement blind (#691's lesson at region granularity — and the #884 class this
    SIP §4.3 exists to end: no repair path, any role, any locus, may modify frozen regions
    or slot boundaries)."""
    path = record.normalized_path or record.attempted_path
    return (
        f"`{path}` is a verification-scaffold shell: its spine — imports, invocation, "
        f"status assertion, and the slot markers — is frozen and hash-verified. A prior "
        f"emission to it was rejected and DISCARDED ({record.detail}). To change this "
        f"file, edit ONLY the lines between its [scaffold-slot:begin]/[scaffold-slot:end] "
        f"markers (domain assertions; no imports, no require(), no network access) and "
        f"keep every other byte exactly as-is."
    )


def frozen_emission_instruction(record: Any) -> str:
    """Authoritative next-attempt instruction for a discarded frozen emission (3.4b signal).

    Injected into the following correction attempt's ``failure_evidence`` (the
    ``scaffold_enforcement`` key) so the analyzer and repair are TOLD the edit was rejected
    instead of silently fighting enforcement — the same deterministic-instruction pattern
    interface-drift uses. Mirrors ``interface_conformance``'s generated instructions.

    #691 measured what silence costs: shk-2's repairs rewrote the frozen ``backend/main.py``
    on three consecutive attempts, each write was enforced away, and each attempt therefore
    produced no net change to the file it was aimed at."""
    path = record.normalized_path or record.attempted_path
    return (
        f"`{path}` is scaffold-frozen and canonical; a prior repair's edit to it was "
        "rejected and DISCARDED — the scaffold's own copy is unchanged and still in effect. "
        "Do NOT re-emit this file — implement the fix in the writable fill slots instead."
    )


def enforce_frozen_ownership(
    artifacts: list[dict], bound_record: Any, envelope: Any
) -> tuple[list[dict], list[Any]]:
    """SIP-0100 2.4: a producer must not overwrite a scaffold-frozen file. Any emitted artifact
    whose normalized path is frozen is DROPPED, so the producer cannot clobber the scaffold
    (pf-26). The attempt is recorded (not silent). Non-frozen artifacts pass through unchanged.

    Per-artifact drop (not response-atomic reject) is the deliberate enforcement shape: the
    current squad still re-emits frozen files, so a whole-response reject would break every
    bind-mode build, while dropping one artifact keeps its siblings — the same disposition
    the QA and builder lanes below already use.

    #691 replaced the original restore-to-scaffold-bytes with the drop. Restore left a copy of
    the scaffold's own bytes stored under the *producer's* task type, and that duplicate did
    real damage: it entered ``artifact_contents``, where interface-drift detection read the
    scaffold's ``GET /health`` probe as producer drift and aimed repairs at a file no producer
    may write. Dropping cannot lose the file — a bound run's scaffold seeds every frozen path
    as its own artifact, which every workspace filter selects by artifact type, independent of
    producer. The bound record remains the D2 restoration authority for materialization.

    SIP-0100 3.3: each enforcement produces a structured ``ScaffoldIntegrityEvidence`` record
    (returned alongside the artifacts). Pure — the caller emits it as an
    ``artifact.ownership_enforced`` event + structured log — so enforcement stays testable and
    3.4 can drive the compliance counter off the returned records.

    SIP-0100 3.1: a **QA** producer is additionally scoped to its own namespace. A QA emission
    of a path writable in principle but owned by another producer's slot (e.g. dev's
    ``routes.py``) is **dropped** — the owning producer's version stays; QA cannot rewrite the
    source under test to agree with its own test (the pf-26 class, one step past ``main.py``).
    QA emissions in its namespace, and undeclared paths (deliverables like ``test_report.md``),
    pass through. Non-QA producers are unaffected here (frozen-path drop only)."""
    from squadops.cycles.write_authorization import normalize_ws_path

    frozen = {n for fa in bound_record.frozen if (n := normalize_ws_path(fa.path)) is not None}
    shells = _shell_map(bound_record)
    shell_verdicts: dict[int, tuple[str, str]] = {}
    qa_authz, builder_authz = _producer_grants(envelope, bound_record)

    # Classify first so each evidence record can report how many sibling artifacts in the SAME
    # response were left untouched (per-artifact disposition — restore/drop keep the rest; a
    # response-atomic reject would not — that difference is exactly what the field captures).
    norms = [
        normalize_ws_path(raw) if isinstance(raw := _artifact_raw_path(art), str) else None
        for art in artifacts
    ]

    dispositions = [
        _classify(
            index,
            art,
            norm,
            frozen=frozen,
            shells=shells,
            shell_verdicts=shell_verdicts,
            qa_authz=qa_authz,
            builder_authz=builder_authz,
        )
        for index, (art, norm) in enumerate(zip(artifacts, norms, strict=True))
    ]
    siblings_retained = sum(1 for d in dispositions if d == _DISP_PASS)

    enforced: list[dict] = []
    evidence: list[Any] = []
    for index, (art, norm, disposition) in enumerate(
        zip(artifacts, norms, dispositions, strict=True)
    ):
        record_evidence = _drop_evidence(
            index,
            art,
            norm,
            disposition,
            envelope=envelope,
            bound_record=bound_record,
            shells=shells,
            shell_verdicts=shell_verdicts,
            siblings_retained=siblings_retained,
        )
        if record_evidence is not None:
            evidence.append(record_evidence)
        else:
            enforced.append(_restore_fill_slot_ownership(art, norm, bound_record, envelope))
    return enforced, evidence


def _classify(
    index: int,
    art: dict,
    norm: str | None,
    *,
    frozen: set[str],
    shells: dict[str, Any],
    shell_verdicts: dict[int, tuple[str, str]],
    qa_authz: Any,
    builder_authz: Any,
) -> str:
    """One artifact's enforcement disposition (records shell verdicts as a side table)."""
    from squadops.cycles.write_authorization import AuthzDecision

    if norm is not None and norm in frozen:
        return _DISP_DROP_FROZEN
    if norm is not None and norm in shells:
        verdict = _shell_verdict(shells[norm], art)
        if verdict is not None:
            shell_verdicts[index] = verdict
            return _DISP_DROP_SHELL
        # Legal — a fill-merge product (body edits inside intact markers). Falls
        # through to the producer lanes below like any other writable emission.
    if qa_authz is not None and (
        qa_authz.authorize(_artifact_raw_path(art) or "") == AuthzDecision.FORBIDDEN_UNAUTHORIZED
    ):
        return _DISP_DROP
    if builder_authz is not None:
        decision = builder_authz.authorize(_artifact_raw_path(art) or "")
        if decision == AuthzDecision.FORBIDDEN_UNAUTHORIZED:
            return _DISP_DROP  # another producer's lane (e.g. the QA namespace)
        if decision == AuthzDecision.FORBIDDEN_UNDECLARED and (norm or "").endswith(
            _BUILDER_FORBIDDEN_SOURCE_SUFFIXES
        ):
            return _DISP_DROP  # net-new source (the fay-7 start.py class)
    return _DISP_PASS


def _drop_evidence(
    index: int,
    art: dict,
    norm: str | None,
    disposition: str,
    *,
    envelope: Any,
    bound_record: Any,
    shells: dict[str, Any],
    shell_verdicts: dict[int, tuple[str, str]],
    siblings_retained: int,
) -> Any:
    """The evidence record for a dropped emission (None = pass-through).

    Every drop retains rather than restores (#691): the prior valid version — the
    scaffold's seeded artifact for frozen paths and shells, the owning producer's
    stored version for slot lanes — remains the workspace copy.
    """
    from squadops.cycles.scaffold_integrity_evidence import (
        frozen_path_evidence,
        shell_region_evidence,
        unauthorized_slot_evidence,
    )

    common = {
        "producer_task_id": envelope.task_id,
        "producer_task_type": envelope.task_type,
        "record": bound_record,
        "normalized_path": norm,
        "attempted_content": art.get("content"),
        "siblings_retained": siblings_retained,
    }
    if disposition == _DISP_DROP_SHELL:
        kind, detail = shell_verdicts[index]
        return shell_region_evidence(
            shell=shells[norm],
            attempted_path=_artifact_raw_path(art) or (norm or ""),
            violation_kind=kind,
            detail=detail,
            **common,
        )
    if disposition == _DISP_DROP_FROZEN:
        return frozen_path_evidence(attempted_path=_artifact_raw_path(art) or norm, **common)
    if disposition == _DISP_DROP:
        return unauthorized_slot_evidence(
            attempted_path=_artifact_raw_path(art) or (norm or ""), **common
        )
    return None


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
