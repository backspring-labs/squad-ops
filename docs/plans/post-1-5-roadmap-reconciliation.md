# Post-1.5 Roadmap Reconciliation — 1.7's identity, 1.8's co-headliners, and the memory rails

**Established:** 2026-08-07 (owner-ratified in session, immediately after the v1.5.0 cut)
· **Amends:** the progression table in `docs/plans/post-1-4-roadmap-reconciliation.md`
— **rows 1.7 and 1.8 only.** The 1.6 and 2.0 rows stand unchanged, as does the trust
ladder that produced them.

## Why this record exists

Three things changed at the v1.5.0 cut (tagged 2026-08-06) that the post-1.4
reconciliation could not have anticipated:

1. **1.8's stated gate cleared.** That record gated 1.8 on "SIP-0096 implemented (its
   `CycleOutcome` fields designed for these readers)." SIP-0096 was promoted **and**
   implemented in 1.5. The scorecard's own SIP header states the same dependency in
   stronger terms — scoring un-integrity-checked evidence "would institutionalize
   exactly the wrong lessons" — so its blocking condition is now satisfied rather than
   pending.
2. **1.7 acquired a real pool.** It was previously "debt from 1.6," a placeholder. The
   1.5 plan's capacity roll (cut gate item 2) moved a *named, classified* set into it,
   and the post-cut issue sweep confirmed every item still live. A release with a
   populated pool and no identity invites the pool to be treated as a junk drawer.
3. **1.5 built two of the seams Cross-Cycle Memory needs**, for unrelated reasons. That
   changes the memory question from "build it in 1.8 or not" to "which half, and do the
   rails now" — a materially different decision.

## 1.7 — identity: **every port is actually a port**

The odd-minor convention says substance gates the cut and each release carries one
coherent claim. 1.5's claim was *finish the promises, extract the proven*. 1.7's is one
layer outward: **the framework's boundaries stop leaking.** Hexagonal architecture
becomes enforced rather than aspirational.

This is load-bearing, not cosmetic. Two consumers depend on it:

- **The Atlas migration cannot happen safely while a vendor's status vocabulary lives in
  domain objects and the composition root bypasses the factories.** Swapping the
  provider under those conditions is a rewrite, not a swap.
- **1.8's scorecard reads across seams.** Grading is only as stable as the boundaries
  the grades are computed over; a taxonomy built on leaking vocabularies inherits the
  leak.

### The pool (classified in the 1.5 plan, re-verified at the post-cut sweep)

| Class | Items | Note |
|---|---|---|
| Boundary / vocabulary leaks | #377 (Prefect `State` in domain objects) · #381 (its twin: `TaskResult.status` untyped UPPERCASE shadowing `TaskStatus`) · #305 Part B (drop the column; Part A shipped) · #559 (5 remaining `task_type ==` sites after #663) | boundary contract tests; replay where handler-visible |
| Composition root | #301 (main.py bypasses the llm/queue factories) · #154 (adapter imports in domain modules) · #286 (config validated at import time) | **design gate before code** — these alter runtime initialization and are not "as ready" as their size suggests |
| Provider neutrality (Atlas groundwork) | #313 + the LLM-port characterization suite · #707 (allowlist inventory + precedence ruling) · #410 observability half | the suite *characterizes* the current contract; it becomes a conformance suite only when a second provider connects |
| Wide infrastructure mechanics | #576 (~40 per-route error-envelope blocks → registered handlers) · #577 (shared asyncpg pool + JSONB codec) | **must not overlap each other** in a window |
| Pure extractions | #567 · #574 · #575 · #579 (premise needs re-verification first — "five byte-identical copies" no longer matches the tree) | golden-output / byte equivalence |

