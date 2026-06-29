# SquadOps 1.2.0 Release Plan + Two-Lane Continuation

**Status:** draft for review · established 2026-06-29 · extends `docs/plans/1-1-x-two-lane-plan.md`

## 1. Frame — mirror the 1.1 playbook

1.1 shipped on a simple, repeatable shape, and 1.2.0 reuses it verbatim:

- **One headline implementing SIP** (1.1 = SIP-0089 Agent Runtime State) **on a named hardening foundation.** The umbrella vision SIP (0088) stayed *accepted, not promoted* — promoting it would overstate what landed.
- **Two lanes off `main`, run concurrently, bundled at release:** Macbook = the feature/minor line, Spark = the hardening/patch line.
- **Semver discipline (confirmed in-repo, `1-1-x-hardening-plan.md:14`):** bug fixes → 1.1.x patches; capability-bearing SIPs → 1.2.0 minors; tech-debt/arch → opportunistic, **never version-gating.**

So: **1.2.0 = Macbook capability SIPs. 1.1.x = Spark hardening, shipping as patches when ready (exactly as 1.1.1 did).**

## 2. The 1.2.0 scope (Macbook lane)

### Committed core — this is what defines the 1.2.0 minor
| Item | What | SIP status | Lane-owned surface |
|------|------|-----------|--------------------|
| **#233** | SIP-0089 §3.5 — route cycle recruitment through the coordinator to acquire a FocusLease | 0089 completion (no new SIP) | `src/squadops/runtime/*` |
| **#244** | SIP-0089 §4.5/D25 — wrap coordinator lease+activity+mode in one Postgres txn (new `RuntimeTransaction` UoW port) | 0089 completion (no new SIP); depends on #233 | `src/squadops/runtime/*`, `ports/runtime/*` |
| **Preflight SIP (#172 + #224)** | Fail-fast at cycle-create: capability/role satisfiability (#172) **and** model availability (#224), behind one preflight seam | **New small SIP** | `api/routes/cycles/*`, `cli/commands/{cycles,doctor}.py`, `bootstrap/setup/checks.py` |
| **#231** | Consolidate agent status vs runtime-state terminology (`network_status` → `runtime_status`); completes the 0089 status model | doc/refactor (no new SIP) | `api/runtime/health_checker.py`, `runtime/lifecycle_status.py` |

This core is **almost entirely Lane-M-owned surface** (runtime/, executor, cycle API) → minimal cross-lane collision, and the preflight directly fixes the model-mismatch failure we hit live on 2026-06-29.

### Stretch headline — SIP-0090 Agent Embodiment (the banner, gated)
SIP-0090 (accepted, the canonical "v1.2 candidate") is the natural 1.2.0 banner: *new surface* (embodiment substrate, identity/surface split, Discord first proof point), vision-aligned (ambient/Discord presence), and it builds on the lease/recruitment substrate the core (#233/#244) completes.

**Recommendation:** design SIP-0090's implementation plan *in parallel* with the core, but **do not let it gate the 1.2.0 minor.** If its plan + first Discord proof land in the release window, it's the headline; if not, it anchors **1.3.0** (alongside SIP-0091 Temporal, already v1.3-tagged) and 1.2.0 ships on the core. This is the 1.1 discipline applied — ship when the foundation is done, don't gold-plate. **← the one decision for you (see §7).**

### Deliberately NOT in the 1.2.0 gating set
- **#152** (split `cycle_tasks.py`) and **#186** (decompose `DispatchedFlowExecutor`) — tech-debt/arch, *never version-gating*. They are clearing moves, sequenced around the features (see §5), not release content.
- **#194 / #114** (SIP-0093 B′ authoring depth, typed-eval) — feature-bearing but they live in the `cycle_tasks.py` collision zone. Hold for **1.2.x**, or pull in only under the §5 sequencing rule. Not core.

## 3. The 1.1.x hardening scope (Spark lane)

Continues the `1-1-x-hardening-plan.md` line, shipping as patches:
- **Build quality:** **#276** (acceptance passes on a non-running app — stub fallback masks ImportError; high priority), #279 (instrumented+builder request profile), #280 (generated frontend hardcodes API base/CORS).
- **Test/infra:** #176 (smoke-invariant integration test), #157 (api/comms/integration coverage), #242 (serviceless integration rot), #198 (Starlette ≥0.136 pin).
- **Platform/debt:** #158 (schema_migrations table + configurable timeouts), #234 (DbRuntime port leaks sqlalchemy), #237 (drop 3.11 → 3.12), #173 (consolidate squad-profile names; also fix the `active_profile: full-squad` footgun).
- **API surface:** #218/#219 (prefix/versioning standard + unversioned chat routes).

## 4. Ownership boundaries (the overlap contract — extends the 1.1 two-lane plan)

The existing boundaries from `1-1-x-two-lane-plan.md` **still hold and already solve most of the risk.** Restated:

- **Lane M (Macbook) owns:** `src/squadops/runtime/*`, `src/squadops/api/runtime/*`, `adapters/persistence/runtime/*`, **`adapters/cycles/dispatched_flow_executor.py`**, the SIP-0089/0090 surface, `cli/commands/agent.py`.
- **Lane S (Spark) owns:** `adapters/comms/*`, `adapters/telemetry/*`, `adapters/persistence/postgres/*`, CI/test infra, `adapters/cycles/factory.py` + `workflow_tracker_factory.py`, the API-prefix work.
- **Shared, append-only — announce before editing, never reformat wholesale:** `pyproject.toml`, `ci-constraints.txt`, `tests/requirements.txt`, `scripts/dev/run_regression_tests.sh`.
- **Migration ranges (already deconflicted):** Macbook `1100–1199`, Spark `1000–1099`.
- **Process:** issue-first / branch-first / per-phase commits / `ruff format .` fail-stop before push / no silent fixes.

### 1.2.0-specific collision findings (from the file-collision matrix)
| File | Risk | Verdict |
|------|------|---------|
| **`capabilities/handlers/cycle_tasks.py`** | **CRITICAL — only true cross-lane hot file.** Spark #276 (`QATestHandler` + `_detect_stubs`) × Mac #152 (whole-file split) × Mac #114 (typed-eval). | **Must-sequence (§5.1).** Keep #152 out of the concurrent window. |
| `adapters/cycles/dispatched_flow_executor.py` | HIGH churn (#186/#233/#172/#244) but **Mac-internal — no Spark contention.** | Within-lane sequencing only (§5.2). Spark ignores this file. |
| `api/runtime/` (Dockerfile, `migrations.py`) | MEDIUM — Spark #237/#158 × Mac #233/#244 (same applier). | Announce-before-edit; coordinate timing (§5.4). |
| `config/squad-profiles.yaml` | MEDIUM — Spark #173 (rename) vs #279 (add); Mac #224 read-dep. | Spark-internal sequence #173→#279 (§5.3). |
| `infra/migrations/`, `CLAUDE.md`, `README.md` | LOW — mostly different files / trivial doc merges. | Migration ranges + announce-before-edit cover it. |

## 5. Cross-lane sequencing (the critical path)

Only four ordering constraints exist; everything else is lane-independent.

1. **Spark #276 BEFORE Mac #152.** #276 fixes a real bug in `cycle_tasks.py`; #152 mechanically moves all 3,246 lines. Land #276 first, then Mac does #152 as an opportunistic clearing move. Never concurrent.
2. **Mac runtime wiring (#233 → #244 → #172) BEFORE Mac #186.** Don't decompose `dispatched_flow_executor.py` while still wiring features into it. #186 is non-gating — it runs *after* the runtime features land (or slips to 1.2.x).
3. **Spark #173 (profile rename) BEFORE Spark #279 (profile add)**, and ideally before Mac #224's preflight finalizes (read-dep on profile names; low risk since read-only). #173 also kills the `active_profile: full-squad` footgun.
4. **Coordinate Spark #237 (Dockerfile) / #158 (`migrations.py`) timing with Mac #233/#244.** Same `api/runtime/` applier path — announce-before-edit, don't land mid-flight.

### 5.5 Spark items that should land before/with 1.2.0

Most Spark hardening is independent of the feature line, but four items have a real relationship to 1.2.0 — front-load these:

1. **#173 (profile-name consolidation + `active_profile` footgun) — BEFORE the Preflight SIP (#224).** #224 reads squad-profile names/models; #173 renames them and fixes the exact `full-squad`-on-a-non-Spark-box footgun #224 guards against. Build the preflight against the final names. *(Downstream: the `local-cycle-squad-profiles` memory + e2e cheatsheet need a name sweep when this lands.)*
2. **#158 (schema_migrations + applier hardening) — EARLY, before Mac's runtime migrations.** 1.2.0 pours an unusual amount of new migration surface through the same applier: #244 (RuntimeTransaction), #233 (lease wiring), #231 (`1100_agent_runtime_state.sql`), and the SIP-0090 Phase 1 embodiment table. Harden the applier first so they all land on a tracked path. *(The configurable-timeouts half of #158 is independent.)*
3. **#176 (framework smoke invariant test) — WITH 1.2.0.** The automated form of the live-validation that caught #270/#272 — a regression net for 1.2.0's runtime changes + preflight. Reads the executor only (low collision); rides *into* the feature release per the convention (safe hardening → even minor).
4. **#198 (pin FastAPI/Starlette) — NOW, regardless.** Pure CI-health patch; land it before 1.2.0 work piles up against a drifting gate.

**Not before/with 1.2.0:** #276 (its only tie is preceding #152, a *1.3.0* item — rides the patch line on its own schedule, not 1.2.0-gating), #234/#186/#152 (1.3.0 stabilization), #237/#279/#280/#157/#242 (independent).

## 6. Versioning, cadence & release mechanics

**Even/odd minor convention** (parity gates *features*, not hardening — #281):
- **Even minor (1.2.0, 1.4.0, …) = feature release** — led by ≥1 headline feature SIP. Hardening rides along freely: safe, ready hardening (#231, small fixes) lands here alongside features.
- **Odd minor (1.3.0, 1.5.0, …) = stabilization release** — feature-free; the home for the big risky refactors quarantined out of the feature line (**#186** decompose executor, **#152** split handlers, **#234** DbRuntime port) + accumulated debt. Cut when consolidation has piled up enough — substance gates the cut, not the clock.
- **Patch (x.y.Z)** — urgent/small fixes any time, either lane (the 1.1.1 cadence). Never held for the next odd release.

So **1.3.0 is the first stabilization release** — the natural home for #186/#152/#234 and the Spark lane's structural backlog. Patches keep flowing from both lanes throughout.

**Mechanics (mirror 1.1.0 → 1.1.1):**
- 1.2.0 bundles the Macbook core when it's done **and live-validated on the deployed stack** — the 1.1 lesson: live validation caught #270/#272 the unit suites couldn't. Run a real `lite` cycle before declaring the minor.
- **SIP lifecycle:** keep SIP-0088 umbrella *accepted* (don't promote). At 1.2.0: author + accept the Preflight SIP; promote SIP-0090 only for the phases that actually land (Phase 1); #233/#244/#231 are 0089 completion (no promotion needed, note in CHANGELOG).
- Version bump via `scripts/maintainer/version_cli.py bump 1.2.0` (needs venv); honest grouped CHANGELOG; sweep CLAUDE.md/README/ROADMAP version markers (they were stale at 1.1.x — don't repeat).

## 7. Decision (resolved 2026-06-29): phase SIP-0090 across the even releases

SIP-0090 is staged along its own phase boundary rather than shipped whole:
- **1.2.0 (feature) headline = runtime core (#233/#244) + SIP-0090 Phase 1** (core embodiment model + budget primitives) — fully internal, CI-able, live-validatable like 0089. A bannerable new-surface story without external-service risk.
- **Later even releases (1.4.0, 1.6.0, …) = SIP-0090 Phases 2–4** (Discord → RuntimeActivity integration → browser) + SIP-0091 Temporal — sequenced *in order* as each proves out, **not pre-bound to specific version numbers** (Phase 1 will reshape what 2–4 should be; OQ#1 — the embodiment↔lease question — resolves during Phase 1).
- **Odd releases between (1.3.0, 1.5.0, …)** stabilize whatever the prior feature drop shook loose.

Why phased, not all-in: SIP-0090's value proof (Phases 2–4) lives behind Discord, which the SIP itself flags as hard-to-CI (§10.2), and Phase 3 stacks on FocusLease/RuntimeActivity semantics #233/#244 finish in the *same* release. Phase 1 has none of that risk — its acceptance is "records exist and transition cleanly; no adapter required yet" (§13). So Phase 1 anchors the feature line; the external-surface phases get their own even releases with room to validate.

## Appendix — Spark-lane kickoff prompt

> **Spark terminal — 1.1.x hardening lane (continues alongside Macbook's 1.2.0 feature line).**
>
> You own the **1.1.x hardening/patch line**. Work off `main`, issue-first and branch-first, per-phase commits, `ruff format .` fail-stop before every push, no silent fixes. Ship patches as they land (the 1.1.1 cadence).
>
> **Your scope (track:spark), in priority order — front-load the 1.2.0 prerequisites:** **#173** (profile-name consolidation + `active_profile` footgun — *start here*; the 1.2.0 preflight depends on the final names), **#158** (schema_migrations + applier hardening — before Mac lands runtime migrations), **#176** (framework smoke invariant test — the 1.2.0 regression net), **#198** (pin FastAPI/Starlette — CI health, now). Then the independent backlog: #276 (stub-fallback masking — real correctness bug, but not 1.2.0-gating), #279, #280, #157, #242, #234, #237, #218/#219.
>
> **Ownership — do NOT edit Macbook-lane files:** `src/squadops/runtime/*`, `src/squadops/api/runtime/*` (except coordinate on `migrations.py`/`Dockerfile` — announce first), `adapters/persistence/runtime/*`, **`adapters/cycles/dispatched_flow_executor.py`** (Mac is decomposing it — hands off), the SIP-0089/0090 surface, `cli/commands/agent.py`.
>
> **Hard sequencing rules:**
> - **1.2.0 prerequisites first:** **#173 before the Macbook preflight (#224) finalizes** (it reads the profile names you're renaming), and **#158 before Macbook lands runtime migrations** (#233/#244/#231 + SIP-0090 Phase 1 all flow through the applier). Coordinate timing with the Macbook lane on both.
> - **#276 before Macbook starts #152** (the `cycle_tasks.py` split) — but #152 is a *1.3.0* item, so #276 is **not** 1.2.0-gating; sequence it whenever, just never concurrent with #152. Tell the Macbook lane when #276 merges.
> - **#173 (profile rename) before #279 (profile add).** #173 also fixes the `active_profile: full-squad` footgun.
> - Migrations: Spark uses range **1000–1099** only (Mac owns 1100–1199).
> - Announce before touching shared append-only files (`pyproject.toml`, `ci-constraints.txt`, `tests/requirements.txt`, `run_regression_tests.sh`) and before `api/runtime/{Dockerfile,migrations.py}`.
>
> Post a corrective comment on any "reduce-scope" issue before narrowing it. Full plan: `docs/plans/1-2-0-release-plan.md`.
