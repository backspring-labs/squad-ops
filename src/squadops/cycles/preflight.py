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

from squadops.cycles.check_registry import get_framework_check
from squadops.cycles.models import (
    REQUIRED_PLAN_ROLES,
    VALID_PLAN_AUTHORING_CONTRIBUTORS,
    WORKLOAD_REQUIRED_ROLES,
    WorkloadType,
)

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


def required_roles_decision(profile: SquadProfile, config: Mapping[str, Any]) -> PreflightDecision:
    """Block when the squad can't satisfy the roles the requested workloads statically require.

    Reads the same inputs dispatch uses — the EFFECTIVE config's
    ``workload_sequence`` (a list of ``{"type": ...}`` entries) or, when
    absent, the legacy ``plan_tasks`` / ``build_tasks`` flags — and the same
    :data:`WORKLOAD_REQUIRED_ROLES` map, so create-time and dispatch never
    drift. ``config`` is the #426 single merge (``models.resolve_config``,
    #724): dispatch honors ``execution_overrides``, so preflight must
    evaluate the same merged view or the two diverge.
    Emits one ``block`` finding per (workload, missing-role). Never warns (role
    satisfiability is always verifiable from the profile).
    """
    profile_roles = frozenset(a.role for a in profile.agents if a.enabled)
    provided = ", ".join(f"`{r}`" for r in sorted(profile_roles)) or "(none)"
    findings: list[Finding] = []
    for label, required in _required_roles_by_workload(config).items():
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


def _required_roles_by_workload(config: Mapping[str, Any]) -> dict[str, frozenset[str]]:
    """Map each requested workload label → its required role set (create-time static).

    Workloads/toggles with no static requirement (``implementation``,
    ``build_tasks``) contribute nothing — a builder-less squad is a valid graceful
    fallback, not a block (SIP §6.1). Unknown workload types are ignored here (the
    executor rejects them at dispatch).
    """
    sequence = config.get("workload_sequence") or []
    if sequence:
        result: dict[str, frozenset[str]] = {}
        for entry in sequence:
            wtype = entry.get("type") if isinstance(entry, Mapping) else None
            roles = WORKLOAD_REQUIRED_ROLES.get(wtype) if wtype else None
            if roles:  # skip unknown + no-requirement workloads (implementation)
                result[wtype] = roles
        return result
    # Legacy path: plan_tasks (default true) requires the plan roles; build_tasks requires none.
    if config.get("plan_tasks", True):
        return {"plan_tasks": REQUIRED_PLAN_ROLES}
    return {}


def _authors_a_plan(config: Mapping[str, Any]) -> bool:
    """True iff this cycle's requested workloads will actually author a plan.

    Mirrors :func:`_required_roles_by_workload`'s reading of the same surface,
    including its legacy fallback, so the two never disagree about whether
    planning happens.
    """
    sequence = config.get("workload_sequence") or []
    if sequence:
        return any(
            (entry.get("type") if isinstance(entry, Mapping) else None) == WorkloadType.FRAMING
            for entry in sequence
        )
    return bool(config.get("plan_tasks", True))


