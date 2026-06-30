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

> **#224 ownership — RESOLVED 2026-06-29 (option a, the split is preserved).** The Spark-lane review surfaced that this plan's §2 table had silently folded the whole Preflight SIP into Mac's surface, dropping the prior sprint split. **Decision (Mac-lane, recorded on #224):** keep the split — **Spark lifts the model-availability helper** (`api/routes/cycles/profiles.py:71-95` → a reusable check both `doctor` and cycle-create call), since model/device availability is the Spark domain; **Mac wires the #172 preflight seam** that calls it. The dual `track:spark`+`track:macbook` labels on #224 stay (each lane owns its half). Per-file ownership detail in §5.6.

### Stretch headline — SIP-0090 Agent Embodiment (the banner, gated)
SIP-0090 (accepted, the canonical "v1.2 candidate") is the natural 1.2.0 banner: *new surface* (embodiment substrate, identity/surface split, Discord first proof point), vision-aligned (ambient/Discord presence), and it builds on the lease/recruitment substrate the core (#233/#244) completes.

**Recommendation:** design SIP-0090's implementation plan *in parallel* with the core, but **do not let it gate the 1.2.0 minor.** If its plan + first Discord proof land in the release window, it's the headline; if not, it anchors **1.3.0** (alongside SIP-0091 Temporal, already v1.3-tagged) and 1.2.0 ships on the core. This is the 1.1 discipline applied — ship when the foundation is done, don't gold-plate. **← the one decision for you (see §7).**

### Deliberately NOT in the 1.2.0 gating set
- **#152** (split `cycle_tasks.py`) and **#186** (decompose `DispatchedFlowExecutor`) — tech-debt/arch, *never version-gating*. They are clearing moves, sequenced around the features (see §5), not release content.
- **#194 / #114** (SIP-0093 B′ authoring depth, typed-eval) — feature-bearing but they live in the `cycle_tasks.py` collision zone. Hold for **1.2.x**, or pull in only under the §5 sequencing rule. Not core.

## 3. The 1.1.x hardening scope (Spark lane)

Continues the `1-1-x-hardening-plan.md` line, shipping as patches:
- **Build quality:** **#276** (acceptance passes on a non-running app — stub fallback masks ImportError; high priority), #279 (instrumented+builder request profile), #280 (generated frontend hardcodes API base/CORS — **not fully independent of #176:** a smoke test that probes a generated app beyond localhost is exactly what surfaces this, so sequence #280 near #176/#276, not in the loose backlog).
- **Test/infra:** #176 (smoke-invariant integration test), #157 (api/comms/integration coverage), #242 (serviceless integration rot), #198 (FastAPI pin DONE #195/#202; ≥0.136 adoption deferred — see §5.5).
- **Platform/debt:** #158 (schema_migrations table + configurable timeouts), #234 (DbRuntime port leaks sqlalchemy — **scope grows because of Mac #244:** #244 adds a `RuntimeTransaction` UoW port in the same persistence/runtime area in 1.2.0, so the 1.3.0 #234 reshape must also absorb it; correct order, just a larger blast radius), #237 (drop 3.11 → 3.12 — **changes the support contract:** raising `requires-python` changes what environments can install the package, so it should ride *with* a minor, e.g. 1.2.0, not land as a stealth patch — decide its release home explicitly), #173 (consolidate squad-profile names; also fix the `active_profile: full-squad` footgun).
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
| **`capabilities/handlers/cycle_tasks.py`** | **CRITICAL — only true cross-lane *code* hot file.** Spark #276 (`QATestHandler` at line 2036 + `_detect_stubs`) × Mac #152 (whole-file split) × Mac #114 (typed-eval). Confirmed: the handler #276 edits is inside the 3,246-line file #152 moves. | **Must-sequence (§5.1).** Keep #152 out of the concurrent window. |
| **`api/routes/cycles/{cycles,profiles}.py`** | **MEDIUM-HIGH — the matrix originally missed this.** Mac's Preflight SIP (#172+#224) hooks **cycle-create** here; but **Spark owns the recent history** (#133/#205 PR #264, #150) and **#224 is dual-labeled `track:spark`+`track:macbook`**. Both lanes legitimately edit this surface. | **Pick an owner per file before the preflight starts** (§5.6). Default: Mac owns the cycle-create *route wiring*; Spark owns the *model-availability helper* it calls (see §2 note). |
| `adapters/cycles/dispatched_flow_executor.py` | HIGH churn (#186/#233/#172/#244) but **Mac-internal — no Spark contention.** | Within-lane sequencing only (§5.2). Spark ignores this file. |
| `api/runtime/` (Dockerfile, `migrations.py`) | MEDIUM — Spark #237/#158 × Mac #233/#244 (same applier). | Announce-before-edit; coordinate timing (§5.4). |
| `config/squad-profiles.yaml` | MEDIUM — Spark #173 (rename) vs #279 (add); Mac #224 read-dep. | Spark-internal sequence #173→#279 (§5.3). |
| `ci-constraints.txt` | LOW now — Spark #198 pin already landed (#195/#202); no re-lock pending. A regen only recurs if the deferred ≥0.136 adoption is scheduled (a CI-job task) or a Mac dep-add lands. | If a regen is needed: **coordinated lock-regen window** (it rewrites many transitive lines), not announce-before-append. |
| `CHANGELOG.md`, `docs/ROADMAP.md` | LOW but **predictably conflicting** — both lanes append at release. | Section-per-lane convention in each file; resolve once at the bump, not piecemeal. |
| `infra/migrations/`, `CLAUDE.md`, `README.md` | LOW — mostly different files / trivial doc merges. | Migration ranges + announce-before-edit cover it. |

## 5. Cross-lane sequencing (the critical path)

Only four ordering constraints exist; everything else is lane-independent.

1. **Spark #276 BEFORE Mac #152.** #276 fixes a real bug in `cycle_tasks.py`; #152 mechanically moves all 3,246 lines. Land #276 first, then Mac does #152 as an opportunistic clearing move. Never concurrent.
2. **Mac runtime wiring (#233 → #244 → #172) BEFORE Mac #186.** Don't decompose `dispatched_flow_executor.py` while still wiring features into it. #186 is non-gating — it runs *after* the runtime features land (or slips to 1.2.x).
3. **Spark #173 (profile rename) BEFORE Spark #279 (profile add)**, and before Mac #224's preflight finalizes (read-dep on profile names). **Not "low risk read-only":** #173 *collapses* tiers (profiles disappear), so anything on a dropped name breaks at runtime — see §5.5. #173 also kills the `active_profile: full-squad` footgun.
4. **Coordinate Spark #237 (Dockerfile) / #158 (`migrations.py`) timing with Mac #233/#244.** Same `api/runtime/` applier path — announce-before-edit, don't land mid-flight.

### 5.5 Spark items that relate to 1.2.0

Four Spark items relate to 1.2.0. **This is not a linear chain** — they have three different shapes, and **#198 turned out to be already done** (corrected 2026-06-30 by a reproduce-first check at kickoff):

- **#198 — DONE (pin); not a launch item.** The original plan called this the cheap "do-first" pin. At kickoff, reproduce-first showed the pin half already shipped on `main` via #195/#202: `tests/requirements.txt` caps `fastapi<0.136`, `ci-constraints.txt` locks 0.135.4, and fastapi isn't in `pyproject.toml` so there's no upper-bound to add. CI is already protected. Its *remaining* half (flatten the router cycle → adopt fastapi ≥0.136) is deferred adoption work, not a now-task (see item 1 + "Not before/with 1.2.0").
- **Two genuine cross-lane gates, order-independent of each other: #173 and #158 — the real first Spark moves.** Each unblocks a different Mac workstream; run them early, in either order (or in parallel).
- **One trailing ride-along: #176.** It validates the *assembled* release, so by definition it lands last.

Execution order: **{#173 ∥ #158} → #176 (trailing).**

1. **#198 — already done (pin) + deferred (adoption).** Pin shipped via #195/#202 (above). The remaining ≥0.136 adoption is *not* a Spark-box task: the cyclic include is in the **external `continuum` package** (`console/app/main.py` includes are clean), it needs fastapi ≥0.136 + a **CI-job lock regen** (the `ci-constraints.txt` header forbids regenerating on the aarch64 Spark box), it re-validates the whole API surface the Mac lane is editing, and there's no urgency (the project runs 0.135 fine). Schedule deliberately with a CI lock-regen if/when ≥0.136 is actually wanted; until then #198 is effectively closed for launch purposes.
2. **#173 (profile-name consolidation + `active_profile` footgun) — cross-lane gate, BEFORE the Preflight SIP (#224).** #224 reads squad-profile names/models; #173 renames them and fixes the exact `full-squad`-on-a-non-Spark-box footgun #224 guards against. Build the preflight against the final names. **Blast radius is wider than a rename:** #173 *collapses* the full/spark tier redundancy (profiles disappear, not just relabel), and the names are referenced across ~20 files (`console/`, `cli/commands/profiles.py`, `llm/model_registry.py`, many tests). Anything on a dropped name breaks at *runtime*, not just the preflight — treat it as a behavioral change, not a low-risk read-only rename. *(Downstream: the `local-cycle-squad-profiles` memory + e2e cheatsheet need a name sweep when this lands.)*
3. **#158 (schema_migrations + applier hardening) — cross-lane gate, EARLY, before Mac's runtime migrations.** 1.2.0 pours an unusual amount of new migration surface through the same applier: #244 (RuntimeTransaction), #233 (lease wiring), #231 (`1100_agent_runtime_state.sql`), and the SIP-0090 Phase 1 embodiment table. Harden the applier first so they all land on a tracked path. *(The configurable-timeouts half of #158 is independent.)*
4. **#176 (framework smoke invariant test) — TRAILING, rides in at the end.** A cheap, small-model CI invariant net for 1.2.0's runtime changes + preflight; reads the executor only (low collision); rides *into* the feature release per the convention (safe hardening → even minor). **It is NOT the automated form of the live-validation that caught #270/#272** (a *full deployed cycle on real models*). A small-model invariant test won't catch the model-mismatch / runtime-wiring class — the two are complementary, and #176 does **not** let us skip the §6 live-validation cycle.

**Not before/with 1.2.0:** #276 (its only tie is preceding #152, a *1.3.0* item — rides the patch line on its own schedule, not 1.2.0-gating), #234/#186/#152 (1.3.0 stabilization), #237/#279/#280/#157/#242 (independent — but see §3 notes on #237's release home and #280's tie to #176).

### 5.6 `api/routes/cycles/*` owner-per-file (resolve before the preflight)

This surface has *legitimate* edits from both lanes (Spark history: #133/#150/#205; Mac incoming: #172+#224 preflight). Before Mac starts the preflight, assign per file: **Mac owns the cycle-create route wiring** (`cycles.py` create handler — that's where the preflight seam lives); **Spark owns the model-availability helper** (`profiles.py:71-95` lift, per the §2 #224 decision). With that split (confirmed by the §2 #224 resolution — option a), the two lanes touch different functions in the same files — annotate the seam with a brief comment so the merge is mechanical.

## 6. Versioning, cadence & release mechanics

**Even/odd minor convention** (parity gates *features*, not hardening — #281):
- **Even minor (1.2.0, 1.4.0, …) = feature release** — led by ≥1 headline feature SIP. Hardening rides along freely: safe, ready hardening (#231, small fixes) lands here alongside features.
- **Odd minor (1.3.0, 1.5.0, …) = stabilization release** — feature-free; the home for the big risky refactors quarantined out of the feature line (**#186** decompose executor, **#152** split handlers, **#234** DbRuntime port) + accumulated debt. Cut when consolidation has piled up enough — substance gates the cut, not the clock.
- **Patch (x.y.Z)** — urgent/small fixes any time, either lane (the 1.1.1 cadence). Never held for the next odd release. **The patch number tracks the latest minor:** hardening that lands *before* 1.2.0 cuts ships as **1.1.x**; the same lane's work *after* the cut ships as **1.2.x**. The "1.1.x hardening lane" is shorthand for an ongoing patch line, not a frozen 1.1 series — you can't ship 1.1.2 after 1.2.0 without a backport branch.

So **1.3.0 is the first stabilization release** — the natural home for #186/#152/#234 and the Spark lane's structural backlog. Patches keep flowing from both lanes throughout.

> **Lane→parity mapping is imprecise (fix the CLAUDE.md wording — Mac owns #281).** CLAUDE.md › Versioning says "Macbook lane emits feature SIPs → even minors; Spark lane emits hardening → patches + big refactors batched into odd minors." But the 1.3.0 refactor batch is **#186 + #152 (Mac-owned) + #234 (Spark)** — *both* lanes feed the odd-minor refactor bucket. The rule (parity gates *features*; refactors quarantine to odd) holds; the clean "Mac=even / Spark=odd-refactors" attribution does not. Reword to: *both lanes emit refactors that target odd minors; only feature SIPs are lane-pinned to even.*

**Mechanics (mirror 1.1.0 → 1.1.1):**
- 1.2.0 bundles the Macbook core when it's done **and live-validated on the deployed stack** — the 1.1 lesson: live validation caught #270/#272 the unit suites couldn't. Run a real `lite` cycle before declaring the minor. **This is a Spark deliverable, not an afterthought:** the deployed stack runs on the Spark box, so Spark is the de-facto validator for the *whole* 1.2.0 (including Mac's runtime core). Track it as an explicit pre-release Spark task — rebuild+redeploy the integrated `main`, run a real cycle, sign off. **#176 does not substitute** for this (it's a small-model CI invariant; the live cycle exercises real models + the deployed wiring — see §5.5).
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
> **Your scope (track:spark), in execution order — front-load the 1.2.0 prerequisites (§5.5 is *not* a linear chain):** start with the two cross-lane gates in either order — **#173** (profile-name consolidation + `active_profile` footgun; the 1.2.0 preflight #224 reads the final names — wider blast radius than a rename, see §5.5) and **#158** (schema_migrations + applier hardening, before Mac lands runtime migrations), then **#176** *trailing* (small-model smoke invariant — the 1.2.0 CI net; does **not** replace the live-validation cycle). **#198 is already done** (pin via #195/#202; ≥0.136 adoption deferred — see §5.5). Then the independent backlog: #276 (stub-fallback masking — real correctness bug, but not 1.2.0-gating), #279, #280 (sequence near #176), #157, #242, #234, #237 (decide release home — it changes `requires-python`), #218/#219. **Also yours:** the pre-release live-validation cycle on the deployed stack (§6) — the stack runs on your box.
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
