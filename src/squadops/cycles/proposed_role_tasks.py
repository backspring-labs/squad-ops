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

import re
from dataclasses import dataclass, field
from typing import Union

import yaml

from squadops.cycles.implementation_plan import (
    TypedCheck,
    _parse_acceptance_criteria,
)


_FOCUS_NORMALIZE_RE = re.compile(r"\s+")


def _normalize_focus(text: str) -> str:
    """Collapse whitespace + lowercase so ``"Backend API"`` and
    ``"backend  api"`` resolve to the same dependency key. Proposers
    aren't expected to type focus strings byte-identically across
    proposals; the merger has to be tolerant."""
    return _FOCUS_NORMALIZE_RE.sub(" ", text.strip().lower())


def focus_key(role: str, focus: str) -> str:
    """Canonical lookup key for cross-role dependencies."""
    return f"{role.strip().lower()}:{_normalize_focus(focus)}"


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
    acceptance_criteria: list[Union[str, TypedCheck]] = field(default_factory=list)
    depends_on_focus: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ProposedRoleTasks:
    """A single role's plan-task proposal."""

    version: int
    proposing_role: str
    tasks: list[ProposedTask] = field(default_factory=list)

    @classmethod
    def from_yaml(cls, content: str) -> ProposedRoleTasks:
        """Parse a proposed_plan_tasks.yaml document.

        Permissive on optional fields, strict on the few required ones —
        a malformed proposal is recoverable (merger drops it and
        proceeds with the survivors), so we surface the specific
        failure rather than abort the whole framing phase.

        Raises:
            ValueError: if the YAML is malformed or required fields
                are missing. Caller decides whether to absorb the
                failure (merger does) or escalate.
        """
        try:
            data = yaml.safe_load(content)
        except yaml.YAMLError as exc:
            raise ValueError(f"Malformed proposal YAML: {exc}") from exc

        if not isinstance(data, dict):
            raise ValueError("Proposal must be a YAML mapping at the top level")

        for key in ("version", "proposing_role"):
            if key not in data:
                raise ValueError(f"Proposal missing required field: {key}")

        version = data["version"]
        if not isinstance(version, int):
            raise ValueError(f"Proposal version must be int, got {type(version).__name__}")

        proposing_role = str(data["proposing_role"]).strip()
        if not proposing_role:
            raise ValueError("Proposal proposing_role must be non-empty")

        raw_tasks = data.get("tasks", [])
        if not isinstance(raw_tasks, list):
            raise ValueError("Proposal tasks must be a list")

        seen_keys: set[str] = set()
        parsed: list[ProposedTask] = []
        for i, td in enumerate(raw_tasks):
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
            depends_on_focus = [str(x).strip() for x in depends_on_focus if str(x).strip()]

            raw_criteria = td.get("acceptance_criteria", [])
            if not isinstance(raw_criteria, list):
                raise ValueError(f"Proposal task {i} acceptance_criteria must be a list")
            criteria = _parse_acceptance_criteria(raw_criteria, i)

            expected_artifacts = td.get("expected_artifacts", [])
            if not isinstance(expected_artifacts, list):
                raise ValueError(f"Proposal task {i} expected_artifacts must be a list")

            parsed.append(
                ProposedTask(
                    task_type=str(td["task_type"]).strip(),
                    role=role,
                    focus=focus,
                    description=str(td["description"]).strip(),
                    expected_artifacts=[str(a) for a in expected_artifacts],
                    acceptance_criteria=criteria,
                    depends_on_focus=depends_on_focus,
                )
            )

        return cls(version=version, proposing_role=proposing_role, tasks=parsed)

    def task_keys(self) -> list[str]:
        """Canonical keys for this proposal's tasks — used by the merger
        to resolve ``depends_on_focus`` references across proposals."""
        return [focus_key(t.role, t.focus) for t in self.tasks]
