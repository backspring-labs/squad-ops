"""The brownfield reference scenario (SIP-0109 §11a; #1804).

A fixed baseline — a stored, accepted group_run tree — and a fixed typed change request, both
pinned by hash, built by one increment cycle with no gate: the request is pre-approved and recorded
as such. It is the yardstick the calibration cycle cannot be: the same change every time, so delta
framing, scoped repair, accumulated acceptance and baseline discrimination are comparable across
framework changes.

This module is the pure half: from the baseline's manifest and tree identity and the authored
change request, the three seeds an increment's framing and implementation bind to — the stored
change request, the candidate manifest and the contract derived from it — exactly what an approved
increment gate stores (#1840), and the ``campaign_proposal`` block the cycle carries.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from squadops.campaigns.change_request import (
    ProposalContext,
    apply_manifest_delta,
    stored_change_request,
    validate_proposal,
)
from squadops.cycles.contract_derivation import derive_contract_bytes

#: The scenario's proposal identity: one request, one version, every time.
REFERENCE_PROPOSAL_ID = "ref_capacity_limit"


class ReferenceDrift(ValueError):
    """An input no longer hashes to its pin: the scenario would measure something else."""


@dataclass(frozen=True)
class ReferenceIncrement:
    change_request: str
    candidate_manifest: str
    contract: bytes

    @property
    def pins(self) -> dict[str, str]:
        return {
            "change_request": _sha(self.change_request),
            "candidate_manifest": _sha(self.candidate_manifest),
        }


def reference_increment(
    authored: Mapping[str, Any],
    *,
    baseline_manifest: str,
    baseline_tree: str,
    stack: str,
    allowed_scope: tuple[str, ...],
) -> ReferenceIncrement:
    """The seeds of the reference increment, through the proposal's own rails: a request the
    rails refuse is refused here too, with every refusal named."""
    verdict = validate_proposal(
        dict(authored),
        ProposalContext(
            REFERENCE_PROPOSAL_ID,
            1,
            baseline_tree,
            baseline_manifest,
            stack,
            tuple(allowed_scope),
            (),
        ),
    )
    if verdict.change_request is None:
        raise ValueError(
            "the reference change request no longer passes the proposal's rails: "
            + "; ".join(f"{r.kind}: {r.detail}" for r in verdict.refusals)
        )
    candidate = apply_manifest_delta(baseline_manifest, verdict.change_request.manifest_delta)
    return ReferenceIncrement(
        change_request=stored_change_request(verdict.change_request),
        candidate_manifest=candidate,
        contract=derive_contract_bytes(candidate),
    )


def check_pins(actual: Mapping[str, str], pinned: Mapping[str, str]) -> None:
    """Refuse a scenario whose inputs moved: a different baseline or change request is a
    different measurement, never the yardstick."""
    drift = sorted(k for k in pinned if actual.get(k) != pinned[k])
    missing = sorted(k for k in actual if k not in pinned)
    if drift or missing:
        raise ReferenceDrift(
            "the reference scenario's inputs moved from their pins: "
            + ", ".join(f"{k} {actual.get(k)} != {pinned.get(k)}" for k in drift)
            + (f"; unpinned: {', '.join(missing)}" if missing else "")
        )


def reference_proposal_block(
    *, baseline_tree: str, accepted_cycle_id: str, baseline_manifest: str, objective: Mapping
) -> dict[str, Any]:
    """The ``campaign_proposal`` block the reference cycle carries: the same keys a campaign's
    increment launch writes (``launch_requests.increment_launch``), so every increment seam reads
    it the same way. No revisions: the request is pre-approved."""
    return {
        "proposal_id": REFERENCE_PROPOSAL_ID,
        "version": 1,
        "baseline_tree": baseline_tree,
        "accepted_cycle_id": accepted_cycle_id,
        "baseline_manifest": baseline_manifest,
        "objective": dict(objective),
        "prior_criteria": [],
        "frozen_criteria": [],
        "max_revisions": 0,
    }


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
