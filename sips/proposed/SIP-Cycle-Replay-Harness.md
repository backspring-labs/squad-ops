# SIP-0XXX: Cycle Replay Harness — Pinned Fast-Forward for Phase-Targeted Iteration

**Status:** Proposed
**Authors:** SquadOps Architecture
**Created:** 2026-07-25
**Revision:** 1

## 1. Abstract

Every investigation into the correction loop currently costs a full cycle. pf-37 —
a representative measurement roll — spent **2h 06m in framing, 30m in dev, and 6m in
builder before the first QA task dispatched**, and the QA phase is the only part
anyone was studying. Three hours of wall clock and roughly 40k generated tokens to
reach minute one of the interesting part, repeated once per hypothesis.

The phases being paid for are the phases that no longer fail. Framing has produced a
clean, lint-quiet plan on four consecutive rolls; the dev phase has run 7/7 clean on
four consecutive rolls. They are re-derived from scratch every time anyway.

This SIP introduces a **replay pin point**: a cycle may be configured to start with a
prior run's stored artifacts already in place, skipping every workload up to a chosen
boundary and executing everything after it for real. Iteration on the correction loop
drops from ~3 hours to minutes.

The mechanism is deliberately small. Seeding artifacts into a run from the vault
already exists and is load-bearing (`execution_overrides.plan_artifact_refs` +
`_seed_prior_artifacts` / `_seed_skeleton_artifacts` — the same seam that seeds the
interface manifest on every measurement roll, and that seeded an entire walking
skeleton during the Phase-0.5 spike with zero new framework code). This SIP
generalises that seam to a declared pin point and adds the one thing that must not be
optional: **a replayed run is structurally barred from counting as evidence.**

## 2. Problem Statement

### 2.1 The iteration tax, measured

pf-37 (`run_010825617319`, 2026-07-25), phase boundaries from the executor log:

| Phase | Wall clock | Outcome |
|---|---|---|
| Framing | 2h 06m | clean plan, gate approved |
| Dev (7 tasks) | 30m | 7/7 pass, 0 corrections |
| Builder | 6m | clean assembly |
| **QA + correction** | **the subject of study** | 2 corrections, both false-accepted |

Four of the last five rolls died in the QA/correction phase. Every one of them paid
the same ~3h entry fee to get there, and the entry fee is spent re-deriving outputs
that have been stable for a week.

### 2.2 What the tax actually costs

- **Hypothesis latency.** A one-line change to a repair prompt takes three hours to
  test. In practice this means one or two experiments per working session.
- **Coupled variables.** Because every roll re-generates everything, a QA-phase
  experiment is contaminated by fresh framing and dev variance. pf-36 and pf-37 drew
  opposite `{id}`/`{run_id}` priors from an identical contract — noise in the phase
  nobody was studying.
- **Serialised debugging.** The Spark is single-GPU and bandwidth-bound; parallel
  rolls are ~sequential in wall clock. The iteration loop cannot be widened by
  running more cycles at once.

### 2.3 Why not just make cycles faster

Smaller models degrade exactly the output-quality signal the rolls exist to measure
(and are already understood as a poor substitute for full-squad measurement). Shorter
budgets truncate the correction loop under study. Neither addresses the actual waste,
which is *re-computing a known-good prefix*.

## 3. Design

### 3.1 The pin point

A cycle request may declare a **replay pin**: the workload boundary at which real
execution begins.

```yaml
execution_overrides:
  replay:
    source_run_id: run_010825617319     # the run whose artifacts are replayed
    resume_at: qa                        # first workload executed for real
```

Everything before `resume_at` is **not dispatched**. Its stored artifacts are loaded
from the vault into the run's workspace exactly as `_seed_prior_artifacts` already
does, so the resumed phase begins against a workspace byte-identical to the source
run's state at that boundary.

Everything at and after `resume_at` executes normally: real dispatch, real generation,
real typed acceptance, real scaffold enforcement, real correction loop.

### 3.2 Why artifact-level, not LLM-level

The intuitive design intercepts the LLM port and replays recorded completions. This
SIP deliberately does not, for v1:

- **You skip a phase because you are not testing it.** Re-running the fenced parser
  over a recorded completion tests the parser — the thing the pin point exists to stop
  paying for.
- **Raw completions are not durably persisted today.** That gap is real and is
  addressed by the LLM Emission Contracts SIP (its P0 evidence rule). Depending on it
  would block this work behind an unaccepted SIP.
- **Artifacts already are persisted**, completely, for every historical run. The
  corpus for replay exists today for pf-27 … pf-38 with no new capture path.

Building no recorder is the point: **v1 introduces zero new capture mechanisms**, so
there is nothing to reconcile when raw persistence lands. Higher-fidelity modes are
purely additive (§5).

### 3.3 Prefix compatibility — the correctness gate

A replayed prefix is only valid against a compatible present. The harness refuses to
replay when the source run's bindings differ from the requested cycle's:

| Pinned | Compared on |
|---|---|
| Verification contract | `contract_ref` + content hash |
| Interface manifest | `plan_artifact_refs` + `interface_manifest_hash` |
| PRD | `prd_ref` |
| Build profile / stack | `resolved_config.build_profile` |
| Squad profile | `squad_profile_id` |

A mismatch is a **hard refusal at create time**, not a warning — the failure mode it
prevents (a dev prefix written against contract v3 replayed under v4) produces
confusing, wrong results that look plausible. This reuses the existing create-time
preflight seam (SIP-0095) rather than adding a new rejection path.

### 3.4 Evidence integrity — non-negotiable

