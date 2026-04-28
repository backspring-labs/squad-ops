# 1.0.x Build Reliability Hardening Plan

**Created:** 2026-04-27
**Status:** Active — #1 drafted, #2 next
**Scope:** SquadOps 1.0.x patch series (Spark lane); orthogonal to v1.1 work (SIP-0088+)

## Intent

The 1.0.x series targets **autonomous cycles long enough to build the best possible vertical slice** — not 1-hour timeboxes. That scoping decision changes what "reliability" means: in a 1-hour cycle the bottleneck is *did the squad ship anything*; in a multi-hour cycle the bottleneck is *did the squad stay coherent over time*. Plans drift, decisions get re-litigated, context windows reset, runaway loops compound into cost incidents, and a half-right manifest at hour two poisons the rest of the run. The proposals in this plan are ordered to attack that "stay coherent" failure mode directly: each SIP either gives the squad better evidence to act on, a better way to evolve its plan when reality diverges, or a guardrail that keeps the loop bounded. Build-reliability work runs as a focused track; release/API hardening runs as a parallel track and is not the target of this plan.

## Build-reliability axis (priority order)

| # | SIP | Status | Where |
|---|-----|--------|-------|
| 1 | **Build Manifest Maturation** — typed acceptance criteria + separated authoring + delta overlays (SIP-0086 follow-up) | drafted 2026-04-27 | `sips/proposed/SIP-Build-Manifest-Maturation.md` |
| 2 | **Smoke & Acceptance Capability Pack** — `qa.start_app` / `qa.probe_endpoint` / `qa.capture_evidence`, cadence-bound for long cycles | net new — to write | — |
| 3 | **Cycle Evaluation Scorecard — phases 1+2 only** — evaluation contract + evidence capture; defer console UI to post-1.0 | proposed, needs scope cut | `sips/proposed/SIP-Cycle-Evaluation-Scorecard.md` |
| 4 | **Cross-Run Memory & Context Handoff** — typed `cycle_handoff.json` ledgers (decisions/defects/open-questions) + run-startup primer + within-run summarization | net new — to write | — |
| 5 | **Run Trajectory & Continuation Protocol** — Strategy declares trajectory hypothesis; Lead emits typed continuation decision per run; default-terminate bias; hard caps. Depends on #2/#3/#4 evidence. | net new — to write | — |
| 6 | **Cycle Resume Contract** — idempotent task re-entry, partial-output preservation, RabbitMQ dedup on restart | net new — to write | — |
| 7 | **Structured Defect Report & Targeted Repair** — `defect_report.json` schema + `qa.localize_defect` step feeding `development.repair` | net new — to write | — |
| 8 | **QA Maturity Ladder** — Stage A/B/C selectable per cycle length | rewrite + rename existing IDEA | `sips/proposed/IDEA-QA-First-Test-Strategy-1h-Cycles-group_run.md` → `SIP-QA-Maturity-Ladder.md` |
| 9 | **LLM Budget operator surface + breakers** | partial — SIP-0073 follow-up | needs new SIP |
| 10 | **Stack Capability Registry concretization** — concrete `DevelopmentCapability` registry: React+Vite, FastAPI, Node test runner, Playwright | partial — SIP-0072 follow-up | needs new SIP |
| 11 | **Planning-Sequence-Strategy-First** — flip `PLANNING_TASK_STEPS` order so Strategy frames before Data researches | proposed (stub) | `sips/proposed/SIP-Planning-Sequence-Strategy-First.md` — flesh out before acceptance |

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
- **#6 after #5.** Resume is a defensive layer; it lands once the things worth resuming exist.
- **#9 (budget breakers)** can pull earlier if cost on long autonomous runs becomes urgent before continuation (#5) lands. Without breakers, dynamic continuation is a cost incident waiting to happen.
- **#11** is cheap and empirically motivated; it can land in parallel with the larger items whenever a contributor has time.

## Net-new SIPs to write: 5

#2 Smoke Pack · #4 Cross-Run Memory · #5 Run Trajectory · #6 Resume Contract · #7 Defect Report

Everything else is either already in `sips/proposed/`, a follow-up to an accepted/implemented SIP, or a rewrite of an existing IDEA file.

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
