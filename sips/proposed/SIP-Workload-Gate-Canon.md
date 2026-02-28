# SIP-0XXX: Workload & Gate Canon

**Status:** Proposed
**Authors:** SquadOps Architecture
**Created:** 2026-02-28
**Revision:** 1

## 1. Abstract

SquadOps currently models execution as Cycle → Run → Task. This SIP formalizes the **Workload** concept as the bounded unit of intended work within a Cycle, and tightens the semantics of Gates, Pulses, and artifact promotion. The result is a cleaner execution hierarchy — Cycle → Workload → Run → Task — where each concept answers a distinct question and the platform can support multi-phase cycles (planning, implementation, wrap-up) without collapsing responsibilities into a single monolithic run.

## 2. Problem Statement

As SquadOps moves toward longer-running, multi-phase cycles, the current Cycle → Run model lacks a semantic layer for "what bounded thing are we trying to get done." Without it:

- A Cycle that includes planning, implementation, and wrap-up must either be one giant Run or multiple Runs with no explicit relationship to the phase they serve.
- Gates conflate in-run health checks with inter-phase progression decisions.
- Artifact provenance is flat — there is no distinction between working artifacts and promoted cycle-level artifacts.
- Pause/resume semantics become ambiguous when a Cycle has multiple sequential concerns.
- Post-run evaluation has no natural workload container.

The platform needs a vocabulary and domain model that keeps these concerns separate so they can be reasoned about, orchestrated, and evaluated independently.

## 3. Goals

1. Introduce **Workload** as a first-class domain concept: a bounded unit of intended work within a Cycle, with its own objective, scope, acceptance criteria, and expected inputs/outputs.
2. Add `workload_type` to Run so each Run is explicitly associated with a Workload classification (e.g., planning, implementation, evaluation).
3. Formalize **Gate** semantics as progression/promotion boundaries between Workloads, not as in-run pause mechanisms.
4. Formalize **Pulse** semantics as in-run health/alignment checkpoints that live inside a Run, distinct from Gates.
5. Introduce an **artifact promotion model** distinguishing working (run-scoped) artifacts from promoted (cycle-scoped) artifacts.
6. Define a recommended multi-workload Cycle pattern: Planning → Implementation → Wrap-Up/Evaluation.

## 4. Non-Goals

- Implementing the Planning, Implementation, or Wrap-Up workload protocols (those are separate SIPs that build on this canon).
- Introducing a Workload database entity with its own table — for 1.0, Workload is a classification on Run (`workload_type`), not a new entity level.
- Defining the MEH-ta evaluation model or scorecard framework (covered by the Cycle Evaluation Scorecard SIP).
- Replacing or modifying existing Pulse Check behavior from SIP-0070 — this SIP clarifies the semantic boundary, not the implementation.
- WebSocket or real-time event delivery — post-1.0 concern.

## 5. Approach Sketch

### Domain Model Extension

Add `workload_type: str | None` to the `Run` frozen dataclass. This preserves the Cycle → Run hierarchy while classifying each Run by the workload it serves. Standard workload types:

- `planning` — plan production and proto validation
- `implementation` — code/build/test convergence loop
- `evaluation` — wrap-up, scorecard, MEH-ta analysis
- `refinement` — plan revision after human feedback

### Gate Semantic Tightening

Gates today are generic decision points. This SIP clarifies two distinct gate roles:

- **Progression Gate** — controls whether the next Workload phase may begin (e.g., plan review before implementation).
- **Promotion Gate** — controls whether a run-scoped artifact is elevated to cycle-level canonical status.

Gate outcomes expand beyond approve/reject to include: `approved`, `approved_with_refinements`, `returned_for_revision`, `rejected`.

### Artifact Promotion

Artifacts gain a `promotion_status` field: `working` (default) or `promoted`. Only promoted artifacts are visible at the cycle level. Promotion happens explicitly at a Gate or via API call, never implicitly.

### Multi-Workload Cycle Pattern

The SIP defines a recommended (not mandatory) Cycle shape:

1. **Planning Workload** — produces plan artifact, undergoes human review gate.
2. **Implementation Workload** — executes the approved plan, owns the dev/test/fix convergence loop.
3. **Evaluation Workload** — runs automatically after implementation, produces closeout and scorecard artifacts.

Each workload may have multiple Runs (initial attempt, retry, refinement).

### Pulse vs Gate Clarification

- **Pulse** = in-run health check. Fires on cadence or milestone. Does not pause execution by default. Monitors alignment, progress, drift, quality.
- **Gate** = inter-workload progression boundary. Requires explicit decision (human or policy). Pauses cycle progression until decided.

## 6. Key Design Decisions

1. **Workload is a Run classification, not a new entity** (Option B from the IDEA). Adding `workload_type` to Run is the minimum viable change. A full Workload entity can come later if the domain model demands it, but 1.0 should not over-engineer.
2. **Gate outcomes are richer than binary** — `approved_with_refinements` enables tracked plan feedback without forcing reject-and-redo cycles.
3. **No HIL gates inside normal workload runs by default** — human intervention belongs at workload boundaries, not as interior pause points. In-run health is Pulse's job.
4. **Evaluation workload starts automatically** — no HIL gate between implementation and evaluation by default. Analysis is most valuable when the run did not go well; gating it suppresses the feedback loop.
5. **Artifact promotion is explicit** — prevents noise, stale drafts, and half-baked outputs from becoming canonical cycle state.

## 7. Acceptance Criteria

1. `Run` dataclass includes `workload_type: str | None` field.
2. Postgres DDL migration adds `workload_type` column to the runs table.
3. Gate decision model supports `approved`, `approved_with_refinements`, `returned_for_revision`, `rejected` outcomes.
4. Artifact model includes `promotion_status` field with `working`/`promoted` values.
5. API routes support filtering Runs by `workload_type`.
6. API routes support promoting artifacts (PATCH or POST endpoint).
7. Documentation defines the Cycle → Workload → Run → Task hierarchy and the Pulse vs Gate distinction.
8. Existing tests pass; new tests cover workload classification, gate outcomes, and artifact promotion.

## 8. Source Ideas

- `docs/ideas/IDEA-cycle-workload-run-gate-mehta-modern-canon.md` — full concept exploration of the Cycle/Workload/Run/Pulse/Gate hierarchy, artifact promotion, gate semantics, and MEH-ta evaluation path.

## 9. Open Questions

1. Should `workload_type` be a free-form string or a constrained enum? Free-form is more extensible; enum is safer.
2. Should the API expose a "workload view" that groups Runs by `workload_type` within a Cycle, or leave that to the console UI?
3. Should artifact promotion require a Gate decision, or should it be independently callable via API?
4. How should Prefect DAGs represent multi-workload Cycles — one flow per workload, or one flow per Cycle with sub-flows?
5. Should `workload_type` values be defined in code, in a config file, or in the cycle request profile?
