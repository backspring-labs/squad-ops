# SIP-0XXX: Cycle Replay Harness — Resuming a Cycle From a Recorded Execution Boundary

**Status:** Proposed
**Authors:** SquadOps Architecture
**Created:** 2026-07-25
**Revision:** 2 (review round 1 incorporated)

## 1. Abstract

A cycle re-derives every phase from scratch, including phases that have been stable for
weeks. pf-37 spent **2h 06m in framing, 30m in dev and 6m in builder before the first QA
task dispatched** — and the QA phase was the only part under study. That entry fee is
paid once per hypothesis.

This SIP defines **replay**: a cycle execution mode that resumes from a recorded
execution boundary of a prior run. Phases before the boundary are not dispatched; their
execution state is restored from that run's durable checkpoint. Everything at and after
the boundary executes normally.

The invariant the design rests on:

> **Replay removes deterministic prefix recomputation. It changes nothing else.**

The mechanism is small because the state representation already exists. `RunCheckpoint`
is a durable snapshot of run execution state at a task boundary (SIP-0079), and
`_restore_checkpoint_state` already rehydrates all of it. Replay is that restore, sourced
from a *different* run. Most of this document is therefore contract, invariant, and
policy rather than mechanism — including the requirement that a replayed run can never be
counted as evidence.

## 2. Problem Statement

Four of the last five measurement rolls failed in the QA/correction phase. Each paid the
same ~3h entry fee to reach it, re-deriving a framing plan that has been clean and
lint-quiet for four consecutive rolls and a dev phase that has run 7/7 clean for four.

The costs compound:

- **Hypothesis latency.** A one-line repair-prompt change takes three hours to test — in
  practice one or two experiments per working session.
- **Coupled variables.** A QA-phase experiment is contaminated by fresh framing and dev
  variance. pf-36 and pf-37 drew opposite `{id}`/`{run_id}` priors from an identical
  contract: noise in a phase nobody was studying.
- **No parallel escape.** The target is single-GPU and bandwidth-bound; concurrent rolls
  are ~sequential in wall clock.

Cheaper cycles are not the answer — smaller models degrade the output-quality signal the
rolls exist to measure, and shorter budgets truncate the correction loop under study.
The waste is specifically *recomputing a known-good prefix*.

## 3. Design

### 3.1 Replay as an execution mode

A run executes in exactly one **execution mode**:

| Mode | Scheduling | State origin | Evidence |
|---|---|---|---|
| `normal` | every task dispatched | produced by this run | eligible |
| `replay` | tasks before the boundary skipped | restored from a source run's checkpoint | **ineligible** (§4) |

Mode is declared at cycle creation and is immutable for the run's lifetime. Modelling
this as a mode rather than a bag of overrides means later capabilities (§6) extend one
concept instead of accumulating flags.

```yaml
execution_mode: replay
replay:
  source_run_id: run_010825617319
  boundary: checkpoint:7          # or the terminal boundary of a named workload
```

### 3.2 The replay boundary

A **replay boundary** is a persisted `RunCheckpoint` of the source run. Checkpoints are
written after every successful task and record exactly the state downstream execution
consumes:

```
run_id · checkpoint_index · completed_task_ids · prior_outputs
       · artifact_refs · plan_delta_refs · created_at
```

Resuming at a boundary is the existing `_restore_checkpoint_state` operation — restore
`prior_outputs`, `completed_task_ids`, `plan_delta_refs`, and the referenced vault
artifacts — with `completed_task_ids` populating `skip_task_ids`, which already
suppresses dispatch. The only novelty is that the checkpoint comes from a different run.

**Granularity is per task, not per workload**, because checkpoints are. No additional
state capture is required to support finer boundaries.

### 3.3 Boundary invariant

> **A boundary is replayable only if every downstream dependency is represented entirely
> by the persisted checkpoint and the artifacts it references.**

This is the load-bearing invariant and it is not automatically true. Verified during
review: downstream prompts consume `prior_outputs`, which is populated as

```python
prior_outputs[role] = {k: v for k, v in (result.outputs or {}).items() if k != "artifacts"}
```

— explicitly *everything except artifacts*. A replay that seeded only stored artifacts
would hand the resumed phase an empty `prior_outputs` and silently violate §3.4.
Checkpoint-sourcing satisfies the invariant today precisely because `RunCheckpoint`
already captures that field.

