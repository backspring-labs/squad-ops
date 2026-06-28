"""MergeDecisions — auditable record of `governance.merge_plan` (SIP-0093 §5.7).

The merger produces two artifacts: ``implementation_plan.yaml`` (the canonical
plan, SIP-0092 M1 schema unchanged) and ``merge_decisions.yaml``. This module
defines the on-the-wire shape of the latter so the merger isn't a new opaque
sole broker — every canonical task carries provenance back to the proposals it
came from, every brief conflict gets a recorded disposition, and the
authoring-mode invariants from RC-26 are enforced at parse time.

RC-26 invariants (enforced by ``MergeDecisions.from_yaml()``):

- ``authoring_mode == "multi_role"`` ⇒ ``sole_author_reason is None`` AND
  ``proposal_completeness in {"complete", "partial"}``.
- ``authoring_mode == "sole_author"`` ⇒ ``sole_author_reason in
  {"no_contributors_configured", "all_proposals_failed"}`` AND
  ``proposal_completeness == "sole_author"``.

Asserting these at the parser level means downstream consumers (gate
package, observability, M3 plan-change applier) can trust the combination
without re-checking.
"""

from __future__ import annotations

from dataclasses import dataclass

import yaml

_VALID_AUTHORING_MODES = frozenset({"multi_role", "sole_author"})
_VALID_SOLE_AUTHOR_REASONS = frozenset({"no_contributors_configured", "all_proposals_failed"})
_VALID_PROPOSAL_COMPLETENESS = frozenset({"complete", "partial", "sole_author"})
_VALID_MERGE_ACTIONS = frozenset({"accepted", "merged", "modified", "gap_filled"})
_VALID_BRIEF_CONFLICT_SEVERITIES = frozenset({"warning", "blocking"})
_VALID_CONFLICT_DISPOSITIONS = frozenset({"accepted", "rejected", "escalated_to_operator"})


@dataclass(frozen=True)
class CanonicalTaskProvenance:
    """Per-canonical-task lineage from proposed tasks to merger output.

    Attributes:
        task_index: the canonical 0..N index in ``implementation_plan.yaml``.
        source_proposal_task_keys: focus_keys (``{role}:{focus}``) of the
            proposed tasks that contributed to this canonical task.
        proposed_by: role IDs that proposed any of the source tasks.
        merge_action:
            ``accepted`` — copied through from a single proposed task.
            ``merged`` — combined from multiple compatible proposed tasks
                (e.g. dev + qa proposed overlapping acceptance criteria).
            ``modified`` — the merger materially changed the proposed task
                (renamed, restructured, retyped) — reason must explain.
            ``gap_filled`` — the merger added this canonical task because
                a proposal referenced it but no proposal proposed it.
        reason: human-readable explanation of the merge decision; surfaces
            in the gate package and the operator console.
    """

    task_index: int
    source_proposal_task_keys: list[str]
    proposed_by: list[str]
    merge_action: str
    reason: str


@dataclass(frozen=True)
class BriefConflictDisposition:
    """How the merger handled a single proposer-raised brief conflict (§5.5).

    Attributes:
        brief_field: brief field the conflict targets.
        severity: ``warning`` (merger resolves) or ``blocking`` (escalated).
        disposition:
            ``accepted`` — merger sided with the proposer; brief value
                overridden in this cycle's canonical plan.
            ``rejected`` — merger sided with the brief.
            ``escalated_to_operator`` — surfaced in ``operator_notes`` for
                gate decision (always the disposition for ``blocking``
                conflicts under Rev 1).
        reason: why this disposition.
    """

    brief_field: str
    severity: str
    disposition: str
    reason: str


@dataclass(frozen=True)
class MissingProposal:
    """A role's proposal that was expected but missing or failed (§5.7).

    Attributes:
        role: role ID (``development``, ``qa``, ``strategy``, ``builder``).
        failure_reason: short tag explaining why — typically one of
            ``not_run``, ``llm_error``, ``timeout``, ``malformed_yaml``,
            ``mismatched_brief_id``. Free-form string at the parser level;
            proposer-handlers (PR 93.2) will adopt a convention.
    """

    role: str
    failure_reason: str


