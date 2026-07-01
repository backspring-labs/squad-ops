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

This module holds both halves so they share ``combine`` and the
``Finding``/``PreflightDecision`` shapes: the **capability** half
(:func:`required_roles_decision`, Macbook lane) and the **model-availability**
half (:func:`model_availability_decision`, pure over ``(profile, pulled_models)``,
Spark lane — SIP §12).

Scope (SIP-0095, option A): the capability check is **static workload→role
satisfiability only**. The materialized-plan / ``builder.assemble`` mismatch
(#172's live case) has no plan at create time and is validated at dispatch
(``task_plan.validate_against_profile``); hoisting it to the plan-review gate is
#295, out of scope here.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
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


def _canonical_model(name: str) -> str:
    """Ollama canonical model tag: a tagless reference defaults to ``:latest``.

    So ``llama3.2`` and ``llama3.2:latest`` compare equal — but NO prefix/family
    inference: ``qwen3:7b`` never matches ``qwen3:27b`` (SIP §137, decided).
    """
    return name if ":" in name else f"{name}:latest"


def model_availability_decision(
    profile: SquadProfile, pulled_models: Iterable[str] | None
) -> PreflightDecision:
    """Block when a profile's enabled agents name a model definitively not pulled.

    ``pulled_models`` is the backend's set of available model *names* — the caller
    fetches it (e.g. from ``OllamaAdapter.list_pulled_models``) and passes names
    in, keeping this decision pure and adapter-free (D26).

    Per SIP §6.2/§6.3:
    - ``pulled_models is None`` ⇒ the backend couldn't be queried: availability is
      *unverifiable*, so **warn and allow** — never block on missing evidence.
    - A reachable-but-empty list is *verifiable* and blocks every required model.
    - Matching is exact on the canonical tag (tagless ⇒ ``:latest``); no
      prefix/family inference (§137). Only enabled agents' models are checked.
    """
    required = sorted({a.model for a in profile.agents if a.enabled and a.model})
    if not required:
        return PreflightDecision()

    if pulled_models is None:
        listed = ", ".join(f"`{m}`" for m in required)
        return PreflightDecision(
            warnings=(
                Finding(
                    code="model_unverifiable",
                    severity="warning",
                    message=(
                        f"could not verify model availability for squad profile "
                        f"`{profile.profile_id}` (LLM backend unreachable) — required "
                        f"models {listed} were not checked and may fail fast at "
                        f"runtime. Verify the backend has them pulled."
                    ),
                ),
            )
        )

    pulled = sorted(pulled_models)
    pulled_canonical = {_canonical_model(m) for m in pulled}
    have = ", ".join(f"`{m}`" for m in pulled[:10]) or "(none)"
    if len(pulled) > 10:
        have += f" (+{len(pulled) - 10} more)"

    findings = [
        Finding(
            code="model_unavailable",
            severity="block",
            message=(
                f"squad profile `{profile.profile_id}` requires model `{model}`, but "
                f"the LLM backend has {have}. Pull `{model}` on the backend or choose "
                f"a profile whose models are available."
            ),
        )
        for model in required
        if _canonical_model(model) not in pulled_canonical
    ]
    return PreflightDecision(blocking=tuple(findings))