def bind_mode_authoring_decision(config: Mapping[str, Any]) -> PreflightDecision:
    """Block a bind-mode cycle whose framing cannot produce a bindable plan (#762).

    In bind mode (``contract_ref`` present) the plan is validated to *bind* the
    contract's criteria by id. Only the proposer task types carry the criteria
    index — ``bind_criteria_index`` is set on ``development.propose_plan_tasks`` and
    ``qa.propose_plan_tasks`` in ``capabilities.context_assembly``, and
    ``governance.merge_plan`` is deliberately excluded there. So with no
    ``plan_authoring_contributors`` there are no proposers, *nothing* in the framing
    workload ever receives the index, and every plan the sole-author merger can
    produce (frozen-surface claims, zero ``criteria_refs``) is rejected by bind-mode
    validation. The configuration is unwinnable by construction, and it costs a full
    framing workload per attempt to discover — shk-6 rolls 1-3 burned three.

    **Scoped to configurations that actually author a plan.** An implementation-only
    bind-mode cycle is legitimate and used: the SIP-0101 replay demonstration
    (``cyc_cfe6962e8fc8``) skipped framing via a ``workload_sequence`` override to
    resume from a checkpoint. Blocking on ``contract_ref`` alone would have rejected
    it, and a net that false-positives on a working configuration is worse than the
    gap it closes.

    Blocks rather than warns: every input is present in the resolved config at create
    time (knowable, per this module's block-vs-warn rule), and the downstream
    rejection is deterministic rather than probable — warning would spend a framing
    workload to reach a certain failure.
    """
    if not config.get("contract_ref"):
        return PreflightDecision()
    if config.get("plan_authoring_contributors"):
        return PreflightDecision()
    if not _authors_a_plan(config):
        return PreflightDecision()

    roles = ", ".join(f"`{r}`" for r in sorted(VALID_PLAN_AUTHORING_CONTRIBUTORS))
    return PreflightDecision(
        blocking=(
            Finding(
                code="bind_mode_without_authoring_contributors",
                severity="block",
                message=(
                    "this cycle is in bind mode (`contract_ref` is set) but "
                    "`plan_authoring_contributors` is empty, so plan authoring would run "
                    "sole-author — a path that never receives the contract's criteria "
                    "index and therefore cannot produce a plan that binds it. Every "
                    "framing attempt would be rejected. Set "
                    f"`plan_authoring_contributors` (any of {roles}) in the request "
                    "profile or `execution_overrides`, or drop `contract_ref` to run in "
                    "author mode."
                ),
            ),
        )
    )


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


def required_check_tooling_decision(
    required_check_ids: Iterable[str],
    available_tooling: Iterable[str] | None,
) -> PreflightDecision:
    """Block when a profile requires a framework check whose tooling is knowably absent.

    SIP-0096 §6.5 *create-time-knowable* routing: a required check that cannot
    execute in the target deployment (e.g. the frontend build check on a squad
    whose image lacks Node) must be caught here — a create-time reject — never a
    mid-run ``not-executed → blocked_unverified`` surprise.

    Mirrors :func:`model_availability_decision` on evidence:
    - ``available_tooling is None`` ⇒ provisioning couldn't be resolved:
      *unverifiable*, so **warn and allow** — never block on missing evidence.
    - a resolved set blocks any required check whose ``required_tooling`` isn't a
      subset. Checks with no external tooling (the test spine, pure-Python diffs)
      never block.

    ``required_check_ids`` come from the effective config's ``required_checks``
    (the #426 single merge, #724); every
    id is a registered framework check (unknown ids are rejected at CRP load, #395),
    so an unregistered id here simply contributes no tooling requirement.
    """
    needing: list[tuple[str, tuple[str, ...]]] = []
    for cid in required_check_ids:
        check = get_framework_check(cid)
        if check and check.required_tooling:
            needing.append((cid, check.required_tooling))
    if not needing:
        return PreflightDecision()

    if available_tooling is None:
        return PreflightDecision(
            warnings=tuple(
                Finding(
                    code="check_tooling_unverifiable",
                    severity="warning",
                    message=(
                        f"could not verify tooling for required check `{cid}` "
                        f"(needs {', '.join(f'`{t}`' for t in tools)}) — the deployment's "
                        f"provisioning could not be resolved; it may fail to execute at "
                        f"runtime. Verify the tooling is provisioned."
                    ),
                )
                for cid, tools in needing
            )
        )

    have = frozenset(available_tooling)
    findings = [
        Finding(
            code="check_tooling_unavailable",
            severity="block",
            message=(
                f"required check `{cid}` needs {', '.join(f'`{t}`' for t in missing)}, "
                f"which the target deployment does not provision. Add the package to the "
                f"role's `system-packages.txt` and rebuild, or drop `{cid}` from "
                f"`required_checks`."
            ),
        )
        for cid, tools in needing
        if (missing := [t for t in tools if t not in have])
    ]
    return PreflightDecision(blocking=tuple(findings))