Plus the API-convention pair (#218/#219), the packaging-fidelity cluster (#198 + #582 +
#637), whatever 1.6 defers, and the standing ops-rider quota.

Item-level homing is **not** executed by this record — see "Not moved by this record."

## 1.8 — co-headliners, ordered within the release

**Decision: the Cycle Evaluation Scorecard and Campaign Orchestration co-headline 1.8**
(the dual-lane precedent set by 1.4). The post-1.4 record billed Campaign as the sole
Lane M headline with the scorecard riding; that billing is amended. The composition of
the release does not change — the *ordering inside it* does.

**Grade definitions land before continuation policy.**

Rationale:

1. **Campaign multiplies whatever the cycle already does.** Automating relaunch without
   grading burns budget faster in whatever direction the machinery already points,
   including its failure modes. The whole 1.4/1.5 arc's lesson is that `completed` is
   not `good`.
2. **The scorecard is the only roadmap item that makes the thesis falsifiable.** The
   project can currently state a functional yield (FAY 6/6). It cannot state that a
   squad beats a single model at the same scaffolding and cost. The squad-vs-single-model
   comparison harness is in the scorecard slice.
3. **2.0 compounds on grades, not on campaigns.** The roadmap's own rule — "Self-
   improvement acts on `CycleAssessment` grades, never raw checks" — puts
   Capability-Backed Agents, Campaign capability-augmentation, and the Test Bay all
   behind the scorecard. Campaign sits behind nothing structural.
4. **Campaign's continuation policy is itself a grading consumer.** Without
   `CycleAssessment`, a continuation policy must invent a stopping rule out of raw
   checks — precisely what the roadmap forbids of self-improvement. A campaign whose
   stopping rule reduces to "the cycle completed" runs the false-green class unattended,
   at scale.

**The counter-argument, recorded because it is real:** grading meaningfully requires many
cycles, and hand-launching them has been the human bottleneck through every FAY window
and shakedown. That is a genuine case for Campaign as the enabler rather than the
consumer. It is resolved by ordering rather than exclusion — both ship in 1.8, and the
scorecard's grade definitions land first so Campaign has something principled to
continue on. Sequencing the scorecard first makes Campaign better, not merely later.

## Cross-Cycle Memory — a decision point, not a commitment

Moved from "Phase 1 rides along" to **an explicit decision taken at 1.8 plan time**:
either a thin Phase 1 or a full push to 2.0 alongside Phase 2. The measurement premise is
unchanged (recurrence measured against 1.6's authored-mode baseline).

**Either way, the rails ship in 1.8.** This follows the repo's standing sequencing rule
— *rails before mechanism* — already applied twice: SIP-0101 shipped evidence rails as
Slice 1 before the harness, and SIP-0096 Phase 1 shipped its pure core inert. Concretely
that means the recall port is defined, a NoOp is injected per the always-inject pattern,
and the call site is wired, whether or not an implementation exists. Phase 1 in 1.8 or
Phase 2 in 2.0 then becomes an adapter swap rather than a redesign, and the decision
stays reversible at low cost.

## Design intentions carried forward

These exist so that building the scorecard and Campaign does not foreclose memory. Two of
the required seams **already exist** — built during 1.5 for unrelated reasons — so the
risk is not missing seams, it is 1.8 inventing second versions of them.

| # | Intention | Owner release | Hook that already exists |
|---|---|---|---|
| 1 | **One cycle-lineage identity.** Campaign's objective envelope defines which cycles belong together, once; inert detection and memory recall both read that definition. Campaign must not invent a private lineage concept. | 1.8 | `inert_detection.py` walks a same-(project, squad_profile, request_profile) series with `INERT_LOOKBACK_CYCLES = 10` |
| 2 | **One failure-class vocabulary.** The scorecard's failure attribution, plan-validation rejection classes, `FailureEvidenceCategory`, and locus classification are one registry of stable ids — not parallel taxonomies memory must later reconcile. The #730 precedent is the model: declaration required, one registry, drift-guarded. | 1.8 | `FailureEvidenceCategory` (×7) + deterministic locus (#568) + `CHECK_SPECS` governance attrs (#730) |
| 3 | **Recall enters through the contract, never a branch.** Memory recall extends the source feeding an existing declared contract flag; it does not add an `if memory_enabled` branch in an authoring handler. | 1.8 | `context_assembly.py` — `plan_rejection_context`, already declared on three authoring task types (#663 S3) |
| 4 | **Ship the recall port with a NoOp, inert.** Define what memory answers when asked "what has this series gotten wrong before?", inject a NoOp, wire the call site — regardless of the Phase 1 decision. | 1.8 | `ports/memory/store.py` (`MemoryPort`) and the always-inject-NoOp pattern from `BaseAgent` |
| 5 | **Record the rejection-class baseline during 1.6.** Memory's value claim is that recurrence of the same mistake falls. That requires a pre-memory baseline, captured from the authored-mode window. **This one cannot be retrofitted** — once memory is live the baseline is unrecoverable. Cheap while building authored mode; impossible afterward. | **1.6** | plan-validation rejections already carry classes; what is missing is durable per-cycle counting |

Intention 5 is the only item on this list that belongs to a release other than 1.8, and it
is the only one whose omission is permanent rather than merely expensive.

## Not moved by this record

- **1.6 and 2.0 rows stand.** Authorship (Squad-Authored Manifest / Generalized Build)
  and Compounding (Capability-Backed Agents umbrella) are unchanged, as is the gate on
  1.8: Functional App Yield repeatably above zero in authored-manifest mode, banked as
  the authored-mode baseline. That baseline does not yet exist, which is the honest
  reason 1.8 gets a shape here and not a plan.
- **No item-level issue re-homing.** The post-cut sweep (2026-08-07) audited all 47 open
  issues, closed #375 as credited-but-open, and posted 1.5 dispositions on nine. The
  remaining re-homing — six issues whose premise moved and whose re-scoping is a planning
  decision (#305, #559, #579, #577, #80, #582) — belongs to the backlog pass, not to this
  progression record.
- **No SIP acceptance.** *(Superseded 2026-08-07, hours after this record: the manifest
  SIP was accepted as **SIP-0103**, `sips/accepted/SIP-0103-Squad-Authored-Manifest.md`,
  as the first step of 1.6 planning. `SIP-Stack-Blueprint-Contract` deliberately stays
  proposed — its own stated acceptance gate is the existence of a second real stack,
  which 1.6 builds, so it is promoted mid-release rather than up front.)*