@dataclass(frozen=True)
class MergeDecisions:
    """Structured audit of how the canonical plan was assembled.

    Required Rev 1 fields (per SIP-0093 §5.7) cover provenance, completeness,
    and conflict disposition. The optional ``operator_notes`` is the surface
    where blocking brief conflicts and other operator-relevant context get
    free-form prose — kept optional so a cycle with no operator-facing
    issues doesn't need to emit it.
    """

    version: int
    target_plan_id: str
    brief_id: str
    proposal_ids: list[str]
    guidance_ids: list[str]
    authoring_mode: str
    sole_author_reason: str | None
    proposal_completeness: str
    missing_proposals: list[MissingProposal]
    canonical_tasks: list[CanonicalTaskProvenance]
    brief_conflicts_disposition: list[BriefConflictDisposition]
    operator_notes: str = ""

    @classmethod
    def from_yaml(cls, content: str) -> MergeDecisions:
        """Parse a ``merge_decisions.yaml`` document.

        Raises:
            ValueError: malformed YAML, missing required fields, invalid
                enum values, RC-26 invariant violation, or canonical task
                indices that aren't unique-and-contiguous from 0.
        """
        try:
            data = yaml.safe_load(content)
        except yaml.YAMLError as exc:
            raise ValueError(f"Malformed merge_decisions YAML: {exc}") from exc

        if not isinstance(data, dict):
            raise ValueError("merge_decisions must be a YAML mapping at the top level")

        for key in (
            "version",
            "target_plan_id",
            "brief_id",
            "authoring_mode",
            "proposal_completeness",
        ):
            if key not in data:
                raise ValueError(f"merge_decisions missing required field: {key}")

        version = data["version"]
        if not isinstance(version, int):
            raise ValueError(f"merge_decisions version must be int, got {type(version).__name__}")

        target_plan_id = str(data["target_plan_id"]).strip()
        brief_id = str(data["brief_id"]).strip()
        if not target_plan_id:
            raise ValueError("merge_decisions target_plan_id must be non-empty")
        if not brief_id:
            raise ValueError("merge_decisions brief_id must be non-empty")

        authoring_mode = _validate_enum(
            data["authoring_mode"], _VALID_AUTHORING_MODES, "authoring_mode"
        )
        proposal_completeness = _validate_enum(
            data["proposal_completeness"],
            _VALID_PROPOSAL_COMPLETENESS,
            "proposal_completeness",
        )

        raw_sole_author_reason = data.get("sole_author_reason", None)
        if raw_sole_author_reason is None:
            sole_author_reason: str | None = None
        else:
            sole_author_reason = _validate_enum(
                raw_sole_author_reason,
                _VALID_SOLE_AUTHOR_REASONS,
                "sole_author_reason",
            )

        _validate_rc26(authoring_mode, sole_author_reason, proposal_completeness)

        proposal_ids = _parse_str_list(data.get("proposal_ids", []), "proposal_ids")
        guidance_ids = _parse_str_list(data.get("guidance_ids", []), "guidance_ids")
        missing_proposals = _parse_missing_proposals(data.get("missing_proposals", []))
        canonical_tasks = _parse_canonical_tasks(data.get("canonical_tasks", []))
        brief_conflicts_disposition = _parse_brief_conflicts_disposition(
            data.get("brief_conflicts_disposition", [])
        )

        return cls(
            version=version,
            target_plan_id=target_plan_id,
            brief_id=brief_id,
            proposal_ids=proposal_ids,
            guidance_ids=guidance_ids,
            authoring_mode=authoring_mode,
            sole_author_reason=sole_author_reason,
            proposal_completeness=proposal_completeness,
            missing_proposals=missing_proposals,
            canonical_tasks=canonical_tasks,
            brief_conflicts_disposition=brief_conflicts_disposition,
            operator_notes=str(data.get("operator_notes", "")).strip(),
        )


def _validate_rc26(
    authoring_mode: str,
    sole_author_reason: str | None,
    proposal_completeness: str,
) -> None:
    """Enforce SIP-0093 RC-26: authoring mode, sole_author_reason, and
    proposal_completeness must agree.

    Pulled out of ``from_yaml`` so the parser stays under ruff's C901 bound;
    also makes the invariant separately testable and re-callable from the
    merger when it constructs decisions in code rather than parsing YAML.
    """
    if authoring_mode == "multi_role":
        if sole_author_reason is not None:
            raise ValueError(
                "merge_decisions: authoring_mode 'multi_role' requires "
                f"sole_author_reason to be null, got {sole_author_reason!r}"
            )
        if proposal_completeness not in {"complete", "partial"}:
            raise ValueError(
                "merge_decisions: authoring_mode 'multi_role' requires "
                "proposal_completeness in {'complete', 'partial'}, got "
                f"{proposal_completeness!r}"
            )
        return

    # sole_author
    if sole_author_reason is None:
        raise ValueError(
            "merge_decisions: authoring_mode 'sole_author' requires sole_author_reason to be set"
        )
    if proposal_completeness != "sole_author":
        raise ValueError(
            "merge_decisions: authoring_mode 'sole_author' requires "
            "proposal_completeness 'sole_author', got "
            f"{proposal_completeness!r}"
        )


def _validate_enum(raw: object, valid: frozenset[str], field_name: str) -> str:
    value = str(raw).strip()
    if value not in valid:
        raise ValueError(
            f"merge_decisions {field_name} must be one of {sorted(valid)}, got {raw!r}"
        )
    return value


