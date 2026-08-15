"""The scaffold evidence pipeline — SIP-0104 P5 (Gate 5).

Kept explicit and separate, exactly as the plan states it::

    observation → classification → correlation → owner → repair route

- **Observation**: the runner's per-failure rows (``RunTestsResult.test_failures``), the
  merged shell contents, the scaffold manifest record, and the fill-merge dispositions.
- **Classification** lands every scaffold-shell failure in one of the SIP §5 classes:
  ``scaffold_invalid`` / ``app_contract`` / ``fill`` / ``test_infrastructure``. The
  attribution logic is line-based against the *merged* file's parsed slot regions: a
  failure inside a slot body belongs to the fill layer; a failure on the spine is the
  frozen contract assertion firing against the app. A mechanical death of a shell whose
  only mutable bytes came from a fill is the fill's; one with no fill merged is the
  generator's (a new uncovered surface — the P6 window rule's subject).
- **Correlation, not causal equivalence**: a shell failure and a probe failure sharing a
  criterion id are *grouped* for the router — both observations retained, never
  auto-collapsed into one, and different criterion ids are never auto-merged. The router
  deduplicates rounds on the shared criterion, not on either observation alone.
- **Ownership is assigned from classification; routing consumes ownership** — both are
  data (``CLASS_OWNERS`` / ``CLASS_ROUTES``), so P5's pipeline stays inspectable and the
  locus consult (:mod:`failure_evidence`) reads the class summary, never re-derives it.

Non-shell failures (additive tests, the harness proof) are deliberately outside this
pipeline: their semantics are owned by the existing suite-health machinery, and
``tests_pass`` credit semantics are untouched (SIP-0096, SIP §10.5).

The summary schema carries the fields the future promotion model needs (SIP §6/§12:
slot/category, assertion provenance, unique-vs-probe-redundant findings, defect class,
cycle/stack identity) — **schema preserved, workflow not built**.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# The SIP §5 failure classes.
CLASS_SCAFFOLD_INVALID = "scaffold_invalid"
CLASS_APP_CONTRACT = "app_contract"
CLASS_FILL = "fill"
CLASS_INFRASTRUCTURE = "test_infrastructure"

#: class → who can act on it (ownership is assigned from classification).
CLASS_OWNERS: dict[str, str] = {
    CLASS_SCAFFOLD_INVALID: "scaffold_generator",
    CLASS_APP_CONTRACT: "dev",
    CLASS_FILL: "qa",
    CLASS_INFRASTRUCTURE: "environment",
}

#: class → repair route (routing consumes ownership). ``scaffold_invalid`` at suite time
#: means the pre-run gates missed a surface — never an LLM round; the P6 window protocol
#: names it and it joins the enforced set.
CLASS_ROUTES: dict[str, str] = {
    CLASS_SCAFFOLD_INVALID: "name_uncovered_surface_no_llm_round",
    CLASS_APP_CONTRACT: "dev_repair",
    CLASS_FILL: "qa_repair_slot_scoped",
    CLASS_INFRASTRUCTURE: "environment_triage",
}


@dataclass(frozen=True)
class ShellObservation:
    """One classified scaffold-shell failure — the pipeline's atom.

    ``criterion_id`` is the bound probe id for spine (app-contract) failures — the join
    key correlation groups on; empty for fill-layer and generator-layer observations.
    """

    file: str
    slot_id: str
    failure_class: str
    detail: str = ""
    criterion_id: str = ""
    line: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "file": self.file,
            "slot_id": self.slot_id,
            "failure_class": self.failure_class,
            "detail": self.detail,
            "criterion_id": self.criterion_id,
            "line": self.line,
            "owner": CLASS_OWNERS[self.failure_class],
            "route": CLASS_ROUTES[self.failure_class],
        }


def classify_shell_failures(
    test_failures: list[dict],
    merged_contents: dict[str, str],
    scaffold_manifest: Any,
    fill_dispositions: dict[str, str],
    *,
    runner_executed: bool = True,
) -> list[ShellObservation]:
    """Classify every scaffold-shell failure among the runner's observation rows.

    Rows for non-shell files pass through unclassified (the existing machinery owns
    them). Ambiguity falls toward ``app_contract`` — the dev/subject direction, the same
    conservative side the test-gaming guard has always chosen: a misroute there costs a
    dev round; a misroute toward qa invites the suite to be rewritten to agree with a
    broken app.
    """
    from squadops.capabilities.handlers.scaffold_execution import _is_assertion_failure
    from squadops.capabilities.verification_scaffold import ScaffoldSpineError, parse_slot_regions

    shell_records = {f.path: f for f in scaffold_manifest.files}
    if not runner_executed:
        return [
            ShellObservation(
                file="",
                slot_id="",
                failure_class=CLASS_INFRASTRUCTURE,
                detail="the runner could not execute the suite — environment triage, "
                "not a work-product round",
            )
        ]

    observations: list[ShellObservation] = []
    for row in test_failures:
        path = str(row.get("file", ""))
        record = shell_records.get(path)
        if record is None:
            continue  # additive tests / harness: existing semantics own these
        slots = list(record.slots)
        primary_slot = slots[0] if slots else None
        slot_id = primary_slot.slot_id if primary_slot else ""
        filled = any(fill_dispositions.get(s.slot_id) == "filled" for s in slots)
        messages = [str(m) for m in (row.get("messages") or [])]

        if row.get("suite_level") or not _is_assertion_failure(messages):
            # Mechanical death. The only mutable bytes in a shell are merged fill
            # bodies: if one was merged, the fill is the variable; if none, the spine
            # itself failed to execute — a generator surface the gates missed.
            detail = messages[0][:400] if messages else "mechanical failure"
            if filled:
                observations.append(
                    ShellObservation(
                        file=path,
                        slot_id=slot_id,
                        failure_class=CLASS_FILL,
                        detail=f"merged fill broke the shell mechanically: {detail}",
                        line=row.get("line"),
                    )
                )
            else:
                observations.append(
                    ShellObservation(
                        file=path,
                        slot_id=slot_id,
                        failure_class=CLASS_SCAFFOLD_INVALID,
                        detail=f"shell with no merged fill died mechanically — a new "
                        f"uncovered generator surface: {detail}",
                        line=row.get("line"),
                    )
                )
            continue

        # Assertion failure: attribute by line against the MERGED file's regions.
        line = row.get("line")
        in_slot = None
        content = merged_contents.get(path)
        if content is not None and isinstance(line, int):
            try:
                for region in parse_slot_regions(content):
                    if region.begin_line < line < region.end_line:
                        in_slot = region.slot_id
                        break
            except ScaffoldSpineError:
                in_slot = None  # unparseable merged content → conservative (spine)
        if in_slot is not None:
            disposition = fill_dispositions.get(in_slot, "")
            observations.append(
                ShellObservation(
                    file=path,
                    slot_id=in_slot,
                    failure_class=CLASS_FILL,
                    detail=(
                        f"slot disposition {disposition or 'filled'}: "
                        f"{messages[0][:400] if messages else 'assertion failed'}"
                    ),
                    line=line,
                )
            )
        else:
            slot_for_criterion = primary_slot
            observations.append(
                ShellObservation(
                    file=path,
                    slot_id=slot_id,
                    failure_class=CLASS_APP_CONTRACT,
                    detail=messages[0][:400] if messages else "spine assertion failed",
                    criterion_id=(slot_for_criterion.probe_id if slot_for_criterion else ""),
                    line=line,
                )
            )
    return observations


@dataclass(frozen=True)
class CorrelatedFinding:
    """One criterion's grouped observations — the router's dedup unit.

    Grouped, never collapsed: both observation lists are retained in full. A finding
    with both sides is ONE defect observed twice (the §5 dedup rule); a finding with
    only shell observations is a scaffold-only detection; probe-only findings are the
    probe layer's existing business and not manufactured here.
    """

    criterion_id: str
    shell_observations: tuple[ShellObservation, ...] = ()
    probe_failures: tuple[dict, ...] = ()

    @property
    def probe_redundant(self) -> bool:
        return bool(self.shell_observations) and bool(self.probe_failures)

    def to_dict(self) -> dict[str, Any]:
        return {
            "criterion_id": self.criterion_id,
            "shell_observations": [o.to_dict() for o in self.shell_observations],
            "probe_failures": list(self.probe_failures),
            "probe_redundant": self.probe_redundant,
        }


def correlate(
    observations: list[ShellObservation], probe_rows: list[dict]
) -> list[CorrelatedFinding]:
    """Group shell and probe failures by shared criterion id — correlation only.

    Different criterion ids are never merged; observations without a criterion id
    (fill/generator/infrastructure classes) are never pulled into a finding.
    """
    from squadops.cycles.verification_integrity import ResultStatus

    # Probe rows speak ResultStatus (probe_runner emits its literals) — compare against
    # the owning vocabulary, never raw strings (#380).
    failing_statuses = {ResultStatus.FAILED, ResultStatus.ERROR}
    failed_probe_rows = [
        row
        for row in probe_rows
        if isinstance(row, dict)
        and row.get("criterion_id")
        and str(row.get("status", "")).lower() in failing_statuses
    ]
    by_criterion: dict[str, CorrelatedFinding] = {}
    for observation in observations:
        if not observation.criterion_id:
            continue
        existing = by_criterion.get(observation.criterion_id)
        shells = (existing.shell_observations if existing else ()) + (observation,)
        probes = existing.probe_failures if existing else ()
        by_criterion[observation.criterion_id] = CorrelatedFinding(
            criterion_id=observation.criterion_id,
            shell_observations=shells,
            probe_failures=probes,
        )
    for row in failed_probe_rows:
        criterion_id = str(row["criterion_id"])
        existing = by_criterion.get(criterion_id)
        if existing is None:
            continue  # probe-only failures stay the probe layer's business
        by_criterion[criterion_id] = CorrelatedFinding(
            criterion_id=criterion_id,
            shell_observations=existing.shell_observations,
            probe_failures=existing.probe_failures + (row,),
        )
    return [by_criterion[k] for k in sorted(by_criterion)]


@dataclass(frozen=True)
class ScaffoldEvidenceSummary:
    """The run-report record — the fields the future promotion model needs (SIP §6/§12).

    Schema preserved, workflow not built: nothing consumes these counts to promote or
    demote anything yet; they exist so the evidence is being banked from the first roll.
    """

    stack: str
    generator_version: int
    shell_count: int
    slot_count: int
    fill_dispositions: dict[str, int]
    additive_test_count: int
    failure_classes: dict[str, int]
    #: Authored suites the runner never collected — additive work that verified nothing
    #: (SIP-0104 roll 1). Banked beside the counts because §6's "is the authored layer
    #: earning its inference spend" question is unanswerable if part of that layer
    #: silently never ran.
    uncollected_test_files: tuple[str, ...] = ()
    observations: tuple[ShellObservation, ...] = ()
    correlations: tuple[CorrelatedFinding, ...] = ()

    @property
    def uncorrelated_fill_failures(self) -> int:
        """Fill-layer failures with no probe echo — the authored layer's unique-signal
        candidates (§6's 'failures detected only by fills', pending human reading)."""
        return sum(1 for o in self.observations if o.failure_class == CLASS_FILL)

    @property
    def probe_redundant_findings(self) -> int:
        return sum(1 for c in self.correlations if c.probe_redundant)

    def to_dict(self) -> dict[str, Any]:
        return {
            "stack": self.stack,
            "generator_version": self.generator_version,
            "shell_count": self.shell_count,
            "slot_count": self.slot_count,
            "fill_dispositions": dict(self.fill_dispositions),
            "additive_test_count": self.additive_test_count,
            "uncollected_test_files": list(self.uncollected_test_files),
            "failure_classes": dict(self.failure_classes),
            "uncorrelated_fill_failures": self.uncorrelated_fill_failures,
            "probe_redundant_findings": self.probe_redundant_findings,
            "observations": [o.to_dict() for o in self.observations],
            "correlations": [c.to_dict() for c in self.correlations],
        }


def build_scaffold_evidence_summary(
    scaffold_manifest: Any,
    fill_dispositions: dict[str, str],
    observations: list[ShellObservation],
    correlations: list[CorrelatedFinding],
    additive_test_count: int,
    uncollected_test_files: tuple[str, ...] = (),
) -> ScaffoldEvidenceSummary:
    disposition_counts: dict[str, int] = {}
    for disposition in fill_dispositions.values():
        disposition_counts[disposition] = disposition_counts.get(disposition, 0) + 1
    class_counts: dict[str, int] = {}
    for observation in observations:
        class_counts[observation.failure_class] = class_counts.get(observation.failure_class, 0) + 1
    return ScaffoldEvidenceSummary(
        stack=scaffold_manifest.stack,
        generator_version=scaffold_manifest.generator_version,
        shell_count=len(scaffold_manifest.files),
        slot_count=len(scaffold_manifest.slot_ids()),
        fill_dispositions=disposition_counts,
        additive_test_count=additive_test_count,
        failure_classes=class_counts,
        uncollected_test_files=tuple(uncollected_test_files),
        observations=tuple(observations),
        correlations=tuple(correlations),
    )
