"""The pre-memory rejection baseline (#809, B1).

Cross-Cycle Memory's value claim is that recurrence of the same mistake falls. Testing that
needs a picture of how often each class of mistake happens **before memory exists** — and the
moment memory is live, the pre-memory picture is gone. Nothing in 1.6 reads what this module
records; that is deliberate. It is written now because it cannot be written later.

**What is impossible afterwards is the data, not the report.** So the work here is making the
inputs durable and classified at the moment they occur; the aggregation is arithmetic that can
run at any time, including retrospectively over cycles already completed. Three of the four
inputs already existed when this landed:

===========================  ====================================================
 authoring failure classes    M5's manifest ``provenance.revisions[].classes``
 attempts consumed            M5's ``provenance.attempts``
 framing re-rolls consumed    one framing run per re-roll — count them
 plan-validation classes      **this module** — nothing recorded them before
===========================  ====================================================

The fourth is the gap this closes. A rejected plan recorded *what* went wrong as a joined
error string and never *which class*, and re-parsing prose at window time is the failure mode
the plan warns against ("one vocabulary, not a free-text field that each reader parses
differently"), not the fix.

Two dimensions, because memory can improve either: **recurrence** (how often a class occurs)
and **time-to-resolution** (attempts and re-rolls burned before it cleared). A memory
implementation that halves recovery cost without changing recurrence is a real win that a
recurrence-only baseline would score as zero.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

#: Artifact type for a recorded rejection. Its own type rather than a ``document`` so the
#: deriver can select it without reading content, and so it never lands in the plan-artifact
#: forwarding set (which keys on type).
REJECTION_ARTIFACT_TYPE = "rejection_record"
REJECTION_FILENAME = "rejection_record.json"


@dataclass
class RejectionClassifier:
    """Accumulates which validator rejected a plan, at the moment it does.

    The gate calls its validators one at a time, so the producing validator is known exactly
    where the errors are collected — no validator signature changes, no error tagging, and no
    prose to parse back. The names are ``ImplementationPlan.validate_*``, which is the same
    vocabulary ``plan_authoring_rules`` keys on and therefore the same one the authoring-rules
    asset teaches. A baseline that spoke different names than the authors are taught would
    make "did teaching this rule reduce it?" unanswerable.
    """

    classes: dict[str, int] = field(default_factory=dict)

    def collect(self, validator: str, errors: list[str]) -> list[str]:
        """Record ``errors`` under ``validator`` and return them unchanged.

        Pass-through by design: it wraps an existing ``errors.extend(...)`` without changing
        what is collected or the order it is collected in, so a classification bug can never
        alter which plans are rejected.
        """
        if errors:
            self.classes[validator] = self.classes.get(validator, 0) + len(errors)
        return errors

    def record(self, gate_name: str, errors: list[str]) -> dict[str, Any]:
        """The artifact payload for a rejection, or ``{}`` when nothing was rejected."""
        if not errors:
            return {}
        return {
            "gate": gate_name,
            "classes": dict(sorted(self.classes.items())),
            "errors": list(errors),
        }


@dataclass(frozen=True)
class ClassBaseline:
    """One rejection class, and what it cost before it cleared."""

    rejection_class: str
    occurrences: int
    #: Authoring attempts consumed in the cycle. Whole-cycle rather than per-class: the
    #: authoring loop revises against every finding at once, so attributing an attempt to one
    #: class among several would be an invention.
    attempts: int
    #: Framing re-rolls consumed in the cycle, on the same whole-cycle basis.
    rerolls: int


@dataclass(frozen=True)
class CycleBaseline:
    """A cycle's rejection classes across both dimensions."""

    cycle_id: str
    classes: tuple[ClassBaseline, ...] = ()
    attempts: int = 0
    rerolls: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "attempts": self.attempts,
            "rerolls": self.rerolls,
            "classes": [
                {
                    "class": c.rejection_class,
                    "occurrences": c.occurrences,
                    "attempts": c.attempts,
                    "rerolls": c.rerolls,
                }
                for c in self.classes
            ],
        }


def build_baseline(
    cycle_id: str,
    *,
    rejection_records: list[dict[str, Any]],
    manifest_provenance: dict[str, Any] | None,
    framing_run_count: int,
) -> CycleBaseline:
    """Assemble one cycle's baseline from durable inputs.

    Pure arithmetic over stored facts — no vault, no registry, no cycle state. That is what
    makes the baseline reconstructible later: the caller supplies what it read, and this
    decides nothing it cannot see.

    ``framing_run_count`` yields re-rolls as ``count - 1``: the sequence creates exactly one
    additional framing run per re-roll, so the runs *are* the record and nothing extra had to
    be persisted to count them.
    """
    counts: dict[str, int] = {}
    for record in rejection_records:
        for name, n in (record.get("classes") or {}).items():
            counts[str(name)] = counts.get(str(name), 0) + int(n)

    provenance = manifest_provenance or {}
    for revision in provenance.get("revisions") or []:
        for name, n in (revision.get("classes") or {}).items():
            counts[str(name)] = counts.get(str(name), 0) + int(n)

    attempts = int(provenance.get("attempts", 0) or 0)
    rerolls = max(0, framing_run_count - 1)
    return CycleBaseline(
        cycle_id=cycle_id,
        attempts=attempts,
        rerolls=rerolls,
        classes=tuple(
            ClassBaseline(rejection_class=name, occurrences=n, attempts=attempts, rerolls=rerolls)
            for name, n in sorted(counts.items())
        ),
    )


def render(baselines: list[CycleBaseline]) -> str:
    """The baseline as JSON — the shape 1.8 reads, and nothing in 1.6 does."""
    return json.dumps(
        {
            "schema": 1,
            "purpose": (
                "pre-memory rejection-class baseline (#809, B1) — recurrence and "
                "time-to-resolution per cycle, captured before Cross-Cycle Memory exists"
            ),
            "cycles": [b.to_dict() for b in baselines],
        },
        indent=2,
        sort_keys=False,
    )
