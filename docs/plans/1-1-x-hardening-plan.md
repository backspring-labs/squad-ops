# 1.1.x Hardening Plan

**Status:** active (historical record + opportunistic backlog) · **Established:** 2026-06-28 · **Partially superseded 2026-06-29 (#281)**

> **Forward pointer (2026-06-29):** Versioning is now governed by the **even/odd minor convention** (#281) — see `CLAUDE.md` › Versioning & Release Cadence and `docs/ROADMAP.md`. Forward release scheduling of this plan's *Capability SIPs* and *Runtime-lane follow-ups* buckets now lives in **[`1-2-0-release-plan.md`](1-2-0-release-plan.md)**. This doc stays authoritative for exactly two things: the **1.1.0 gate re-baseline record** (below) and the **un-scheduled opportunistic tech-debt backlog**. Items shipped in **1.1.1** are struck/marked inline.

## Why this exists

The original 1.0.x plan gated the `1.1.0` version bump on *all* build-reliability
hardening completing. With SIP-0089 (Agent Runtime State) delivered and tested,
that gate was re-read (joint Spark/Mac decision, 2026-06-28) as **foundational
hardening completeness** — the CI-trust arc + reliability bugs — which *is* done.
1.1.0 shipped on that basis; the remaining hardening is re-baselined here as the
**1.1.x hardening plan** — ongoing post-1.1 work that no longer blocks a version.

Versioning discipline: ~~bug fixes → 1.1.x patches; larger capability-bearing
SIPs may warrant 1.2.0 minors; tech-debt/arch → opportunistic~~ — **superseded
2026-06-29 by the even/odd minor convention (#281):** even minors = feature
releases (headline SIP; safe hardening rides along), odd minors = feature-free
stabilization (big risky refactors + debt), patches = urgent fixes any time.
See `CLAUDE.md` › Versioning & Release Cadence.

Supersedes the gating framing of
[`1-0-x-build-reliability-hardening-plan.md`](1-0-x-build-reliability-hardening-plan.md)
(that doc remains the detailed build-reliability axis; this one is the release-lane view).

## Foundational hardening — DONE (shipped in 1.1.0)

- CI-trust arc: declared deps (#206/#191), dev+CI on Python 3.12 (#217),
  ruff-format gate (#196), adapters in the gate (#207), pulse-e2e (#211),
  integration config (#209).
- Reliability bugs: #146 (channel recovery), #155 (frozen-result mutation),
  #77 (cancel→Prefect), #150 (cycle-route scope enforcement — security).

## 1.1.x patches (bug fixes)

Most of this batch shipped in **1.1.1**. Genuinely still open: **#198**. ⚠️ **Hygiene gap:** **#133** and **#205** were credited in the 1.1.1 CHANGELOG but their issues are **still open** — verify residual scope or close them.

| Issue | | Status |
|-------|--|--------|
| #132 | `runs resume --reason` always returns 422 (CLI/API contract drift) | ✅ closed |
| #133 | `runs retry` is dead weight — advertises but never executes | ⚠️ fix shipped in 1.1.1, **issue still open** — verify/close (same for #205) |
| #245 | RabbitMQ `publish()` has no retry during the reconnect window | ✅ 1.1.1 |
| #239 | OTel `BrokenExporter` test pollutes every regression run (atexit noise) | ✅ 1.1.1 |
| #168 | Residual `DistributedFlowExecutor` refs after the #164 rename | ✅ 1.1.1 |
| #198 | FastAPI cap-lift (console router cycle) — adopt ≥0.136 | ⬜ open — a **1.2.0 prerequisite** (CI health), see `1-2-0-release-plan.md` §5.5 |
| #130 | Neo `development.develop` unparseable output under spark models | ✅ 1.1.1 |

## Capability SIPs (feature-bearing — likely 1.2.0+ minors)

These add new capabilities, so they ship as minor releases. **Now scheduled in
[`1-2-0-release-plan.md`](1-2-0-release-plan.md):** #176 rides *with* 1.2.0 (the
smoke/invariant net); SIP-0093 B′ (#194) is a later even release; the rest stay
backlog. Order per the build-reliability axis.

| # | Item |
|---|------|
| 2 | Smoke & Acceptance Capability Pack (#176): `qa.start_app`/`probe_endpoint`/`capture_evidence` |
| — | SIP-0093 authoring depth: B′ (revision loop) → C (M3.1/M3.2) → D (M3.3) |
| 4 | Cross-Run Memory & Context Handoff (typed ledger) |
| 6 | Structured Defect Report & Targeted Repair |
| 7 | Cycle Resume Contract (technical idempotency) |
| 5/5a | Run Trajectory & Continuation Protocol + minimal budget breakers |
| 3 | Cycle Evaluation Scorecard (phases 1–2) |
| 8 | QA Maturity Ladder (composes #2 into stages) |
| 10 | Stack Capability Registry concretization |

## Ongoing tech-debt / arch (slot opportunistically — never version-gating)

**Shipped in 1.1.1:** ~~#153 (DbRuntime sqlalchemy sub-piece)~~, ~~#156 (`_parse_jsonb` dedup)~~,
~~#250 (duplicate WorkflowTracker factory)~~, ~~#216 (pytest-xdist)~~,
~~#134 (qwen2.5:32b YAML brittleness)~~.

**Still open:** #234 (DbRuntime sqlalchemy-port leak — broader than the closed #153),
#154 (adapter imports in domain), #242 (gate serviceless integration tests),
#218/#219 (runtime-api URL conventions), #157 (api/comms coverage),
#158 (schema_migrations table), #173 (squad-profile name consolidation),
#224 (model-availability preflight), #237 (drop 3.11 / migrate prod to 3.12),
#80 (cycle lineage on the record).

**Pulled into the 1.2.0 schedule** (see `1-2-0-release-plan.md`): #234/#186/#152 →
quarantined to **1.3.0** stabilization; #158/#173 → **1.2.0 prerequisites** (§5.5);
#224 → folded into the 1.2.0 **Preflight SIP** (#172+#224).

## Runtime-lane follow-ups carried out of 1.1.0 (SIP-0089 known limitations)

~~#222 (resume a hard-duty-deferred cycle — needs a checkpoint)~~ **shipped in 1.1.1.**
#233 (recruitment-acquired FocusLeases via coordinator) and #244 (single-transaction
coordinator writes vs best-effort compensation) are **now the 1.2.0 committed core** —
see [`1-2-0-release-plan.md`](1-2-0-release-plan.md) §2.
