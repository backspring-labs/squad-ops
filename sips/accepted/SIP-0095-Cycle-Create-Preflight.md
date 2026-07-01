---
title: Cycle-Create Preflight
status: accepted
author: jladd
created_at: '2026-07-01T00:00:00Z'
sip_number: 95
updated_at: '2026-06-30T21:57:45.818751Z'
---
# SIP-0095: Cycle Create Preflight

## Status
Accepted

**Targets:** v1.2
**Combines:** #172 (capability/role satisfiability) + #224 (model availability)
**Depends on:** #173 (squad-profile name consolidation) — *merged*.
**Precedent:** SIP-0089 §2.5 reserve-buffer guard — a pure pre-dispatch decision enforced at a choke point. This SIP applies the same shape, hoisted from dispatch to **create** time.

---

## 1. Summary

Add a fail-fast **Cycle Create Preflight** that rejects unsatisfiable cycle requests before persistence or dispatch. The preflight blocks when the selected squad profile cannot satisfy the roles implied by the requested workloads, or when the profile names models that are *definitively* unavailable on the configured LLM backend. The check follows the reserve-buffer precedent: pure decision logic, enforced at a single choke point, with actionable operator feedback. Dispatch-time validation remains as defense in depth.

The two checks **primarily hoist logic that already exists** — role satisfiability is enforced today at dispatch, and model availability exists today as a non-fatal warning in profile CRUD. This SIP primarily *hoists and shares* existing validation, while making the create-time workload/defaults→role mapping explicit where dispatch does not already express it statically — which is why it is small and low-risk.

---

## 2. Motivation / Problem

Nothing validates plan↔squad satisfiability or model availability before a cycle is persisted and dispatched. The checks that exist run too late:

