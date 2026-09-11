#!/usr/bin/env python3
"""Framework smoke — do the pipeline's invariants hold, whatever the run's verdict (#176).

The crux, and the reason this exists rather than a status check: **assert on framework
invariants, not on the run reaching ``completed``.** Small models reliably exercise the
plumbing and cannot clear content-quality gates — a 7b builder under-produces and the
output validator correctly rejects it. A smoke harness keyed on terminal status is
therefore a false-negative generator on exactly the squads cheap enough to gate merges
with, and it reports "the framework is broken" when the framework worked perfectly.

The reference case is `cyc_02682aa4efa2` (lite/7b, builder-assemble, play_game,
2026-06-14): terminal status FAILED, every invariant held. Its artifact references are
committed at `tests/fixtures/framework_smoke/` and are what the unit tests assert against
— the harness is validated on a real cycle's stored state, not on invented fixtures.

Two recipes, per #176:

1. **Invariant smoke** — `lite`/`builder-assemble`. PASS = the invariants below hold;
   terminal status is out of scope. Covers the full pipeline including the build path and
   the correction loop. This is the primary framework smoke.
2. **Terminal-status smoke** — `smoke` (3b) + `hello_squad` + `selftest`. A trivial path
   small models *can* finish, so it asserts reaching `completed` for an unambiguous
   baseline green. Does not exercise `builder.assemble`.

Usage:

    python scripts/dev/framework_smoke.py --project play_game --cycle cyc_02682aa4efa2
    python scripts/dev/framework_smoke.py --refs path/to/artifact_refs.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

#: The roles a framing sequence must each leave an artifact for. Read off what the task
#: types produced rather than off a role list, because "five roles ran" and "five roles
#: each authored their artifact" are different claims and only the second is the
#: invariant — a role that dispatched and emitted nothing is the failure this catches.
FRAMING_TASK_TYPES: tuple[str, ...] = (
    "strategy.analyze_prd",
    "data.report",
    "development.design",
    "qa.validate",
    "governance.review",
)

#: The correction protocol's own three steps, in order. All three, because the loop is
#: only observable end-to-end: an analysis with no decision is a chain that died, and a
#: decision with no plan delta is one whose reasoning was never banked.
CORRECTION_TASK_TYPES: tuple[str, ...] = (
    "data.analyze_failure",
    "governance.correction_decision",
)

#: The plan delta is stored by the runner rather than by a task, so it carries no
#: producing task type and is identified by artifact type.
PLAN_DELTA_TYPE = "plan_delta"


@dataclass(frozen=True)
class Invariant:
    """One machine-checked pipeline invariant, and what it saw.

    ``detail`` is not decoration. The whole point of #176 is that this replaces a human
    reading a run and deciding it looked fine, so a failing invariant has to say what it
    found — "3 of 5 framing artifacts" is actionable, "FAIL" is not.
    """

    name: str
    held: bool
    detail: str

    def __str__(self) -> str:
        return f"{'PASS' if self.held else 'FAIL'}  {self.name}  — {self.detail}"


def _producing_task_types(refs: Iterable[Mapping[str, Any]]) -> list[str]:
    return [
        str((ref.get("metadata") or {}).get("producing_task_type") or "")
        for ref in refs
        if isinstance(ref, Mapping)
    ]


def multi_role_framing(refs: Sequence[Mapping[str, Any]]) -> Invariant:
    """Every framing stage left an artifact behind.

    Catches the shape where a role dispatches, the model answers, and nothing is stored —
    the run continues and the next stage frames against a gap it cannot see.
    """
    produced = set(_producing_task_types(refs))
    missing = [t for t in FRAMING_TASK_TYPES if t not in produced]
    return Invariant(
        "multi-role framing: every stage authored its artifact",
        not missing,
        f"{len(FRAMING_TASK_TYPES) - len(missing)} of {len(FRAMING_TASK_TYPES)}"
        + (f"; missing {', '.join(missing)}" if missing else ""),
    )


def develop_to_assemble_handoff(refs: Sequence[Mapping[str, Any]]) -> Invariant:
    """The dev stage delivered source for the builder to assemble.

    Keyed on the producing task type and the artifact type together: a `development.develop`
    that emitted only a `build_warnings.md` document has run and delivered nothing, which
    is the #998 contentless shape and reads identically to success if you count tasks.
    """
    source = [
        ref
        for ref in refs
        if (ref.get("metadata") or {}).get("producing_task_type") == "development.develop"
        and ref.get("artifact_type") == "source"
    ]
    return Invariant(
        "develop → assemble handoff: source was delivered",
        bool(source),
        f"{len(source)} source file(s)"
        + (f": {', '.join(sorted(str(r.get('filename')) for r in source)[:4])}" if source else ""),
    )


def correction_loop_fired(refs: Sequence[Mapping[str, Any]]) -> Invariant:
    """The SIP-0086 correction loop ran end to end and banked its reasoning.

    Analysis → decision → plan delta. An analysis with no decision is a chain that died
    mid-protocol; a decision with no delta is one whose reasoning was never stored, which
    is what makes the next round re-derive the failure blind (#870).

    Absent entirely is reported, not failed: a run that never failed a task has no
    correction loop to fire, and calling that a broken framework would be the
    false-negative this harness exists to avoid.
    """
    produced = set(_producing_task_types(refs))
    steps = [t for t in CORRECTION_TASK_TYPES if t in produced]
    delta = [r for r in refs if r.get("artifact_type") == PLAN_DELTA_TYPE]
    if not steps and not delta:
        return Invariant(
            "correction loop: fired end to end",
            True,
            "no correction was triggered — no task failed (not exercised)",
        )
    complete = len(steps) == len(CORRECTION_TASK_TYPES) and bool(delta)
    return Invariant(
        "correction loop: fired end to end",
        complete,
        f"{len(steps)} of {len(CORRECTION_TASK_TYPES)} protocol step(s), "
        f"{len(delta)} plan delta(s)",
    )


#: Artifacts the RUNNER stores rather than a task: the correction protocol's plan delta
#: and the end-of-run report. They carry no ``task_id`` because no task produced them, and
#: a provenance rule that demanded one would fail a perfectly healthy cycle — which the
#: reference corpus proved on this function's first run, before it was narrowed.
RUNNER_OWNED_TYPES: tuple[str, ...] = (PLAN_DELTA_TYPE,)
RUNNER_OWNED_REPORTS: tuple[str, ...] = ("run_report",)


def _is_runner_owned(ref: Mapping[str, Any]) -> bool:
    metadata = ref.get("metadata") or {}
    return (
        ref.get("artifact_type") in RUNNER_OWNED_TYPES
        or metadata.get("report_type") in RUNNER_OWNED_REPORTS
    )


def artifacts_persisted(refs: Sequence[Mapping[str, Any]], *, minimum: int = 1) -> Invariant:
    """The run's work reached the vault, with the provenance a reader needs.

    Every **task-produced** artifact must name the task that produced it. One whose
    producer is unknown cannot be attributed, superseded per ``(check_id, subject)``, or
    used to tell a repair's files from the failed attempt's — the #1264 class.

    Runner-owned artifacts are exempt by identity, not by silence: the plan delta and the
    run report are stored by the runner and by construction have no producing task. That
    carve-out was not designed, it was **found** — the first run of this function against
    the reference corpus failed a cycle whose every invariant held, which is precisely the
    false negative #176 exists to avoid, one level down.
    """
    unattributed = [
        str(ref.get("artifact_id"))
        for ref in refs
        if not (ref.get("metadata") or {}).get("task_id") and not _is_runner_owned(ref)
    ]
    return Invariant(
        "artifacts persisted with their provenance",
        len(refs) >= minimum and not unattributed,
        f"{len(refs)} artifact(s)"
        + (f"; {len(unattributed)} name no producing task" if unattributed else ""),
    )


def check_all(refs: Sequence[Mapping[str, Any]]) -> list[Invariant]:
    """Every artifact-derivable invariant, in pipeline order."""
    return [
        multi_role_framing(refs),
        develop_to_assemble_handoff(refs),
        correction_loop_fired(refs),
        artifacts_persisted(refs),
    ]


def load_refs_from_vault(vault: Path, project: str, cycle_id: str) -> list[dict[str, Any]]:
    """Every artifact reference a cycle stored, read from the filesystem vault.

    Across runs, because a resumed or re-run cycle spreads its artifacts over more than
    one run directory and the invariants are about the cycle.
    """
    root = vault / project / cycle_id
    if not root.is_dir():
        raise SystemExit(f"no such cycle in the vault: {root}")
    return [json.loads(p.read_text()) for p in sorted(root.glob("*/*/metadata.json"))]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--project")
    parser.add_argument("--cycle")
    parser.add_argument("--vault", default="data/artifacts", type=Path)
    parser.add_argument("--refs", type=Path, help="a captured artifact_refs.json instead")
    args = parser.parse_args(argv)

    if args.refs:
        refs = json.loads(args.refs.read_text())
    elif args.project and args.cycle:
        refs = load_refs_from_vault(args.vault, args.project, args.cycle)
    else:
        parser.error("give --refs, or both --project and --cycle")

    results = check_all(refs)
    for result in results:
        print(result)
    failed = [r for r in results if not r.held]
    print()
    print(
        f"{len(results) - len(failed)} of {len(results)} invariants held. "
        "Terminal run status is deliberately not among them (#176)."
    )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
