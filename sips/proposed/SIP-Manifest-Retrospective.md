# SIP-0XXX: Manifest Retrospective — Evidence-Driven Task-Type Taxonomy Evolution

**Status:** Proposed
**Authors:** SquadOps Architecture
**Created:** 2026-04-18
**Revision:** 1

## 1. Abstract

SquadOps' build-manifest task_type taxonomy is small by design (`development.develop`, `qa.test`, `builder.assemble`) and its role taxonomy is bounded by the active squad profile. Planning runs routinely expose *felt needs* for finer distinctions — Max has been observed inventing `quality_assurance.validate`, `backend_dev`, `frontend_dev`, and `integration_dev` when decomposing real builds. Today those inventions are rejected at parse/validation time and the signal is discarded to a WARN log. This SIP captures manifests, invention attempts, and downstream outcomes in a structured retrospective table so the taxonomy can evolve by evidence (cluster + miss-rate + retry-rate) instead of opinion. The SIP proposes observation only; taxonomy changes still go through human review and a separate SIP per new type.

## 2. Problem Statement

We just validated (SIP-0086 cycles on 2026-04-18) that Max, even on a 32b model, reaches for task_type and role names that don't exist. When we constrain him upfront, the cycle succeeds. When we don't, the cycle fails. That tells us two things:

1. Constraining the vocabulary is correct.
2. The inventions themselves are real signal about where the vocabulary is too coarse.

Concrete gaps today:

- **Invention attempts are discarded.** The retry path in `_produce_manifest` emits a WARN listing the invented task_type/role, then the record is gone. It never lands in a queryable surface.
- **No link from manifest task to downstream outcome.** We know a manifest had 12 tasks, but we can't ask "which `focus` clusters produced the most plan_delta corrections?" or "which role/task_type combos hit the most acceptance-criteria misses?"
- **No decision rule for taxonomy expansion.** Adding a new task_type is currently an ad-hoc judgment. Without data, it's hard to tell whether `qa.validate` vs `qa.test` is a real distinction or a model quirk to correct against.
- **Correction protocol state is orphan to manifests.** Plan deltas carry `trigger: task_failure:X.Y` but not the originating manifest_task_index, so retrospectively slicing by "which manifest tasks keep needing correction" requires log archaeology.

Without closing these gaps, taxonomy drift happens — by opinion, by PR-of-the-week, or by expedience — instead of by observation.

## 3. Goals

1. Record every manifest task produced (accepted or fallback) with enough context for retrospective analysis: `cycle_id`, `run_id`, `task_index`, `task_type`, `role`, `focus`, `description`, `expected_artifacts`, `acceptance_criteria`.
2. Record every invention attempt rejected by the retry loop: invented `task_type` / `role`, the `focus` it was used for, the corrective feedback that superseded it.
3. Link each manifest task to its materialized impl task_id(s) so downstream outcomes (corrections, AC evaluations, repairs) can be attributed upstream.
4. Provide a queryable surface (CLI command + Console view) that surfaces focus clusters, invented-type frequency, correction rates per cluster, AC miss rates per cluster.
5. Document a normative decision rule for adding a new task_type / role so expansion is evidence-gated.
6. Zero impact on the hot path. Telemetry writes are best-effort and non-authoritative; retrospective data is lost, not cycle execution, if persistence fails.

## 4. Non-Goals

- **Not** automatic taxonomy mutation. Adding a task_type or role still requires a human-reviewed SIP. This SIP observes; it does not act.
- **Not** a scoring system for agents or models. Retrospective data is about *taxonomy fitness*, not agent performance reviews.
- **Not** a replacement for LangFuse traces. LangFuse captures LLM-call-level detail per generation. This captures manifest-structural outcomes per cycle. They complement rather than overlap.
- **Not** a full analytics platform. Queries are bounded (top-K clusters, aggregates over N cycles) and land in postgres + CLI, not a warehouse.
- **Not** a correction-protocol replacement. Corrections still fire live; this records their occurrence against the originating manifest for later review.
- **Not** changing the manifest schema or the existing `BuildTaskManifest` model.

## 5. Approach Sketch

### 5.1 Data model

Two new postgres tables:

```sql
CREATE TABLE manifest_retrospective (
    cycle_id            text NOT NULL,
    run_id              text NOT NULL,
    manifest_task_index int  NOT NULL,
    task_type           text NOT NULL,
    role                text NOT NULL,
    focus               text NOT NULL,
    description         text NOT NULL,
    expected_artifacts  jsonb NOT NULL DEFAULT '[]',
    acceptance_criteria jsonb NOT NULL DEFAULT '[]',
    depends_on          int[] NOT NULL DEFAULT '{}',
    produced_at         timestamptz NOT NULL DEFAULT now(),
    produced_by_role    text NOT NULL,
    attempt_number      int  NOT NULL,                  -- 1 or 2 under current retry policy
    impl_task_ids       text[] NOT NULL DEFAULT '{}',   -- filled by executor at dispatch
    correction_count    int  NOT NULL DEFAULT 0,        -- incremented by correction protocol
    ac_miss_count       int  NOT NULL DEFAULT 0,        -- incremented by pulse verification
    repair_count        int  NOT NULL DEFAULT 0,        -- incremented by repair handler
    final_status        text,                           -- completed | failed | skipped
    PRIMARY KEY (run_id, manifest_task_index)
);

CREATE TABLE manifest_invention_log (
    id                  bigserial PRIMARY KEY,
    cycle_id            text NOT NULL,
    run_id              text NOT NULL,
    attempt             int  NOT NULL,
    invented_field      text NOT NULL,   -- 'task_type' | 'role'
    invented_value      text NOT NULL,
    in_focus            text,            -- the focus string the invention was used for
    corrected_to_allowed text[] NOT NULL DEFAULT '{}',  -- what the retry feedback offered
    created_at          timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX ON manifest_retrospective (cycle_id);
CREATE INDEX ON manifest_retrospective (task_type, role);
CREATE INDEX ON manifest_invention_log (invented_field, invented_value);
```

### 5.2 Capture points

- **`_produce_manifest`** — on success, write one `manifest_retrospective` row per `ManifestTask` with `attempt_number` from the retry loop. On rejected attempt with invented values, write one `manifest_invention_log` row per invented field instance with the focus context.
- **Executor `_dispatch_task`** — when dispatching an impl task materialized from a manifest task, append the impl `task_id` to the retrospective row's `impl_task_ids` array.
- **Correction protocol** — when a plan_delta fires with `trigger: task_failure:X.Y` on a manifest-materialized task, increment `correction_count` on the originating retrospective row.
- **Pulse verification / AC evaluation** — when acceptance criteria fail for a manifest-materialized task, increment `ac_miss_count`.
- **Repair handler** — when a repair task fires for a manifest-materialized task, increment `repair_count`.
- **Run finalization** — when the impl run terminates, write `final_status` for each manifest task based on its materialized impl tasks' outcomes.

All writes are fire-and-forget at INFO level and degrade gracefully if the DB is unreachable (same policy as existing pulse verification writes).

### 5.3 Query surface

New CLI command `squadops retrospective` under a fresh top-level group or under `cycles`:

```bash
# Invented vocabulary frequency across last N days
squadops retrospective inventions --project P --since 30d
# output: top invented task_types / roles, count, representative focus strings

# Focus clusters with highest correction rates
squadops retrospective clusters --project P --metric correction_rate --top 10

# Focus clusters with highest AC miss rates
squadops retrospective clusters --project P --metric ac_miss_rate --top 10

# Per-cycle detail view
squadops retrospective cycle CYCLE_ID
```

Clustering starts simple: token-based n-gram similarity on the `focus` string, min-cluster-size 3. Not ML — just enough to group "Backend API endpoints" with "Implement backend API routes." Can evolve.

Continuum Console gets a read-only page mirroring the CLI at `/retrospective`.

### 5.4 Decision rule (normative)

Adding a new `task_type` or promoting an invented role to first-class requires meeting at least one of these thresholds from retrospective data:

**Invention-frequency evidence:**
- N ≥ 5 invention attempts of the same value
- Across K ≥ 3 distinct cycles
- In at least 2 different `project_id`s (to rule out project-specific idiosyncrasy)

**Outcome-quality evidence:**
- A focus cluster with `ac_miss_rate > 50%` or `correction_rate > 2× baseline`
- Across ≥ 10 cycles
- Where a proposed specialized `task_type` with a distinct handler / prompt fragment would plausibly address the root cause

**Plus, for every expansion:**
- A SIP per proposed type describing:
  - The new handler (prompt fragment + routing logic)
  - The target agent role
  - The bounding case this type handles that existing types do not
  - Expected effect on observed metrics (with post-ship verification)
- Test coverage plan
- Deprecation / migration story for any retired types

This rule lives in `CONTRIBUTING.md` and is enforced by design review, not code.

### 5.5 Review cadence

- **Per-initiative** — when starting a new domain of builds (new project type, new squad profile, new request profile), run a retrospective across the last N cycles in that domain first.
- **Quarterly** — global review of invention log and cluster metrics. Output: zero or more SIPs proposing taxonomy changes.
- **Ad hoc** — whenever a build run shows repeated failures in similar focus clusters.

No automated trigger. Review is an explicit human act informed by the data.

## 6. Key Design Decisions

