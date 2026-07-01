# SIP-0095 Cycle Create Preflight — Implementation Plan

**Status:** draft (for review before implementation) · **Created:** 2026-07-01 · **Branch:** `feature/sip-0095-cycle-create-preflight`
**Implements:** `sips/accepted/SIP-0095-Cycle-Create-Preflight.md` (accepted 2026-07-01)
**Lanes:** Macbook (capability half + route wiring) · Spark (model-availability half + doctor parity)

This plan resolves SIP-0095's two open questions and reconciles the SIP against the actual code, then lays out the build. **Read §1–§3 first — they contain one material scope correction to the accepted SIP that needs a nod before implementation.**

---

## 1. Open Question 1 — where to surface *unverifiable* warnings

**Resolved:** the operator-visible surfaces are **(a) the create API response, (b) the CLI echo after a successful create, and (c) a durable warning persisted on the cycle record** (visible in `squadops cycles show`). Runtime-event and Continuum surfaces are **explicitly deferred** (optional follow-ups), not built here.

**Why this set:**
- (a) + (b) cover the operator *at create time* — already SIP-mandated (§6.3).
- (c) covers the *post-hoc investigator*: when a run later misbehaves, `cycles show` reveals "model availability was unverifiable at create time," turning a silent condition into a durable, queryable signal — the whole "make it legible" goal.
- Deferring events/Continuum honors the SIP-0089 §2.5 discipline (reuse existing surfaces, don't mint a new EventType or UI plumbing for a small SIP). If a runtime-event surface is wanted later, it rides the existing event bus as a follow-up.

**Implication:** the create-cycle response DTO gains an optional `warnings: list[str]` (or `list[{code,message,severity}]`) field; warnings are stored on the cycle record (a `preflight_warnings` entry in existing cycle metadata — no new table). Warning severity is **`warning`**, never `info` (§6.3).

---

## 2. Open Question 2 — the `applied_defaults` → required-role map

**Resolved (from tracing `cycles/task_plan.py`).** The create-time capability check evaluates the **static** required-role sets implied by the requested workloads:

| Requested work | Required roles (create-time-checkable) | Source |
|---|---|---|
| workload `FRAMING` | `{strat, dev, qa, data, lead}` (`REQUIRED_PLAN_ROLES`) | `task_plan.py:278` |
| workload `REFINEMENT` | `{lead, qa}` (`REQUIRED_REFINEMENT_ROLES`) | `:285` |
| workload `EVALUATION` | `{strat, dev, qa, data, lead}` | `:296` |
| workload `WRAPUP` | `{data, qa, lead}` (`REQUIRED_WRAPUP_ROLES`) | `:299` |
| workload `IMPLEMENTATION` | **none** (builder-optional; graceful) | `:289–294` |
| legacy `plan_tasks` (default true) | `{strat, dev, qa, data, lead}` | `:324–325` |
| legacy `build_tasks` | **none** (builder-optional; graceful) | `:312–322` |

The check reads `run.workload_type` (per-run, forming the sequence across a multi-run cycle) or, when absent, the legacy `applied_defaults.plan_tasks` / `build_tasks` flags — the same dispatch (`generate_task_plan:363`) uses.

### 2.1 Scope correction to SIP-0095 (needs your nod)

Tracing the code contradicts one SIP claim: **`build_tasks` / `IMPLEMENTATION` do NOT statically require a `builder` role.** `_has_builder_role` selects the builder-vs-non-builder step path (`task_plan.py:290, 313`); a builder-less squad gracefully runs the **non-builder** build steps. That graceful fallback is *intentional*, not a bug.

Therefore **SIP-0095 §9 acceptance criterion #4 ("a build-enabled cycle on a builder-less squad is blocked at create time") is not implementable as written and should be revised.** The `builder.assemble`-on-a-builder-less-squad failure (#172's live case) comes from a **materialized** implementation plan (authored *during* the framing run), and is validated by `ImplementationPlan.validate_against_profile` — which is already wired, but at **dispatch** (`task_plan.py:492`, inside `generate_task_plan`), not at create time. At create time there is no plan to check, so this class of mismatch is *structurally* not a create-time gate.

**Recommended revision (baked into this plan; confirm in review):**
- The **create-time** capability check covers **static workload→role satisfiability** only (the table above). It catches "you requested a `WRAPUP` workload but your squad has no `data` role," etc.
- The **materialized-plan** capability mismatch (the builder case) stays with `validate_against_profile`. It already runs at dispatch; **optionally** hoisting it earlier — to the `progress_plan_review` gate, right after framing authors the plan and before implementation dispatch — is the real "catch #172 sooner" win, but it is a **distinct seam from create-time** and arguably its own small follow-up (not this SIP's create-time scope).

**Decision for you:** (A) ship SIP-0095 as create-time-only (static role + model) and file the gate-time hoist of `validate_against_profile` as a separate follow-up to fully close #172; or (B) include the gate-time hoist as Phase 5 of this plan. I recommend **(A)** — it keeps SIP-0095 cohesively "create-time," and the gate hoist is a clean, separately-reviewable change. This plan is written for (A) with (B) sketched as an optional appendix phase.

---

## 3. What this plan delivers

A create-time preflight that, before a cycle is persisted or dispatched:
- **blocks** when the resolved squad snapshot is missing a role the requested workloads statically require (§2);
- **blocks** when a profile-named model is definitively not pulled on the backend;
- **warns-and-allows** when model availability is unverifiable, surfaced per §1;
- returns **HTTP 422** with an actionable, standardized message;
- shares the model check with `squadops doctor`.

Dispatch-time validation (role check + `validate_against_profile`) is untouched and remains the deeper net (SIP §5).

---

## 4. Design

### 4.1 New module `src/squadops/cycles/preflight.py` (pure)

```python
@dataclass(frozen=True)
class Finding:            # one check outcome
    code: str             # e.g. "missing_role", "model_unavailable", "model_unverifiable"
    severity: str         # "block" | "warning"
    message: str          # standardized, actionable (SIP §7)

@dataclass(frozen=True)
class PreflightDecision:  # the aggregate "decision summary" (SIP §6)
    blocking: tuple[Finding, ...]
    warnings: tuple[Finding, ...]
    @property
    def rejected(self) -> bool: return bool(self.blocking)

def required_roles_decision(profile, workload_types) -> PreflightDecision   # pure (Mac)
def model_availability_decision(profile, pulled_models: list[str] | None) -> PreflightDecision   # pure (Spark)
def combine(*decisions) -> PreflightDecision   # any block ⇒ rejected; warnings ride alongside (SIP §6)
```

Pure over already-fetched inputs (mirrors `reserve_buffer_decision`). Callers do the I/O. Importable by both the API route and the CLI `doctor` with no D26 violation (`cycles/*` is domain).

- `required_roles_decision`: derive `profile_roles = {a.role for a in profile.agents if a.enabled}`, map each requested workload to its `REQUIRED_*` set (§2), block on any missing role. Reuses the constants from `cycles/models.py:181`.
- `model_availability_decision`: `pulled_models is None` → one `warning` finding (`model_unverifiable`); else each enabled agent model **exact-matched** against `pulled_models` (SIP §6.2 — no prefix/family inference), absent → `block`.

### 4.2 Create-route seam (`api/routes/cycles/cycles.py::create_cycle`, Mac)

Insert after `resolve_snapshot` (line 50, gives `profile.agents`) and before first persist (line ~104):

```python
decision = combine(
    required_roles_decision(profile, _requested_workloads(body)),
    model_availability_decision(profile, await _pulled_models_or_none()),
)
if decision.rejected:
    raise CycleError(decision.summary())          # → handle_cycle_error → HTTP 422
warnings = [f.message for f in decision.warnings]  # attached to response + persisted (§1)
```

- `_pulled_models_or_none()` calls `LLMPort.refresh_models()`, returning `None` when the port is unconfigured/unreachable (the unverifiable path).
- 422: confirm `handle_cycle_error` maps `CycleError` (or a `PreflightRejected(CycleError)` subclass) to 422; add the mapping if it currently maps to 400.
- `warnings` flow into the response DTO and the persisted cycle metadata (§1).

### 4.3 doctor parity (`bootstrap/setup/checks.py`, Spark)

Add a check that feeds the squad-profile models + the pulled list into `model_availability_decision` and renders each `Finding` as a `CheckResult`. Reconciles the current divergence (doctor uses `subprocess ollama list` + bootstrap profile) by sharing the *judgment*, not the fetch.

---

## 5. Cross-lane sequencing (PR order)

The two lanes touch `api/routes/cycles/*` and `cycles/*`; sequence to keep merges mechanical (SIP §12, plan §5.6 of the 1.2.0 plan):

1. **Mac — `cycles/preflight.py` scaffold** (the dataclasses + `combine` + `required_roles_decision`). Pure, no route change. Lands first; Spark rebases onto it.
2. **Spark — `model_availability_decision`** added to `cycles/preflight.py` (new function, same module — no collision) + the doctor check. Independent of the route.
3. **Mac — create-route wiring** (`cycles.py`) calling `combine(required_roles_decision, model_availability_decision)`. Depends on 1 + 2 being on main.
4. **Mac — response/persistence** of warnings (DTO + cycle metadata) + 422 mapping.

Annotate the `cycles.py` seam with a one-line comment marking the Mac wiring vs the Spark helper, per the §5.6 convention.

---

## 6. Phases

1. **Preflight module + capability decision (Mac)** — `preflight.py`, `required_roles_decision`, `combine`; unit tests (§7). No behavior change yet (nothing calls it).
2. **Model decision + doctor (Spark)** — `model_availability_decision`; doctor check; unit tests.
3. **Route wiring (Mac)** — call both in `create_cycle`; 422 mapping; block path.
4. **Warning surface (Mac)** — response DTO `warnings` + persist on cycle metadata + CLI echo on success.
5. *(Optional, pending §2.1 decision (B))* — hoist `validate_against_profile` to the `progress_plan_review` gate to catch the materialized-plan/builder mismatch earlier than dispatch.

---

## 7. Testing (maps to SIP §13 + the §2.1 correction)

- **Unit — capability:** each workload's `REQUIRED_*` set; missing role → `block` naming the role; satisfied → allow; **`build_tasks`/`IMPLEMENTATION` on a builder-less squad → allow** (graceful fallback — the corrected behavior, *not* a block).
- **Unit — model:** reachable + absent → block (names the model); `None` → `warning` (unverifiable); all present → allow; **tag mismatch** (`qwen2.5:7b` vs pulled `qwen2.5:7b-instruct`) → block (exact matching, SIP §6.2).
- **Unit — combine:** any block ⇒ rejected even with warnings present; warnings ride alongside without altering the reject reason.
- **Integration (create route, real persistence):** missing role → 422, **no cycle row, no dispatch**; missing model → 422, no row/dispatch; **unverifiable → cycle IS created + warning on response and persisted**; happy path → 201 unchanged.
- **Defense-in-depth:** dispatch-time `validate_against_profile` still rejects a materialized-plan mismatch the static preflight can't see (proves addition, not replacement).
- **doctor:** flags a squad-profile model not pulled; passes when all present.

---

## 8. Risks / residual

- **422 mapping:** if `handle_cycle_error` currently maps `CycleError` → 400, either add a `PreflightRejected` subclass → 422 or adjust the mapping; verify no other `CycleError` caller depends on the current status.
- **Warning-surface persistence:** confirm the cycle record has a metadata field (or `applied_defaults`-adjacent slot) to carry `preflight_warnings` without a schema migration; if not, a small additive migration (Mac lane, migration range 11xx).
- **Model-name exactness:** exact tag matching (SIP §6.2) means `config/squad-profiles.yaml` model tags must match Ollama's reported tags exactly; a mismatch is a *clear config error* by design, but worth a one-time audit of the current profiles against a pulled list.
- **Scope creep into the gate:** §2.1 decision (B) would pull the plan-review gate into scope — keep it out unless you choose (B).

---

## 9. Summary of decisions baked in (for review)

1. **OQ1:** warnings surface on create response + CLI echo + persisted cycle metadata; defer event/Continuum.
2. **OQ2:** static workload→role map as tabled; **`build_tasks`/`IMPLEMENTATION` require no static role** (builder-optional).
3. **Scope correction:** SIP §9 AC#4 revised — the builder/materialized-plan case is a dispatch/gate concern (`validate_against_profile`), not create-time. **Recommend option (A):** SIP-0095 ships create-time-only; the gate-time hoist is a separate follow-up.

Awaiting your review before implementation begins.
