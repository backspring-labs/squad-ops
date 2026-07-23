"""SIP-0100 follow-up — deterministic fill-slot binding at plan authoring.

A **read-only projection** of the scaffold ownership surfaces (the same source the runtime write
enforcement uses), applied at plan-authoring time so a bind-mode plan's dev/qa targets are gated
against the fill slots *before* generation lands (Phase B), and the surfaces can be published to the
proposer (Phase A).

Architectural boundary (plan review #3): the plan domain model consumes this projection; it never
constructs runtime ``WriteGrant`` objects. Reason codes are a ``PLAN_TARGET_*`` family — deterministic
plan-contract violations, not proposer-quality or implementation failures.
"""

from __future__ import annotations

import posixpath
from dataclasses import dataclass

from squadops.capabilities.scaffold import qa_test_namespace_for_stack
from squadops.cycles.verification_contract import VerificationContract
from squadops.cycles.write_authorization import normalize_ws_path


class PlanTargetViolation:
    """Stable codes for a deterministic plan-contract violation (constants-class, not enum)."""

    UNAUTHORIZED = (
        "plan_target_unauthorized"  # target isn't an authorized writable path for the role
    )
    MISSING_REQUIRED_SLOT = (
        "plan_target_missing_required_slot"  # a required fill slot is unassigned
    )
    DUPLICATE_OWNERSHIP = "plan_target_duplicate_ownership"  # two tasks own the same slot
    AMBIGUOUS_SCOPE = (
        "plan_target_ambiguous_scope"  # glob/dir/absolute — not a concrete workspace file
    )


@dataclass(frozen=True)
class PlanTargetRejection:
    """One rejected target (or coverage defect), carrying everything the re-roll prompt + metrics need."""

    code: str
    task_index: int
    role: str
    raw_target: str
    canonical_target: str | None
    detail: str
    nearest_slots: tuple[str, ...]
    contract_hash: str

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "task_index": self.task_index,
            "role": self.role,
            "raw_target": self.raw_target,
            "canonical_target": self.canonical_target,
            "detail": self.detail,
            "nearest_slots": list(self.nearest_slots),
            "contract_hash": self.contract_hash,
        }


def _is_glob_or_dir(raw: str) -> bool:
    """A concrete workspace file has no glob metacharacter and no trailing separator."""
    return any(ch in raw for ch in "*?[") or raw.rstrip().endswith("/")


@dataclass(frozen=True)
class PlanAuthorization:
    """Read-only planning authorization projection derived from the bound contract.

    ``read_only_paths`` = frozen files; ``dev_writable`` = fill slots; ``qa_namespace`` = QA test
    prefixes; ``required_coverage`` = the fill slots the plan MUST assign; ``source_prefixes`` = the
    workspace source-tree directory prefixes (so an off-slot source file is caught as *undeclared
    source* rather than waved through as a deliverable)."""

    read_only_paths: frozenset[str]
    dev_writable: frozenset[str]
    qa_namespace: tuple[str, ...]
    required_coverage: frozenset[str]
    source_prefixes: tuple[str, ...]
    contract_hash: str

    @classmethod
    def from_contract(cls, contract: VerificationContract) -> PlanAuthorization:
        frozen = frozenset(
            n for f in contract.frozen_files if (n := normalize_ws_path(f.path)) is not None
        )
        fill = frozenset(
            n for f in contract.fill_files if (n := normalize_ws_path(f.path)) is not None
        )
        # Source-tree prefixes: the parent dir of every scaffold source file. A dev/qa target under
        # one of these that is neither a slot nor frozen is undeclared *source* (reject), vs a
        # root-level deliverable (e.g. qa_handoff.md) which sits under no source prefix.
        prefixes = {posixpath.dirname(p) + "/" for p in (frozen | fill) if posixpath.dirname(p)}
        return cls(
            read_only_paths=frozen,
            dev_writable=fill,
            qa_namespace=qa_test_namespace_for_stack(contract.skeleton.expander),
            required_coverage=fill,
            source_prefixes=tuple(sorted(prefixes)),
            contract_hash=contract.skeleton.interface_manifest_hash,
        )

    def _in_qa_namespace(self, norm: str) -> bool:
        return any(norm.startswith(ns) for ns in self.qa_namespace)

    def _is_source_tree(self, norm: str) -> bool:
        return any(norm.startswith(p) for p in self.source_prefixes)


_DEV_TASK_TYPES = frozenset({"development.develop"})


def _role_of(task_type: str) -> str | None:
    """The write-authority role a task is gated as, or None (not gated in v1 — e.g. builder)."""
    if task_type in _DEV_TASK_TYPES:
        return "dev"
    if task_type.startswith("qa."):
        return "qa"
    return None