1. **Observe, don't act.** The retrospective surface is purely informational. The decision to expand the taxonomy is a human judgment gate, not an automated reaction. This keeps the system deterministic and the taxonomy curated.

2. **Invention attempts are first-class signal.** When Max tries to invent `quality_assurance.validate`, that's him telling us something about his mental model of QA work. Logging it with the focus context preserves the signal for review. Silent rejection loses information.

3. **Postgres, not LangFuse.** LangFuse tracks LLM-call-level data: prompts, completions, tokens. Retrospective tracks structural-decomposition-level data: which focus clusters worked, which didn't. Different granularity, different query patterns, different retention needs. Postgres keeps it queryable from the CLI without a second infra hop.

4. **Link backward from outcome to manifest task.** A correction or AC miss that can't be attributed to a manifest task is lost signal. The impl_task_ids linkage is the load-bearing join. Executor writes it at dispatch; everything else aggregates against it.

5. **Best-effort writes, same policy as pulse verification.** Retrospective data is valuable but not authoritative. A DB outage during a cycle drops some retrospective rows; the cycle itself proceeds unaffected. No exception from retrospective writes enters the task path.

6. **Clustering is not ML.** Start with simple token-overlap / n-gram similarity. The cluster quality just has to be "good enough for a human reviewer to skim." Over-engineering here delays shipping.

7. **Decision rule is in docs, not code.** Enforcing "5 inventions across 3 cycles across 2 projects" in code would be rigid. The rule lives in `CONTRIBUTING.md` and the SIP review process applies it with judgment.

8. **Retention is bounded.** Default 90-day rolling window on retrospective tables. Long-term trend analysis is a follow-up SIP if the need arises.

## 7. Acceptance Criteria

1. Every accepted manifest task writes one row to `manifest_retrospective` with all required fields populated.
2. Every retry attempt that rejects an invention writes one row to `manifest_invention_log` per invented field, with the focus context.
3. After impl dispatch, the retrospective row's `impl_task_ids` contains the task_id(s) materialized from that manifest task.
4. A plan_delta firing on a manifest-materialized impl task increments `correction_count` on the originating retrospective row.
5. An AC miss (pulse verification failure) on a manifest-materialized impl task increments `ac_miss_count`.
6. Run finalization writes `final_status` for every retrospective row of that run.
7. `squadops retrospective inventions --project P --since 30d` returns top-K invented values with frequency and representative focus strings, ordered by count desc.
8. `squadops retrospective clusters --project P --metric correction_rate --top 10` returns the top-10 focus clusters by correction rate, with cluster size ≥ 3.
9. Retrospective DB writes that fail (timeout, connection loss) log one WARN and do not propagate into the calling cycle execution path.
10. `CONTRIBUTING.md` contains the decision rule (5.4) verbatim and references this SIP.
11. Retention job prunes retrospective rows older than 90 days (configurable via `SQUADOPS__RETROSPECTIVE__RETENTION_DAYS`).
12. New tests cover: manifest-accept write, invention write, impl-dispatch linkage, correction-count increment, AC-miss increment, graceful DB-failure degradation, cluster query correctness (synthetic fixtures).

## 8. Source Ideas

- SIP-0086 validation 2026-04-18 — observed Max inventing `quality_assurance.validate`, `backend_dev`, `frontend_dev`, `integration_dev` across three planning attempts. Rejected with WARN, signal discarded.
- Live design conversation 2026-04-18 — operator asked "how should we expand task_types? Can we harvest learnings?" Led to this retrospective design.
- Existing pulse verification writes in `pulse_verification_records` table — provides the precedent for best-effort structured telemetry.
- LangFuse adapter — provides the precedent for graceful-degradation telemetry under failure.

## 9. Open Questions

1. Should invention logs be per-field (one row per invented `task_type`, one per invented `role`) or per-attempt (one row with both fields)? Per-field makes frequency queries cleaner; per-attempt preserves co-occurrence.
2. How do we attribute an AC miss back to a specific manifest task when acceptance criteria span multiple tasks? First-match? Weighted?
3. Should the retrospective surface also record *which* profile_roles / task_types were *offered* at the time of planning? (Today the allowed set could drift across cycles as the profile changes.)
4. Is 90-day retention right, or should we keep inventions indefinitely (they're small) and only prune the larger retrospective rows?
5. Should the CLI command be `squadops retrospective ...` or live under `squadops cycles retrospective ...`?
6. Clustering: ship with simple n-gram now, or invest in sentence-embedding clustering (via the LLM adapter we already have)? N-gram is probably enough for the first year.
7. Should invented values from *one* cycle be visible to subsequent planning runs in the same project (as "other planners considered these; here's why they were rejected")? Risk: anchoring the model. Benefit: fewer repeat inventions.