This framework's central defect has been runs that report success for deliverables
that do not work. A replay harness manufactures convincing-looking runs cheaply and is
therefore a direct threat to the evidence chain. Three structural requirements:

1. **The outcome carries the pin.** `CycleOutcome` records `replay: {source_run_id,
   resume_at}`, or its absence. Not a note field — a typed attribute.
2. **Replayed runs cannot be measurements.** The N=5 green baseline and Functional App
   Yield must *refuse* a run with a replay pin, at the aggregation seam
   (`verification_integrity`), not by operator discipline. A replayed run is never
   "green"; it produces a verdict about a *phase*, never about a cycle.
3. **Visible everywhere the run is.** CLI listings, console, and the run report render
   the pin. An operator must never have to check config to know whether a result was
   earned.

The bar: it should be impossible to accidentally cite a replayed run as evidence that
the system works.

### 3.5 What replay does not give you

Stated plainly so the harness is not misused:

- **It pins LLM variance.** A replayed roll answers "does this fix work against *this*
  input," never "does this fix work." Convergence rates, first-pass yield, and prior
  distributions require real rolls.
- **It cannot validate the skipped phases.** A fix to framing or dev prompts (e.g.
  #588) is untestable under a pin that skips them — by construction.
- **It is a debugging accelerator, not a measurement instrument.** Every claim about
  system capability still comes from unpinned rolls.

## 4. Phasing

**Phase 1 — replay pin (this SIP's v1).** Pin point in `execution_overrides`, prefix
seeding via the existing seam, compatibility gate at create time, outcome marking, and
aggregation refusal. No new capture path, no LLM-port changes.

**Phase 2 — fault injection.** Synthetic responses reproducing known failure shapes
(truncated fence, `ApiError(status_code=…)`, unresolvable imports) so every defect
found in the field becomes a repeatable regression test. Strictly better than today's
reliance on small models to produce faults organically. **Depends on** a raw-emission
format (LLM Emission Contracts).

**Phase 3 — LLM-level replay.** Intercept at `LLMPort` to exercise parsing and
extraction against recorded raw output; enables provider A/B (identical inputs through
Ollama and Atlas) as migration conformance evidence. **Depends on** the same format.

Phases 2 and 3 are named here so the v1 seam does not foreclose them; neither is in
scope for acceptance of this SIP.

## 5. Alternatives Considered

**Prompt-hash-keyed response cache.** Rejected. Our fixes *are* prompt changes (#584,
#585, #588 were all prompt edits), so a prompt-keyed cache invalidates on exactly the
commits worth iterating on, silently falling through to live inference and quietly
restoring the 3h loop.

**Checkpoint/resume of a real run.** `run_checkpoints` already exists and resumes a
*paused* run in place. It cannot serve here: it resumes the same run rather than
starting a fresh one against a recorded prefix, so it cannot re-run a phase repeatedly
against varying code, which is the entire use case.

**Just cache the framing artifacts manually.** Already possible via
`plan_artifact_refs`, and effectively what the measurement launcher does for the
manifest. Rejected as the whole answer because it has no compatibility gate and no
outcome marking — i.e. it is this design minus the two parts that keep it honest.

**Make cycles cheaper instead (smaller models, shorter budgets).** Degrades the signal
the rolls exist to produce. Addressed in §2.3.

## 6. Compatibility & Risks

- **Backward compatible by construction.** Absent `execution_overrides.replay`,
  behaviour is byte-identical to today — the same data-driven pattern the manifest
  seeding uses.
- **Risk: false confidence.** The dominant risk; §3.4 is the mitigation and is
  non-optional.
- **Risk: stale prefixes.** A pinned prefix ages as contracts evolve. §3.3's hard
  refusal converts silent wrongness into a loud failure.
- **Risk: harness gravity.** Tooling attracts polish. v1 is scoped to a pin point and
  a refusal rule; Phases 2–3 require their own justification.
- **Risk: over-reliance.** If pinned iteration becomes the default, real-roll evidence
  thins. Mitigation is cultural, but §3.4's aggregation refusal ensures the release
  gates still consume only earned runs.

## 7. Relationship to Existing Work

- **LLM Emission Contracts (proposed).** Supplies the raw-emission persistence Phases
  2–3 need. Explicitly *not* a dependency of Phase 1 — see §3.2.
- **SIP-0095 Cycle Create Preflight.** §3.3's compatibility gate belongs in that
  existing seam, not a new one.
- **SIP-0096 Verification Evidence Integrity.** Owns `CycleOutcome` and the
  aggregation choke point where §3.4's refusal is enforced.
- **SIP-0099 / SIP-0100 (scaffolding, frozen enforcement).** The artifacts a pin seeds
  include the bound skeleton; the bound-record hash participates in §3.3.
- **Ephemeral Application Sandbox (proposed).** Orthogonal. The sandbox changes *where*
  verification executes; this changes *how much of the cycle precedes it*. A pinned
  cycle reaching sandbox verification in minutes compounds both.

## 8. Open Questions

1. **Pin granularity.** Workload boundaries (`framing` / `implementation` / `qa`) are
   the obvious unit. Is a mid-workload pin (e.g. "after dev, before builder") worth the
   extra surface, or does workload granularity cover the real cases?
2. **Prefix provenance.** Should a pin reference a *run* (today's proposal) or a
   curated, named **fixture** promoted from a run? The latter is more stable and more
   citable; the former needs no new artifact lifecycle.
3. **Recording retention.** Replay depends on vault artifacts persisting; no retention
   policy exists today. Worth stating before pins are built on top of it.
4. **Does the compatibility gate belong at create time or run start?** Create-time
   fails fastest; run-start sees the fully resolved config.