def _parse_str_list(raw: object, field_name: str) -> list[str]:
    if raw is None or raw == "":
        return []
    if not isinstance(raw, list):
        raise ValueError(f"merge_decisions {field_name} must be a YAML list")
    return [str(x).strip() for x in raw if str(x).strip()]


def _parse_missing_proposals(raw: object) -> list[MissingProposal]:
    if raw is None or raw == "":
        return []
    if not isinstance(raw, list):
        raise ValueError("merge_decisions missing_proposals must be a list")
    parsed: list[MissingProposal] = []
    for i, entry in enumerate(raw):
        if not isinstance(entry, dict):
            raise ValueError(f"merge_decisions missing_proposals[{i}] must be a mapping")
        for req in ("role", "failure_reason"):
            if req not in entry:
                raise ValueError(
                    f"merge_decisions missing_proposals[{i}] missing required field: {req}"
                )
        parsed.append(
            MissingProposal(
                role=str(entry["role"]).strip(),
                failure_reason=str(entry["failure_reason"]).strip(),
            )
        )
    return parsed


def _parse_canonical_tasks(raw: object) -> list[CanonicalTaskProvenance]:
    if raw is None or raw == "":
        return []
    if not isinstance(raw, list):
        raise ValueError("merge_decisions canonical_tasks must be a list")

    parsed: list[CanonicalTaskProvenance] = []
    seen_indices: list[int] = []
    for i, entry in enumerate(raw):
        if not isinstance(entry, dict):
            raise ValueError(f"merge_decisions canonical_tasks[{i}] must be a mapping")
        for req in ("task_index", "merge_action", "reason"):
            if req not in entry:
                raise ValueError(
                    f"merge_decisions canonical_tasks[{i}] missing required field: {req}"
                )

        task_index = entry["task_index"]
        if not isinstance(task_index, int) or isinstance(task_index, bool):
            raise ValueError(
                f"merge_decisions canonical_tasks[{i}].task_index must be int, "
                f"got {type(task_index).__name__}"
            )
        seen_indices.append(task_index)

        merge_action = _validate_enum(
            entry["merge_action"],
            _VALID_MERGE_ACTIONS,
            f"canonical_tasks[{i}].merge_action",
        )

        source_keys = entry.get("source_proposal_task_keys", [])
        if not isinstance(source_keys, list):
            raise ValueError(
                f"merge_decisions canonical_tasks[{i}].source_proposal_task_keys must be a list"
            )
        proposed_by = entry.get("proposed_by", [])
        if not isinstance(proposed_by, list):
            raise ValueError(f"merge_decisions canonical_tasks[{i}].proposed_by must be a list")

        parsed.append(
            CanonicalTaskProvenance(
                task_index=task_index,
                source_proposal_task_keys=[str(k).strip() for k in source_keys],
                proposed_by=[str(r).strip() for r in proposed_by],
                merge_action=merge_action,
                reason=str(entry["reason"]).strip(),
            )
        )

    # Unique-and-contiguous from 0 (enforces SIP-0092 M1 schema canonical ordering)
    if seen_indices:
        if sorted(seen_indices) != list(range(len(seen_indices))):
            raise ValueError(
                "merge_decisions canonical_tasks task_index values must be unique "
                f"and contiguous from 0, got {sorted(seen_indices)}"
            )

    return parsed


def _parse_brief_conflicts_disposition(raw: object) -> list[BriefConflictDisposition]:
    if raw is None or raw == "":
        return []
    if not isinstance(raw, list):
        raise ValueError("merge_decisions brief_conflicts_disposition must be a list")

    parsed: list[BriefConflictDisposition] = []
    for i, entry in enumerate(raw):
        if not isinstance(entry, dict):
            raise ValueError(f"merge_decisions brief_conflicts_disposition[{i}] must be a mapping")
        for req in ("brief_field", "severity", "disposition", "reason"):
            if req not in entry:
                raise ValueError(
                    f"merge_decisions brief_conflicts_disposition[{i}] "
                    f"missing required field: {req}"
                )
        severity = _validate_enum(
            entry["severity"],
            _VALID_BRIEF_CONFLICT_SEVERITIES,
            f"brief_conflicts_disposition[{i}].severity",
        )
        disposition = _validate_enum(
            entry["disposition"],
            _VALID_CONFLICT_DISPOSITIONS,
            f"brief_conflicts_disposition[{i}].disposition",
        )
        parsed.append(
            BriefConflictDisposition(
                brief_field=str(entry["brief_field"]).strip(),
                severity=severity,
                disposition=disposition,
                reason=str(entry["reason"]).strip(),
            )
        )
    return parsed
