"""
Cycle Create Preflight — pure create-time decisions (SIP-0095).

A deterministic validation gate applied *before* a cycle is persisted or
dispatched. Each check is a pure function over the resolved squad-profile snapshot
and the requested workloads; it returns a :class:`PreflightDecision` aggregating
``block`` and ``warning`` findings. The route calls :func:`combine` over the
checks: **if any check blocks, the cycle is rejected — even if other checks are
unverifiable; warnings ride alongside but do not alter the rejection** (SIP §6).

Pure by design (mirrors ``runtime.recruitment.reserve_buffer_decision``): callers
fetch the I/O (the profile snapshot, the backend's pulled-model list) and pass it
in, so the decisions stay unit-testable and this module imports no adapters (D26).

This module holds the **capability** half (:func:`required_roles_decision`,
Macbook lane). The **model-availability** half — ``model_availability_decision``,
pure over ``(profile, pulled_models)`` — is added here by the Spark lane (SIP §12,
plan Phase 2); it belongs in this module so both halves share ``combine`` and the
``Finding``/``PreflightDecision`` shapes.

Scope (SIP-0095, option A): the capability check is **static workload→role
satisfiability only**. The materialized-plan / ``builder.assemble`` mismatch
(#172's live case) has no plan at create time and is validated at dispatch
(``task_plan.validate_against_profile``); hoisting it to the plan-review gate is
#295, out of scope here.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from squadops.cycles.models import REQUIRED_PLAN_ROLES, WORKLOAD_REQUIRED_ROLES

if TYPE_CHECKING:
    from squadops.cycles.models import SquadProfile


@dataclass(frozen=True)
class Finding:
    """One preflight check outcome (SIP §7).

    ``severity`` is ``"block"`` (rejects the request) or ``"warning"`` (surfaced
    to the operator but does not reject). ``code`` is a stable machine label
    (``missing_role`` / ``model_unavailable`` / ``model_unverifiable``);
    ``message`` is the standardized, actionable operator text.
    """

    code: str
    severity: str
    message: str


@dataclass(frozen=True)
class PreflightDecision:
    """The aggregate decision summary for a set of checks (SIP §6)."""

    blocking: tuple[Finding, ...] = field(default_factory=tuple)
    warnings: tuple[Finding, ...] = field(default_factory=tuple)

    @property
    def rejected(self) -> bool:
        """True iff any check blocked — the cycle must not be created."""
        return bool(self.blocking)

    def summary(self) -> str:
        """The joined blocking messages, for the error raised at the route."""
        return " ".join(f.message for f in self.blocking)


def combine(*decisions: PreflightDecision) -> PreflightDecision:
    """Aggregate check decisions: any block ⇒ rejected; warnings ride alongside."""
    return PreflightDecision(
        blocking=tuple(f for d in decisions for f in d.blocking),
        warnings=tuple(f for d in decisions for f in d.warnings),
    )


def required_roles_decision(
    profile: SquadProfile, applied_defaults: Mapping[str, Any]
) -> PreflightDecision:
    """Block when the squad can't satisfy the roles the requested workloads statically require.

    Reads the same inputs dispatch uses — ``applied_defaults["workload_sequence"]``
    (a list of ``{"type": ...}`` entries) or, when absent, the legacy
    ``plan_tasks`` / ``build_tasks`` flags — and the same
    :data:`WORKLOAD_REQUIRED_ROLES` map, so create-time and dispatch never drift.
    Emits one ``block`` finding per (workload, missing-role). Never warns (role
    satisfiability is always verifiable from the profile).
    """
    profile_roles = frozenset(a.role for a in profile.agents if a.enabled)
    provided = ", ".join(f"`{r}`" for r in sorted(profile_roles)) or "(none)"
    findings: list[Finding] = []
    for label, required in _required_roles_by_workload(applied_defaults).items():
        for role in sorted(required - profile_roles):
            findings.append(
                Finding(
                    code="missing_role",
                    severity="block",
                    message=(
                        f"workload `{label}` requires role `{role}`, but squad profile "
                        f"`{profile.profile_id}` provides {provided}. Choose a profile with a "
                        f"`{role}` agent or adjust the requested workloads."
                    ),
                )
            )
    return PreflightDecision(blocking=tuple(findings))


def _required_roles_by_workload(applied_defaults: Mapping[str, Any]) -> dict[str, frozenset[str]]:
    """Map each requested workload label → its required role set (create-time static).

    Workloads/toggles with no static requirement (``implementation``,
    ``build_tasks``) contribute nothing — a builder-less squad is a valid graceful
    fallback, not a block (SIP §6.1). Unknown workload types are ignored here (the
    executor rejects them at dispatch).
    """
    sequence = applied_defaults.get("workload_sequence") or []
    if sequence:
        result: dict[str, frozenset[str]] = {}
        for entry in sequence:
            wtype = entry.get("type") if isinstance(entry, Mapping) else None
            roles = WORKLOAD_REQUIRED_ROLES.get(wtype) if wtype else None
            if roles:  # skip unknown + no-requirement workloads (implementation)
                result[wtype] = roles
        return result
    # Legacy path: plan_tasks (default true) requires the plan roles; build_tasks requires none.
    if applied_defaults.get("plan_tasks", True):
        return {"plan_tasks": REQUIRED_PLAN_ROLES}
    return {}