The invariant's ongoing value is as a **review rule**: any future run-scoped state that
influences downstream execution and is not in the checkpoint is a defect in the
checkpoint, not a special case for replay. New artifact types need no replay support so
long as they are reachable from `artifact_refs`.

### 3.4 Determinism contract

> **For every skipped task, replay SHALL present downstream execution with state
> byte-equivalent to that produced by the source run at the same boundary.**

Byte-equivalence covers restored artifact content, `prior_outputs`, `completed_task_ids`
and `plan_delta_refs`. It is directly testable: replay a source run at its terminal
boundary and assert the resumed run's initial state equals the source run's state at that
index.

### 3.5 Compatibility policy

A prefix is only valid against a compatible present. Rather than one global hash list,
**each boundary declares the compatibility set its replay requires** — the bindings that
actually influence the phases at and after it.

| Boundary class | Compatibility set |
|---|---|
| post-framing | PRD ref, contract ref + hash, manifest ref + hash, build profile, squad profile |
| post-dev | the above, plus the bound scaffold record hash |
| post-builder | the above, plus build profile required-file set |

Artifacts and config that demonstrably cannot affect the resumed phases — logging,
documentation, unrelated metadata — are outside every set by construction, so unrelated
commits do not invalidate a prefix.

A mismatch is a **hard refusal at cycle creation**, not a warning: the failure it prevents
(a dev prefix authored against contract v3 replayed under v4) produces plausible-looking
wrong results. This extends the existing SIP-0095 create-time preflight rather than adding
a rejection path.

### 3.6 Required change: checkpoint retention

`save_checkpoint(..., max_keep=5)` prunes all but the latest five checkpoints per run. A
ten-task run therefore **deletes the post-framing and post-dev boundaries before it
finishes** — exactly the boundaries worth replaying.

Phase 1 must make boundary checkpoints durable. Two candidate mechanisms, either
acceptable:

- retain all checkpoints for runs flagged as replay sources, or
- mark boundary checkpoints exempt from pruning at write time.

Unbounded retention for every run is not proposed; the pruning default exists for a
reason and this SIP does not relitigate it.

## 4. Evidence Policy

This framework's defining defect has been runs reporting success for deliverables that do
not work. Replay manufactures convincing-looking runs cheaply and is therefore a direct
threat to the evidence chain. These are requirements, not guidance.

1. Replay metadata (`source_run_id`, `boundary`, resolved compatibility set) **SHALL** be
   a typed attribute of `CycleOutcome`, not a free-text note.
2. Replay metadata **SHALL** be immutable after run creation.
3. Replayed runs **SHALL NOT** satisfy baseline aggregation (the N=5 green baseline).
4. Replayed runs **SHALL NOT** count toward Functional App Yield.
5. Requirements 3–4 **SHALL** be enforced at the `verification_integrity` aggregation
   seam — refusal in code, not operator discipline.
6. Replay metadata **SHALL** be rendered on every surface that reports the run: CLI
   listings, console, and the run report.

**Acceptance bar:** it must be impossible to accidentally cite a replayed run as evidence
that the system works.

### 4.1 What replay cannot tell you

- **It pins model variance.** A replayed roll answers "does this fix work against *this*
  input," never "does this fix work." Convergence rates, first-pass yield and prior
  distributions require `normal` runs.
- **It cannot validate a skipped phase.** A fix to framing or dev prompts is untestable
  under a boundary that skips them — by construction. #588 is a live example.
- **It is a debugging accelerator, not a measurement instrument.**

## 5. Acceptance Criteria (Phase 1)

Phase 1 is complete when:

1. A cycle can be created in `replay` mode against a source run and boundary.
2. Tasks at or before the boundary perform **no dispatch** — verifiable as zero
   `Dispatched task` records for those task ids.
3. Tasks after the boundary execute normally: real dispatch, typed acceptance, scaffold
   enforcement, correction loop.
4. The resumed run's initial state is byte-equivalent to the source run's state at that
   boundary (§3.4), asserted by test.
5. An incompatible prefix is **rejected at cycle creation** with the failing element
   named (§3.5).
6. A boundary checkpoint survives to the end of its source run (§3.6).
7. Replay metadata is present, typed, and immutable on `CycleOutcome`.
8. A replayed run is **refused** by baseline aggregation and FAY at the
   `verification_integrity` seam, asserted by test.
