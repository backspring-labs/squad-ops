# SIP: Cross-Cycle Memory

## Status
Draft (proposed)

**Author:** Jason Ladd
**Created:** 2026-08-03
**Revision:** 2 (2026-08-03 — design-review round 1 incorporated: typed Phase-1
primitive, governed encoding templates, lifecycle `status` dimension, deterministic
Phase-1 retrieval, recall-vs-outcome metric split, Phase-1 decay)
**Builds on:** SIP-042 (LanceDB semantic memory — the storage mechanics), SIP-0088/0089
(persistent agent identity), #669 (framing re-roll rejection context — the within-cycle
rung and the injection seam this SIP reuses), SIP-0101 (Cycle Replay Harness — the
measurement instrument), Campaign Orchestration (proposed, v1.8 — same-release
companion; see §7).
**Absorbs:** the "Hierarchical Cognitive Memory Architecture" idea doc (J. Ladd, 2026-08)
as the long-term vision (§10); this SIP normatively specifies only Phase 1.
**External reference:** CrewAI, "How we built cognitive memory for agentic systems"
(blog.crewai.com) — adopted for its failure catalog and recall design; deliberately
diverged from on agent-discretionary memory tools (§6).

---

## 1. Summary

SquadOps ships memory mechanics that nothing uses: `MemoryPort` + LanceDB (SIP-042) is
wired into `BaseAgent` via DI and consumed by no execution path. Meanwhile the 1.4 arc
demonstrated, four separate times, that injecting a known failure class into an authoring
prompt converts a recurring loss into a pass — and every one of those injections was a
hand-built framework patch shipped after a human recognized the recurrence:

