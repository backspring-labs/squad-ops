"""The repair half of the correction protocol (1.7.5 recovery extraction map §4 step 5).

*Determine the repair steps, enforce ownership, dispatch the repair, judge whether a usable
repair emission exists.* Blocks 4 and 5 of ``run_correction_protocol`` — its largest coherent
half — plus the module-level helpers only they call. A named collaborator rather than a module
of functions because this is the seam Scoped Code Revision will evolve: a scoped revision is
composed by the repair and materialised by ``PatchAcceptance``, and both are now things with a
constructor and a contract.

**The authority split, at this seam.** ``CorrectionRepair`` determines what the repairing
producer is allowed to attempt — it resolves and carries the ``WriteGrant`` onto each repair
envelope. ``PatchAcceptance`` proves the emitted candidate lies inside that authority before
materialisation and verification. Neither derives authority the other already resolved, which
is the inconsistency Scoped Code Revision exists to remove.

``refuted_source_claims`` and ``_attach_refuted_claims`` deliberately stayed with
``CorrectionRunner``: they are the *decision*'s, not the repair's.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from squadops.capabilities.context_assembly import (
    REPAIR_CONTEXT_CONTRACT,
    forwarded_failed_artifacts,
    manifest_surface_fragments,
    repair_forwarded_inputs,
)
from squadops.cycles.agent_config import resolve_agent_config
from squadops.cycles.scaffold_enforcement import name_producer
from squadops.cycles.task_plan import repair_steps_for
from squadops.tasks.models import TaskEnvelope

if TYPE_CHECKING:
    from squadops.cycles.models import ArtifactRef, Cycle
    from squadops.tasks.models import TaskResult

logger = logging.getLogger(__name__)


def _top_level_package(path: str) -> str:
    """First path segment of a repo-relative artifact path.

    ``backend/tests/x.py`` → ``backend``; a bare filename is its own package.
    """
    head, _, _ = str(path).strip().lstrip("./").partition("/")
    return head


def _scope_to_shared_packages(candidates: list[str], anchors: list[str]) -> list[str]:
    """Keep ``candidates`` whose top-level package matches some ``anchor``'s.

    RC2 (pf-24) blast-radius control: a failing ``backend/tests/…`` test retargets
    ``backend/…`` source but leaves ``frontend/…`` untouched, so a backend failure
    can never regress frontend source. No anchors → nothing (the caller falls back
    to the failed artifacts alone).
    """
    anchor_pkgs = {_top_level_package(a) for a in anchors if a}
    if not anchor_pkgs:
        return []
    return [c for c in candidates if c and _top_level_package(c) in anchor_pkgs]


def _scope_to_shared_language(candidates: list[str], anchors: list[str]) -> list[str]:
    """Keep ``candidates`` on the same side of the frontend/backend line as ``anchors``.

    The guarantee RC2 was actually written to give — "a backend failure can never
    regress frontend source" — expressed against the source language instead of the
    directory tree, so it holds wherever the suite was authored.
    """
    from squadops.cycles.acceptance_check_spec import is_frontend_source

    anchor_sides = {is_frontend_source(a) for a in anchors if a}
    if len(anchor_sides) != 1:
        # No anchors, or anchors straddling both sides — nothing is excluded, so
        # scoping would not be bounding anything. Stay silent rather than widen.
        return []
    side = anchor_sides.pop()
    return [c for c in candidates if c and is_frontend_source(c) is side]


def _scoped_implementation_surface(candidates: list[str], anchors: list[str]) -> list[str]:
    """The implementation source a failure in ``anchors`` may legitimately retarget.

    Package scoping first — pf-24's rule, unchanged whenever it matches anything.
    When it comes back EMPTY the anchor was uninformative, not exclusive, and #688
    measured what that costs: shk-2's qa suite was authored at root-level ``tests/``,
    so its anchor package was ``tests``, ``backend/routes.py`` was filtered out, and
    the correction loop had no route to app source at all. fay-16…19 authored
    ``backend/tests/…``, which matched — so whether pf-24 and pf-27 worked at all
    depended on where the squad happened to put its tests.

    So the empty case falls back to the language boundary, which bounds the blast
    radius the way RC2 intended (a backend failure still cannot reach frontend
    source) without depending on the authored layout. A non-empty package match is
    strictly narrower, so it keeps winning.
    """
    scoped = _scope_to_shared_packages(candidates, anchors)
    if scoped:
        return scoped
    widened = _scope_to_shared_language(candidates, anchors)
    if widened:
        logger.info(
            "correction_repair_target: package scoping matched nothing for anchors %s — "
            "falling back to same-language implementation source %s (#688)",
            ", ".join(anchors),
            ", ".join(widened),
        )
    return widened


def _frontend_build_failed(failure_evidence: Any) -> bool:
    """#650 (fay-8): the failed task's validation shows the frontend build failing.

    A failing ``frontend_build`` row places the defect in frontend source no
    matter which task reported it — the check runs inside the backend qa.test
    task, so ownership-anchored targeting never reaches the broken view.
    """
    from squadops.cycles.check_registry import CHECK_FRONTEND_BUILD

    if not isinstance(failure_evidence, dict):
        return False
    checks = (failure_evidence.get("validation_result") or {}).get("checks") or []
    return any(
        isinstance(row, dict)
        and row.get("check") == CHECK_FRONTEND_BUILD
        and row.get("passed") is False
        for row in checks
    )


def _widen_target_for_frontend_build(
    target: list[str], failure_evidence: Any, failed_inputs: dict[str, Any]
) -> list[str]:
    """#650 minimal provenance targeting: a failing ``frontend_build`` unions the
    plan's frontend implementation source into the repair target.

    fay-8 (cyc_7f5f1b8b1790): five correction rounds, four identical
    ``frontend_build`` failures, every repair emitted backend/test files only —
    RC2's package scoping is deliberately conservative (``backend/tests/*`` →
    ``backend/*``, never ``frontend/*``), which is exactly the trap: the loop
    polished a passing backend while the build-breaking view sat outside every
    target. The general provenance-driven scope seam stays deferred (1.5);
    this widens exactly the measured case, derived from the same
    ``implementation_artifacts`` surface RC2 already threads.
    """
    if not _frontend_build_failed(failure_evidence):
        return target
    # #822: which files are views is the CONTRACT's answer, not a directory prefix. This read
    # `p.startswith("frontend/")` — stack #1's layout stated as a property of views. A stack
    # that builds at the project root would union nothing, and the fay-8 trap this function
    # exists to close would reopen intact for it. Same authoring-independent relation
    # `_probe_owned_slots` uses (#688), one criterion over.
    view_slots = [p for p in (failed_inputs.get("contract_view_slots") or []) if isinstance(p, str)]
    return list(dict.fromkeys([*target, *view_slots]))


def _failed_probe_ids(failure_evidence: Any) -> list[str]:
    """Ids of the behavioral probes that FAILED, in evidence order (#688).

    Probe rows enter ``validation_result.checks`` from ``probe_check_rows`` with
    ``check`` == ``criterion_id`` == the probe id and a ``status`` of
    passed/failed/skipped. Only ``failed`` counts: ``skipped`` means the subject
    never booted, which indicts no particular endpoint.
    """
    if not isinstance(failure_evidence, dict):
        return []
    evidence = failure_evidence if isinstance(failure_evidence, dict) else {}
    rows = (evidence.get("validation_result") or {}).get("checks") or []
    ids = [
        str(row.get("check"))
        for row in rows
        if isinstance(row, dict) and row.get("status") == "failed" and row.get("check")
    ]
    # #1015: the same probe failing INSIDE the suite. A scaffold shell is bound to a
    # probe id, and when its frozen assertion fails the scaffold evidence classifies
    # that as ``app_contract`` with ``criterion_id`` = the probe id — structured data,
    # not the analyzer's prose. The 1.6.3 set's three reds all failed this way, on
    # ``vc-probe-api-runs-join``, and never as an HTTP probe row; so the #688 chain to
    # the owning slot started from an empty list every round. Fill-layer and
    # generator-layer observations carry no criterion and indict no endpoint.
    from squadops.cycles.scaffold_evidence import CLASS_APP_CONTRACT

    summary = failure_evidence.get("scaffold_evidence")
    observations = (summary.get("observations") or []) if isinstance(summary, dict) else []
    for obs in observations:
        if (
            isinstance(obs, dict)
            and obs.get("failure_class") == CLASS_APP_CONTRACT
            and obs.get("criterion_id")
            and str(obs["criterion_id"]) not in ids
        ):
            ids.append(str(obs["criterion_id"]))
    return ids


def _probe_owned_slots(failure_evidence: Any, failed_inputs: dict[str, Any]) -> list[str]:
    """Fill-slot files owning the endpoints whose behavioral probes failed (#688).

    The deterministic chain the shk-2 loss chain needed and did not have:
    failed probe row → the probe's declared ``METHOD /path`` → the contract's
    endpoint→fill-slot map → the file that owns the failing endpoint.

    shk-2 (cyc_88162ecfd895): ``vc-probe-runs`` answered 500 because
    ``backend/routes.py`` used ``RunEvent`` without importing it. Both repairs
    emitted ``backend/main.py`` (named by interface-drift evidence) plus the
    failed qa task's own suite, and never ``routes.py`` — the target set could
    not name the defect site, so the loop reproduced the identical 500 and
    exhausted. This resolution names it from contract data alone, independent of
    the drift evidence and of where the squad chose to put its tests.

    Empty whenever the inputs are absent (author mode, probe-less contracts,
    pre-#688 envelopes) or no probe failed — the caller's target is then
    byte-identical to its prior behavior.
    """
    owners = failed_inputs.get("contract_endpoint_owners") or {}
    probes = failed_inputs.get("contract_probes") or []
    if not owners or not probes:
        return []
    failed_ids = _failed_probe_ids(failure_evidence)
    if not failed_ids:
        return []

    from squadops.cycles.verification_contract import Probe

    tokens_by_id: dict[str, str] = {}
    for raw in probes:
        try:
            probe = Probe.from_dict(raw)
        except ValueError:  # a malformed row indicts nothing; it must not raise here
            continue
        token = probe.endpoint_token()
        if token:
            tokens_by_id[probe.id] = token

    slots: list[str] = []
    for probe_id in failed_ids:
        owner = owners.get(tokens_by_id.get(probe_id, ""))
        if owner and owner not in slots:
            slots.append(owner)
    if slots:
        logger.info(
            "correction_repair_target: probe-owned fill slots %s (failed probes: %s)",
            ", ".join(slots),
            ", ".join(failed_ids),
        )
    return slots


def _fill_observations(failure_evidence: Any) -> list[dict[str, str]]:
    """The scaffold evidence's fill-layer observations, one per (file, slot) (#970).

    ``classify_shell_failures`` attributes an assertion failure inside a slot region
    to the FILL layer with the slot id and the shell path — structured data, the
    same source #1015 reads app-contract observations from. These are the sites an
    own-artifact qa repair can reach: the shell files, addressed by slot.
    """
    if not isinstance(failure_evidence, dict):
        return []
    from squadops.cycles.scaffold_evidence import CLASS_FILL

    summary = failure_evidence.get("scaffold_evidence")
    observations = (summary.get("observations") or []) if isinstance(summary, dict) else []
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, str]] = []
    for obs in observations:
        if not isinstance(obs, dict) or obs.get("failure_class") != CLASS_FILL:
            continue
        key = (str(obs.get("file") or ""), str(obs.get("slot_id") or ""))
        if not key[0] or key in seen:
            continue
        seen.add(key)
        out.append({"file": key[0], "slot_id": key[1], "detail": str(obs.get("detail") or "")})
    return out


def _qa_scaffold_repair_inputs(
    role: str, failed_inputs: dict[str, Any], failed_result: Any, failure_evidence: Any
) -> dict[str, Any]:
    """What a qa repair of a scaffold-bound task needs to reach a fill (#970, 1.6.5 D).

    Presence-keyed: only a qa-role step repairing a task that carried the scaffold
    receives anything. The scaffold rides as the task was authored against it
    (pristine shells, manifest, tables, element kinds) plus ``current_files`` — the
    failed task's stored artifacts at shell paths, i.e. the shells WITH the fills the
    task merged — so the repair can replace one slot and keep every other byte for
    byte; ``repair_slots`` names the failing slots for the brief.
    """
    scaffold_input = failed_inputs.get("verification_scaffold")
    if role != "qa" or not isinstance(scaffold_input, dict):
        return {}
    shell_paths = {str(f.get("name")) for f in (scaffold_input.get("files") or [])}
    artifacts = (getattr(failed_result, "outputs", None) or {}).get("artifacts") or []
    current_files = [
        {"name": str(a["name"]), "content": str(a.get("content") or "")}
        for a in artifacts
        if isinstance(a, dict) and a.get("name") in shell_paths
    ]
    return {
        "verification_scaffold": {**scaffold_input, "current_files": current_files},
        "repair_slots": _fill_observations(failure_evidence),
    }


def _empty_emission_signature(result: Any) -> list[str]:
    """The #998 signature a repair step's handler put on its ``emission_failure`` marker,
    as a zero-or-one-element list so the caller can ``extend`` without branching."""
    marker = (getattr(result, "outputs", None) or {}).get("emission_failure")
    if isinstance(marker, dict) and marker.get("signature"):
        return [str(marker["signature"])]
    return []


def _narrowed_or_scoped(
    probe_slots: list[str], failed_inputs: dict[str, Any], failed_artifacts: list[str]
) -> list[str]:
    """The implementation surface a repair may reach — narrowed when the defect site is known.

    **#1015 part A, the narrowing.** When a failing probe resolves to the slot that owns
    its endpoint, that slot IS the target and the language-wide surface is not appended.
    The 1.6.3 set measured the alternative: with the join route in a seven-file "you may
    emit" list, roll 1's round 2 and roll 4's rounds 2–3 repaired the create route while
    the decision text named the join handler, and the loop spent its budget beside the
    defect. Minimality and the attempt counter (#1015 B/C) were in force and did not
    help a repair aimed at the wrong file. Drift files and the failed task's own
    artifacts still ride (pf-21: they carry real defects too); only the fallback that
    exists for the case of *no* site evidence is withheld when site evidence exists.

    With no probe-owned slot the surface is what it was: package scoping, then the
    #688 language fallback.
    """
    if probe_slots:
        logger.info(
            "correction_repair_target: narrowed to the slot(s) owning the failing probe(s) — "
            "%s; the language-wide surface is withheld (#1015)",
            ", ".join(probe_slots),
        )
        return []
    return _scoped_implementation_surface(
        failed_inputs.get("implementation_artifacts", []) or [], failed_artifacts
    )


def _verified_implicated_files(
    failure_analysis: dict[str, Any] | None, failed_inputs: dict[str, Any]
) -> list[str]:
    """The analyzer's ``implicated_files``, kept only where the workspace agrees (#968).

    The analyzer's file claims are prose-adjacent — #968 counted three false ones in a
    single roll, one of them carried verbatim into the correction decision. The cheapest
    mechanical check is whether the named path is a file the failed task's envelope knows
    about at all: an implementation artifact, one of its own expected artifacts, or a
    contract-owned slot. A path outside that set is not a defect site the loop can act
    on, and is dropped with a log line rather than aimed at.
    """
    if not isinstance(failure_analysis, dict):
        return []
    claimed = [str(f) for f in (failure_analysis.get("implicated_files") or []) if f]
    if not claimed:
        return []
    known: set[str] = set()
    for key in ("implementation_artifacts", "expected_artifacts"):
        known.update(str(x) for x in (failed_inputs.get(key) or []) if x)
    known.update(str(x) for x in (failed_inputs.get("contract_endpoint_owners") or {}).values())
    verified = [f for f in dict.fromkeys(claimed) if f in known]
    dropped = [f for f in claimed if f not in known]
    if dropped:
        logger.info(
            "correction_repair_target: analyzer implicated %s but the workspace has no such "
            "file — dropped, not aimed at (#968)",
            ", ".join(dropped),
        )
    return verified


def _resolve_repair_target(
    failure_evidence: Any,
    failed_inputs: dict[str, Any],
    failure_analysis: dict[str, Any] | None = None,
) -> tuple[list[str], str | None, str | None]:
    """Choose ``(expected_artifacts, focus, description)`` for a patch-path repair.

    #531: the target defaults to the *failed task's own* artifacts — but the
    ``tests_pass`` check lives on the qa test task, so anchoring there regenerates
    the tests (the symptom) while the drifted source (the cause) is never rewritten
    and the loop can't converge. When the correction carries deterministic
    interface-drift evidence (an AST diff, not the free-text ``affected_task_types``),
    the drifted files ARE part of the target so the dev repair rewrites the source.

    pf-21 (cyc_2aac58b9f03d): drift is not always the *whole* story — the failing
    check's OWN artifact can carry an independent bug too (there: models.py drift
    AND a broken pytest ``client`` fixture in the test file). #532 targeted the
    drift files EXCLUSIVELY, orphaning that file so the loop re-patched already-fixed
    source every attempt and never touched the real test bug → non-convergence. So
    when drift is present, target the UNION (drift files first, then the failed
    task's artifacts): the drifted source is always in the set (no masking — the
    cause is always fixable, the #531/#532 win holds), and the failing artifact's
    own bug is fixable too.

    pf-24 (cyc_38415226ad82) — RC2: a ``tests_pass``/probe failure with NO interface
    drift (a behavioral/runtime bug — there a missing ``/api`` router prefix in
    main.py) has its fix in the *source under test*, which the failing qa.test does
    NOT own (its artifacts are the test files). Anchoring on the failed task then
    edits only the test and the loop exhausts. So with no drift, extend the target
    with the plan's implementation source (``implementation_artifacts``, threaded
    onto qa.test envelopes by task_plan) that shares a top-level package with a
    failing artifact — ``backend/tests/*`` failure → ``backend/*`` source, never
    ``frontend/*`` (package-scoping bounds the blast radius). Absent that surface
    (author mode, non-build corrections) the target is byte-identical to the #531
    fallback below.

    shk-2 (cyc_88162ecfd895) — #688: every surface above is *indirect*. The drift branch
    names whatever files the drift evidence happened to name; the package-scoped union
    reaches app source only when the failed qa task's own artifacts share a top-level
    package with it. Both missed a one-line defect in ``backend/routes.py`` — drift
    pointed at ``backend/main.py``, and the suite was authored at root-level ``tests/``,
    so the scoped union came back empty (it matches on ``backend/tests/…``, which is what
    fay-16…19 happened to author: the reach depended on an authoring coincidence). Two
    changes, one per half of that:

    * The target now LEADS with the fill slots that own the FAILING PROBES' endpoints,
      resolved from contract data (``_probe_owned_slots``). Drift files and the failed
      task's own artifacts still ride — they carry real defects too, the pf-21 lesson —
      but they can no longer displace the defect site.
    * The scoped implementation surface falls back from package to language when the
      package anchor matches nothing (``_scoped_implementation_surface``), so a
      SUITE-ONLY failure — one with no probe evidence to resolve — can still reach the
      source under test on a root-level-``tests/`` layout.
    """
    probe_slots = _probe_owned_slots(failure_evidence, failed_inputs)
    drift = failure_evidence.get("interface_drift") if isinstance(failure_evidence, dict) else None
    drift_files = sorted(
        {d["file"] for d in (drift or []) if isinstance(d, dict) and d.get("file")}
    )
    failed_artifacts = failed_inputs.get("expected_artifacts", []) or []
    if drift_files:
        # Union, drift first, de-duplicated preserving order. The instructional "how"
        # is NOT authored here — it is the interface-drift `instruction`, already a
        # managed/authored asset surfaced into the repair prompt's failure summary
        # as the "INTERFACE CONFORMANCE" section, plus the failure summary itself for
        # the failing artifact's bug. So focus/description stay unset (no inline
        # prompt content — CLAUDE.md #448); the named artifacts + that instruction
        # redirect the repair onto both the drifted source and the failing file.
        # pf-27 (cyc_d01810b2922f): a ``tests_pass`` failure can CO-OCCUR with
        # interface drift on a scaffold-FROZEN file (there: backend/main.py — its
        # /health route + the repair's own un-restored inline routes), which pins the
        # target to this drift branch. But the behavioral fix still lives in the
        # fill-slot source under test (routes.py), which is neither a drift file nor
        # the failing qa.test's own artifact — so without the same package-scoped
        # implementation surface the no-drift branch already unions (RC2), the repair
        # edits only the drifted file + the test and NEVER reaches routes.py →
        # non-convergence. Union it here too; empty surface (author mode) → the scoped
        # set is empty and the target is byte-identical to the pre-pf-27 union.
        scoped_source = _narrowed_or_scoped(probe_slots, failed_inputs, failed_artifacts)
        target = list(
            dict.fromkeys([*probe_slots, *drift_files, *failed_artifacts, *scoped_source])
        )
        target = _widen_target_for_frontend_build(target, failure_evidence, failed_inputs)
        return (target, None, None)
    # RC2 no-drift path: union the failing task's own artifacts with the
    # package-scoped implementation surface so a behavioral failure can reach the
    # source under test. Empty surface → byte-identical to the #531 fallback
    # (failed_artifacts, focus, description).
    # #1015 part A, the analyzer's half: consulted only when no deterministic site
    # evidence exists (no failing probe resolved to a slot, no drift). Verified entries
    # narrow the target exactly as a probe-owned slot does; none → the surface is what
    # it was.
    analysis_files = (
        _verified_implicated_files(failure_analysis, failed_inputs) if not probe_slots else []
    )
    # #1120: the failed task's OWN artifacts are never a narrowing site. They already ride
    # the target as failed_artifacts and the ownership veto (#884) decides who may touch
    # them; letting one of them withhold the language-wide surface left a dev-role
    # repair of a qa-side failure with an EMPTY target (stack #1, cyc_3cde35fa5204:
    # the analyzer named the failing jsx suite, the veto removed it, every round was
    # refunded). Sites that narrow are files someone else owns.
    own = {str(f) for f in failed_artifacts}
    own_only = [f for f in analysis_files if f in own]
    analysis_files = [f for f in analysis_files if f not in own]
    if own_only and not analysis_files:
        logger.info(
            "correction_repair_target: the analyzer implicated only the failed task's own "
            "artifact(s) %s — not a narrowing site; the surface is what it was (#1120)",
            ", ".join(own_only),
        )
    scoped_source = _narrowed_or_scoped(
        [*probe_slots, *analysis_files], failed_inputs, failed_artifacts
    )
    target = list(dict.fromkeys([*probe_slots, *analysis_files, *failed_artifacts, *scoped_source]))
    target = _widen_target_for_frontend_build(target, failure_evidence, failed_inputs)
    return (
        target,
        failed_inputs.get("subtask_focus"),
        failed_inputs.get("subtask_description"),
    )


def _locus_and_repair_target(
    failed_task_type: str,
    failure_evidence: Any,
    failed_inputs: dict[str, Any],
    failure_analysis: dict[str, Any] | None = None,
    decision_outputs: dict[str, Any] | None = None,
) -> tuple[str, list[str], str | None, str | None]:
    """#568: classify the failure locus and choose the repair target for it.

    Returns ``(locus, expected_artifacts, focus, description)``. An
    OWN_ARTIFACT failure (the failed task's own emission is missing or
    uncollectable) targets the failed task's own contract — pointing
    ``_resolve_repair_target``'s subject-implementation union at a test
    re-author would aim it at app source files. Every other locus keeps the
    existing target resolution unchanged.
    """
    from squadops.cycles.failure_evidence import (
        OWN_ARTIFACT_FROM_TESTS_PASS_ROW,
        FailureLocus,
        absent_anchor_cases,
        classify_failure_locus,
        decision_disputes_own_artifact,
        own_artifact_signal,
        qa_owned_suite_defects,
    )

    failure_locus = classify_failure_locus(failure_evidence)
    own_expected = [str(e) for e in (failed_inputs.get("expected_artifacts") or []) if e]
    # #970 (1.6.5 D): under fill mode the shells are merge products, never in
    # ``expected_artifacts``, so aiming the own-artifact repair at the plan's declared
    # file left a failing FILL structurally unreachable — roll 6 of the 1.6.4 set
    # re-produced ``__tests__/runs.test.ts`` twice while every shell rendered "no
    # fill received". When the failed task carried the scaffold and the evidence
    # names fill-layer observations, the target is their shells, by slot.
    fill_sites = (
        _fill_observations(failure_evidence) if failed_inputs.get("verification_scaffold") else []
    )
    if failure_locus == FailureLocus.OWN_ARTIFACT and fill_sites:
        shells = list(dict.fromkeys(site["file"] for site in fill_sites))
        logger.info(
            "correction_repair_locus: own_artifact — %s re-fills slot(s) %s in %s (#970)",
            failed_task_type,
            ", ".join(site["slot_id"] or "?" for site in fill_sites),
            ", ".join(shells),
        )
        return (
            failure_locus,
            shells,
            failed_inputs.get("subtask_focus"),
            failed_inputs.get("subtask_description"),
        )
    # #1130: the suite raised in its own frame in a file the stack says is the qa role's
    # (1.6.5 roll 3: ``TestClient.delete(json=…)`` in ``backend/tests/test_runs.py``,
    # sent to the dev chain 3/3 rounds). The target is THAT file — the failed task's
    # other suites, if any, were not the defect and are not re-authored.
    qa_defects = qa_owned_suite_defects(failure_evidence)
    if failure_locus == FailureLocus.OWN_ARTIFACT and qa_defects:
        defect_files = list(dict.fromkeys(str(d["file"]) for d in qa_defects if d.get("file")))
        target = [f for f in own_expected if f in defect_files] or defect_files
        logger.info(
            "correction_repair_locus: own_artifact — qa_owned_routed: %s raised %s in its own "
            "frame (%s); %s re-authors %s (#1130)",
            ", ".join(defect_files),
            ", ".join(sorted({str(d.get("exception") or "?") for d in qa_defects})),
            "; ".join(f"{d.get('title') or d.get('file')}:{d.get('line')}" for d in qa_defects[:5]),
            failed_task_type,
            ", ".join(target),
        )
        return (
            failure_locus,
            target,
            failed_inputs.get("subtask_focus"),
            failed_inputs.get("subtask_description"),
        )
    # #1123: a failing case asserted an anchor no view declares — the suite that made
    # the assertion is the target, not the views a dev repair would bend toward it.
    anchor_cases = absent_anchor_cases(failure_evidence)
    if failure_locus == FailureLocus.OWN_ARTIFACT and anchor_cases:
        defect_files = list(dict.fromkeys(str(c["file"]) for c in anchor_cases if c.get("file")))
        target = [f for f in own_expected if f in defect_files] or defect_files or own_expected
        logger.info(
            "correction_repair_locus: own_artifact — absent_anchor_routed: %s asserted "
            "undeclared anchor(s) %s; %s re-authors %s (#1123)",
            ", ".join(defect_files) or "?",
            ", ".join(sorted({a for c in anchor_cases for a in c.get("absent_anchors", [])})),
            failed_task_type,
            ", ".join(target),
        )
        return (
            failure_locus,
            target,
            failed_inputs.get("subtask_focus"),
            failed_inputs.get("subtask_description"),
        )
    if failure_locus == FailureLocus.OWN_ARTIFACT and own_expected:
        # #1054: the GENERIC own-artifact route — no fill sites, no qa-owned frame, no
        # absent anchor. Every branch above carries specific machine evidence naming the
        # suite as the defect site; this one has only "the failing check belongs to the
        # task that emitted it", which is exactly the #531 shape the docstring above warns
        # about: `tests_pass` lives on the qa task, so anchoring here regenerates the
        # symptom while the cause is never rewritten.
        #
        # Arm A of the 2026-08-23 pair is the case. Its decision named route handlers and
        # a store module; all three repairs re-authored the same suite file; the shadow
        # store survived. When the decision mentions the suite NOWHERE, that unanimity is
        # the one signal available here that the generic read is wrong, and the target
        # falls through to the dev chain below.
        #
        # The evidence-backed branches above are deliberately NOT overridable this way:
        # `affected_task_types` is model-authored (#968/#788), and the test-gaming guard
        # must keep every seam where a machine signal actually named the suite.
        if own_artifact_signal(failure_evidence) == OWN_ARTIFACT_FROM_TESTS_PASS_ROW and (
            decision_disputes_own_artifact(decision_outputs)
        ):
            # The LOCUS is what routes — `repair_steps_for` reads it to choose the role,
            # and the target follows from that. Returning the same locus with a different
            # target would still dispatch `qa.test_repair`, which is arm A's defect
            # exactly. Disputed, the read falls back to the classifier's own documented
            # ambiguity default: UNKNOWN, which routes to the dev chain.
            logger.warning(
                "correction_repair_locus: own_artifact DISPUTED — the decision names %s "
                "and mentions the suite nowhere, so %s does not re-author its own %s; the "
                "read falls back to the dev chain (#1054)",
                ", ".join(str(t) for t in (decision_outputs or {}).get("affected_task_types", [])),
                failed_task_type,
                ", ".join(own_expected),
            )
            failure_locus = FailureLocus.UNKNOWN
        else:
            logger.info(
                "correction_repair_locus: own_artifact — %s re-produces %s",
                failed_task_type,
                ", ".join(own_expected),
            )
            return (
                failure_locus,
                own_expected,
                failed_inputs.get("subtask_focus"),
                failed_inputs.get("subtask_description"),
            )
    expected, focus, description = _resolve_repair_target(
        failure_evidence, failed_inputs, failure_analysis
    )
    return (failure_locus, expected, focus, description)


def _log_repair_brief(
    task_type: str,
    role: str,
    failure_evidence: Any,
    targets: list[str],
    evidence_from: str = "?",
) -> None:
    """#1123: the set's R4 readout — how many failing cases a qa repair brief carries (the
    brief renders exactly the ``failing_cases`` rows on the failed task's ``tests_pass``
    row). Logged for the qa role only; a dev repair has no case list to scope.

    **``from=`` and ``tests_pass_rows=`` (#1276).** The count alone cannot be read: a brief
    carrying zero cases is correct when the failed result had no behavioural evidence to
    carry, and is the #1273 defect when the result *did* and a refunded round re-briefed
    from the repair's own empty emission instead. The two are told apart by which result
    the evidence was built from and whether that result carried a ``tests_pass`` row at
    all — both known here, neither on the line the 1.7.1 record was read from.
    """
    if role != "qa":
        return
    from squadops.cycles.failure_evidence import failing_cases_from_evidence

    evidence = failure_evidence if isinstance(failure_evidence, dict) else {}
    rows = (evidence.get("validation_result") or {}).get("checks") or []
    tests_pass_rows = sum(
        1 for row in rows if isinstance(row, dict) and row.get("check") == "tests_pass"
    )
    logger.info(
        "correction_repair_brief: %s carries %d failing case(s) for %s from=%s tests_pass_rows=%d",
        task_type,
        len(failing_cases_from_evidence(failure_evidence)),
        ", ".join(targets) or "?",
        evidence_from,
        tests_pass_rows,
    )


def _apply_ownership_veto(
    target: list[str],
    failed_task_type: str,
    step_role: str,
    failed_own_artifacts: list[str],
) -> list[str]:
    """#884: a repair step may not receive another role's artifacts.

    ``_resolve_repair_target`` unions the failed task's own artifacts into
    every target (the pf-21 lesson: the failing artifact can carry its own
    bug) — but when the repair chain runs under a DIFFERENT role than the one
    that produced those artifacts, handing them over invites a guidance-less
    cross-role rewrite: roll 14's resume #3/#4 (#884) had the dev chain
    rewrite the qa suite into a live-fetch version, and its page rewrites
    shipped a compile break that blocked the verdict. Ownership comes from
    the own-artifact repair table (``own_artifact_role``); task types without
    an entry are already repaired by their own role and pass through
    untouched. If the veto empties the target, the locus classifier missed an
    own-artifact case — logged as such, and the repair proceeds empty rather
    than handing the artifacts across the boundary.
    """
    from squadops.cycles.task_plan import own_artifact_role

    owner = own_artifact_role(failed_task_type)
    if owner is None or step_role == owner:
        return target
    own = {str(a) for a in failed_own_artifacts if a}
    if not own:
        return target
    stripped = [t for t in target if t not in own]
    if len(stripped) != len(target):
        removed = [t for t in target if t in own]
        logger.info(
            "correction_repair_target: ownership veto (#884) — %s-owned %s removed "
            "from %s-role repair target",
            owner,
            ", ".join(removed),
            step_role,
        )
        if not stripped:
            logger.warning(
                "correction_repair_target: ownership veto emptied the %s-role target for "
                "failed %s — the locus classifier missed an own-artifact case (#884)",
                step_role,
                failed_task_type,
            )
    return stripped


def _apply_emission_ownership_veto(
    artifacts: list[dict[str, Any]],
    failed_task_type: str,
    step_role: str,
    failed_own_artifacts: list[str],
    test_file_patterns: tuple[str, ...],
) -> list[dict[str, Any]]:
    """#1014: the emission-side completion of #884's targeting veto.

    #884 edits the repair *brief* — but the failing suite is in the step's
    context as evidence, and a model can rewrite what it can see: V38 slot 6's
    dev repairs emitted a full rewrite of the qa-owned suite on all three
    rounds, storage accepted it, and the overlay handed the retest a suite the
    dev wrote to match his own changes. This is the storage-side half: a step
    running under a foreign role may not LAND the failed task's own artifacts
    either, nor anything on the failed task's test-collection surface (basename
    patterns plus the ``__tests__/`` convention — over-matching is the safe
    direction here, same rationale as source-set exclusion; a wrongly dropped
    borderline file merely leaves the original in the tree).

    Applied AFTER the #507 rebase, so the names filtered are the names the
    overlay would actually supersede — a wrong-directory emission that #507
    re-homes onto a qa-owned expected path is caught by the post-rebase name.
    Same-role steps and task types with no declared owner pass through
    untouched, mirroring the targeting veto's scope exactly.
    """
    from squadops.capabilities.development_profiles import matches_test_file_patterns
    from squadops.cycles.task_plan import own_artifact_role

    owner = own_artifact_role(failed_task_type)
    if owner is None or step_role == owner:
        return artifacts
    own = {str(a) for a in failed_own_artifacts if a}
    kept: list[dict[str, Any]] = []
    dropped: list[str] = []
    for art in artifacts:
        name = str(art.get("name") or "")
        if (
            name in own
            or matches_test_file_patterns(name, test_file_patterns)
            or ("__tests__/" in name)
        ):
            dropped.append(name)
        else:
            kept.append(art)
    if dropped:
        logger.info(
            "correction_repair_emission: ownership veto (#1014) — %s-role step emitted "
            "%s-owned %s; discarded, never stored",
            step_role,
            owner,
            ", ".join(dropped),
        )
    return kept


def _repair_step_rows(repair_result: Any) -> list[dict[str, Any]]:
    """The ``repair_typed_checks`` a repair step banked on its outputs (#1229), as the
    protocol result carries them (#1256): one entry when the step evaluated any row,
    none otherwise — a step that emitted nothing, or ran before rule B, contributes
    nothing rather than an empty environment."""
    rows = (getattr(repair_result, "outputs", None) or {}).get("repair_typed_checks")
    if isinstance(rows, dict) and rows.get("checks"):
        return [rows]
    return []


@dataclass(frozen=True)
class RepairOutcome:
    """What the repair step produced.

    ``steps_ran`` is not ``bool(artifacts)``: a rewind or continue path emits nothing
    legitimately and must never be refunded, which is the distinction #1053's refund
    turns on.
    """

    artifacts: list[dict[str, Any]]
    typed_checks: list[dict[str, Any]]
    steps_ran: bool
    empty_signatures: list[str]


class CorrectionRepair:
    """Repair-step selection, the ownership vetoes, the dispatch, the emission judgment.

    Holds no ports. One late-bound callable — ``CorrectionRunner._dispatch_protocol_step``,
    which map §4 step 4 leaves untouched and which owns task-run creation and the SIP-0087
    task events, so correction-driven repairs appear in the Prefect UI. Following the
    ``store_artifact=lambda …`` precedent already on ``CorrectionRunner`` (SIP-0097 §6.3).
    """

    def __init__(self, *, dispatch_step: Callable[..., Any]) -> None:
        self._dispatch_step = dispatch_step

    async def dispatch(
        self,
        correction_path: str,
        diagnosis: Any,
        envelope: TaskEnvelope,
        result: TaskResult,
        cycle: Cycle,
        run_id: str,
        correction_attempts: int,
        *,
        prior_outputs: dict[str, Any],
        all_artifact_refs: list[str],
        stored_artifacts: list[tuple[str, ArtifactRef]],
        completed_task_ids: list[str],
        plan_delta_refs: list[str],
        profile: Any,
        flow_run_id: str | None,
        interface_manifest: Any,
        scaffold_enforcement_carry: list[str] | None,
        budget_guard: Callable[[], None] | None,
        bound_record: Any,
    ) -> RepairOutcome:
        """Step 4 — select the repair steps, enforce ownership, dispatch, collect.

        Repair-step selection is keyed on the failed task's ``task_type`` and the
        deterministic failure locus, never on the LLM-emitted ``affected_task_types``
        (free text, and it once routed a builder failure to the dev repair handler).
        """

        correlation_id = diagnosis.correlation_id
        # What the earlier steps produced, read off the value they returned —
        # never reached backward into their locals (map §4 step 4).
        failure_evidence = diagnosis.failure_evidence
        analysis_outputs = diagnosis.analysis_outputs
        decision_outputs = diagnosis.decision_outputs
        # 7. Handle patch path: dispatch repair tasks
        # Repair-step selection is keyed on the failed task's task_type
        # (authoritative) rather than the LLM-emitted `affected_task_types`
        # field, which is free-text and previously caused builder failures
        # (`affected_task_types: ["QA Handoff"]`) to silently route to the
        # dev repair handler.
        #
        # #568: selection is additionally keyed on the deterministic failure
        # locus — a task whose OWN artifact is missing/uncollectable is repaired
        # by its own role re-producing that artifact (qa.test → qa.test_repair),
        # and the repair target is the failed task's own contract, not the
        # subject-implementation surface (_resolve_repair_target aims repairs at
        # the SUBJECT and would point a test re-author at app source files).
        repair_artifacts: list[dict[str, Any]] = []
        repair_typed_checks: list[dict[str, Any]] = []
        repair_steps_ran = False
        empty_signatures: list[str] = []
        if correction_path == "patch":
            failed_inputs = envelope.inputs or {}
            # #667/#663 S2: the anchor surface rides every repair envelope,
            # re-derived from the manifest under both key variants — the
            # declaration lives with the registry (REPAIR_CONTEXT_CONTRACT).
            repair_surfaces = manifest_surface_fragments(
                REPAIR_CONTEXT_CONTRACT, interface_manifest
            )
            (
                failure_locus,
                repair_expected_artifacts,
                repair_focus,
                repair_description,
            ) = _locus_and_repair_target(
                envelope.task_type,
                failure_evidence,
                failed_inputs,
                analysis_outputs,
                # #1054: the decision's own account of what is affected. Read AGAINST the
                # conservative locus default, never as authority — see
                # `decision_disputes_own_artifact`.
                decision_outputs,
            )

            for step_idx, (task_type, role) in enumerate(
                repair_steps_for(envelope.task_type, failure_locus)
            ):
                # #884: the target union may carry the failed task's own
                # artifacts (pf-21); a step running under a foreign role must
                # not receive them.
                step_expected_artifacts = _apply_ownership_veto(
                    repair_expected_artifacts,
                    envelope.task_type,
                    role,
                    [str(e) for e in (failed_inputs.get("expected_artifacts") or [])],
                )
                repair_task_id = f"repair-{run_id[:12]}-{correction_attempts:02d}-{task_type}"
                _log_repair_brief(
                    task_type,
                    role,
                    failure_evidence,
                    step_expected_artifacts,
                    evidence_from=envelope.task_id,
                )
                resolved = resolve_agent_config(role, profile)
                agent_id = resolved.agent_id
                agent_model = resolved.model
                agent_overrides = resolved.config_overrides

                # Plumb the (retargeted) task contract through to the repair
                # envelope. Without this the repair handler only sees the PRD +
                # failure evidence and produces a generic "repair_output.md" rather
                # than re-emitting the named artifact that must actually be fixed.
                repair_inputs: dict[str, Any] = {
                    "prd": cycle.prd_ref,
                    "failed_task_type": envelope.task_type,
                    "failure_evidence": failure_evidence,
                    "failure_analysis": analysis_outputs,
                    "correction_decision": decision_outputs,
                    "prior_outputs": prior_outputs,
                    "artifact_refs": list(all_artifact_refs),
                    "agent_model": agent_model,
                    "agent_config_overrides": agent_overrides,
                    # The repair handler's scaffold fill-only appendix gates on
                    # resolved_config.build_profile (is_scaffoldable_stack) — without
                    # this the gate sees an empty profile and silently no-ops, and
                    # repairs freely rewrite scaffold-owned interface (pf-30:
                    # attempts 1-3 re-emitted routes.py with relative decorator
                    # paths against a correct diagnosis). Mirrors the retest
                    # threading in reexecute_repaired_suite below.
                    "resolved_config": failed_inputs.get("resolved_config", {}),
                    "subtask_focus": repair_focus,
                    "subtask_description": repair_description,
                    "expected_artifacts": step_expected_artifacts,
                    "acceptance_criteria": failed_inputs.get("acceptance_criteria", []),
                    # #1015 part C: the loop's position. Both values were already here
                    # and simply never crossed into the prompt, so the repair author
                    # could not tell round 1 from round 3 or know the budget was finite.
                    "correction_attempt": correction_attempts + 1,
                    "max_correction_attempts": int(
                        cycle.resolved_config().get("max_correction_attempts", 3)
                    ),
                }
                # #667: fay-14's first fill complied with the manifest
                # convention and every repair regenerated the view blind,
                # stripping the anchors — hence the registry-declared
                # re-derivation above (presence-keyed: no manifest, no keys).
                repair_inputs.update(repair_surfaces)
                # #1229: the typed-acceptance workspace, so the repair can evaluate its
                # own patch against the tree it lands in, where the toolchain lives.
                repair_inputs.update(repair_forwarded_inputs(failed_inputs))
                # #1264: the failed task's own files, so the repair evaluates the failed
                # task's criteria on the tree the verifier will overlay — not one missing them.
                repair_inputs.update(forwarded_failed_artifacts(result.outputs))
                # #970 (1.6.5 D), presence-keyed: the scaffold + the task's current
                # merged shells + the slots whose fills failed, for a qa repair.
                repair_inputs.update(
                    _qa_scaffold_repair_inputs(role, failed_inputs, result, failure_evidence)
                )

                repair_envelope = TaskEnvelope(
                    task_id=repair_task_id,
                    agent_id=agent_id,
                    cycle_id=cycle.cycle_id,
                    pulse_id=uuid4().hex,
                    project_id=cycle.project_id,
                    task_type=task_type,
                    correlation_id=correlation_id,
                    causation_id=envelope.task_id,
                    trace_id=uuid4().hex,
                    span_id=uuid4().hex,
                    inputs=repair_inputs,
                    metadata={"role": role, "step_index": step_idx},
                )

                # Dispatch the repair step (task_run creation + task events
                # live in _dispatch_protocol_step, SIP-0087 B2 — so
                # correction-driven repairs appear in the Prefect UI).
                repair_steps_ran = True
                repair_result = await self._dispatch_step(
                    repair_envelope,
                    run_id,
                    cycle,
                    flow_run_id,
                    prior_outputs=prior_outputs,
                    all_artifact_refs=all_artifact_refs,
                    stored_artifacts=stored_artifacts,
                    completed_task_ids=completed_task_ids,
                    plan_delta_refs=plan_delta_refs,
                    # 3.4b: repair emissions get the same frozen-ownership
                    # enforcement as regular storage (restore + carry signal).
                    bound_record=bound_record,
                    enforcement_carry=scaffold_enforcement_carry,
                    budget_guard=budget_guard,
                )

                # Collect repair outputs under the role key, matching the
                # regular fan-in convention (summaries only — `artifacts` are
                # surfaced to the overlay below, not through prompt context).
                role_key = repair_envelope.metadata.get("role", "unknown")
                prior_outputs[role_key] = {
                    k: v for k, v in (repair_result.outputs or {}).items() if k != "artifacts"
                }

                # #389: surface the repair's emitted files to the executor for
                # behavioral patch verification.
                step_artifacts = (repair_result.outputs or {}).get("artifacts") or []
                # #1256: the rows this step evaluated on its own patch (rule B) ride the
                # protocol result to the executor's verifier beside the files.
                repair_typed_checks.extend(_repair_step_rows(repair_result))
                # #998: the handler names what kind of nothing it emitted; keep it for
                # the round's disclosure below.
                empty_signatures.extend(_empty_emission_signature(repair_result))
                # #507: re-home repair files onto the failed task's expected
                # paths before they reach the overlay — a repair emitted under
                # the wrong directory otherwise lands as a net-new file, patch
                # verification runs on the un-patched original, and the
                # validated repair is discarded by re-dispatch.
                from squadops.capabilities.development_profiles import test_file_patterns_for
                from squadops.cycles.patch_verification import rebase_artifact_paths

                rebased = rebase_artifact_paths(
                    [a for a in step_artifacts if isinstance(a, dict)],
                    failed_inputs.get("expected_artifacts") or [],
                )
                # #1014: emission-side ownership veto, post-rebase — a foreign-role
                # step's emission may not land the failed task's own artifacts or
                # anything on its test-collection surface (see the veto docstring).
                # Pattern derivation is failure-isolated like the #870 gate: an
                # unresolvable capability weakens the veto to its own-set +
                # ``__tests__/`` halves rather than crashing the protocol.
                try:
                    patterns = test_file_patterns_for(failed_inputs.get("resolved_config"))
                except Exception as exc:
                    logger.warning("emission ownership veto: pattern surface unavailable: %s", exc)
                    patterns = ()
                # #1350: the step's emission names the step. The verifier and the re-store
                # receive these on the FAILED task's envelope, and the repairing role can
                # differ from the failed one — the grants must be this step's, not the
                # failed task's, or a dev repair of a dev slot reads as a QA write to it.
                repair_artifacts.extend(
                    name_producer(
                        _apply_emission_ownership_veto(
                            rebased,
                            envelope.task_type,
                            role,
                            [str(e) for e in (failed_inputs.get("expected_artifacts") or [])],
                            patterns,
                        ),
                        repair_envelope,
                    )
                )
        return RepairOutcome(
            artifacts=repair_artifacts,
            typed_checks=repair_typed_checks,
            steps_ran=repair_steps_ran,
            empty_signatures=empty_signatures,
        )

    def judge_emission(self, repair: RepairOutcome, correction_attempts: int) -> bool:
        """Step 5 — did the repair emit a *file*?

        The extractor's marker is the answer and prose is not content. A rewind or
        continue emits nothing legitimately and is never refunded, which is what
        ``steps_ran`` keeps distinct.
        """
        repair_artifacts = repair.artifacts
        repair_steps_ran = repair.steps_ran
        empty_signatures = repair.empty_signatures
        # #1053: did the repair steps that ran produce anything at all? Judged on
        # emitted CONTENT, not on the artifact count — a zero-byte file is still a file,
        # and counting it as an attempt is what spent arm B's budget. `repair_steps_ran`
        # keeps this distinct from a rewind/continue path, which legitimately emits
        # nothing and must never be refunded.
        # #1273: the extraction FALLBACK is not an emission. A repair that returns prose
        # and no fenced block produces one non-empty `repair_output.md` — which counted as
        # content, so the round was spent rather than refunded, and the loop then
        # terminated as `unverifiable` for a file that was never written (Next.js roll 1,
        # cyc_9be98128f0e9). "Did the repair emit a FILE" is the question; the marker the
        # extractor stamps is the answer.
        emission_empty = repair_steps_ran and not any(
            str(a.get("content") or "").strip()
            for a in repair_artifacts
            if isinstance(a, dict) and not a.get("emission_fallback")
        )
        if emission_empty:
            logger.warning(
                "correction: repair emitted no content on attempt %d (%d artifact(s), all "
                "empty; signature %s) — the round produced nothing to verify (#1053, #998)",
                correction_attempts,
                len(repair_artifacts),
                ", ".join(empty_signatures) or "unreported",
            )
        return emission_empty