- **Capability mismatch fails at dispatch (#172).** Role satisfiability is enforced inside the flow executor, *after* the cycle is persisted and running. A cycle whose workloads need a role the squad lacks (the live case: `builder.assemble` on a builder-less squad) fails ~9 minutes in with `No handler for capability: builder.assemble`.
- **Model mismatch fails ~1s in, cryptically (#224).** When a profile names a model that isn't pulled (the live case: `full` → `qwen3.6:27b` on a non-Spark host), every task fails instantly with `Model '…' not found`, surfaced only in Prefect flow logs — the operator gets no create-time signal.

Both are the same anti-pattern: an unsatisfiable request is accepted, dispatched, and fails deep in execution instead of being rejected at the door — "confident garbage caught late."

---

## 3. Decision

Cycle creation MUST apply a deterministic preflight gate that:

1. **fails fast when the selected squad profile cannot satisfy the roles implied by the requested workloads**, and
2. **fails fast when the profile names a model that is definitively unavailable on the configured backend**,

**before the cycle is persisted or dispatched**, returning an actionable error that names the missing role or model. When the preflight cannot obtain the evidence it needs (e.g. the LLM backend is unreachable), it MUST NOT block — it surfaces the uncertainty as a warning and allows creation.

---

## 4. Scope

- Applies to cycle creation via the API route and, transitively, the `squadops cycles create` CLI (which POSTs to it).
- Evaluates the **resolved squad-profile snapshot** — the same immutable snapshot that would be persisted with the cycle — not a mutable profile name, so a concurrent profile edit cannot produce a create/dispatch mismatch.
- Shares the model-availability decision with `squadops doctor` so environment diagnosis and create-time enforcement stay in agreement.

---

## 5. Non-Goals

- **Not a planner fix.** Stopping the planner from *authoring* unsatisfiable tasks is separate; this gate is defense-in-depth against a mismatch from *any* source (manual plan, planner regression, role typo).
- **Not a replacement for dispatch-time validation.** The existing role check at dispatch stays as the deeper net.
- **Not model quality/context validation.** Only *availability* (is the model pulled) — not context-window fit or throughput.
- **Not a live-model smoke test.** Actually invoking a model on real hardware is #176 / the pre-release live-validation cycle. Availability ≠ good output.
- **Not an authorization gate.** This validates request *satisfiability*, not whether the operator is *permitted* to create the cycle. Permissions/safety policy are a separate concern.

---

## 6. Preflight Policy

A deterministic validation gate applied before a cycle is persisted or dispatched. It is composed of independent, pure checks over the resolved profile snapshot and the requested workloads; each check yields **allow**, **block(reasons)**, or **unverifiable(reasons)**. The gate returns a **decision summary** aggregating blocking findings and warning findings. **If any check blocks, the cycle is rejected — even if other checks are unverifiable; warnings ride alongside the rejection but do not alter the rejection reason.** Otherwise the cycle is allowed and any warnings are returned with it. (This aggregate shape is what future create-time checks slot into without changing semantics.)

### 6.1 Capability / role satisfiability (#172)

Capability satisfiability is evaluated through the **required role sets implied by the requested workloads** — this SIP validates *static workload-role* satisfiability, not a dynamic per-task capability-registry proof. It does not attempt to prove that every eventually-materialized task capability has a handler; **dispatch-time plan validation remains the deeper defense.**

- The gate maps each requested workload (and workload-expanding defaults) to its required role set and blocks when the enabled squad roster is missing any required role.
- **Workload-expanding defaults MUST be accounted for, not just the bare workload sequence** — in particular, **build-task paths require a builder-capable squad** (the motivating `builder.assemble` case). A build-enabled cycle on a builder-less squad MUST be blocked at create time.

### 6.2 Model availability (#224)

- The gate resolves the models named by the profile's enabled agents and checks each against the backend's set of available (pulled) models.
- A profile-named model that the backend reports as **not available** is a `block`.
- **Matching is exact on the canonical model name/tag.** Until an explicit alias/normalization table exists, prefix or family similarity does **not** imply availability — `qwen2.5:7b` is not `qwen2.5:7b-instruct`. Exact matching is the conservative default (a profile naming a tag the host doesn't hold is then a clear, fixable config error, never a silent fuzzy match); an alias table can relax it later.

### 6.3 Block / warn / allow behavior (product decision)

**The model-availability preflight blocks only on definitive negative evidence.**

| Backend state | Required model | Result |
|---|---|---|
| reachable | present | **allow** |
| reachable | absent | **block** |
| unreachable / unconfigured | — | **unverifiable → warn, allow** |

**"Unconfigured" here means availability is not measurable from the current caller** (no reachable model-lister for this host/lane) — *not* that the profile is missing a required provider configuration. A profile that is known-invalid for the runtime (e.g. it requires a provider the deployment does not configure at all) is a stronger *configuration* failure, out of scope for this warn-and-allow path — a candidate future preflight check (Appendix B), not a reason to weaken this one into a bypass.

If the backend cannot be queried, the result is *unverifiable* and MUST be surfaced as a warning, **not** a create-time rejection. This keeps the SIP from being read later as "any uncertainty should block" — blocking cycle creation whenever the LLM backend briefly hiccups would be a worse failure than the one this SIP fixes.

**Unverifiable model availability MUST be surfaced to the operator even when creation is allowed** — otherwise the system silently permits the exact failure mode this SIP exists to make legible. Minimum expectation: a **warning-level** operator message (not merely informational — it may still lead to a fast runtime failure) returned on the create response **and printed by the CLI after a successful create**. Additional surfaces (cycle metadata, operator/runtime event, Continuum) are desirable but out of scope here (see Open Questions).

---

## 7. Error Surface

- A preflight rejection is a **client/config error, not a server error** → **HTTP 422** (the request is syntactically valid but semantically unsatisfiable given the selected profile/runtime environment). It flows through the existing cycle-error handling, so the CLI surfaces the message unchanged.
- Error content is standardized and actionable:
  - **Missing role:** squad-profile name · requested workload/modifier · required role · provided roles · recommended action.
    > *Cycle create rejected: workload `build` requires role `builder`, but squad profile `full` provides `lead`, `strat`, `dev`, `qa`, `data`. Choose a builder-capable profile or disable the build workload.*
  - **Missing model:** squad-profile name · required model · backend host/context if available · pulled models (concise) · recommended action.
    > *Cycle create rejected: squad profile `full` requires model `qwen3.6:27b`, not available on this host. Pull the model or choose a profile that uses available models.*

---

## 8. Doctor Parity

`squadops doctor` gains the same model-availability finding, driven by the shared decision, so proactive environment diagnosis and create-time enforcement do not drift. (Today `doctor` checks *bootstrap-profile* models by shelling out to `ollama list`, a separate path from the API's model check; the shared decision unifies the *judgment* even where the two callers gather the pulled-model list differently.)

---

## 9. Acceptance Criteria

1. A rejected cycle-create request **creates no cycle row**.
2. A rejected cycle-create request **creates no dispatch request** and **starts no background execution**.
3. The operator receives a **clear, actionable error** naming the missing role or the missing model (per §7).
4. **Build-task expansion is honored:** a build-enabled cycle on a builder-less squad is blocked at create time (§6.1).
5. **Unverifiable ≠ blocked:** when the backend is unreachable, the cycle is still created and the operator is warned (§6.3) — creation is not blocked on missing evidence.
6. **Unverifiable warning is visible:** when creation succeeds with unverifiable model availability, the API response includes a warning-level message **and the CLI visibly prints it** — the warning cannot be returned-but-invisible.
7. **Doctor parity:** the same model-availability finding enforced at create time is visible through `doctor` when `doctor` has enough backend visibility to evaluate it.
8. **Defense in depth intact:** dispatch-time validation still rejects a materialized-plan mismatch the static preflight cannot see (proving the preflight is an addition, not a replacement).
9. **Happy path unchanged:** a satisfiable cycle with available models is created and dispatched exactly as today.

---

## 10. Risks

- **Model-name / tag normalization false positives.** The backend's pulled list is exact tags; a profile naming `qwen2.5:7b` against a host holding `qwen2.5:7b-instruct` (or an implicit `:latest`) could *falsely block*. **Mitigation (decided, §6.2): exact canonical-tag matching, no prefix/family inference, until an explicit alias table exists** — so a mismatch is a clear, fixable config error rather than a silent fuzzy match.
- **Ignored warnings.** Warn-and-allow only helps if the warning surface is actually seen; if it lands somewhere no operator looks, the unverifiable case regresses to a silent failure. Hence the §6.3 minimum-surface requirement.
- **Over-blocking from an incomplete required-role map.** If the workload→required-role mapping misses an expanding default (§6.1), a valid cycle could be blocked, or the live builder bug could be missed. The static map must stay **aligned with the same workload-role constants and materialized-plan validation assumptions** used by dispatch-time validation — there may be no single identical source, since dispatch validates *materialized-plan* capabilities while the preflight is *static*.

---

## 11. Open Questions

1. **Where should unverifiable (backend-unreachable) warnings be surfaced besides the immediate create response?** (Cycle metadata, a runtime/operator event, Continuum, doctor.) The minimum — create response + CLI echo — is decided (§6.3); the broader surface is open.
2. **Exact workload/defaults → required-role map.** Confirm the complete set of `applied_defaults` toggles (beyond the bare workload sequence) that expand required roles, so §6.1's build-task rule generalizes correctly.

---

## 12. Delivery Coordination

Delivery may be split across lanes, but **the behavioral contract is unified: one create-time preflight gate.** Per the 1.2.0 plan (§2/§5.6) and the #224 ownership decision:

- **Spark** owns the **model-availability** half — the shared decision (lifted from the existing profile-CRUD warning) and the `doctor` parity check; model/device availability is the Spark domain.
- **Macbook** owns the **capability/role** half and the **create-route wiring** that invokes both checks.

The two lanes touch different functions on the same cycle-API surface; annotate the seam so the merge stays mechanical.

---

## 13. Testing

- **Capability (unit):** missing required role per workload → block with the role named; satisfied squad → allow; each workload's required-role set; **build-enabled + builder-less squad → block** (the live bug).
- **Model (unit):** reachable + absent → block (message names the model); unreachable → unverifiable (warn, allow); all present → allow; **tag-normalization** case (present under a different tag) behaves per the chosen matching rule.
- **Create route (integration, real persistence):**
  - missing role → 422, **no cycle row, no dispatch**;
  - missing model → 422, **no cycle row, no dispatch**;
  - **unverifiable model availability still persists the cycle** (warn, not block);
  - happy path → created + dispatched unchanged.
- **Defense in depth:** dispatch-time guard still catches a materialized-plan mismatch the static preflight cannot see.
- **Doctor:** flags a squad-profile model that isn't pulled; passes when all present.

---

## 14. Relationships

- **Depends on** #173 (profile-name consolidation) — merged; evaluate against `smoke`/`lite`/`full`.
- **Complements** the planner capability filter (separate) — this is the defense-in-depth net.
- **Precedent** SIP-0089 §2.5 `reserve_buffer_decision` — a pure pre-dispatch gate; this hoists the same class of check to create time.
- **Sequenced with** #176 (small-model smoke invariant) — complementary; neither replaces the other.

---

## Appendix A — Implementation Notes (non-normative)

Likely seams; the SIP defines the policy, not the patch.

- **Choke point:** the create-cycle API route, after the squad-profile snapshot is resolved and before the first domain-object construction / persist. A preflight that raises the existing cycle-error type funnels through the current error handler to HTTP 422 with no new plumbing.
- **Hoisted role logic:** the dispatch-time role enforcement (`_check_required_roles` and the `REQUIRED_*` role-set constants) expressed as a pure create-time decision over `(profile, workload_sequence + expanding defaults)`. Static analog of the existing materialized-plan check (`ImplementationPlan.validate_against_profile`), which stays as the deeper net.
- **Hoisted model logic:** the existing profile-CRUD `_check_model_availability` (currently a non-fatal warning list) lifted into a shared, blockable decision over `(profile models, pulled models)`, with the pulled list fetched by the caller (`LLMPort.refresh_models()` for the route; `ollama list` for doctor).
- **Suggested home:** a pure `cycles/preflight` module importable by both the API route and the CLI doctor without an import-hygiene violation.
- **Doctor result shape:** reuse the existing doctor `CheckResult` so the model finding renders through the standard check registry.

## Appendix B — Future preflight checks (not in scope)

Cycle Create Preflight is intended as an **extensible policy seam**. Plausible future create-time checks — named to establish the pattern, explicitly out of scope here: context-window fit, budget/reserve readiness, tool availability, workspace/repo availability, secrets readiness, runtime-lane compatibility, storage/output-path readiness, and **provider/configuration validity** (a profile requiring a provider the deployment does not configure at all — the stronger config-failure case §6.3 deliberately excludes from warn-and-allow).