def _authorize_target(
    authz: PlanAuthorization, role: str, raw: str, task_index: int
) -> PlanTargetRejection | None:
    """Authorize one workspace target for a dev/qa task, or None if allowed. Returns a rejection for
    frozen, cross-role slot, undeclared source, or ambiguous (glob/dir/escape) targets. A path under
    no source prefix and in no owned surface is treated as a (non-workspace) deliverable — allowed."""
    if _is_glob_or_dir(raw):
        return PlanTargetRejection(
            PlanTargetViolation.AMBIGUOUS_SCOPE,
            task_index,
            role,
            raw,
            None,
            "glob/directory targets are not concrete workspace files; name each fill slot explicitly",
            tuple(sorted(authz.dev_writable if role == "dev" else ())),
            authz.contract_hash,
        )
    norm = normalize_ws_path(raw)
    if norm is None:
        return PlanTargetRejection(
            PlanTargetViolation.AMBIGUOUS_SCOPE,
            task_index,
            role,
            raw,
            None,
            "absolute or workspace-escaping path",
            (),
            authz.contract_hash,
        )
    if norm in authz.read_only_paths:
        return PlanTargetRejection(
            PlanTargetViolation.UNAUTHORIZED,
            task_index,
            role,
            raw,
            norm,
            "frozen scaffold file — read-only; put logic in a fill slot",
            tuple(sorted(authz.dev_writable)),
            authz.contract_hash,
        )
    if role == "dev":
        if norm in authz.dev_writable:
            return None
        if authz._in_qa_namespace(norm):
            return PlanTargetRejection(
                PlanTargetViolation.UNAUTHORIZED,
                task_index,
                role,
                raw,
                norm,
                "QA test namespace — dev does not author tests",
                tuple(sorted(authz.dev_writable)),
                authz.contract_hash,
            )
        if authz._is_source_tree(norm):
            return PlanTargetRejection(
                PlanTargetViolation.UNAUTHORIZED,
                task_index,
                role,
                raw,
                norm,
                "undeclared workspace source — not a fill slot",
                tuple(sorted(authz.dev_writable)),
                authz.contract_hash,
            )
        return None  # under no source prefix, not frozen → deliverable (allowed, v1-permissive)
    # role == "qa"
    if authz._in_qa_namespace(norm):
        return None
    if norm in authz.dev_writable:
        return PlanTargetRejection(
            PlanTargetViolation.UNAUTHORIZED,
            task_index,
            role,
            raw,
            norm,
            "dev fill slot — QA writes tests, not source (needs an explicit correction grant)",
            tuple(authz.qa_namespace),
            authz.contract_hash,
        )
    if authz._is_source_tree(norm):
        return PlanTargetRejection(
            PlanTargetViolation.UNAUTHORIZED,
            task_index,
            role,
            raw,
            norm,
            "workspace source — QA writes only its test namespace",
            tuple(authz.qa_namespace),
            authz.contract_hash,
        )
    return None  # deliverable (allowed)


def validate_plan_write_targets(tasks: list, authz: PlanAuthorization) -> list[PlanTargetRejection]:
    """Bind-mode plan target validation (Phase B). Returns per-target rejections plus coverage
    defects (missing required slot / duplicate ownership). Empty ⇒ the plan's targets are authorized
    and complete. The caller rejects the whole plan atomically on any rejection (never silent-strips)."""
    rejections: list[PlanTargetRejection] = []
    slot_owners: dict[str, list[int]] = {}
    for task in tasks:
        role = _role_of(task.task_type)
        if role is None:
            continue
        for raw in task.expected_artifacts:
            rej = _authorize_target(authz, role, str(raw), task.task_index)
            if rej is not None:
                rejections.append(rej)
                continue
            if role == "dev":
                norm = normalize_ws_path(str(raw))
                if norm in authz.dev_writable:
                    slot_owners.setdefault(norm, []).append(task.task_index)

    # Coverage: every required slot assigned exactly once.
    for slot in sorted(authz.required_coverage):
        owners = slot_owners.get(slot, [])
        if not owners:
            rejections.append(
                PlanTargetRejection(
                    PlanTargetViolation.MISSING_REQUIRED_SLOT,
                    -1,
                    "dev",
                    slot,
                    slot,
                    "required fill slot is not assigned by any dev task",
                    (slot,),
                    authz.contract_hash,
                )
            )
        elif len(owners) > 1:
            rejections.append(
                PlanTargetRejection(
                    PlanTargetViolation.DUPLICATE_OWNERSHIP,
                    owners[-1],
                    "dev",
                    slot,
                    slot,
                    f"fill slot assigned by multiple dev tasks {owners}",
                    (slot,),
                    authz.contract_hash,
                )
            )
    return rejections
