# SIP-0101 Implementation Plan — Cycle Replay Harness (Phase 1)

**SIP:** `sips/accepted/SIP-0101-Cycle-Replay-Harness.md` (accepted 2026-07-25)
**Reuses:** SIP-0079 (`RunCheckpoint`, `_restore_checkpoint_state`), SIP-0095 (create preflight),
SIP-0096 (`CycleOutcome`).
**Motivating case:** pf-37 (`run_010825617319`) spent 2h 06m in framing, 30m in dev and 6m in builder
before the first QA task dispatched — and the QA phase was the only part under study. Four of the last
five measurement rolls failed in QA/correction, each paying the same ~3h entry fee to reach it.

## Intent

Make the known-good prefix of a cycle **replayable** so iteration targets the phase actually under
study. Phase 1 delivers: an execution mode, checkpoint-sourced prefix restore, durable boundaries, a
create-time compatibility gate, and — non-negotiably — evidence rails that make a replayed run
impossible to mistake for earned evidence.

## Status snapshot (already true on `main`)

| Item | State | Where |
|------|-------|-------|
| Boundary state representation | **DONE** — `RunCheckpoint` carries `completed_task_ids`, `prior_outputs`, `artifact_refs`, `plan_delta_refs` | `cycles/checkpoint.py:16` |
| Prefix rehydration | **DONE** — restores all four fields + vault artifacts | `dispatched_flow_executor.py:_restore_checkpoint_state` |
| Dispatch suppression | **DONE** — `completed_task_ids` → `skip_task_ids` → `_check_task_preconditions` returns skip | `dispatched_flow_executor.py:1147` |
| Checkpoint read API | **DONE** — `get_latest_checkpoint` / `list_checkpoints` | `ports/cycles/cycle_registry.py:177,181` |
| Outcome surface | **DONE** — `CycleOutcome` derived in `verification_integrity`, surfaced on cycle detail GET | `verification_integrity.py:264`, `api/routes/cycles/mapping.py:144` |
| Everything below | **NOT built** — this plan | — |

The mechanism is small because the state representation already exists. The bulk of Phase 1 is rails,
retention and gating — which is a fair reflection of where the risk is.

## Sequencing rule

> **The evidence rails must not lag the mechanism.**

If replay ships before marking, there exists a window in which an unlabelled replayed run can be
produced — precisely what SIP-0101 §4 forbids. So the rails are built first, against a mechanism that
does not yet exist.

---

## Slice 1 — Evidence rails (no behaviour change)

**Nothing sets the attribute yet.** This slice is inert by design and independently mergeable.

| Task | Change | Where |
|---|---|---|
| 1.1 | `ReplayProvenance` frozen dataclass: `source_run_id`, `boundary_index`, `compatibility_set` | `cycles/replay.py` (new, pure) |
| 1.2 | `CycleOutcome.replay: ReplayProvenance \| None` | `verification_integrity.py:264` |
| 1.3 | DTO field + mapping | `api/routes/cycles/dtos.py`, `mapping.py:144` |
| 1.4 | Render in run report | `cycles/run_report_builder.py` |
| 1.5 | Render in `cycles show` / `runs list` | `cli/commands/` |

**Tests:** outcome carries provenance when present and `None` when absent; DTO round-trip; report and
CLI both render a replay marker; a `normal` outcome renders no marker (guards accidental always-on).

**Done when:** an outcome constructed with provenance is visibly marked on every surface, and behaviour
for `normal` runs is byte-identical.

---

## Slice 2 — Boundary retention

`save_checkpoint(..., max_keep=5)` prunes all but the latest five checkpoints per run. A twelve-task
run therefore **deletes its post-framing and post-dev boundaries before it finishes** — exactly the
boundaries worth replaying.

| Task | Change | Where |
|---|---|---|
| 2.1 | `save_checkpoint(..., retain: bool = False)` on the port | `ports/cycles/cycle_registry.py:173` |
| 2.2 | Postgres: `retained` column (migration), excluded from the prune `DELETE` | `postgres_cycle_registry.py:428`, `infra/migrations/` |
| 2.3 | Memory adapter parity | `memory_cycle_registry.py:286` |
| 2.4 | Mark workload-terminal checkpoints `retain=True` at the two write sites | `dispatched_flow_executor.py:2253`, `correction_runner.py:348` |

**Tests:** a retained checkpoint survives `max_keep` overflow; unretained pruning is unchanged; memory
and postgres adapters agree.

