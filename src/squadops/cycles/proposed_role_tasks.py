"""ProposedRoleTasks — per-role plan-task proposals (SIP-0093).

Each contributing role emits a ``proposed_plan_tasks.yaml`` artifact during
the framing phase. The merger (``governance.merge_plan``) consumes all
proposals, resolves cross-role dependencies, deduplicates overlap, fills
gaps, and produces the canonical ``implementation_plan.yaml``.

This module defines the on-the-wire shape proposers write. It is
deliberately lighter than ``ImplementationPlan``:

- No ``project_id`` / ``cycle_id`` / ``prd_hash`` — those belong to the
  merger's canonical artifact.
- No ``task_index`` — proposers don't know their position in the
  combined plan. The merger assigns indices.
- No numeric ``depends_on`` — proposers refer to dependencies by the
  ``{role}:{focus}`` of the depended-on task. The merger resolves these
  references to indices after dedup.

A failed or missing proposal does not block the merger. If everyone
fails, the merger falls back to sole-broker authoring per SIP-0093 §5.4.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

import yaml

from squadops.cycles.implementation_plan import (
    TypedCheck,
    _parse_acceptance_criteria,
)

logger = logging.getLogger(__name__)

_FOCUS_NORMALIZE_RE = re.compile(r"\s+")


def _normalize_focus(text: str) -> str:
    """Collapse whitespace + lowercase so ``"Backend API"`` and
    ``"backend  api"`` resolve to the same dependency key. Proposers
    aren't expected to type focus strings byte-identically across
    proposals; the merger has to be tolerant."""
    return _FOCUS_NORMALIZE_RE.sub(" ", text.strip().lower())


# Role display-name → role-id. The proposer vocabulary uses display names
# (``proposing_role: development``) while produced tasks carry role-ids
# (``role: dev``). Dependency keys must collapse to the role-id form so a
# ``development:`` reference resolves against the produced ``dev:`` task
# (issue #189). Single source of truth: ``task_plan._PLAN_AUTHORING_PROPOSER_STEPS``
# derives its role-id column from this map via :func:`role_to_id`.
ROLE_NAME_TO_ID: dict[str, str] = {"development": "dev", "strategy": "strat"}


def role_to_id(role: str) -> str:
    """Collapse a role token (display-name or id) to its canonical role-id.

    Unknown tokens pass through unchanged — ``qa``/``builder``/``data`` are
    identical in both vocabularies, so only ``development`` and ``strategy``
    are aliased."""
    token = role.strip().lower()
    return ROLE_NAME_TO_ID.get(token, token)


def focus_key(role: str, focus: str) -> str:
    """Canonical lookup key for cross-proposal dependencies.

    Tolerant of role display-name vs role-id prefixes (issue #189):
    ``development``/``strategy`` collapse to ``dev``/``strat`` so a proposer
    that references ``development:Backend models`` resolves against the
    produced ``dev:backend models`` task. Focus is whitespace-collapsed and
    lowercased via :func:`_normalize_focus`."""
    return f"{role_to_id(role)}:{_normalize_focus(focus)}"


def canonicalize_dep_ref(dep_ref: str) -> str:
    """Normalize a ``depends_on_focus`` ``"role:focus"`` reference the same
    way :func:`focus_key` normalizes a produced task's key, so the resolve
    side (raw reference string) and the produce side cannot drift (#189).

    A bare string with no ``":"`` is treated as a focus with no role prefix."""
    role, sep, focus = dep_ref.partition(":")
    if not sep:
        return _normalize_focus(dep_ref)
    return focus_key(role, focus)


@dataclass(frozen=True)
class ProposedTask:
    """A single task proposed by a role for the build phase.

    Attributes:
        task_type: ``development.develop`` / ``qa.test`` /
            ``builder.assemble``. Same vocabulary as ``PlanTask``.
        role: the role that will execute this task — typically the
            proposing role itself, but a proposer may suggest a task
            for an adjacent role (e.g. dev proposing a builder task);
            the merger keeps or rejects per its conflict-resolution
            policy.
        focus: short, human-readable summary; serves as the proposer's
            identity for cross-role dependency references. Must be
            unique within a single proposal.
        description: detailed prose for the build LLM.
        expected_artifacts: filenames the build task must produce.
        acceptance_criteria: prose strings + typed checks (same shape
            as ``PlanTask.acceptance_criteria``).
        depends_on_focus: list of ``{role}:{focus}`` keys — references
            into other tasks (this proposal's or others'). The merger
            resolves these to numeric ``depends_on`` indices.
    """

    task_type: str
    role: str
    focus: str
    description: str
    expected_artifacts: list[str] = field(default_factory=list)
    acceptance_criteria: list[str | TypedCheck] = field(default_factory=list)
    depends_on_focus: list[str] = field(default_factory=list)


_VALID_BRIEF_CONFLICT_SEVERITIES = frozenset({"warning", "blocking"})


@dataclass(frozen=True)
class BriefConflict:
    """A proposer's structured disagreement with the shared brief (SIP-0093 §5.5).

    Raised in a proposal's ``brief_conflicts`` list when a role believes the
    brief contradicts the PRD, omits a requirement, or pins a stack/scope
    choice the role can't honor. The merger resolves each conflict per its
    severity:

    - ``warning``: merger may resolve unilaterally; disposition recorded.
    - ``blocking``: merger escalates to operator at gate; canonical plan
      still emits, blocking conflict surfaces in ``operator_notes``.

    Attributes:
        brief_field: which brief field the conflict targets (e.g.,
            ``accepted_stack``, ``must_cover_requirements``, ``scope_cuts``).
        proposed_change: what the proposer wants done instead.
        reason: why — typically a citation to the upstream PRD or a
            correctness argument.
        severity: ``warning`` or ``blocking``.
        affected_proposal_task_keys: focus_keys of tasks in this proposal
            that depend on the conflict's resolution. Empty if the conflict
            is informational.
    """

    brief_field: str
    proposed_change: str
    reason: str
    severity: str
    affected_proposal_task_keys: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ProposedRoleTasks:
    """A single role's plan-task proposal (SIP-0093 §5.4.1).

    Required fields (Rev 1):
        version, proposal_id, source_brief_id, proposing_role, scope_statement.

    The ``source_brief_id`` ties the proposal to an immutable
    ``plan_authoring_brief.yaml`` (RC-22); the merger rejects proposals that
    cite a brief other than the one it received.

    ``brief_conflicts`` defaults empty — most proposals will have none.

    Recommended optional fields (parsed if present, no validation beyond
    YAML shape): ``source_artifact_refs``, ``assumptions``, ``risks``,
    ``gaps_not_covered``, ``confidence``. These are LLM-output fields that
    populate inconsistently even when required (per SIP-0093 §5.4.1) — kept
    optional so a proposer that fails to surface its assumptions doesn't
    invalidate an otherwise good proposal.

    Optional sections degrade gracefully (issue #187): a malformed
    ``brief_conflicts`` entry or wrong-typed advisory list is dropped (warn +
    recorded in ``degraded_sections``) instead of discarding the proposal's
    load-bearing ``tasks``. ``tasks`` and the required header fields stay
    strict — a problem there still raises and the merger drops the proposal.
    """

    version: int
    proposal_id: str
    source_brief_id: str
    proposing_role: str
    scope_statement: str
    tasks: list[ProposedTask] = field(default_factory=list)
    brief_conflicts: list[BriefConflict] = field(default_factory=list)
    source_artifact_refs: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    gaps_not_covered: list[str] = field(default_factory=list)
    confidence: str = ""
    # Optional sections dropped during tolerant parsing (issue #187). Empty for
    # a clean proposal; e.g. ``["brief_conflicts[0]"]`` when one conflict entry
    # was skipped. The merger can surface these without re-deriving them.
    degraded_sections: list[str] = field(default_factory=list)

    @classmethod
    def from_yaml(cls, content: str) -> ProposedRoleTasks:
        """Parse a proposed_plan_tasks.yaml document.

        Permissive on optional fields, strict on the few required ones —
        a malformed proposal is recoverable (merger drops it and
        proceeds with the survivors), so we surface the specific
        failure rather than abort the whole framing phase.

        Optional/advisory sections (``brief_conflicts`` and the str-list
        fields) degrade rather than raise (issue #187): a malformed entry is
        dropped and noted in ``degraded_sections`` so one fumbled annotation
        can't discard the load-bearing ``tasks``. Only the required header
        fields and the ``tasks`` list still raise.

        Raises:
            ValueError: if the YAML is malformed, required header fields
                are missing, or a ``tasks`` entry is malformed. Caller
                decides whether to absorb the failure (merger does) or
                escalate.
        """
        try:
            data = yaml.safe_load(content)
        except yaml.YAMLError as exc:
            raise ValueError(f"Malformed proposal YAML: {exc}") from exc

        if not isinstance(data, dict):
            raise ValueError("Proposal must be a YAML mapping at the top level")

        # Order matters for error-test stability: version + proposing_role first,
        # then SIP-0093 PR 93.1 requireds. Each test asserting on a specific
        # missing-field message expects its target to be checked first.
        for key in (
            "version",
            "proposing_role",
            "proposal_id",
            "source_brief_id",
            "scope_statement",
        ):
            if key not in data:
                raise ValueError(f"Proposal missing required field: {key}")

        version = data["version"]
        if not isinstance(version, int):
            raise ValueError(f"Proposal version must be int, got {type(version).__name__}")

        proposing_role = str(data["proposing_role"]).strip()
        if not proposing_role:
            raise ValueError("Proposal proposing_role must be non-empty")

        proposal_id = str(data["proposal_id"]).strip()
        if not proposal_id:
            raise ValueError("Proposal proposal_id must be non-empty")

        source_brief_id = str(data["source_brief_id"]).strip()
        if not source_brief_id:
            raise ValueError("Proposal source_brief_id must be non-empty")

        scope_statement = str(data["scope_statement"]).strip()
        if not scope_statement:
            raise ValueError("Proposal scope_statement must be non-empty")

        raw_tasks = data.get("tasks", [])
        if not isinstance(raw_tasks, list):
            raise ValueError("Proposal tasks must be a list")

        seen_keys: set[str] = set()
        parsed: list[ProposedTask] = []
        for i, td in enumerate(raw_tasks):
            parsed.append(_parse_proposed_task(td, i, seen_keys))

        # Optional sections degrade rather than raise (issue #187): each helper
        # appends the names of dropped sections to ``degraded`` instead of
        # failing the whole proposal.
        degraded: list[str] = []
        brief_conflicts = _parse_brief_conflicts(data.get("brief_conflicts", []), degraded)

        return cls(
            version=version,
            proposal_id=proposal_id,
            source_brief_id=source_brief_id,
            proposing_role=proposing_role,
            scope_statement=scope_statement,
            tasks=parsed,
            brief_conflicts=brief_conflicts,
            source_artifact_refs=_parse_str_list(
                data.get("source_artifact_refs", []), "source_artifact_refs", degraded
            ),
            assumptions=_parse_str_list(data.get("assumptions", []), "assumptions", degraded),
            risks=_parse_str_list(data.get("risks", []), "risks", degraded),
            gaps_not_covered=_parse_str_list(
                data.get("gaps_not_covered", []), "gaps_not_covered", degraded
            ),
            confidence=str(data.get("confidence", "")).strip(),
            degraded_sections=degraded,
        )

    def task_keys(self) -> list[str]:
        """Canonical keys for this proposal's tasks — used by the merger
        to resolve ``depends_on_focus`` references across proposals."""
        return [focus_key(t.role, t.focus) for t in self.tasks]


def _parse_proposed_task(td: object, i: int, seen_keys: set[str]) -> ProposedTask:
    """Parse a single ``ProposedTask`` entry, enforcing required fields,
    focus_key uniqueness, and RC-24 (no integer ``depends_on_focus``).

    Pulled out of ``ProposedRoleTasks.from_yaml`` so the parent parser
    stays under ruff's C901 complexity bound.
    """
    if not isinstance(td, dict):
        raise ValueError(f"Proposal task {i} must be a mapping")

    for req in ("task_type", "role", "focus", "description"):
        if req not in td:
            raise ValueError(f"Proposal task {i} missing required field: {req}")

    role = str(td["role"]).strip()
    focus = str(td["focus"]).strip()
    if not focus:
        raise ValueError(f"Proposal task {i} focus must be non-empty")

    key = focus_key(role, focus)
    if key in seen_keys:
        raise ValueError(
            f"Proposal task {i} focus collides with an earlier task: {key!r}. "
            "Proposers must use distinct focus values within a single proposal."
        )
    seen_keys.add(key)

    depends_on_focus = td.get("depends_on_focus", [])
    if not isinstance(depends_on_focus, list):
        raise ValueError(f"Proposal task {i} depends_on_focus must be a list")
    # RC-24: reject integer entries. Proposers don't know their numeric
    # task_index — only the merger assigns those. An int here means the
    # proposer leaked a numbering assumption from somewhere.
    for j, entry in enumerate(depends_on_focus):
        if isinstance(entry, bool) or isinstance(entry, int):
            raise ValueError(
                f"Proposal task {i} depends_on_focus[{j}] must be a "
                f"focus_key string, not an integer (RC-24): {entry!r}"
            )
    depends_on_focus = [str(x).strip() for x in depends_on_focus if str(x).strip()]

    raw_criteria = td.get("acceptance_criteria", [])
    if not isinstance(raw_criteria, list):
        raise ValueError(f"Proposal task {i} acceptance_criteria must be a list")
    criteria = _parse_acceptance_criteria(raw_criteria, i)

    expected_artifacts = td.get("expected_artifacts", [])
    if not isinstance(expected_artifacts, list):
        raise ValueError(f"Proposal task {i} expected_artifacts must be a list")

    return ProposedTask(
        task_type=str(td["task_type"]).strip(),
        role=role,
        focus=focus,
        description=str(td["description"]).strip(),
        expected_artifacts=[str(a) for a in expected_artifacts],
        acceptance_criteria=criteria,
        depends_on_focus=depends_on_focus,
    )


def _parse_str_list(raw: object, section: str, degraded: list[str]) -> list[str]:
    """Coerce an optional YAML list field to a list of strings.

    Tolerant (issue #187): a wrong-typed advisory section is an LLM-output
    annotation, not load-bearing — so it's dropped (warn + recorded in
    ``degraded``) rather than failing the whole proposal. ``None``/empty →
    ``[]``; a list gets stringified element-wise.
    """
    if raw is None or raw == "":
        return []
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    logger.warning(
        "Proposal: dropping malformed optional section %r — expected a YAML list, got %s",
        section,
        type(raw).__name__,
    )
    degraded.append(section)
    return []


def _parse_brief_conflicts(raw: object, degraded: list[str]) -> list[BriefConflict]:
    """Parse the optional ``brief_conflicts`` list (SIP-0093 §5.5).

    Tolerant per-entry (issue #187): a malformed conflict entry is skipped
    (warn + recorded in ``degraded`` as ``brief_conflicts[i]``), preserving the
    valid entries and the proposal's load-bearing ``tasks``. A wrong-typed
    section is dropped whole. This is an *advisory* section — the dev proposer
    repeatedly fumbled a single sub-field here and lost its entire proposal
    (cyc_ee7a5dfcdb16); one bad annotation must no longer discard real work.
    """
    if raw is None or raw == "":
        return []
    if not isinstance(raw, list):
        logger.warning(
            "Proposal: dropping malformed 'brief_conflicts' — expected a YAML list, got %s",
            type(raw).__name__,
        )
        degraded.append("brief_conflicts")
        return []

    parsed: list[BriefConflict] = []
    for i, entry in enumerate(raw):
        try:
            parsed.append(_parse_one_brief_conflict(entry, i))
        except ValueError as exc:
            logger.warning("Proposal: skipping malformed brief_conflicts[%d] — %s", i, exc)
            degraded.append(f"brief_conflicts[{i}]")
    return parsed


def _parse_one_brief_conflict(entry: object, i: int) -> BriefConflict:
    """Parse + validate a single ``brief_conflicts`` entry (strict).

    Raises ``ValueError`` on any shape problem; the caller decides whether to
    skip (it does) or propagate.
    """
    if not isinstance(entry, dict):
        raise ValueError(f"brief_conflicts[{i}] must be a mapping")

    for req in ("brief_field", "proposed_change", "reason", "severity"):
        if req not in entry:
            raise ValueError(f"brief_conflicts[{i}] missing required field: {req}")

    severity = str(entry["severity"]).strip().lower()
    if severity not in _VALID_BRIEF_CONFLICT_SEVERITIES:
        raise ValueError(
            f"brief_conflicts[{i}] severity must be one of "
            f"{sorted(_VALID_BRIEF_CONFLICT_SEVERITIES)}, got {entry['severity']!r}"
        )

    affected = entry.get("affected_proposal_task_keys", [])
    if not isinstance(affected, list):
        raise ValueError(f"brief_conflicts[{i}] affected_proposal_task_keys must be a list")

    return BriefConflict(
        brief_field=str(entry["brief_field"]).strip(),
        proposed_change=str(entry["proposed_change"]).strip(),
        reason=str(entry["reason"]).strip(),
        severity=severity,
        affected_proposal_task_keys=[str(k).strip() for k in affected if str(k).strip()],
    )
