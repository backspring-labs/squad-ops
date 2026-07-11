---
title: Fine-Grained Issue Enumeration
status: proposed
author: jladd
created_at: '2026-07-10T00:00:00Z'
---
# SIP: Fine-Grained Issue Enumeration

## Status
Proposed — **vision stub** (early direction, not a committed spec)

**Targets:** vision item — no committed release. The fine-grained successor to the SIP-0086 convergence loop; a candidate for the 2.0 capability/campaign arc once the evidence substrate (SIP-0096) and behavioral build path (Contract-First Scaffolding) are in place.
**Builds on:** SIP-0096 (Verification Evidence Integrity — the per-check evidence families + `CheckResult` + the `CycleOutcome` roll-up §10), SIP-0086 (Build Convergence Loop — the coarse predecessor).
**Coordinates with:** `SIP-Contract-First-Build-Scaffolding` (build/boot so QA reaches behavioral issues) and `SIP-Externalized-Build-Sandbox` (where QA runs the app to find them).
**Origin:** `docs/ideas/IDEA-Checks-as-Issue-Ledger.md`, distilled from the #374/#379 verification work.

---

## 1. Abstract

Today's build convergence is **coarse and binary**: a whole task fails, the correction loop repairs the whole task, and it re-runs — an "issue count" of ~1. This SIP proposes the **fine-grained successor**: QA emits **many small checks** (one per endpoint / behavior / acceptance criterion); the set of **failed** checks *is* an enumerated **issue list**; dev **resolves them one by one**, each fix flipping one check from failed → passed; and the run is `accepted` only when every required check is executed-and-passed.

The load-bearing reframe: **a check is an issue's definition-of-done.** The `(check_id, subject_ref)` identity (SIP-0096 provenance) is a discrete unit with an **open (FAILED) → resolved (PASSED)** lifecycle — an issue's state machine in miniature. This SIP promotes that latent structure into a first-class **issue ledger**.

## 2. Problem

- **Granularity.** One coarse failure signal ("qa.test failed") cannot be triaged, prioritized, or resolved independently. Real defects are many and distinct; the loop should address them as such.
- **No enumerated lifecycle surface.** `run_report.md` enumerates *failed* and *not-executed* checks but only *counts* passed, and shows only the final post-correction state. The failed→passed trail is scattered across `failure_analysis.md` / `plan_delta_N.json` / `repair_validation.md`; the append-only `RunLedger` holds both states but is never persisted as an enumerated view. There is no single place to see "which issues were open, which are resolved, which remain."
- **One-by-one remediation isn't modeled.** The convergence loop repairs in bulk; it cannot assign, order, or independently verify discrete defects the way a human team resolves a backlog.

## 3. Proposal (sketch)

1. **Fine-grained checks.** QA authors checks at behavior/endpoint/criterion granularity (extends SIP-0092 typed acceptance), each with a stable `(check_id, subject_ref)` identity.
2. **Issue ledger.** A durable per-run/per-cycle ledger enumerating every check as an issue: subject, severity, evidence, and open/resolved lifecycle — the `CycleOutcome` roll-up (SIP-0096 §10) extended from a summary into a tracker.
3. **One-by-one resolution.** Dev tasks target individual open issues; each is independently re-verified (its check re-run to passed, per the #374/#379 mechanism) and closed when — and only when — its check is executed-and-passed.
4. **Discrete re-validation tasks (observability).** Each open issue's check re-runs as its **own orchestrator task**, so the repair loop appears in Prefect as a live board of checks flipping green one-by-one — riding the existing SIP-0087 per-task task-run + log-streaming rails (which already surface correction/repair steps). Split by execution model: **deterministic/behavioral checks** (build passes, test passes, endpoint returns 200) are re-run by the **harness** — execution, not judgment (cheap, objective, and exactly SIP-0096 "executed-and-passed"); **LLM-judgment checks** stay agent-run and coarser. The dev agent **fixes**; the harness **re-validates**.
5. **Verdict.** Unchanged in spirit from SIP-0096: `accepted` iff every required issue's check is executed-and-passed; open required issues → `rejected`/`blocked_unverified`.

## 4. Non-Goals (for the stub)

- No new verdict/evidence semantics — reuse SIP-0096.
- Not the near-term #374/#379 scope — those build the *substrate* (re-verification + final-state identity); this is the *tracker* on top.
- No external issue-tracker integration (GitHub, Jira) in v1 — the ledger is internal; external sync is a later question.

## 5. Open Questions

1. **Issue identity & dedup** across runs — when is a re-surfaced failure "the same issue"? (`(check_id, subject_ref)` is the seed; cross-run identity is harder.)
2. **Severity & ordering** — how issues are prioritized for one-by-one resolution.
3. **Assignment granularity** — one dev task per issue vs. batched, and how that interacts with the convergence loop's attempt budget.
4. **Surface** — where the ledger lives (run_report section, dedicated artifact, Console view) and whether it ever syncs to an external tracker.
5. **Relationship to Campaign / Test Bay** (SIP-0096 downstream consumers) — is the issue ledger the evidence they act on?
6. **Granularity prerequisite for discrete tasks** — per-check re-validation tasks are only meaningful once checks are per-behavior (today `tests_pass` is one coarse suite-level check). Enumeration must precede decomposition.
7. **Dependency ordering** — structural checks gate behavioral ones (build → boot → endpoints); the re-validation graph must respect this or it burns task-runs re-checking things that cannot pass yet.
8. **Harness vs. agent execution** — which checks are harness-executed (deterministic) vs. agent-judged, and the cost of one Prefect task-run per check on a bandwidth-bound single GPU.