**Done when:** a run with more than five tasks still has its workload-boundary checkpoints at
completion.

> ⚠️ **Time-critical, see "Tonight" below.** Until this ships, every running cycle is destroying the
> boundaries a replay would want.

---

## Slice 3 — The mechanism

| Task | Change | Where |
|---|---|---|
| 3.1 | `execution_mode` + `replay` block on the create request; validated, persisted, immutable | `api/routes/cycles/`, `cycle_registry` |
| 3.2 | Resolve the source checkpoint (`list_checkpoints(source_run_id)` → boundary index) | `dispatched_flow_executor.py` ~:246 |
| 3.3 | Feed it to the existing `_restore_checkpoint_state` instead of the self-resume checkpoint | same |
| 3.4 | Populate `CycleOutcome.replay` from the resolved pin | `run_completion` → `verification_integrity` |
| 3.5 | **Interim compatibility gate:** refuse unless source and target share identical `contract_ref`, `plan_artifact_refs`, `prd_ref`, `build_profile` | create path |

**Tests:**
- **Determinism (SIP §3.4):** replay a source run at boundary *k*; assert restored `prior_outputs`,
  `completed_task_ids`, `plan_delta_refs` and artifact contents are byte-equal to the source's state
  at *k*.
- **No dispatch:** zero `Dispatched task` records for task ids at or before the boundary.
- **Normal execution after:** the first post-boundary task dispatches and evaluates for real.
- **Interim gate:** mismatched `contract_ref` refused at create with the failing element named.
- **Regression:** absent `execution_mode: replay`, behaviour byte-identical.

**Done when:** a cycle resumes pf-38's prefix at post-builder and reaches the QA phase in minutes.

**Why the interim gate rather than waiting for §3.5's policy:** strict equality is a few lines and is
*more* conservative than the eventual per-boundary sets, so Slice 4 relaxes an existing guard rather
than adding a missing one. At no point does a usable-but-ungated replay exist.

---

## Slice 4 — Compatibility policy (post-tonight)

Replace strict equality with SIP §3.5's per-boundary compatibility sets, hosted in the SIP-0095
preflight so unrelated commits (logging, docs, metadata) stop invalidating a prefix.

## Slice 5 — Console visibility (post-tonight)

Replay marker in the console run views. Separate service, separate language — deliberately last.

---

## Tonight

**Goal:** replay usable for the night's correction-loop work.

**Minimum path: Slices 1 → 2 → 3.** Slice 4's absence is covered by 3.5's strict-equality gate; Slice
5's absence is covered by CLI + report rendering from Slice 1.

**Decision needed now — pf-38 as a replay source.** pf-38's implementation run is executing under
today's `max_keep=5`. Its post-dev boundary will be pruned before the run ends; its post-builder
boundary may or may not survive depending on final task count. Options:

1. **Accept it** — the first replay source is a *future* run started after Slice 2 deploys. Costs one
   extra roll before replay is useful.
2. **Land Slice 2 first and deploy mid-flight** — a runtime-api restart during pf-38 kills the run
   (and #586 now stops it cleanly rather than zombie-ing). Costs pf-38.
3. **Reconstruct a boundary by hand** — pf-38's artifacts are all in the vault; a checkpoint row could
   be synthesised from them. Cheap, but hand-built state is exactly what the determinism contract
   exists to prevent. **Not recommended.**

**Recommendation: (1).** pf-38 is measuring three freshly-deployed fixes on a clean unified deploy —
the first such roll — and its result is worth more than one night's iteration speed. Slices 1–3 land
while it runs; the next roll after it becomes the first replay source, with boundaries retained.

## Risks

| Risk | Mitigation |
|---|---|
| Rails ship but mechanism slips → no harm | inert by design |
| Mechanism ships without rails | prevented by sequencing rule; do not reorder |
| Replayed run cited as evidence | Slice 1 rendering + the binding obligation on any future aggregator (SIP §4.1) |
| Migration in Slice 2 | additive column, backward compatible; range 1000–1099 per lane convention |
| Determinism regressions later | the byte-equivalence test in 3.3 is the standing guard |

## Out of scope (explicit)

Named/curated fixtures with their own lifecycle; LLM-level replay; fault injection. The latter two
depend on durable raw-emission capture and belong with the LLM Emission Contracts proposal
(SIP-0101 §6).
