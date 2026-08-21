# SquadOps Development Roadmap

Living document tracking the implementation progression from initial prototype to production framework.

## Versioning Convention

Semver with an **even/odd minor** overlay (parity gates *features*, not hardening — #281): **even minors (1.2, 1.4, …) are feature releases** (led by a headline feature SIP; hardening rides along), **odd minors (1.3, 1.5, …) are feature-free stabilization releases** (the big risky refactors + debt paydown), and **patches ship urgent fixes any time, either lane.** Hardening lands wherever it's ready. See `docs/plans/1-2-0-release-plan.md` and CLAUDE.md.

## Forward Cadence (planned)

Version labels per the even/odd remap in `docs/plans/2-0-roadmap-reconciliation.md` (Findings 2 + 4):

- **v1.3 — shipped 2026-07-08** (first stabilization minor; see Release Timeline).
- **v1.4 — shipped 2026-07-31** — **the Verified Canonical App Build**: the dual-lane golden-path pair — Contract-First Build Scaffolding (**SIP-0099**, Lane M headline) + Ephemeral Application Sandbox 1.4 floor (**SIP-0102**, Lane S headline — floor shipped: sandbox service + canonical env image + post-hoc delivered-app audit; the SIP itself STAYS ACCEPTED, SIP-0090-Phase-1 precedent, until migration steps 3–7 land: in-cycle typed-op routing, clean-room verdicts at finalization, #306 qa-Node retirement, golden-path live validation) — with **SIP-0098** Verification Contracts and **SIP-0100** Scaffolded Test Harness/Frozen-File Enforcement as the arc, and three windows of fix packages as hardening. **Cut-gate supersession (owner decision 2026-07-28, executed at cut):** the original gate here ("≥3 consecutive golden-benchmark runs, squad-authored-manifest mode only") was replaced by the pre-registered **Functional App Yield** fixed-budget measurement (`docs/plans/functional-app-yield-measurement.md`) in **seeded-manifest (bind) mode** — exit number **FAY 6/6 (100%), greens 5/6, five consecutive**, on frozen deploy `9522ef4d`. What this honestly demonstrates: given a PRD **and a fully specified interface manifest**, the squad implements, verifies, and delivers a working app. **What remains unmeasured — by the original gate's own correct reasoning — is squad-authored-manifest mode; that rung moves to v1.6 as a headline.** SIP-0101 Cycle Replay Harness stays accepted (deferral condition now spent). Plan: `docs/plans/1-4-evidence-arc-plan.md`.
- **v1.5 — shipped 2026-08-07** — **Finish the Promises, Extract the Proven** (see Release Timeline): SIP-0096 verification integrity completed and implemented, qa on the typed-acceptance seam (#670), correction evidence + progress-aware termination (#687/#431/#435), and the structural quarantine's extractions (#663 context assembly, #331 planning package, #730/#504 typed-check governance, #481, #734) plus SIP-0101's minimum replay slice. Feature-free verified at the cut; contract v9 / manifest v4 byte-stable. Original slate, for the record: serious hardening on the 1.4 machinery. On the slate from earned evidence: executor context-assembly extraction (#663, the #186 strangler lineage), curated typed-check menu, workspace-revision unification, **qa typed-check enforcement (#670 — owner-ruled fork 1, 2026-08-04)**: `qa.test` joins the typed-acceptance seam, so authored checks AND framework injections both reach qa emissions. Ruled buildable because #671 (v1.4.1) disarmed the loaded gun it was blocked on — a nonexistent `import_present` module is now rejected at the gate — and because leaving it out silently excludes qa from every framework check, measured on shk-3 where #689 never reached the qa suite emission, the **"show the author the contract" package** (the #629/#627 family; its #686 authoring-rules-render item pulled forward to the 1.4.2 patch plan, PR #692), plus accumulated debt; scope finalized at freeze-exit per the odd-minor convention (substance gates the cut, not the clock). Plan: `docs/plans/1-5-0-stabilization-plan.md`.
- **v1.6** — **the Authorship release** (reshuffled 2026-08-03, `docs/plans/post-1-4-roadmap-reconciliation.md`): **Squad-Authored Interface Manifest** (Lane M headline — the authorship rung moves up the ladder: from filling a given design to authoring the design from the PRD, under the same gate discipline — manifest-authoring framing task, schema + winnability gates in-cycle, manifest review gate, measured in its own FAY-style window; this IS the 1.4 gate's deferred squad-authored-manifest condition; **SIP-0103**, accepted 2026-08-07, `sips/accepted/SIP-0103-Squad-Authored-Manifest.md` — accepted with its §5a/§5b/§5c design-review rounds in force, including the scope correction that mechanical contract derivation enters scope) + **Generalized Build Capability** (Lane S headline — pluginized blueprints via the Stack Blueprint contract, second stack; scope includes the QA-decomposition anchor's structural derivation: tasks declare produce-vs-verify and `expected_artifacts` derive from the blueprint's ownership map, making the shk-1 dual-claim class inexpressible). Riding: SIP-0091 duty durability, SIP-0090 Phase 2, SIP-0102 migration steps 3–7, **SIP-0093 completion** (93.4 + §5.8 merge rules, amended so merge-time plan validation revises *before* the gate — the shift-left that turns a framing re-roll into an in-task retry), agent-comms delivery guarantees (hardening). Gated on **Functional App Yield repeatably > 0 in authored-manifest mode**, banked as the authored-mode baseline. (Campaign moved out → v1.8: automating relaunch over authored-mode cycles requires the authored-mode baseline to exist first.)
- **v1.7** — stabilization (feature-free by rule): **every port is actually a port** (identity assigned 2026-08-07, `docs/plans/post-1-5-roadmap-reconciliation.md`). Where 1.5 extracted structure *inside* the machinery, 1.7 fixes where the machinery meets the outside world — hexagonal architecture enforced rather than aspirational. Load-bearing for two consumers: the Atlas provider migration cannot happen safely while a vendor's status vocabulary lives in domain objects and the composition root bypasses the factories, and 1.8's scorecard grades over seams that must be stable first. Pool, classified in the 1.5 plan's capacity roll and re-verified at the post-cut sweep: **boundary/vocabulary leaks** (#377 Prefect `State` in domain objects, #381 its `TaskResult.status` twin, #305 Part B, #559's residual `task_type ==` sites, **#922 three meanings of "capability"** — `capability_id` is the task type, `dev_capability` is a stack settings bundle, and the capability-packs SIP needs the word for bindable agent competence; **must land before packs publish against it**, since the name would then be frozen in a distribution format), the **composition-root cluster** (#301/#154/#286 — **design gate before code**; these alter runtime initialization), **provider neutrality / Atlas groundwork** (#313 + the LLM-port characterization suite, #707's allowlist inventory and precedence ruling, #410's observability half), **wide infrastructure mechanics** (#576 error-envelope handlers, #577 asyncpg pool + JSONB codec — must not overlap each other), and **pure extractions** (#567, #574, #575, #579). Plus the API-convention pair (#218/#219), the packaging-fidelity cluster (#198/#582/#637), 1.6's deferrals, and the standing ops-rider quota. Substance gates the cut.
- **v1.8** — **the Automation + Learning release**, **dual-lane co-headliners** (billing amended 2026-08-07, `docs/plans/post-1-5-roadmap-reconciliation.md`; previously Campaign was sole Lane M headline): the **Cycle Evaluation Scorecard** (`sips/proposed/SIP-Cycle-Evaluation-Scorecard.md` — `CycleAssessment` over the `CycleOutcome` seam + benchmark registry + first-wave internal eval packs (Dev, QA, Research, Tool Executor) + a squad-vs-single-model comparison harness that makes the SquadOps thesis *falsifiable*; sliced from `docs/ideas/SIP-Plutarch-Experimentation-and-Cycle-Assessment-Framework-*`, retarget off its stale `v1.1` tag) **+ the Campaign mechanic** (retargeted from 1.6 — objective envelope + continuation policy; `sips/proposed/SIP-Campaign-Orchestration.md`; its #316 request-profile-taxonomy dependency moves with it). **Ordered inside the release: grade definitions land before continuation policy** — without `CycleAssessment` a continuation policy must invent a stopping rule out of raw checks, which is exactly what self-improvement is forbidden to do; a campaign whose stopping rule reduces to "the cycle completed" runs the false-green class unattended at scale. **Cross-Cycle Memory** is a **decision point, not a commitment** (`sips/proposed/SIP-Cross-Cycle-Memory.md`): thin Phase 1 here, or pushed whole to 2.0 with Phase 2 — decided at 1.8 plan time. Either way **the rails ship in 1.8** (recall port + NoOp + wired call site, per the standing rails-before-mechanism rule), so the choice is an adapter swap rather than a redesign. Its 1.5 gate — SIP-0096 implemented, so grades are never computed over fabricatable evidence — **cleared 2026-08-06**; the remaining gate is 1.6's authored-mode baseline.
- **v2.0** — compound on the *shipped* 1.8 scorecard: the 2.0 pillars — Capability-Backed Agents (what an agent *is*; consumes Cross-Cycle Memory **Phase 2** — consolidation, promotion, duty/ambient utilization — as its scoped-memory substrate), Campaign capability-augmentation, Self-Improvement + Test Bay (the capstone). Self-improvement acts on `CycleAssessment` grades, never raw checks.

Each even-minor consumer sits strictly behind the release that earns its trust: author over honest evidence (1.6 behind 1.4); automate and grade over the authored baseline (1.8 behind 1.6); compound over trustworthy grades (2.0 behind 1.8). Odd minors (1.5, 1.7, 1.9) are the stabilization tails between — and they are not junk drawers: 1.5 shipped a named claim, and 1.7 has one (above). The ladder in one line: **1.6 teaches the squad to design, 1.7 makes the seams hold, 1.8 teaches it to judge — and only then to run on its own.**

## Release Timeline

### v1.6.0 (2026-08-21) — Current — the Authorship release
The rung above 1.4: from *filling* a given interface design to **authoring the design from the PRD**, under the same gate discipline. Dual-lane headlines: **SIP-0103 Squad-Authored Manifest** (Lane M — the authoring stage with schema/winnability gates in-cycle, the question-gated manifest review, revision loop, and authoring provenance; **implemented at this cut**) and **Generalized Build Capability** (Lane S — the five per-stack surfaces collapsed into a single `ScaffoldStack` registration and a second real stack, `nextjs_ts`, landed 2026-08-10; **SIP-0105 Stack Blueprint Contract accepted 2026-08-17 with its unbuilt parts named** — it stays accepted, SIP-0102-at-1.4 precedent). Release gate — **authored-mode Functional App Yield repeatably > 0 — MET and banked as the authored-mode baseline**: the pre-registered V7 window closed **amended 4/6 functional (dual record: 3/6 under the pre-registered instrument / 4/6 corrected, #1004/#1005, both always reported)**, zero manual interventions, frozen deploy — and the follow-on V38 comparison window re-exercised the full authored path under a second model (qwen3.8:27b) at **4/6**, equal yield at roughly half the wall-clock, with its §6 synthesis recording the failure-class shift (framing-rooted, contract-violating deliveries — the classes no current gate checks). Records: `docs/plans/1-6-0-v7-fay-window-record.md`, `docs/plans/1-6-0-v38-window-record.md`. **Cut basis:** the deploy the windows validated IS the cut — zero code drift between frozen deploy `f7a5e0a2` and main at the cut (docs only), full regression 7,615 passed, Guard 1a/1b architecture+equivalence tests green. Riding: SIP-0093 completion (§5.8 merge rules, shift-left revision), M-ladder fixes through #811/#812, Track S S1–S2. **Deliberately not in this cut (post-window queue → 1.6.1+):** #1014 emission-side ownership veto, #1011 repair clamp parity, the #1012 retest-evidence code read (byte-verified reproducer banked), #1013 manifest↔plan consistency gate, #1015 repair-loop focus, compile-credit bookkeeping. Plan: `docs/plans/1-6-0-authorship-plan.md`.

### v1.5.0 (2026-08-07) — Finish the Promises, Extract the Proven (stabilization)
The odd-minor stabilization release: the 1.4 machinery's normative promises get finished, and the structure that survived five patch lines gets extracted while nothing else is moving. Feature-free by rule and verified as such at the cut — no new contract fields, manifest fields, request-profile capabilities, or squad-facing handler/workflow surfaces; **contract v9 (`art_4f368ea08799`) and manifest v4 (`art_8becd104e9fc`) byte-stable line-wide**; every behavior change traces to an accepted design or a ruled defect. 34 PRs, one per issue, across three gates. Plan: `docs/plans/1-5-0-stabilization-plan.md`.
- **Promises finished (Track A + SIP-0096 completion).** **SIP-0096 is implemented, not just promoted** — its three normative items landed first: **#682** gate waivers as additive schema + CLI `--waive/--waiver-reason`, where a waived check is recorded and disclosed but the verdict itself is never rewritten (PR #742, migration 1030); **#683** wrap-up consumes the `CycleOutcome` seam and *clamps* over-claiming closeout prose to the evidence it cites (PR #743); **#684** inert-cycle detection derived on read over persisted summaries — a squad that stops producing evidence is detected, not read as passing (PR #744). Then the promotion itself (PR #749), which caught its own premise delta: the audit's fourth normative item (pulse SKIP-only ≠ pass) had been dropped from the plan and was implemented in the promotion PR rather than waved through. **#670** brings `qa.test` onto the typed-acceptance seam, so authored checks *and* framework injections reach both authoring surfaces (PR #738 — the gap shk-3 found). **#687** captures the application's real traceback from the probe runner's spool delta and hoists it into `build_failure_evidence` (PR #739); **#431** makes emission accounting explicit at four producer seams so extraction loss is *named* rather than silently truncated (PR #740) — together, the correction loop's long-standing diagnosis blindness. **#435** makes correction termination progress-aware: a moving chain is never cut short, a repeating one never burns the budget (PR #741). **#629** makes a test suite whose assertions contradict the frozen contract a blocking failure, with the prose half deliberately advisory (PR #745). **#506** returns full task lifecycle ownership to the transport, fixing retry attempts that never re-entered RUNNING (PR #746). **#724** sweeps ~20 config reads through `resolved_config`, closing the class #426 opened (PR #748). **#452** moves the last live-path prompt prose into managed assets with byte-equivalence pinned by test (PR #747).
- **Structure extracted (Track B — the quarantine).** **#663** replaces the executor's five context tables and three branches with a declared `ContextAssemblyContract` per task type, landed in three golden-first slices — 19 goldens captured *before* each refactor and byte-identical through (PRs #751–#753). **#331** splits the 1,887-line planning handler into a package by authoring stage, a pure move AST-verified 20/20 names with every pre-split test passing unmodified through the shim (PR #754). **#730 + #504** give every typed check its own governance metadata in one registry — required, no-default fields, so a new check *cannot* be added without declaring who owns its failures and whether it replays — with a generated menu pinned by drift tests, and promote the fill-slot report to the blocking `fill_slot_signature` check (PRs #757–#758). **#481** adds stranded-cycle detection as the fourth startup sweep, read-only, emitting the exact recovery command (PR #755). **#734** stamps a workspace revision id at every acceptance surface, so every verdict names the tree it measured (PR #756). **SIP-0101**'s minimum slice ships the maintainer-only cycle replay harness, rails before mechanism (PRs #735–#737, migration 1020).
- **Verified as a line.** Two confirmation shakedowns, both green on integrated deploys: the **Gate-2 exit** (`cyc_ea0b82cfbd17` — accepted, 17/17 checks, zero corrections) plus a live replay demonstration (`cyc_cfe6962e8fc8` — a 5-task prefix restored from a retained boundary, 33 min against ~2.5 h), a waiver end-to-end probe (`cyc_e2e9cfd0a0c4` — three waived checks recorded, verdict unchanged, undisclosed-check waiver refused), and a 3-workload wrap-up green; and the **cut shakedown** (`cyc_b07183b3cf5c` on deploy `df29d45c` — accepted, 36 checks executed / 36 passed, 15/15 contract criteria, zero corrections, zero unreleased leases, zero machinery defects), which also discharged `fill_slot_signature`'s surveillance disposition on its first natural bind-mode outing. Plus a replay zero-diff over the stored green corpus: all 9 registry-replayable evaluation rows re-evaluate identically post-change, the 5 non-replayable rows excluded by the registry's own attribute.
- **Found by the line, not by the tests**: #481's first live boot surfaced **2 genuinely stranded cycles** (framing complete, gate approved, successor never created) that had been invisible for weeks — cancelled by owner ruling so the boot warning stays meaningful. The Gate-2 shakedown's own launch bug (a bind-mode contract with sole-author framing is a guaranteed plan rejection) became **#762**; its coarse `tests_pass` correction signature became **#761**.
- **Filed forward**: #761, #762, #668's suite half, #707, `package_builds` (declared-unbuilt, with its trigger recorded in the registry), SIP-0102 migration steps 3–7, SIP-0092's M3, and the #557 post-retest governance review (SIP drafted, `sips/proposed/SIP-Post-Retest-Governance-Acceptance-Review.md`) → v1.6+.

### v1.4.4 (2026-08-05) — No False Verdicts (verification integrity)
Every verdict is earned: greens are enforced, reds are explained, budgets are honored. Seven premise-verified fixes, one PR each: **#427** terminal failure reason persisted on the run row + surfaced by `runs show`/report (PR #717 — migration 1010, the line's only one; the logging half had already shipped), **#426** builder offer and gate net both key off configured build_profile via the new single-source `Cycle.resolved_config()` (PR #718), **#715** plan-time check-applicability — a qa.test task whose declared artifacts can never satisfy required `tests_pass` is rejected at authoring, on BOTH gate seams (PR #719, which also closed #718's workload-seam gap), **#423** skip-cause split — an authored check the evaluator cannot run is an evidence gap (`evaluator_gap:` disclosure, required-level when contract-bound) and never `passed: true` (PR #720), **#424** plan-authoring collapse → gate rejection + dispatch backstop, never a silent static-step fallback (PR #721), **#511** the time budget gates correction-chain dispatch at the runner's single choke point (PR #722), **#571** LanceDB prefilter + explicit cosine metric, revert-checked against a real store (PR #723).
- **Verified as a line** (2026-08-05 overnight, integration deploy of all seven): migration 1010 applied at boot; in-container replays — the deployed #715 validator rejects the STORED shk-4 plan, #423's `.tsx` exhibit row reads honest, #571 proven on the agent image's pinned lancedb 0.8.2; designed-failure probe `cyc_c110af382480` budget-killed at the first boundary with `failure_reason` persisted and surfaced (#427+#511 live); **confirmation shk-5 `cyc_07ae691af9d6` green — verdict `accepted`, zero corrections, all 17 checks verified**, new nets silent on a well-formed roll (no false reds); lifecycle hygiene 9/9 leases released, zero residue; contract v9 / manifest v4 untouched.
- **Filed forward**: #724 (`time_budget_seconds` read from applied_defaults, bypassing `resolved_config` — the #426 class, sighted while building #511) → 1.4.5+.

### v1.4.3 (2026-08-04) — Lifecycle Hygiene (the loop can't strand or hide)
A cycle can neither strand the next one nor fail silently. Seven hash-stable fixes — five planned plus two found *by the deploy window itself* — one PR each: **#373+#529** focus-lease reaper (PR #704 — cancel routes, executor finalize, and startup sweep all drive the coordinator so mode and lease release as one unit; `cancel_cycle` also transitions in-flight runs), **#561** activity self-heal (PR #705 — a D9 one-active-row conflict supersedes the stale row and retries instead of failing the new task; cancel teardown + widened startup reap), **#498** interpreter resolution (PR #706 — bare `python` resolves to `sys.executable` at spawn, strictly after the safelist gate; riders: the #605 registry-wide skip pin and the pyflakes load-bearing declaration), **#572** queue capability honesty (PR #708 — `delay` and `priority` declared False; a non-zero delay raises NotImplementedError instead of laundering into a transient-looking QueueError), **#573** redaction char-class overrun (PR #709 — the literal `|` in `[A-Z|a-z]` made the email pattern swallow adjacent pipe-delimited log fields), **#710** stranded-mode sweep (PR #711 — startup returns lease-less `cycle`-mode agents to ambient), **#712** owner-checked release (PR #713 — ambient entry refuses to release a lease owned by a different `owner_ref`: `focus_lease_held_by_other_owner`).
- **Found by the window, not the tests**: **#710** — pre-deploy state capture showed 6 agents in `cycle` mode with zero held leases; focus arbitration had been silently inert for 64 cycles over two weeks (the #288 same-mode branch finds no conflicting lease → idempotent-skip → admitted without acquiring → finalize releases nothing). **#712** — pre-deploy code review: cancel detection is a dispatch-boundary poll, so a cancelled run's finalize fires minutes late and would have stripped the *relaunched* run's focus; unreachable before this patch only because #529's leak was an accidental guard.
- **Deploy verification**: first-boot mode reap returned exactly the 6 stranded agents to ambient (lease and activity reaps 0, matching banked pre-state). Cancel probe (`cyc_df79b68c94b3`): recruitment acquired 5 leases — the first acquisitions in 64 cycles — then cancel released all 5 and aborted the running activity within 15s, **no restart**; relaunch re-acquired within a minute; the cancelled run's stale finalize then fired 5m48s late and was refused on all 5 agents — #712 demonstrated in production shape on the first try. Contract v9 / manifest v4 untouched (no migrations; rollback = image swap).
- **Confirmation (shk-4, `cyc_c3413e8ed3c3`, unscored)**: **green — verdict `accepted`, zero failed, zero unverified, 2 runs, 3 correction rounds.** The 1.4.3 surfaces were clean end-to-end: leases acquired at recruitment in both workloads and every one released at finalize (9/9), zero unreleased leases / zero active activities / all agents ambient at terminal, no restart at any point; the only `focus_lease.rejected` events in the window are the five #712 refusals. All three correction rounds trace to *plan-planted* defects, not 1.4.3 regressions: round 0 repaired a plan-asserted field absent from the frozen model (`created_at`); rounds 1–2 chased a plan task whose declared test artifact (`backend/tests/test_integration.js`) can never satisfy pytest-based `tests_pass` — the loop escaped only by emitting a placeholder `.js` stub plus an undeclared `.py` twin carrying the real tests (~2h and three rounds for a defect visible statically at plan time, with the planned Vite-proxy smoke silently narrowed to TestClient coverage).
- **Filed forward**: #707 (dual command allowlists disagree both ways; made deterministic, not created, by #498) → v1.5; the shk-4 unwinnable-plan class (plan-time check-applicability validation) + fresh #426/#427 evidence → v1.4.4.

### v1.4.2 (2026-08-04) — Correction Aim + Authoring Prevention
The correction chain aims true, and known authoring classes can't be authored. Every fix traces to shk-2's diagnosed loss chain (`cyc_88162ecfd895`), where a one-line defect survived two correction attempts. Four fixes, hash-stable, one PR each: **#688** repair targeting (PR #695 — failed probe → endpoint → contract's endpoint→slot map → the owning fill slot, which now LEADS the target; plus a package→language scoping fallback, because pf-24's package anchor silently matched nothing whenever the suite was authored outside the source package), **#691** frozen-file handling (PR #696 — scaffold-frozen paths excluded from interface-drift detection, and frozen emissions dropped-with-disclosure instead of restored-and-stored), **#689** `undefined_names` (PR #697 — pyflakes F821, framework-injected at emission acceptance on `.py` fill slots; the call-time NameError class every prior gate missed), **#686** plan-shape rules rendered into the four authoring prompts (PR #698 — validator rules stated up front, bound to the validator family by a classification table + test).
- **Corrected premises, recorded**: #691's filing blamed an unauthorized dev write; provenance showed the artifacts were `scaffold.expand`-seeded and hash-identical to the contract's frozen entries. The real defect was drift detection reporting the scaffold's own `GET /health` probe as producer drift — a permanent false positive on every bind-mode cycle that corrects. The issue was rewritten before it was built.
- **Confirmation (shk-3, `cyc_74a741292539`, unscored)**: **green — verdict `accepted`, zero failed, zero unverified, zero corrections.** #686 confirmed at framing in its strongest form: a compliant plan on the FIRST roll (zero dual claims; the verification-only `expected_artifacts: []` form the new asset teaches), where shk-1 needed a #673 rejection plus a re-roll — with `request.planning_task_base v3` in the prompt provenance. #689 confirmed live on the dev surface: one injection on `backend/routes.py` (passed), correctly none on the three `.jsx` views. #688/#691 never fired (zero corrections), so their evidence remains the stored-artifact replays — a green cycle never credits an unfired fix. #672 silent; leases/activities clean without a restart; contract v9 / manifest v4 untouched.
- **Found by the confirmation, not by the tests**: #689 stops at the `qa.test` boundary, which overrides `_validate_output` and never joins the typed-acceptance seam. That is #670, now owner-ruled fork 1 → v1.5, with scope widened to bringing qa onto the seam so authored checks and framework injections both reach it.

### v1.4.1 (2026-08-03) — Hardening Patch (the 1.4 known-open ledger)
The five hash-stable fixes filed at the 1.4.0 cut, one PR per issue: **#672** runtime_activities reaper (PR #676 — startup + finalize sweeps through the abort choke point), **#671** module-existence validation (PR #677 — closed-surface proof; entry_modules exempt by design), **#673** duplicate expected_artifacts net (PR #678 — first plan-wide cross-task rule), **#667** repair-envelope testid threading (PR #679 — surface re-derived from the manifest at repair-input construction), **#669** framing re-roll rejection context (PR #680 — re-rolls revise instead of re-dicing; `framing_max_rerolls` becomes a revision budget). Contract v9 / manifest v4 unchanged (hash-stable by construction); #668/#670 deliberately out (next window).
- **Deploy verification**: startup reap ended exactly the 4 stranded activity rows; in-container replay of the real fay-16..19 plans against contract v9 (trip/clean exactly as pinned); loaded-module checks across runtime-api + all four authoring agents.
- **Confirmation (unscored shakedowns by pre-declaration)**: **shk-1 green** — framing-1 authored a real dual-claim, #673 auto-rejected it (live true positive), #669 threaded the rejection into a surgically-revised re-roll (tasks identical except the flagged claim), implementation cleared all 14 criteria with zero corrections; full-cycle #672 silence; leases/activities clean. **shk-2** fired #667's trigger live (repair envelopes built by the new path), then surfaced a **pre-existing** correction-chain loss mode diagnosed to root cause (unimported symbol → call-time NameError → 500; analyzer guessed causes without the traceback, repairs mis-aimed at drift-named files) — filed **#687/#688/#689**, cycle cancelled after confirmation evidence was complete (recorded rationale; zero defects in the five fixes under test).

### v1.4.0 (2026-07-31) — the Verified Canonical App Build
First dual-lane-headline feature release: **SIP-0099** Contract-First Build Scaffolding (Lane M) + the **SIP-0102** Ephemeral Application Sandbox 1.4 floor (Lane S — floor shipped, SIP stays accepted pending in-cycle integration, steps 3–7 of its migration plan), with **SIP-0098** Verification Contracts (14-criteria v9 contract, per-criterion evidence) and **SIP-0100** Scaffolded Test Harness + Frozen-File Enforcement completing the arc.
- **Exit evidence (pre-registered):** Functional App Yield window 3 — **6/6 functional (100%), 5/6 green, five consecutive greens** (fay-15..19), unfiltered, frozen deploy `9522ef4d`, seeded-manifest mode; bar was ≥4/6. Full record: `docs/plans/functional-app-yield-measurement.md`. Cut-gate supersession + the deliberately unmeasured authored-manifest rung (→ v1.6) recorded in the version-labels entry above.
- **Hardening riding the release** (three window fix packages): #645 plan-validator rules, #648 frontend_compiles at view acceptance, #649 builder write-authorization, #650 repair-provenance targeting, #651 contract v8 chained probes, #657 proposer context threading, #658 frozen-claim net, #659 DOM testid contract, #597 dev success evidence, #665 missing-suite repair locus — plus the #643 acceptance-workspace fix and #626 runner-owned suite-health verdicts from the window-1 deploy.
- **Known-open ledger at cut** (filed, queued 1.4.1+): #667 repair-envelope testid threading, #668 DOM/client-contract enforcement, #669 framing re-roll context, #670 qa typed-check enforcement fork, #671 module-existence validation, #672 runtime_activities reaper, #673 duplicate expected_artifacts net; packaging determinism #598 (Stack Blueprint); machinery ruling: the #670 render-only gap is constant/pre-existing and taints no measured datum (owner-ratified at cut).

### v1.3.1 (2026-07-08) — Hardening Patch
Post-1.3.0 batch from the 2026-07-04 independent health assessment (Macbook lane while Spark offline). All fixes, no feature SIPs — patches ride either lane anytime, independent of even/odd feature parity (#281). Every runtime-affecting change live-validated before merge.
- **#326 (security):** agent-status writes moved off the unauthenticated `/health` lane (any client could write) to `POST/PUT /api/v1/agents/status` behind `agents:write`; `/health/*` is GET-only and the middleware allowlist is method-scoped so a future `/health` write fails closed. Agents authenticate heartbeats via a new `squadops-agent` service identity (client credentials, `agent` role ⇒ `agents:write`).
- **#288 (concurrency):** concurrent same-agent cycles no longer bypass FocusLease arbitration — a same-mode recruit from a *different* lease owner now rejects with `focus_lease_conflict` (the run defers) instead of free-riding the incumbent's lease and losing the agent mid-run.
- **#306 (inert check):** the QA image now has Node.js, so the frontend build check (#290) + vitest actually run instead of silently skipping on "npm not found". Node ships in the qa image only, via a config-driven per-role `system-packages.txt` (no role name hardcoded).
- **#328 (broker hygiene):** new `broker` category in `squadops doctor` flags retired-scheme (`cycle_results_*`) queues + undrained backlogs (messages, no consumer); the orphaned pre-SIP-0094 queues (one with 48 undrained messages) were swept.
- **Docs/SIP:** filed the Externalized Build Sandbox proposal (the principled exit to toolchain-bundling that #306 works around near-term); stays `proposed`.

### v1.3.0 (2026-07-08) — First Stabilization Release (feature-free)
First **odd-minor stabilization release** (#281): the big structural refactors quarantined out of feature releases, plus debt paydown. Entire core scope landed from the Macbook lane (Spark offline); every structural change live-validated before merge.
- **SIP-0097 executor decomposition (#186, #295):** `DispatchedFlowExecutor` 3,358→1,805 lines across 6 sliced PRs; five injected collaborators (pure hoists, `RunLedger`+`RunCompletion` — zero per-run mutable state, the SIP-0096 §6.4 seam — `CorrectionRunner`, `PulseBoundaryRunner`, `TaskDispatcher`); slice 6 = the #295 plan-review gate check. SIP-0097 promoted → implemented.
- **#152:** `cycle_tasks.py` (3,276 lines) → `capabilities/handlers/cycle/` package behind a compat shim (after the #332 helper hoist).
- **#323:** agent comms poll→push — persistent `subscribe()` consumer, prefetch 1; kills consumer churn, up-to-1s pickup latency, and the `aio_pika` log flood (obsoleted #329).
- **#234:** dead sqlalchemy `DbRuntime` backend removed — `ports/` is vendor-type-free; asyncpg everywhere.
- **Fixed:** #327 prompt-registry drift (deploy re-sync + manifest hard-fail), #342 resume insta-fail (live pause→resume→complete verified, closed #258), #345 color-env test flakiness.
- **Docs/CI:** #335 hygiene pass (this file's stats/tables un-froze) + #336 docs-drift guards in the regression gate (version markers, SIP target parity, doc-ref existence).
- **Deferred:** #331/#333 (→ 1.5). (#288, originally eyed for the 1.4 window, shipped in the 1.3.1 hardening patch above.)

### v1.2.0 (2026-07-04) — First Feature Release (even/odd cadence)
First **even-minor feature release** (#281). Three feature SIPs, on a hardening base:
- **SIP-0090 Agent Embodiment Substrate — Phase 1:** the internal embodiment model — lifecycle state machine (single-active-per-agent, enforced in code + a Postgres partial unique index), resource budget primitives (non-silent exhaustion), `EmbodimentStatePort` + Postgres persistence, `EmbodimentCoordinator`. No adapter yet (#312, #317).
- **SIP-0095 Cycle Create Preflight:** create-time fail-fast (422 `PREFLIGHT_REJECTED`) on unsatisfiable roles / unpulled models; unreachable backend warns-and-allows; doctor parity; warnings on response + CLI (#298, #309, #311, #315, #321).
- **SIP-0089 runtime-arc completion:** recruitment via coordinator + FocusLease (#233); single-transaction coordinator UoW (#244).
- **#231** health signal → single source of truth (`runtime_status` always-populated); **#173** profiles → smoke/lite/full; **#158** operational hardening; **#319/#320** CLI error-message fix.
- **Deferred:** #295 (materialized-plan gate check → rides #186); SIP-0090 budget persistence/wiring (→ Phase 2).

### v1.1.1 (2026-06-28) — Runtime Lane Hardening
- **Live-validated the runtime lane (SIP-0089) end-to-end** after 1.1.0, which surfaced two regressions the unit suites couldn't catch:
  - **#270** cycle API routes 403'd every authenticated user — #150's `cycles:*` scope checks didn't account for the role-centric Keycloak realm (issues roles, not scopes); fixed with a role→scope bridge in `resolve_identity`.
  - **#272** duty windows never auto-opened under the default `missed_window_policy="skip"` — poll-cadence lag was misread as a missed window; fixed with an on-time grace of one poll interval.
- **Resume reliability:** duty-deferred runs now actually re-execute on resume (#222); mid-sequence runs resume at the correct workload index (#257).
- **Reliability:** bounded RabbitMQ publish retry/backoff (#245); `runs retry` actually executes (#133, #205); strip `<think>` before fenced parsing (#130); OTel provider test leak fixed (#239).
- **Additive (backward-compatible):** per-role Prefect task names (#94); agent `mode` + `runtime_status` on the agent list / console (#230, #231).
- **Internal:** `establish_contract` → `define_done` rename (#79); regression suite parallelized via pytest-xdist (#216); SIP-status script rewrites the body status line (#253).

### v1.1.0 (2026-06-28) — Agent Runtime State + 1.0.x Hardening
- **SIP-0089** Agent Runtime State (Phases 1–4): runtime modes (ambient/cycle/duty) with a single-writer coordinator + in-process duty scheduler, assignments & duty windows, FocusLease arbitration, RuntimeActivity observability. Migrations 1100–1130.
- **1.0.x hardening foundation** landed: CI-trust arc (declared deps, dev+CI on Python 3.12, ruff-format gate, adapters in the gate) + reliability fixes (#146 channel recovery, #155 frozen-result mutation, #77 cancel→Prefect, #209 integration config) + **#150 cycle-route scope enforcement (security)**.
- The remaining build-reliability work is re-baselined as the **1.1.x hardening plan** (`docs/plans/1-1-x-hardening-plan.md`) — it no longer gates the version. (Gate read as foundational-hardening completeness; joint Spark/Mac decision 2026-06-28.)
- **SIP-0088** (Agent Runtime Modes umbrella) stays **accepted** — its v1.2 pieces (embodiment, recruitment-driven leases) are future; promoting the umbrella would overstate it.

### v1.0.6 (2026-06-21) — Per-Agent Reply Queues
- **SIP-0094** Per-Agent Reply Queues + Long-Lived Subscription Model
  - Replaces the leaky per-run `cycle_results_{run_id}` reply queues — which lost replies in the consumer-tag churn window and leaked one orphan queue per run — with durable per-agent `{agent_id}_replies` queues
  - `ReplyRouter` holds one long-lived subscription per agent and resolves replies by `task_id`; new `QueuePort.subscribe()` primitive backed by a reconnecting RabbitMQ iterator (resubscribe surfaced in `health()`)
  - `TaskResult.from_dict` hardened to drop unknown keys (forward-compat across rolling agent deploys)
  - Substrate precondition for the 1.0.x build-reliability hardening line

### v1.0.5 (2026-04-24) — Prefect Task Log Streaming
- **SIP-0087** Prefect Task-Scoped Log Streaming
  - Per-task log forwarding to the Prefect UI with heartbeats

### v1.0.4 (2026-04-19) — Build Convergence Loop
- **SIP-0086** Build Convergence Loop
  - Dynamic task decomposition, output validation, and correction activation

### v1.0.3 (2026-04) — Post-1.0 Hardening
Post-1.0 patch line. Docs hygiene, complexity tightening (C901 threshold 15→12), streaming LLM chat path (`chat_stream_with_usage()`).

### v1.0.2 (2026-03-15) — Console Messaging
- **SIP-0085** Console Messaging Capability for Live Agents via A2A
  - Joi agent routes operator messages to the live squad via the A2A protocol
  - Modal-overlay UI approach with phase audit gates
- Continuum (console UI component) pinned to v1.0.2

### v1.0.1 (2026-03-13) — Prompt Registry
- **SIP-0084** Prompt Registry Integration
  - Versioned prompt management for handler prompts

### v1.0.0 (2026-03-10) — Architecture Complete
Release milestone, not a new SIP. 13 SIPs landed between v0.9.0 and v1.0.0 (auth → LangFuse → cycles → workload protocols → correction → wrap-up → bootstrap → multi-run). 3,032 tests passing at release. See the v1.0 Progression section below for the retrospective.

### v0.9.19 (2026-03-07) — Multi-Run Orchestration & Bootstrap
- **SIP-0083** Multi-Run Cycle Orchestration
  - `execute_cycle()` loops over `workload_sequence`, creating a Run per workload
  - `"auto"` gate sentinel for workload-to-workload handoffs without HITL
  - `_build_forwarding_overrides()` passes promoted artifacts and `impl_run_id` between workloads
  - Multi-phase cycle request profile (1 HITL gate + 1 auto gate)
- **SIP-0082** Time Budget Awareness in Planning Prompts
  - `time_budget_seconds` coerced from string at CRP load time
  - Budget awareness injected into planning prompt fragments
- **SIP-0081** Profile-Driven Bootstrap
  - Three-layer architecture: profile YAML → shell scripts → doctor validation
  - Three profiles: `dev-mac`, `dev-pc`, `local-spark`
  - `squadops bootstrap <profile>` and `squadops doctor <profile>` commands
  - State file at `.squadops/bootstrap/<profile>.json`

### v0.9.18 (2026-03-06) — Wrap-Up Workload Protocol & Test Quality Enforcement
- **SIP-0080** Wrap-Up Workload Protocol
  - Domain models: ConfidenceClassification, CloseoutRecommendation, UnresolvedIssueType/Severity, NextCycleRecommendation
  - 5 wrap-up handlers (gather_evidence, assess_outcomes, classify_unresolved, closeout_decision, publish_handoff)
  - YAML frontmatter validation for structured closeout/handoff decisions
  - wrapup.yaml cycle request profile with 3 milestone pulse check suites
  - WRAPUP_TASK_STEPS and REQUIRED_WRAPUP_ROLES validation
- **Test Quality Enforcement**
  - AST linter made blocking in regression script (was non-blocking)
  - 235 tautological tests removed across 77 files (attribute-only, sole isinstance, issubclass-only)
  - Linter false-positive fix: gate isinstance/is-not-None on has_calls
  - Codebase fully ruff-clean (4 pre-existing violations fixed)

### v0.9.17 (2026-03-05) — Implementation Run Contract & Correction Protocol
- **SIP-0079** Implementation Run Contract & Correction Protocol
  - Domain models: RunContract, RunCheckpoint, PlanDelta, TaskOutcome, FailureClassification
  - Checkpoint persistence in both registry adapters, FAILED→RUNNING FSM transition
  - Implementation/correction/repair task steps with deterministic IDs
  - 6 bounded execution CRP schema keys (`max_task_retries`, `max_task_seconds`, `max_consecutive_failures`, `max_correction_attempts`, `time_budget_seconds`, `implementation_pulse_checks`)
  - Executor checkpoint/resume, time budget enforcement, `_PausedError`
  - Correction protocol handlers (analyze_failure, correction_decision, define_done, repair handlers)
  - Outcome routing with `outcome_class` on TaskResult
  - Resume and checkpoints API routes (`POST /{run_id}/resume`, `GET /{run_id}/checkpoints`)
  - Resume and checkpoints CLI commands (`squadops runs resume`, `squadops runs checkpoints`)
  - Implementation cycle request profile with milestone + cadence pulse check suites
  - MetricsBridge correction counters, PrefectBridge RUN_RESUMED state mapping
  - AST-based test quality linter with Claude Code PostToolUse hook

### v0.9.16 (2026-03-03) — Planning Workload Protocol
- **SIP-0078** Planning Workload Protocol
  - `PLANNING_TASK_STEPS` (5 steps) and `REFINEMENT_TASK_STEPS` (2 steps) with workload-type branching
  - `UnknownClassification` constants (5 classification levels)
  - 7 planning/refinement handlers with `_PlanningTaskHandler` base (task_type prompt assembly)
  - `GovernanceAssessReadinessHandler` structural validation (YAML frontmatter, readiness, sufficiency_score)
  - `GovernanceIncorporateFeedbackHandler` D17 fail-fast and differentiated companion artifact
  - 7 task_type prompt fragments with manifest integrity
  - Planning cycle request profile with `progress_plan_review` gate, 2 pulse check suites, cadence policy
  - `REQUIRED_REFINEMENT_ROLES` validation for refinement runs

### v0.9.15 (2026-03-01) — Cycle Event System
- **SIP-0077** Cycle Event System
  - `CycleEventBusPort` with 20-event taxonomy across 6 entity types
  - `InProcessCycleEventBus` adapter with per-run monotonic sequences
  - Bridge subscribers: LangFuseBridge, PrefectBridge, MetricsBridge
  - 25 emission points (19 executor + 6 API routes)
  - Dual-emit alongside existing telemetry (v0 scope)
  - Drift detection tests for registry/event parity

### v0.9.14 (2026-02-28) — Workload & Gate Canon
- **SIP-0076** Workload & Gate Canon
  - `WorkloadType` and `PromotionStatus` constants, DDL migration
  - Artifact promotion (one-way, idempotent, route-level baseline check)
  - `workload_type` filter on list_runs, gate name prefix validation
  - CRP `workload_sequence` key, CLI gate flags with mutual exclusion

### v0.9.13 (2026-02-26) — LLM Budget & Timeout Controls
- **SIP-0073** LLM Budget & Timeout Controls
  - `chat()` budget/timeout params, model registry, prompt guard
  - Capability-level `max_completion_tokens` and `test_timeout_seconds`
  - Handler wiring for Dev, QA, and test runner budgets

### v0.9.12 (2026-02-24) — Stack-Aware Development Capabilities
- **SIP-0072** Stack-Aware Development Capabilities
  - `DevelopmentCapability` registry with file classification
  - Handler stack awareness (dev, QA, builder)
  - Node test runner, fullstack build profile

### v0.9.11 (2026-02-22) — Builder Role
- **SIP-0071** Builder Role (Dedicated Product Builder Agent)

### v0.9.10 (2026-02-20) — Squad Configuration Perspective
- **SIP-0075** Squad Configuration Perspective (console plugin, icon distribution)

### v0.9.9 (2026-02-18) — Pulse Checks and Verification
- **SIP-0070** Pulse Checks and Verification Framework
  - Milestone and cadence-based pulse checks in the cycle execution pipeline
  - Repair loops with acceptance engine integration
  - Verification record persistence (memory + Postgres)
  - Pulse check cycle request profiles (pulse-check, pulse-check-build)
- CLI `--prd` accepts file paths (auto-ingest) in addition to artifact IDs
- Fix: PRD content resolution in executor (artifact ID → full text)
- BuildKit cache mounts for all Dockerfiles

### v0.9.8 (2026-02-16) — Console Control-Plane UI
- **SIP-0069** Console Control-Plane UI via Continuum Plugins
  - SvelteKit shell with 7 plugins (home, agents, cycles, projects, artifacts, observability, system)
  - Auth BFF with PKCE flow, session store (Redis/memory), token refresh
  - Same-origin API proxy for runtime-api (eliminates cross-origin issues)
  - Cycle command handlers (create, cancel, gate approve/reject)
  - API-backed dashboard widgets: run activity, build artifacts, gate decisions, cycle stats

### v0.9.7 (2026-02-14) — Agent Build Capabilities
- **SIP-0068** Enhanced Agent Build Capabilities
  - Fenced code parser, build handlers (development, QA)
  - Task plan generator with BUILD_TASK_STEPS
  - Assembly CLI command (`runs assemble`) for extracting build artifacts
  - Reference apps: hello_squad, group_run

### v0.9.6 (2026-02-12) — Durable Persistence + Observability
- **SIP-0067** Postgres Cycle Registry (durable cycle/run/gate persistence with migrations)
- **SIP-0066** Distributed Cycle Execution Pipeline (RabbitMQ dispatch, Prefect DAG, LangFuse cross-process traces)
- **SIP-0065** CLI for Cycle Execution (Typer CLI with cycle request profile contract packs)

### v0.9.3 (2026-02-08) — Cycle Execution API
- **SIP-0064** Project Cycle Request API (cycles, runs, gates, artifacts via REST)

### v0.9.2 (2026-02-08) — Keycloak Hardening
- **SIP-0063** Keycloak Production Hardening (config, realms, console auth)

### v0.9.1 (2026-02-07) — Auth Boundary
- **SIP-0062** Auth Boundary (Keycloak OIDC, JWT middleware, service identities, audit logging)

### v0.9.0 (2026-02-06) — LLM Observability
- **SIP-0061** LangFuse LLM Observability Foundation (buffered trace/span/generation recording)

### v0.8.9 (2026-02-01) — Legacy Retirement
- **SIP-0060** Agent Migration to Hexagonal Application Layer
- **SIP-0059** Infrastructure Ports Migration
- Removal of `_v0_legacy/` directory

### v0.8.8 (2026-02-01) — Hexagonal Completion
- **SIP-0058** Capability Contracts + Reference Workloads

### v0.8.5 (2026-01-29) — Hexagonal Middleware
- **SIP-0057** Hexagonal Layered Prompt System
- **SIP-0056** Hexagonal Queue Transport Layer

### v0.8.3 (2026-01-24) — Hexagonal Foundation
- **SIP-0055** DB Deployment Profile (Postgres portability)

### v0.8.2 (2026-01-10) — Secrets Management
- **SIP-0052** Secrets Management (env, file, docker_secret providers)

### v0.8.0 (2025-12-13) — ACI v0.8
- **SIP-0050** Agent Container Interface (ACI)
- **SIP-0048** CDS Baseline + Runtime API with FastAPI
- **SIP-0049** Agent Lifecycle & Health Check Integration

### v0.6.x (2025-11) — Skills + Memory
- **SIP-0040** Capability System & Loader (v0.6.0)
- **SIP-042** LanceDB Semantic Memory (v0.5.0)

### v0.4.0 (2025-11-03) — Orchestration
- **SIP-0041** Naming & Correlation (cycle/pulse/channel)
- **SIP-0031** Internal A2A Envelope Standard

### v0.2.0 (2025-10-11) — Test Coverage Milestone
- **SIP-0026** Testing Framework and Philosophy

### v0.1.x (2025-10) — Genesis
- First end-to-end AI agent collaboration (2025-10-07)
- WarmBoot runs 001–006 proving real agent work
- Initial 5-agent squad (Max, Neo, Nat, Eve, Data)
- Initial repo structure (2025-09-20)

---

## v1.0 Progression (Retrospective — 1.0 shipped 2026-03-10)

1.0 was organized around one concrete objective: **the first trustworthy long-running DGX Spark cycle**. Every SIP was prioritized by how directly it contributed to that objective.

**What actually shipped in 1.0**: all five Spark-critical SIPs (SIP-0076/77/78/79/80) landed between v0.9.14 and v0.9.18, followed by multi-run orchestration and bootstrap tooling in v0.9.19. The 1.0.0 release tag on 2026-03-10 marked architecture completion.

**What did not ship in 1.0**: the two originally-scoped "1.0 Hardening" SIPs (API Contract Hardening, Cycle Evaluation Scorecard) remain in the proposed backlog. They are now post-1.0 work tracked separately. If they become blocking, they get numbered and promoted — but 1.0 did not gate on them.

### Cross-Cutting Dependency: Canonical Artifact Flow

Multiple SIPs depend on a shared artifact contract. The following artifact types must have a consistent identity, storage, and promotion model across the platform:

- **Planning artifact** — durable handoff from planning to implementation
- **Plan refinement artifact** — structured deltas from human review
- **Implementation outputs** — code, tests, build results
- **QA findings** — defect reports, verification evidence
- **Plan deltas** — correction records during implementation
- **Closeout artifact** — wrap-up adjudication and evidence
- **Next-cycle handoff artifact** — carry-forward for the next planning phase

The Workload & Gate Canon SIP defines the artifact promotion model (working vs promoted). All pipeline SIPs produce or consume these artifacts. This dependency should be treated as a first-order integration concern, not an afterthought.

### Spark-Critical — Execution Readiness

These SIPs must land before the first DGX Spark validation run. They are sequenced by dependency.

| Order | SIP | Focus | Status |
|-------|-----|-------|--------|
| 1 | **SIP-0076** Workload & Gate Canon | `workload_type` on Run, gate outcome expansion, artifact promotion, Pulse vs Gate semantics | **Implemented (v0.9.14)** |
| 2 | **SIP-0077** Cycle Event System (v0) | Canonical lifecycle event bus, 20-event taxonomy, bridge adapters. v0 scope only — emit + bridge. Full rewire (v1) and event-first (v2) follow later. | **Implemented (v0.9.15)** |
| 3 | **SIP-0078** Planning Workload Protocol | Planning contract, durable planning artifact, QA-first test strategy, proto validation, unknown classification, readiness decision | **Implemented (v0.9.16)** |
| 4 | **SIP-0079** Implementation Run Contract | Run contract, correction protocol (detect → RCA → decide → plan delta → resume), **durable checkpoint/resume**, bounded retry/timebox | **Implemented (v0.9.17)** |
| 5 | **SIP-0080** Wrap-Up Workload Protocol | Closeout artifact, planned-vs-actual comparison, confidence classification, structured unresolved issues, next-cycle handoff | **Implemented (v0.9.18)** |

**Why this order**: Workload Canon defines the execution vocabulary. Event System provides lifecycle facts. The three pipeline protocols (Planning → Implementation → Wrap-Up) build on both. Implementation Run Contract is the single most important Spark-readiness SIP — without durable checkpoint/resume, a long run is fragile regardless of how clean the architecture is. Wrap-up is execution safety, not reporting polish — it is what makes memory, evaluation, and next-cycle readiness trustworthy.

### Milestone Stage 1: Local Validation (MacBook)

All Spark-critical SIPs are developed, tested, and validated locally on MacBook before the DGX Spark is available. The protocols are duration-agnostic — if they don't work reliably on a 1-hour MacBook cycle, they won't work on an 8-hour Spark cycle. Duration amplifies problems; it doesn't create them.

**Target**: One bounded Cycle on MacBook (1–2 hours) using the existing Docker Compose stack and Ollama with:
- 1 approved planning workload (15–30 min, timeboxed to local model speed)
- 1–2 bounded implementation workloads
- Pulse Checks active throughout execution
- At least one correction path exercised (simulated failure or real)
- Mandatory wrap-up artifact generation
- Checkpoint/resume tested (interrupt and resume a short cycle cleanly)

**Preflight Checklist** (required before local validation):
- [ ] Deployed platform version includes all Spark-critical SIPs
- [ ] Reference workload/app selected and cycle request profile defined
- [ ] Role capability readiness verified (Lead, Dev, QA, Data, Builder)
- [ ] Model budgets and timeouts configured for local Ollama models
- [ ] Checkpoint/resume tested on a trivial cycle (e.g., selftest profile)
- [ ] Event emission visible in LangFuse / Prefect
- [ ] Artifact persistence verified (create, retrieve, promote)
- [ ] Wrap-up path verified (closeout artifact emitted on both success and failure)
- [ ] Restart/redeploy confidence confirmed (services recover cleanly)
- [ ] Operator can monitor cycle health via console or Prefect UI

**Success Criteria** (same for both stages):
- Cycle completes or terminates cleanly (no orphaned state)
- Closeout artifact is produced with confidence classification
- Planned-vs-actual comparison is present and accurate
- Next-cycle handoff artifact is usable
- Operator can reconstruct what happened without reading raw logs

**Acceptable Failure Classes** (not a milestone failure):
- Partial completion with honest confidence classification
- Correction protocol triggered and executed cleanly
- Model limitations identified and attributed correctly (expected on smaller local models)

**Milestone Failure** (requires investigation before retry):
- Orphaned or inconsistent run state
- Missing or corrupted artifacts
- Checkpoint/resume fails silently
- Wrap-up does not execute or produces false confidence
- Events missing or out of order

### Milestone Stage 2: DGX Spark Validation Run

Once local validation passes, the same protocols are exercised at longer duration on DGX Spark. The Spark run proves the protocols hold under sustained execution with stronger models — it should not be the first time they are tested.

**Target**: One bounded Cycle on DGX Spark (4–8 hours) with:
- 1 approved planning workload (60–90 min)
- 2–4 bounded implementation workloads
- Pulse Checks active throughout execution
- At least one supported correction path exercised or verified
- Mandatory wrap-up artifact generation
- Checkpoint/resume tested (at minimum: verified that a resumed run recovers cleanly)

**Additional Spark-specific checks**:
- [ ] Model budgets and timeouts reconfigured for Spark-class models
- [ ] Longer execution does not introduce state drift, memory pressure, or artifact corruption
- [ ] Wrap-up quality does not degrade with larger evidence volume
- [ ] Correction protocol handles real (not simulated) mid-run issues

### Post-1.0 Hardening (Originally Scoped for 1.0 — Deferred)

These SIPs were originally scoped as "1.0 Hardening" but did not land before the 1.0.0 release. They remain in the proposed backlog.

| SIP | Focus |
|-----|-------|
| API Contract Hardening | Pagination, error shapes, OpenAPI response models, status codes, gate identity, artifact validation, DB retry |
| Cycle Evaluation Scorecard | Four-dimension evaluation (outcome, quality, coordination, efficiency), failure attribution, benchmarking, Scorecard console page |

**API Contract Hardening** was kept out of 1.0 because the Spark validation path did not expose execution-safety-blocking API issues. It is sequenced whenever a consumer (console, external integrator) surfaces a specific contract pain point.

**Cycle Evaluation Scorecard** is now slotted as the **v1.8** grading release — gated on SIP-0096 Verification Evidence Integrity implemented, consuming the `CycleOutcome` roll-up rather than raw checks. Scorecard sophistication improves learning *after* runs; it does not improve the success of any individual run, which is exactly why it sits behind honest evidence (1.4) and trusted automation (1.6). See `docs/plans/1-4-evidence-arc-plan.md`.

### Critical Path

```
Workload & Gate Canon ─── Planning Workload Protocol ──────────────┐
          │                                                         │
          │            Implementation Run Contract ─────────────────┤
          │                                                         │
          │            Wrap-Up Workload Protocol ───────────────────┤
          │                                                         │
Cycle Event System (v0) ───────────────────────────────────────────┤
                                                                    │
                    ┌── LOCAL VALIDATION (MacBook) ──┐              │
                    │   1-2 hour bounded cycle       │              │
                    └────────────────────────────────┘              │
                                  │                                 │
                    ┌── SPARK VALIDATION ────────────┐              │
                    │   4-8 hour long run            │              │
                    └────────────────────────────────┘              │
                                                                    │
          API Contract Hardening ───────────────────────────────────┼── v1.0
                                                                    │
          Cycle Evaluation Scorecard ──────────────────────────────┘
```

### Post-1.0 Horizon

The following areas are identified for future work but do not block 1.0 readiness:

- **WebSocket / Realtime Channels** — live event streaming to the console, real-time chat protocol between operators and agents. Depends on the Cycle Event System. See `docs/ideas/IDEA-WebSocket-*` and `docs/ideas/IDEA-Realtime-Chat-*`.
- **Cycle Event System v1/v2** — rewire call sites (v1), event-first architecture (v2).
- **Retrieval-enriched planning memory** — LanceDB integration for planning phases.
- **Cross-cycle learning** — historical comparison, scored memory, trend analysis.
- **Autonomous improvement proposals** — agent-driven suggestions based on repeated failure patterns.
- **Advanced benchmarking** — rule-based recommendations on top of the scorecard framework.

---

## Accepted (Next Up)

| SIP | Title | Target |
|-----|-------|--------|
| **SIP-0088** | Agent Runtime Modes (umbrella; runtime arc shipped 1.1–1.2, remaining pieces future) | stays accepted (audited 2026-08-03: children 0090 P2–4 / 0091 open, → v1.6) |
| **SIP-0090** | Agent Embodiment Substrate (Phase 1 shipped 1.2.0) | Phases 2+ → v1.6 |
| **SIP-0091** | Duty Durability via Temporal | v1.6 |
| **SIP-0092** | Implementation Plan Improvement — Typed Acceptance, Separated Authoring, and Plan Changes | stays accepted (audited 2026-08-03: M1 landed, M2 partial on 93.4, M3 unstarted; `docs/plans/sip-promotion-audit-2026-08-03.md`) |
| **SIP-0093** | Multi-Role Plan Authoring | stays accepted (audited 2026-08-03: runtime-complete; 93.4 + §5.8 merge rules 2–5 + two required tests remain) |
| **SIP-0101** | Cycle Replay Harness | next up — deferral condition (98.5 baseline) spent at the 1.4 cut |
| **SIP-0103** | **Squad-Authored Manifest** (accepted 2026-08-07 — the v1.6 Lane M headline; §5a/§5b/§5c in force) | **v1.6** |
| **SIP-0102** | Ephemeral Application Sandbox (1.4 floor shipped as the v1.4.0 S-lane headline) | migration steps 3–7 → v1.6 S-lane rider (in-cycle routing, clean-room verdicts, #306 retirement, golden-path validation; kept out of 1.5 to keep the odd minor feature-free) |

## Proposals (Backlog)

### Post-1.0 Hardening (Deferred from 1.0 Scope)

| SIP | Title |
|-----|-------|
| (unnumbered) | API Contract Hardening |
| (unnumbered) | Cycle Evaluation Scorecard |

### Unnumbered Drafts (filed, awaiting design review)

| SIP | Title |
|-----|-------|
| (unnumbered) | Squad-Authored Manifest (v1.6 Lane M headline candidate) |
| (unnumbered) | Campaign Orchestration (v1.8 Lane M headline candidate; retargeted from 1.6, 2026-08-03) |
| (unnumbered) | Cross-Cycle Memory (Phase 1 → v1.8 rider; Phase 2 → v2.0 scoped-memory substrate) |
| (unnumbered) | Campaign Self-Improvement and Test Bay Requirements (2.0 vision anchor) |
| (unnumbered) | Agent Comms Delivery Guarantees (Campaign gate — moves to 1.8 with Campaign, or rides 1.6 as hardening) |
| (unnumbered) | Edge Deployment Profile |
| (unnumbered) | Experiment Queue and Cycle Assessment |

### Legacy Proposals

| SIP | Title |
|-----|-------|
| SIP-0012 | Pattern-First Development Escalation Protocol |
| SIP-0013 | Extensibility & Customization Protocol |
| SIP-0016 | Human-Agent Hybrid Squad Operations |
| SIP-0018 | Enterprise Process CoE Enablement |
| SIP-0018-v2 | Squad Context Protocol |
| SIP-0023 | Domain Expert Architecture for Product Strategy |
| SIP-0028 | Hybrid Deployment Model (Multi-Environment) |

---

## Stats

*As of 2026-08-21 (v1.6.0):*

- **Framework version**: 1.6.0
- **SIPs**: 65 implemented, 9 accepted (SIP-0088, 0090–0093, 0101, 0102, 0104, 0105), 20 deprecated (registry)
- **Tests**: 7,600+ passing in the regression suite
- **Python source**: ~61,000 lines (src + adapters; ~88,000 test lines, ~119,000 doc lines)
- **~6 months** from initial repo (2025-09-20) to 1.0.0 release (2026-03-10)
