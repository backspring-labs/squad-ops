# 1.0.x Build Reliability Hardening Plan

**Created:** 2026-04-27
**Updated:** 2026-04-27 (rev 2 — incorporated external review feedback)
**Status:** Active — #1 drafted, #2 next
**Scope:** SquadOps 1.0.x patch series (Spark lane); orthogonal to v1.1 work (SIP-0088+)

## Intent

The 1.0.x series targets **autonomous cycles long enough to build the best possible vertical slice** — not 1-hour timeboxes. That scoping decision changes what "reliability" means: in a 1-hour cycle the bottleneck is *did the squad ship anything*; in a multi-hour cycle the bottleneck is *did the squad stay coherent over time*. Plans drift, decisions get re-litigated, context windows reset, runaway loops compound into cost incidents, and a half-right manifest at hour two poisons the rest of the run. The proposals in this plan are ordered to attack that "stay coherent" failure mode directly: each SIP either gives the squad better evidence to act on, a better way to evolve its plan when reality diverges, or a guardrail that keeps the loop bounded. Build-reliability work runs as a focused track; release/API hardening runs as a parallel track and is not the target of this plan.

## Build-reliability axis (priority order)

| # | SIP | Status | Where |
|---|-----|--------|-------|
| 1 | **SIP-0092 Build Manifest Maturation** — typed acceptance criteria + separated authoring + delta overlays (SIP-0086 follow-up) | accepted 2026-04-29; plan on `feature/sip-0092-build-manifest-maturation` | `sips/accepted/SIP-0092-Build-Manifest-Maturation-Mechanical.md` |
| 2 | **Smoke & Acceptance Capability Pack** — `qa.start_app` / `qa.probe_endpoint` / `qa.capture_evidence`, cadence-bound for long cycles | net new — to write | — |
| 3 | **Cycle Evaluation Scorecard — phases 1+2 only** — evaluation contract + evidence capture; defer console UI to post-1.0 | proposed, needs scope cut | `sips/proposed/SIP-Cycle-Evaluation-Scorecard.md` |
| 4 | **Cross-Run Memory & Context Handoff** — typed `cycle_handoff.json` ledgers (decisions/defects/open-questions/artifact pointers/known failing checks) + run-startup primer + within-run summarization | net new — to write | — |
| 5a | **Minimal LLM Budget Breakers** *(precondition for #5)* — wall-clock cap, max continuation count, max LLM spend, max repeated-failure count, emergency-stop reason code, operator-visible termination summary | partial — SIP-0073 minimal follow-up, pulled forward | needs new SIP (small) |
| 5 | **Run Trajectory & Continuation Protocol** — Strategy declares trajectory hypothesis; Lead emits typed evidence-gated continuation decision per run; default-terminate bias. Depends on #2/#3/#4 evidence and #5a's hard breakers. | net new — to write | — |
| 6 | **Structured Defect Report & Targeted Repair** — machine-actionable `defect_report.json` schema (failing check / expected / observed / suspected component / evidence ref / repair recommendation / confidence / retest needed) + `qa.localize_defect` step feeding `development.repair` | net new — to write | — |
| 7 | **Cycle Resume Contract** *(technical idempotency only)* — idempotent task re-entry, partial-output preservation, RabbitMQ dedup on restart. NOT defect-aware "smart resume" — that's #6's job at the planning level. | net new — to write | — |
| 8 | **QA Maturity Ladder** — composes #2's primitives into Stage A/B/C profiles. Stages map to cycle duration AND risk profile, not just "more tests." | rewrite + rename existing IDEA | `sips/proposed/IDEA-QA-First-Test-Strategy-1h-Cycles-group_run.md` → `SIP-QA-Maturity-Ladder.md` |
| 9 | **LLM Budget Operator Surface** — live per-role spend, projected burn, dashboards, configuration UI/CLI. (Enforcement breakers split into #5a above.) | partial — SIP-0073 follow-up | needs new SIP |
| 10 | **Stack Capability Registry concretization** — concrete `DevelopmentCapability` registry where each entry declares its acceptance capabilities (React+Vite knows how to run/build/smoke-test itself; FastAPI knows how to start, expose OpenAPI, probe endpoints). Tightens #2's primitives by stack. | partial — SIP-0072 follow-up | needs new SIP |
| 11 | **Planning-Sequence-Strategy-First** — flip `PLANNING_TASK_STEPS` order so Strategy frames before Data researches. Treat as empirical tweak: ship with before/after run evidence; revert if it doesn't measurably improve manifest quality or reduce re-litigation. | proposed (stub) | `sips/proposed/SIP-Planning-Sequence-Strategy-First.md` — flesh out before acceptance |

## Capability/policy boundaries (explicit)

To keep these SIPs from accumulating responsibility creep:

- **#1 — Build contract, not universal artifact.** Stays scoped to build decomposition + acceptance + overlays. Does NOT own planning, execution, QA cadence, continuation, or memory.
- **#2 — Capability primitives.** Provides reusable executable checks (start, probe, capture). Does NOT decide when, how often, or how deeply they run — that's #8's job.
- **#3 — Evaluates evidence; does not invent it.** Evidence sources are #2 and existing cycle artifacts. Scorecard does not run smoke checks itself.
- **#4 — Typed handoff ledger.** What it IS: decisions, defects, accepted constraints, rejected paths, open questions, artifact pointers, continuation recommendations, known failing checks, next-run primer. What it is NOT: transcript dump, chain-of-thought storage, unbounded summarization, alternate planning document.
- **#5 — Evidence-gated continuation, default-terminate.** Cannot ship before #5a's breakers exist. Continuation decision must cite trajectory hypothesis, evidence summary, remaining gap, confidence, risk/cost status, explicit reason, hard-cap check.
- **#6 — Machine-actionable defect reports.** Prose-only QA findings explicitly out of scope.
- **#7 — Technical idempotency only.** Resume restores known state; it does not interpret what's worth resuming. That's #6's responsibility.
- **#8 — Composes, doesn't reinvent.** Stage A = smoke only. Stage B = smoke + endpoint + basic UI. Stage C = deeper acceptance + repair loop + evidence pack. Each stage is a profile composed from #2's primitives.
- **#10 — Registry tightens primitives by stack.** Each capability entry declares its run/build/probe/smoke-test contract; #2 calls into them rather than reimplementing per stack.

## Parallel 1.0.x track (orthogonal to build reliability)

These ship on the 1.0.x patch lane but do not contribute to build-reliability. Listed for completeness so the program isn't fragmented across multiple plans.

| SIP | Status | File |
|-----|--------|------|
| Version-Bump-Hardening | proposed | `sips/proposed/SIP-Version-Bump-Hardening.md` |
| API-Contract-Hardening | proposed | `sips/proposed/SIP-API-Contract-Hardening.md` |

## Triage / skip for 1.0.x

- `sips/proposed/SIP-intelligent-delegation-protocols.md` — v1.1+ architectural overlay
- March-vintage proposed SIPs (`SIP-0012`, `SIP-0013`, `SIP-0016`, `SIP-0018`, `SIP-0018-v2`, `SIP-0023`, `SIP-0028`) — likely stale or superseded by 0064–0087; need a triage pass but not on the critical path

## Why this order

- **#1 first.** The current build manifest is informational and one-shot. There is no point hardening downstream signals until the plan can both *validate* against typed criteria and *evolve* via overlays when reality diverges.
- **#2 and #3 next.** They produce the evidence every later SIP cites. A continuation decision (#5) cannot be stronger than the acceptance signal (#2) and the evaluation contract (#3) it references.
- **#4 before #5.** Run trajectory and continuation only work if cross-run memory exists. Otherwise run N+1 starts amnesiac and re-litigates run N's decisions.
- **#5a as hard precondition for #5.** Continuation without breakers is a cost incident waiting to happen. The minimal-breaker subset is small enough to ship as a focused SIP-0073 follow-up; the full operator surface (#9) can land later.
- **#6 before #7 (Defect Report before Resume).** Defect reports have higher per-week reliability impact on long cycles than infrastructure resilience does. Resume is defensive against rare events (container restart, network blip); defect reports are offensive against the routine event (every failed validation). Higher-leverage work first.
- **#7 scoped narrowly.** Resume is technical idempotency only. The "knows what to repair" intelligence belongs to #6, not #7. Keeping the boundary clean prevents Resume from over-scoping.
- **#11 in parallel.** Cheap and empirically motivated; can land alongside larger items whenever a contributor has time. Treat as empirical: revert if it doesn't measurably help.

## Net-new SIPs to write: 6

#2 Smoke Pack · #4 Cross-Run Memory · #5a Minimal Breakers · #5 Run Trajectory · #6 Defect Report · #7 Resume Contract

Everything else is either already in `sips/proposed/`, a follow-up to an accepted/implemented SIP, or a rewrite of an existing IDEA file. (#5a is a focused SIP-0073 follow-up — small, but called out separately because it gates #5.)

## How to use this plan

- **Picking the next item:** default to the lowest-numbered un-drafted SIP. As of 2026-04-27 that's #2 (Smoke & Acceptance Capability Pack).
- **Updating this plan:** when a SIP moves status (drafted → accepted → implemented), update its row. When ordering changes based on new evidence, update the rationale section explaining why.
- **Branching:** each SIP gets a feature branch off main per the standard SIP workflow in `CLAUDE.md`. Land via PR; promote SIP status with `scripts/maintainer/update_sip_status.py` after merge.

## References

- `CLAUDE.md` — SIP workflow, repository rules
- `sips/registry.yaml` — canonical SIP index
- Memory: `project_two_session_split.md` — confirms 1.0.x = Spark lane, v1.1 = Mac lane
- Memory: `project_sip0086_manifest_handoff_bug.md` — motivates artifact-type discipline #1's overlays inherit
- Memory: `project_spark_cycle_status.md` — motivates #1's authoring split

## Revision history

- **rev 2 (2026-04-27):** Incorporated external review. Three structural changes: (1) split former #9 into #5a (minimal breakers, precondition for #5) and #9 (full operator surface, original slot); (2) swapped former #6 ↔ #7 — Defect Report now precedes Resume Contract, with Resume scoped to technical idempotency only; (3) added explicit Capability/Policy Boundaries section. Plus annotations on #4 (typed-not-soup), #6 (machine-actionable fields), #8 (duration AND risk), #10↔#2 link, #11 (empirical, revertible).
- **rev 1 (2026-04-27):** Initial plan landed via PR #67.