| Hand-built injection | What recurred until it shipped |
|---|---|
| `api_behavior_contract` lines (#629) | five authored suite versions asserted 200 where the probe pinned 201 |
| `dom_testid_surface` inventory (#659) | suites invented DOM roles/text the view never promised (fay-6/fay-12) |
| error-contract block in repair prompts (pf-34) | repairs guessed `ApiError(status_code=, detail=)` and 500'd every error path |
| framing rejection context (#669) | re-rolls re-emitted the exact rejected shape (fay-10: same class, all three framings) |

This SIP mechanizes that pattern for failures that recur **across cycles**: observe
rejections and validated failures at deterministic seams, encode them as class-labeled
*behavioral* memories through the existing `MemoryPort`, and recall them into
plan-authoring inputs through the appendix-slot machinery #669 already built — so the
squad stops needing a framework patch per recurring mistake class.

Rung ladder: **#669 = within-cycle** (a re-roll sees this cycle's rejection; shipped in
1.4.1) → **this SIP = cross-cycle** (a new cycle sees prior cycles' rejection classes) →
**organization scope** (Phase 2 promotion, evidence-gated).

The substrate is **mode-neutral by design** (§6): Phase 1 implements the cycle-mode
loop, but the schema, identity model, and port are specified so duty- and ambient-mode
memory utilization (SIP-0089 postures, SIP-0091 duty durability) extends the system
rather than reworking it.

**The thesis, stated once:** this SIP does not build a generic AI memory system. It
builds a *validated organizational learning system* — the value is not that an agent
remembers things; it is that SquadOps can **prove** a learned behavior improved future
execution.

## 2. Justification — the specific cycle-success value

Cycle success today is bounded by two scarce budgets, and recurring known-class failures
tax both:

**The framing lane.** A framing pass on the full squad costs ~45 minutes wall-clock
(shk-1, 2026-08-03: framing-1 ran 16:17→17:04 UTC) — ~25% of the 3-hour cycle budget.
`framing_max_rerolls=2`, so a third rejection is a hard cycle failure. The rejection
classes that consume this budget demonstrably recur across independent cycles with fresh
dice:

- qa-claims-dev-slots: fay-2, fay-10, fay-11, fay-13
- dev-claims-frozen: fay-12 (pre-registered), fay-15 (live)
- doomed command checks: fay-2, fay-4, fay-5
- dual-claimed expected artifact: fay-18 (latent, rode to green), **shk-1 framing-1
  (2026-08-03 — the first roll on the 1.4.1 deploy tripped the same class again and paid
  a full re-roll for it)**

Every one of these rejections after the first is a *known* class re-authored by a squad
with no memory of it. A recalled one-line behavioral warning at framing-1 authoring time
("prior plans in this project dual-claimed a dev test file from the QA validation task;
verification-only tasks declare `expected_artifacts: []` + `criteria_refs`") targets the
rejection before it is authored. Value per prevented recurrence: ~45 minutes of budget
returned, one re-roll of headroom preserved, and the tail risk of re-roll exhaustion —
which is a 0% cycle, not a degraded one — removed for that class.

**The correction lane.** `max_correction_attempts=5` is the scarcest implementation
resource. Recurring emission classes (the ApiError signature guess burned repair chains
across pf-33 *and* pf-34; status-code mismatches burned five suite versions in the #629
loop) consume attempts that novel, genuinely-informative failures then don't get. The
banked 1.4 baseline is 3/5 green (60%) with zero machinery defects — the residual losses
are exactly this category: model emission classes (#627/#628/#629) that recur. Front-
loading a recalled class into first authoring spends ~10 prompt lines to save 1–2
correction attempts; attempts saved on known classes are attempts available for unknown
ones.

**The measurable claim** (hypothesis, not forecast): with rejection memory on, the
recurrence rate of already-labeled rejection classes drops measurably vs. the memory-off
baseline, and saved framing/correction budget converts to a Functional App Yield delta.
§9 defines the measurement; the SIP's phase-1 gate is the recurrence-rate number, scored
against stored plans via the SIP-0101 replay harness plus live rolls.

## 3. Problem

1. **Learning is trapped in artifacts nobody reads.** Plan-validation rejections are
   deterministic, class-labeled, repair-precise teaching text (#658's message names the
   file, the rule, and the consequence) — persisted in `gate_decisions` and, before #669,
   read by nobody. #669 fixed this within a cycle. Across cycles the blindness is intact:
   shk-1 re-tripped fay-18's class on a fresh deploy today.
2. **The alternative to memory is a patch per class.** The four hand-built injections in
   §1 each took a human noticing a recurrence, filing an issue, and shipping a prompt/
   framework change. That loop does not scale with project count and is exactly the
   "collection of independent agents" failure the vision doc names.
3. **Naive memory would make things worse.** CrewAI's reported failure modes — context
   bloat, stale facts poisoning later executions, contradiction accumulation — are what a
   store-everything/retrieve-by-similarity v1 produces. The design below adopts their
   countermeasures (atomic memories, composite scoring, confidence-gated recall,
   consolidation as a first-class operation) and scopes Phase 1 to a seed corpus that is
   deterministic and class-labeled by construction, so encoding quality is not dependent
   on model judgment on day one.

## 4. Design principles

- **Behavioral, not factual.** "The `location` field is required" helps only on re-runs
  of one manifest. "You tend to rename interface identifiers — check the manifest before
  emitting" generalizes. Phase-1 encodings state the *tendency and the corrective rule*,
  not the instance data.
- **Mode-neutral substrate, mode-appropriate access.** Agents operate in three postures
  (`mode: ambient | cycle | duty`, SIP-0089), and the memory substrate — schema, store,
  port — must serve all three. What varies by mode is the *access discipline*, not the
  memory model. Nothing in the schema or port may assume a cycle exists (§6).
- **Deterministic seams in cycle mode, not model discretion.** Within cycle execution,
  memory writes happen at fixed pipeline points (gate rejection recorded, cycle
  finalized) and reads at fixed input-construction points (plan authoring, repair
  envelopes later). No agent-invoked `remember()`/`recall()` tools *in cycle-mode task
  execution* — this diverges from CrewAI's design and matches the 1.4-arc lesson that
  every win came from moving judgment out of the dice. It is a cycle-mode discipline,
  not a property of the substrate: ambient- and duty-mode access is agent-initiated by
  nature (§6).
- **Data-only inputs; prose in managed assets** (#448, CLAUDE.md). Recalled memories ride
  task inputs as data keys; the "here is what past cycles got rejected for — revise
  accordingly" prose lives in `src/squadops/prompts/fragments/` assets rendered through
  a template slot, exactly as `rejection_context_section` does today.
- **Memory is cognition, not storage** (CrewAI's core claim, adopted): retrieval is
  confidence-gated and budget-capped, consolidation resolves contradictions rather than
  accumulating them, and forgetting is a scheduled operation, not an accident.

## 5. Phase 1 (normative): cross-cycle rejection memory

One loop, end-to-end, one memory type, one consumer. Phase 1 does **not** implement
generic memory — it implements *recurring failure classes transformed into validated
behavioral guidance*, and the pipeline is typed to make that the only thing that can
flow through it.

**The Phase-1 primitive: `ReflectiveFailurePattern`.** A typed domain model — not a
convention over generic entries — that *serializes into* SIP-042's `MemoryEntry` for
storage (the storage substrate is unchanged; the type lives at the domain layer, per
the constants-not-strings discipline). Generic `MemoryEntry` becomes the future
umbrella: later phases add sibling types (`ProceduralSkill`, `EpisodicEvent`,
`SemanticKnowledge`, `HandoffMemory` — vision §10); Phase 1's encode, recall, and
inject paths accept `ReflectiveFailurePattern` only, so future contributors cannot
assume arbitrary memories flow through the proving loop.

**Observe.** On a plan-validation rejection (gate auto-reject or human gate rejection
with reasons), and on cycle finalize for correction-loop failure classes that carry a
deterministic label (validator-emitted classes only in Phase 1).

**Encode — through a governed template registry, never invented.** The flow is
*validator rejection class → deterministic encoding template → behavioral entry*, with
an explicit abstraction layer in the middle: a per-class template (pattern statement +
corrective rule) that lives beside the prompt fragment assets (#448 discipline) and is
reviewed like any prompt content. Example: class `artifact_claim_conflict` → pattern
"plans tend to assign ownership of produced artifacts to validation roles" + correction
"verification-only tasks declare `expected_artifacts: []`; check ownership against the
producer/consumer split before authoring." The validator supplies the evidence; the
template supplies the generalization; **the memory system invents no patterns in
Phase 1** — a rejection class with no registered template is not encoded (and the gap
is disclosed, not silently skipped). No LLM anywhere in the encode path.

One `ReflectiveFailurePattern` per rejection class occurrence (atomic — one class, one
entry; never a blob of the whole gate decision):

- `namespace`: `project:<project_id>` (Phase 1 *writes* only this scope; the schema
  admits the full ladder from day one)
- `content`: the template-rendered behavioral statement + corrective rule
- `tags`: `rejection_class:<class>`, `task_type:<authoring task>`, `sip:cross-cycle-memory`
- metadata: `owner_role` (role id, never an agent name in source), `agent_id` (nullable —
  the persistent identity per SIP-0088/0089, for agent-scoped entries; null for
  squad-attributed ones), `scope` (`agent | role | project | organization` — the full
  ladder is schema-legal from day one even though Phase 1 writes only `project`),
  `origin_mode` (`cycle | duty | ambient` — Phase 1 writes only `cycle`), `status`
  (`candidate | validated | promoted | deprecated` — **lifecycle trust state,
  orthogonal to origin**: `origin_mode` says where a memory came from, `status` says
  whether it may influence execution; origin does not equal trust. Phase-1 rule:
  validator-sourced, template-encoded entries enter as `validated` — their evidence is
  a deterministic validator firing through a reviewed template, and requiring a
  further validation pass would deadlock the first proving loop; every other source,
  including all duty/ambient-born entries, enters as `candidate`. Only
  `validated`/`promoted` entries are ever injected; decay demotes to `deprecated`,
  which never injects again), `type`
  (`reflective`), `confidence`, `importance`, `reuse_count`, `success_rate`,
  `created_cycle` (**optional** — duty- and ambient-born memories have no cycle),
  `created_campaign` (**optional** — carried when the origin cycle ran under a Campaign,
  per §7; a campaign is provenance and a recall-scoring signal, never a scope),
  `source` (a discriminated provenance union: `gate_decision:<ref>` in Phase 1;
  extensible to duty-handoff, observation, and conversation origins), `summary`.
  (SIP-042's `MemoryEntry` already carries namespace/tags/importance/cycle_id; the delta
  is the scoring/provenance/identity fields.)

**Store.** Existing `MemoryPort` → LanceDB adapter. No new storage service.

**Recall — deterministic filters first; semantic ranking is Phase 2.** Phase 1's
retrieval question is narrow — *has this project previously failed with this class?* —
and class-labeled entries answer it exactly, so Phase 1 recall is a deterministic
filter chain, not a ranking system: project namespace match → task-type tag match →
`status ∈ {validated, promoted}` → confidence ≥ threshold → most-recent-per-class →
hard cap on total injected lines (all thresholds config-driven via
`SQUADOPS__MEMORY__*`). This keeps retrieval variance out of the measured lane
entirely — two identical cycles recall identical memories. Embeddings are still
*stored* (the schema keeps `embedding`), so Phase 2 can add composite semantic scoring
(similarity·recency·importance, the CrewAI formula) retroactively over the corpus when
exact class labels stop being sufficient. Zero matches → zero keys → templates render
without the section (presence-keyed, the #639/#643 pattern).

**Inject.** New data keys on the four plan-authoring task types (#657's set, merger
excluded — deterministic path stays dry), rendered through a new managed appendix asset
family and a template slot alongside `rejection_context_section`. Within-cycle #669
context and cross-cycle memory context stay *separate slots*: one is "this plan just
died," the other is "plans in this project tend to die this way."

**Feedback.** On the next gate decision, update `reuse_count` (recalled entries) and
`success_rate` — defined strictly as **recall effectiveness**: was the *targeted class*
absent from the authored plan? It deliberately does not measure whether the plan or
cycle was good overall (a memory can suppress its class while the resulting strategy is
still poor) — that is **outcome effectiveness**, a later-phase metric (§9). This
telemetry is what Phase 2's promotion gates on — collected from day one, acted on later.

**Decay — the Phase-1 bad-memory protection.** Full consolidation is Phase 2, but bad
lessons must not accumulate in the proving loop: if a recalled entry's targeted class
recurs anyway on K consecutive recalls (config, default small), or its guidance is
implicated in a false-positive rejection, its `confidence` is decremented; below the
recall threshold it stops being injected, and past a floor its `status` moves to
`deprecated` (never injected again, retained for the audit trail). Computed entirely
from the same per-gate feedback above — no new machinery.

## 6. Mode neutrality: cycle, duty, and ambient utilization

Phase 1 implements the cycle-mode loop, but the substrate is designed so duty- and
ambient-mode utilization is an *extension*, never a *migration*. Binding constraints on
Phase 1's implementation (normative), with the utilization sketch they exist to permit:

**Constraints Phase 1 must honor:**

1. **No cycle assumption in schema or port.** `created_cycle` is optional, `origin_mode`
   is first-class, and provenance is a discriminated union — a memory formed during a
   duty window or ambient observation is schema-legal without a fake cycle ref.
2. **Identity is carried, not inferred.** `agent_id` (persistent identity, SIP-0088/0089)
   travels on every entry alongside `owner_role`. An agent-scoped memory survives role
   reassignment and squad recomposition; collapsing agent into role in the storage key
   would corner exactly the identity-memory future this section protects.
3. **Recall is a port operation, not an executor feature.** The composite-scored,
   confidence-gated recall of §5 lives behind `MemoryPort`, callable from any mode. The
   executor's plan-authoring seam is Phase 1's *consumer*, not the recall API's owner.
4. **Access discipline is a per-mode policy, not a substrate property.** Cycle mode:
   seam-mediated only (§4). Duty and ambient modes: agent-initiated recall/remember
   through the same port is the intended shape — there is no deterministic pipeline seam
   in a duty window waiting on events (SIP-0091) or in ambient presence, so discretionary
   access is not a compromise there; it is the only coherent design.

**Utilization sketch (non-normative, later phases):**

- **Duty mode:** a duty agent recalls its own agent-scoped and project-scoped memories at
  window start; duty handoff (the Duty-Continuity/Handoff-Ledger draft) is a natural
  encode/recall pair — the outgoing agent's handoff summary is an encode, the incoming
  agent's context load is a recall. Temporal owns duty durability (SIP-0091); memory owns
  what the duty *learned*.
- **Ambient mode:** ambient agents accumulate observations as agent-scoped candidate
  memories via agent-initiated `remember()`.
- **The quarantine rule (design stance, review-confirmable), generalized by the
  lifecycle `status` dimension (§5):** what may influence execution is governed by
  `status`, not by origin — **origin does not equal trust** (a cycle-generated memory
  can be wrong too). Duty/ambient-born memories enter as `candidate` and do **not**
  reach cycle-mode recall until promoted through Phase 2's evidence gates;
  validator-sourced cycle-born entries enter as `validated` (their evidence is a
  deterministic validator firing through a reviewed template); decay can demote any
  entry to `deprecated` regardless of where it came from. Cycle execution is the dice
  we measure; letting unvetted observations into authoring prompts would reintroduce
  the nondeterminism the 1.4 arc spent a release removing. Ambient/duty agents may
  freely recall *validated* project memories; the gate is on what flows *into* the
  measured lane, not out of it.

## 7. Campaign interaction

Campaign Orchestration (targeting v1.8, the same release as this SIP's Phase 1) is the
sharpest consumer of cross-cycle memory: `repair`/`retry`/`fork` continuations create
back-to-back cycles pursuing one objective, where the prior cycle's failure classes are
maximally relevant and the recurrence metric takes its tightest form (did the class
recur *within the campaign*?).

Design decisions this implies:

- **Campaign is provenance, not scope.** Memories born in a campaign must outlive it —
  organizational learning would be defeated by campaign-lifetime memories. `created_campaign`
  rides the metadata; recall scoring may boost same-campaign provenance (the "this
  objective's own history" signal); the scope ladder (§5) is unchanged.
- **Campaign close is Phase 2's consolidation clock.** Consolidation and success-rate
  updates need a deterministic trigger; cycle-end is too frequent and wall-clock is
  arbitrary. Campaign disposition — the final continuation decision — is the natural
  batch point: reflect over the campaign's accumulated evidence (SIP-0096
  `CycleOutcome` roll-ups), consolidate per-class entries, update `success_rate` from
  the outcome trajectory. This instantiates the idea doc's reflection pipeline
  (Execution → Audit → Reflection → Extraction → Consolidation) at a real runtime seam.
- **The purity boundary (binding constraint):** memory is **never** an input to the
  campaign continuation decision. The Campaign SIP specifies that decision as a pure
  function of (objective, policy, accumulated evidence, latest outcome) — the
  reserve-buffer-guard pattern. Memory improves *how the next cycle authors*; the
  campaign decides *whether and what to launch*. Coupling them would make the
  continuation decision non-replayable and structurally entangle the two SIPs — and it
  would open a self-reinforcing loop: past failures bias the continuation decision,
  biased continuation reduces new experiments, and reduced experimentation reinforces
  the original belief. Keeping campaign control deterministic preserves replayability
  and measurement integrity.

## 8. Phase 2 (design-sketch, separately gated): consolidation and promotion

- **Consolidation** — CrewAI's genuine differentiator: on encode, similarity-search for
  related entries; on contradiction, update-or-delete with provenance preserved (never
  two competing facts). Scheduled forgetting/summarization for entries with low
  reuse_count past a config horizon.
- **Promotion** agent→project→organization, gated on observed `reuse_count`,
  `success_rate`, and audit validation — using Phase 1's telemetry, not judgment.
- LLM-assisted encoding for failure classes that lack a validator label (correction-loop
  behavioral classes), behind the same schema.

Phase 2 does not begin until Phase 1's recurrence-rate measurement is in hand.

## 9. Success metrics (measured, not aspirational)

Two tiers, deliberately separated — a memory can suppress its targeted class while the
overall result stays poor, so conflating them would let recall wins masquerade as
outcome wins:

**Recall effectiveness (Phase 1 measures this; gates the phase):**
1. **Primary:** recurrence rate of labeled rejection classes, memory-on vs. memory-off
   — scored against stored plans via the SIP-0101 replay harness and over a
   pre-registered set of live rolls (FAY methodology; N declared before rolling).
2. Injection cost: prompt lines added per authoring task (must stay under the cap;
   context bloat is a regression, not a side effect).
3. Retrieval usefulness: `reuse_count`/`success_rate` distributions, decay/deprecation
   counts (Phase 2's promotion evidence).

**Outcome effectiveness (observed in Phase 1, measured later — never gates Phase 1):**
4. Framing re-rolls consumed per cycle (memory-on vs. baseline window).
5. Correction attempts consumed by already-labeled classes.
6. Functional App Yield delta (the §2 hypothesis; a later-phase measurement once
   recall effectiveness is established).

## 10. Long-term vision (from the idea doc; non-normative here)

The destination is an engineering organization that learns from every execution cycle:
a memory hierarchy (Agent → Cycle → Project → Organization), four cognitive memory types
(episodic/semantic/procedural/reflective), role-tuned retrieval profiles
(developer procedural-heavy, qa episodic-heavy, strategy semantic-heavy, audit
reflective-heavy), a full Observe→Evaluate→Score→Encode→Consolidate→Store→Retrieve→
Promote→Forget lifecycle, and evidence-gated promotion into validated institutional
knowledge. Phase 1 deliberately instantiates the smallest slice of this that can prove
value on a number: one memory type (reflective), one scope (project), one consumer
(plan authoring), one metric (rejection recurrence).

## 11. Non-goals (Phase 1)

- Organization-scope memory and cross-project promotion (Phase 2, evidence-gated).
- Role cognitive profiles and per-role retrieval tuning (vision).
- Memory analytics services, governance service, "Memory Consolidation Engine" as a
  standalone service — Phase 1 adds **zero new services**; it is a pipeline through
  existing ports.
- Agent-discretionary remember/recall tools **in cycle-mode task execution** (deliberate
  divergence from CrewAI, §4). Duty- and ambient-mode discretionary access is explicitly
  designed *for* (§6) — deferred, not excluded.
- A Memory Librarian role — the Campaign-Self-Improvement draft's §12.7 should defer to
  this SIP rather than grow a parallel memory surface.
- Memories of *facts about the app under build* (manifest fields, endpoint shapes) — the
  contract/manifest seams already carry those deterministically; duplicating them in
  memory recreates the stale-fact poisoning CrewAI warns about.

## 12. Placement in the dev arc

Per the ratified post-1.4 reshuffle (`docs/plans/post-1-4-roadmap-reconciliation.md`,
2026-08-03):

- **Phase 1 → v1.8, riding as a thin non-headline feature** beside the release's
  headliners (Campaign mechanic, Lane M; scorecard/benchmark registry). Phase 1 adds
  zero services — the 1.2.0 precedent (three feature SIPs, one release) covers a thin
  rider. Deliberately **not** v1.6: injecting memory into authoring during the release
  that measures the authored-manifest baseline would confound that baseline; and not
  earlier, because by 1.8 Phase 1 inherits **two** seed corpora (plan-validation classes
  + the manifest-authoring rejection classes v1.6 creates) and measures recurrence
  against the banked 1.6 authored-mode FAY baseline.
- **Phase 2 → v2.0, inside the Capability-Backed Agents arc.** The 2.0 umbrella names
  scoped memory as a component of what an agent is and its problem statement demands
  exactly Phase 2's content — "memory needs scope, provenance, promotion, and
  disclosure." Phase 2 (consolidation, promotion, duty/ambient utilization, §6–§8) is
  that substrate, delivered with a Phase-1 measured result behind it rather than
  specified cold from inside an umbrella. Framed at the 2.0 altitude, this SIP is the
  *learned-experience* leg of the capability-backed agent equation — **agent = identity
  (SIP-0088/0089) + capability (packs) + memory (this SIP) + policy + evidence
  history** — which is why it precedes the umbrella rather than riding inside it.
- **Sequencing (readiness, not dates):** implementation can begin once design review
  accepts; hard dependencies are already shipped (SIP-042 mechanics, the #669 injection
  seam, `gate_decisions` persistence). SIP-0101's replay harness must be usable before
  the Phase-1 *measurement* is scored, not before implementation starts. Campaign
  landing in the same release supplies `created_campaign` provenance and the
  within-campaign consumer from day one (§7); nothing in Phase 1 hard-requires it.
- **File ownership:** planning/authoring surfaces (task_plan, planning handlers,
  prompt assets) — Macbook-lane per the #281 ownership split; the LanceDB adapter and
  any config plumbing are shared surfaces.

## 13. Open questions for design review

1. Should human gate rejections (free-text reasons) enter Phase 1's corpus, or only
   validator-emitted classes? (Draft position: validator-only — deterministic encode; the
   human-reason path needs the Phase-2 LLM encode.)
2. Per-class deduplication key: rejection class alone, or class × task_type?
3. Does recall also belong on repair envelopes in Phase 1 (the correction lane of §2), or
   is that scope creep past "one consumer"? (Draft position: plan authoring only; repair
   recall is the first Phase-1.5 extension once the metric exists.)
4. Retention horizon and the memory-off control protocol for the measurement window.
5. Role-scoped expertise memory (procedural — "how this role solves problems well",
   keyed to persistent identity per SIP-0088/0089): does it enter as a Phase 1.5 with
   its own seed corpus, or wait for Phase 2's LLM-assisted encode?
6. The `candidate → validated` transition (§5/§6): what validation evidence promotes a
   duty- or ambient-born memory into cycle-mode recall — reuse under observation, audit
   sign-off, or a replay-scored trial? (Draft position: Phase 2's promotion gates are
   the single mechanism; no side door. The lifecycle `status` field now carries the
   answer's machinery; this question is about the *evidence bar*.)
7. Decay calibration (§5): the consecutive-ineffective threshold K and the confidence
   floor — fixed defaults, or derived from the measurement window's base rates?
8. Encoding-template governance: who reviews new per-class templates (they are prompt
   content under #448 — same review path as fragments?), and is a missing template a
   release-blocking gap for a newly shipped validator or a disclosed backlog item?