9. Replay status is visible in CLI, console and run report output.
10. Absent `execution_mode: replay`, behaviour is byte-identical to today.

## 6. Extension Layers

Replay is layered by **what feeds the execution seam**, not by delivery order. Phase 1
establishes the seam; later phases change the source.

| Layer | Substitutes | Source | Status |
|---|---|---|---|
| **Workspace state** | whole tasks | recorded checkpoint | **Phase 1 (this SIP)** |
| **Model output** | LLM responses within an executed task | recorded raw emissions | future |
| **Model output** | LLM responses within an executed task | synthetic (fault injection) | future |

The lower layer is a single seam at `LLMPort`, parameterised by source: *recorded*
enables provider A/B (identical inputs through Ollama and Atlas, as migration conformance
evidence), *synthetic* turns every field defect — truncated fence, `ApiError(status_code=…)`,
unresolvable imports — into a repeatable regression test.

Both require durable raw-emission capture, which this SIP deliberately does not build
(§7). They are named so the Phase 1 seam does not foreclose them; **neither is in scope
for acceptance.**

## 7. Alternatives Considered

**Replay at `LLMPort` for Phase 1.** Rejected. A phase is skipped *because it is not
under test*, so re-running the fenced parser over a recorded completion tests the parser —
the cost the boundary exists to avoid. Raw completions are also not durably persisted
today; that gap belongs to the LLM Emission Contracts SIP, and depending on it would block
this behind an unaccepted proposal. Phase 1 therefore introduces **no new capture path**,
so nothing must be un-built when raw persistence lands.

**Prompt-hash-keyed response cache.** Rejected. Our fixes *are* prompt changes (#584,
#585, #588 were all prompt edits), so a prompt-keyed cache invalidates on exactly the
commits worth iterating on, then silently falls through to live inference.

**Checkpoint resume as-is.** SIP-0079 resume rehydrates a *paused* run in place and cannot
re-run a phase repeatedly against changing code, which is the entire use case. This SIP
adopts its **state representation** while rejecting its resume-in-place semantics — the
reason Phase 1 is small.

**Cheaper cycles (smaller models, shorter budgets).** Degrades the signal the rolls exist
to produce (§2).

## 8. Compatibility & Risks

- **Backward compatible by construction** — absent `execution_mode: replay`, behaviour is
  unchanged (criterion 10).
- **False confidence** — the dominant risk; §4 is the mitigation and is non-optional.
- **Stale prefixes** — §3.5 converts silent wrongness into a loud create-time refusal.
- **Checkpoint growth** — §3.6 changes retention; scoped to replay sources rather than
  globally unbounded.
- **Harness gravity** — tooling attracts polish. Phase 1 is a mode, a refusal rule and a
  retention change; §6 layers require their own justification.
- **Thinning real evidence** — if pinned iteration becomes the default, `normal`-run
  evidence thins. §4.3–4.5 ensure release gates still consume only earned runs.

## 9. Relationship to Existing Work

- **SIP-0079** — owns `RunCheckpoint` and `_restore_checkpoint_state`; this SIP reuses
  both and changes their retention (§3.6).
- **SIP-0095 Cycle Create Preflight** — hosts the §3.5 compatibility gate.
- **SIP-0096 Verification Evidence Integrity** — owns `CycleOutcome` and the aggregation
  choke point enforcing §4.
- **SIP-0099 / SIP-0100** — the bound scaffold record participates in post-dev
  compatibility sets.
- **LLM Emission Contracts (proposed)** — supplies the raw-emission capture the §6 lower
  layer needs. Explicitly *not* a dependency of Phase 1.
- **Ephemeral Application Sandbox (proposed)** — orthogonal; it changes *where*
  verification executes, this changes *how much of the cycle precedes it*.

## 10. Open Questions

1. **Retention mechanism (§3.6)** — flag replay-source runs, or exempt boundary
   checkpoints at write time?
2. **Compatibility set ownership** — should each boundary class declare its set in code,
   or should the set be derived from the resumed workloads' declared inputs?
3. **Cross-project replay** — is a source run from another project ever valid, or should
   replay be project-scoped by rule?

**Explicitly out of scope:** promoting a boundary into a named, curated **fixture** with
its own lifecycle. Replay references a run. Fixtures are a separate proposal if the need
proves real.
