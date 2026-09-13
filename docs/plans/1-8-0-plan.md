# 1.8.0 — plan

**Revision 2, 2026-09-12.** Rev 1 was written the day the 1.7 line closed; rev 2 the same
evening, recording the owner's rulings on §8 decisions 1–3 (§10). Written from the ROADMAP's 1.8 row
and the reconciliation that wrote it (`docs/plans/post-1-5-roadmap-reconciliation.md`), the
1.7.5 plan (`docs/plans/1-7-5-plan.md` §3.9a, §5, §6, §7 step 14, §8), the 1.7.5 record
(`docs/plans/1-7-5-verification-set-record.md` §5, §7, §9), the 1.6.0 plan's "Owed to 1.8"
(`docs/plans/1-6-0-authorship-plan.md`), the three proposed SIPs the row names, the Scoped
Code Revision draft on PR #1325, and every open issue in the tracker on the day of writing
— twenty-eight before this plan, thirty after it (#1506 and #1507 were filed with it).

**1.8 is the release where the squad is judged.** The ROADMAP's ladder reads: *1.6 teaches the
squad to design, 1.7 makes the seams hold, 1.8 teaches it to judge — and only then to run on
its own.* 1.7 closed with zero drift under `src/` and `adapters/`, the seams the grades are
computed over now hold, and the authored-mode baseline 1.8 was gated on has been banked four
times over (1.6.0 4/6; 1.7.3–1.7.5 at 7 to 8 of 9). Nothing structural stands in front of
this release.

What has changed since the row was written in August is the evidence about **where the loop
loses**, and it reshapes the row. The 1.7.5 set's two rejections were the same failure: a
repair loop spending its whole budget re-emitting whole files while its own record held enough
evidence to stop after one round (#1501); the 1.6.5 set lost two of six rolls to whole-file
rewrites, one carrying the correct fix (#1213). That is a contract defect between the agent
and the repository, and the design that fixes it — **Scoped Code Revision**, PR #1325 — has
been ruled 1.8's by the owner twice (the 1.7.4 plan §1; the 1.7.5 plan rev 2, 2026-09-09).
Its design review, which the 1.7.4 plan said would run "beside" that line, never opened.

So this plan carries **two headlines, one per lane** — **ruled by the owner on 2026-09-12**
(§8, decisions 1–3; the rationale is §2.3 and is not re-argued after it). The ladder the ruling
produces, stated once:

- **1.8 bounds edits and makes outcomes judgeable** — Scoped Code Revision, and the scorecard's
  mechanical judgement contract; the lineage seam and the pre-memory baseline land as rails.
- **1.9 closes the 1.x line** — the cycle-completion boundary extracted (#1507) and the named
  debts retired; that boundary is **2.0's entry condition** (§6).
- **2.0 continues on its own** — Campaign Orchestration, the first consumer allowed to act on
  `CycleAssessment`; its continuation policy never reads raw checks.
- **2.1 installs memory's inert rail; 2.2 activates cross-cycle recall** — after 2.1 re-reads
  Phase 1's proving workload against the recurrence evidence of that day.

| lane | headline | what it is | its proof |
|---|---|---|---|
| **M — the loop** | **Scoped Code Revision** (PR #1325, rev 2) | for an existing artifact the agent describes the smallest reliable revision; the framework realizes it under an explicit write grant, preserves every byte outside the accepted range, and verifies exactly the tree it persists | the draft's own §39: zero outside-grant change, zero restoration, candidate identity equals persisted identity, on **N** live repair transactions across both stacks and every producer lane, N fixed before roll 1 (§4) |
| **S — the judgement** | **Cycle Evaluation Scorecard, the 1.8 slice** (`sips/proposed/SIP-Cycle-Evaluation-Scorecard.md`, to be revised before review) | `CycleAssessment` as a projection over the `CycleOutcome` seam; **one** failure-attribution registry shared with the vocabularies the code already has; a benchmark registry over the stored counted rolls; the squad-versus-single-model comparison harness | every counted record of this release carries an assessment whose every dimension cites evidence that resolves; the historical corpus re-graded deterministically; **one pre-registered comparison window closed with its result stated, whichever way it goes** |

**Moved off the row, by the owner's ruling.** *Campaign Orchestration* is **2.0's headline** —
behind the grades its continuation policy consumes, the ROADMAP's own ordering rule — and its
**rail** ships here: the one cycle-lineage seam that inert detection already defines and the
scorecard must read rather than reinvent. *Cross-Cycle Memory* moves to **2.2**, on evidence
the row did not have: its seed corpus at the plan gate has dried up (§2.3). What 1.8 keeps of
it is the part that cannot wait — the pre-memory baseline (B1) that 1.6 recorded the inputs
for is finally emitted. The recall port moves with its mechanism to **2.1**, so 1.8 does not
ship a port with no consumer for two even minors (§2.3).

Rules carried from the 1.7 lines without discount:

- **a measured tranche and a structural tranche do not share a deploy** — the prelude lands on
  deploy A behind a checkpoint pair, the headlines on deploy B, so a red has one owner;
- **no fault, no prediction** — and this time the rule is load-bearing rather than defensive:
  seven of nine 1.7.5 rolls took **zero** correction rounds, so a repair-path feature cannot be
  proven by counted rolls alone, and §4 says exactly how much of N the diagnostics must supply;
- **every registered field carries one of three states** — observed, asked-and-none, or
  unaskable with its reason (#1445) — and every diagnostic reaches its seam on the pinned
  deploy, with #1506 making the one that could not reach in 1.7.5 reachable again;
- **acceptance before the branch** (CLAUDE.md, the contributor workflow): both headline SIPs
  are accepted on main before their first feature PR, and each is amended in place (§5a) when
  implementation shows the design was wrong.

---

## 1. What the 1.7 line says the release has to be

| what the line showed | evidence | what it says about this release |
|---|---|---|
| **both 1.7.5 rejections were one failure** — a qa suite re-authoring itself every round, a stable failing core (`runs-list-view`, `create-run-error` in every attempt) that the exact-repeat rule never matched, three rounds and six applied patches burned; roll 6 was the control, an exact repeat caught at round 1 | 1.7.5 record §5 F-1, #1501 | **#1501 lands in the prelude** — the repeat rule gains a stable-core test beside the exact match, proven by replaying roll 3's eight stored `test_report.md` versions as a fixture with roll 6 as the control (§3.2); and the class behind it — a repair that re-emits the whole artifact — is the headline's subject |
| **seven of nine accepted rolls took zero correction rounds**; the repair path ran on two rolls, five rounds in total | record §1 | a counted set of nine exercises the repair path on roughly two rolls; **the headline's live evidence comes mostly from fault-injected diagnostics**, per lane and per stack, and §4 budgets them rather than hoping |
| **the experimental gate was not met** — `contentless-builder` cannot reach its seam on any deploy carrying #1372, because the aimed retry recovers the builder before correction; the remedy was written against an issue (#1374) that had already closed | plan §3.9a, record §4/§7, #1506 | **#1506 lands in the prelude**: R1 and F1 become two readouts, F1 keyed on the `ALL_EMISSION_ATTEMPTS` scope (`src/squadops/capabilities/handlers/fault_injection.py:213`) that #1310 added for exactly this. F1 is unexercised on any current deploy until then, and the plan says so rather than carrying it silently |
| **the delivered app's most common record shape is unstyled** — `<dl>` in 92 files across 81 cycles, against 13 `<table>`, which the baseline sheet styles | record §5 F-2, #1499 | **#1499 lands in the prelude** — it moves the skeleton and a committed golden, so it cannot land after the checkpoint pair (the #906/#1463 lesson) |
| the recovery path left the executor for two collaborators, byte-identical goldens through six steps; the executor still carries three methods of 396, 325 and 301 lines, named out of the map, and the issue that owned them closed | 1.7.5 recovery extraction map §4, PR #1491, #1507 | **1.9's** (#1507), not this release's: the completion boundary is what Campaign lands through in 2.0, and it is extracted in the stabilization minor between — the close of the 1.x line — in the same order the recovery path was |
| the qa and dev handlers' `handle()` each carry two output shapes — 617 and 332 lines on main today (`src/squadops/capabilities/handlers/cycle/qa_test.py:1217`, `develop.py:408`); Scoped Code Revision adds a third | #1444, measured 2026-09-12 | **#1444 is the first extraction, before the headline's first PR** — the owner's ruling (1.7.5 plan §8 decision 16), not a feature and not optional |
| the Scoped Code Revision design review never opened — PR #1325 has zero reviews and zero comments since 2026-09-07 | the PR, 2026-09-12 | **the review is this plan's opening step, with a named reviewer and a fixed outcome vocabulary** (§3.1); "beside the line" produced nothing across a whole line |
| the pre-memory rejection baseline's inputs were made durable (`src/squadops/cycles/rejection_baseline.py`, `scripts/dev/emit_rejection_baseline.py`) and the report was never emitted; **thirteen rejection records exist in the vault, all between 2026-08-10 and 2026-08-23, none since** | the vault, 2026-09-12; every set record since 1.6.3 ("zero framing re-rolls") | the baseline is emitted in this release (§3.5), and its emptiness after 1.6.2 is the evidence behind decision 2 (§2.3) |
| `container_packaging` failed on five of nine, four of nine and eight of nine counted rolls across three lines; the owner ruled the promotion to blocking not taken and the packaging becomes a rendering | 1.7.5 plan §8 decision 1 | **#598 lands in the prelude as a rendering** — a SIP-0105 amendment first, then the Dockerfile rendered from the stack declaration with `container_packaging` as the guard on the rendering; roll-verified, its own prediction (§4) |
| every 1.7.x plan carried #567, #579 and #353 to "the 1.8 rider" | 1.7.5 plan §5, §6 | each is disposed of by decision here (§6, §8 decision 7): #579 lands, #567 and #353 go to 1.9 with the reason written |

---

## 2. Why this release, on the roadmap — two headlines and two moves

### 2.1 Lane M — the loop stops re-emitting what the framework can preserve

The correction contract today is whole-file re-emission: a repair that changes three lines
re-authors every other line and gives each a fresh chance to be wrong. The draft on PR #1325
(rev 2, 2026-09-07) separates four things the pipeline conflates — authorization (a
`WriteGrant`), intent, resolution to an exact source range, and composition of the candidate
tree — and makes the existing artifact's contract a version-bound revision transaction:
replace, insert or remove against a structural target, an exact anchored target (#1213's
uniqueness rule), an authorized region (the shipped QA slot-body path), or whole-file
replacement as an explicit last resort. The framework owns every byte outside the accepted
revision; the candidate tree gets an identity; verification and persistence bind to that
identity (`compute_revision_id` is taken on the base workspace one call before the patch is
materialized today, so the verified candidate has no identity — the draft's §3.6).

It is a feature by its own §44 — it changes task framing, write authorization, the agent
response contract, scaffold semantics, composition, integrity enforcement, retries,
verification evidence, persistence, replay and observability — and it is the loop's next rung
after 1.7's honesty work: 1.7.2 and 1.7.4 made the loop's *record* true; this makes the loop's
*edits* small. The evidence is current: #1501's two rolls, #1213's two rolls, and the roll-1
`routes.py` record in the draft's §1.3 (3 status codes restored, 5 response models and 3
handler names observed only — the acceptance criterion is zero restoration *and* an empty
observed set).

**What 1.7.5 handed it:** the accepted-patch path and the correction protocol as named
collaborators (`adapters/cycles/patch_acceptance.py`, `correction_repair.py`), which are the
seams a scoped revision lands through; and #1444 as its first extraction, because building a
third output shape into a 617-line function that already interleaves two is how the fill mode
got its reasoning declaration wrong (#1434).

### 2.2 Lane S — the thesis becomes falsifiable

The project can state a functional yield; it cannot state that a squad outperforms a single
model at equal scaffolding and cost. The scorecard slice is the only roadmap item that makes
that claim testable, and it is the load-bearing dependency of 2.0, whose rule is that
self-improvement acts on `CycleAssessment` grades and never on raw checks.

The seam exists and already names its consumer: `CycleOutcome`
(`src/squadops/cycles/verification_integrity.py:418`) is "the substrate the later
cycle-evaluation scorecard derives its outcome/quality/efficiency/stability dimensions from —
those are *projections* over this honest evidence, not new raw fields here." The failure
vocabularies the reconciliation's intention 2 says must be **one registry** also exist, and
there are more of them than the SIP knows: `FailureEvidenceCategory` (seven values,
`src/squadops/cycles/failure_evidence.py:189`), `FailureLocus` (`:249`) with
`classify_failure_locus` (`:353`), the fourteen `ImplementationPlan.validate_*` rejection
classes the baseline keys on, `WinnabilityFinding` classes at the manifest gate
(`src/squadops/cycles/manifest_gates.py:70`), and the correction movement tokens
(`src/squadops/cycles/correction_signature.py:166`). The SIP's seven attribution categories are
a parallel taxonomy today; the slice's first deliverable is that they stop being one.

**The SIP needs a revision before review.** It is 149 lines from 2026-02-28, revision 1, with
acceptance criteria that include a console Scorecard page and an API endpoint, and an open
question asking whether "the Data agent assembles evidence, Lead evaluates". The 1.8 slice is
mechanical and headless by the ROADMAP's own description. Rev 2 (§3.1) narrows the normative
text to the slice, moves the console page to SIP-0069's surface as a later consumer, answers
the LLM question with *no* (an assessment computed by an agent is exactly the self-graded
evidence SIP-0096 exists to refuse), and defines the single-model arm — which is a genuine
design question (§8 decision 5) and the reason the comparison window is a separate
pre-registration from the loop's set.

### 2.3 The two moves, and the evidence behind each

**Campaign → 2.0, as its headline; its rail here.** *Ruled by the owner, 2026-09-12.* The
ROADMAP orders grade definitions before continuation policy and says why: without
`CycleAssessment` a continuation policy must invent a stopping rule out of raw checks. Both
were to ship in 1.8. Three feature SIPs — the two above plus Campaign — is one more than a
release carries (one headline per lane; 1.4 and 1.6 are the precedent, and 1.6 took two weeks
and six patch lines with two). The owner's ruling goes further than this plan's rev 1
recommendation (the next even minor) and gives the move a shape: **the 1.x line closes on 1.8
and its 1.9 stabilization tail, and 2.0 opens on Campaign** — "teaches it to judge, and only
then to run on its own" becomes the boundary between the major versions. Campaign's Phase 2
dependencies move with it (#316, the request-profile taxonomy). Its **rail** is the thing the
reconciliation actually protected: one cycle-lineage identity. That identity exists in the
code — inert detection walks a same-(project, squad profile, request profile) series
(`src/squadops/cycles/inert_detection.py:45`, `INERT_LOOKBACK_CYCLES = 10`) — and the scorecard
would otherwise invent a second one. §3.5 extracts it as a named seam that inert detection and
the scorecard both read — **a stable consumer contract, not provisional architecture**: Campaign
in 2.0 may enrich the derivation behind that seam with its objective envelope; it introduces no
second lineage concept and asks no consumer to migrate. **What the 2.0 row loses, stated:** its former pillars — Capability-Backed
Agents, Self-Improvement and the Test Bay — sequence behind Campaign, by the 2.0 plan.

**Cross-Cycle Memory → 2.2; the baseline here, the rails with the mechanism.** *Ruled by the
owner, 2026-09-12.* Phase 1's value claim is that recurrence of labeled plan-validation
rejection classes falls, measured against a pre-memory baseline. The baseline's inputs were
made durable in 1.6 (B1, #809): thirteen `rejection_record.json` artifacts in the vault, dated
2026-08-10 to 2026-08-23. **None has been written since.** 1.6.2's success-status
single-sourcing (#1067, #1070 part A, merged 2026-08-24) removed the class that produced most
of them, and every counted set since — 1.6.3 through 1.7.5, seventy-nine rolls — reports zero
framing re-rolls. Phase 1's seed corpus, on this workload, is empty. **That zero says the
original Phase-1 proving workload is no longer active; it does not say cross-cycle memory has no
value** — and B1 preserves the result so 2.1 can revalidate the proving workload rather than
manufacture a baseline retrospectively. The recurrence that *does*
happen now is in the correction loop (a suite re-authoring its failing set; a repair rewriting
a file), which the memory SIP's own §13 question 3 calls a Phase 1.5 extension "once the metric
exists" and which the Lane M headline addresses structurally. So 1.8 emits the baseline from the
thirteen records so it exists as a document rather than as inputs, and states the emptiness as
a finding. **The recall port does not ship in 1.8.** The reconciliation's "rails ship in 1.8
either way" was written for a decision between 1.8 and 2.0 — one release ahead of the
mechanism, the SIP-0101 and SIP-0096 precedent. Two even minors ahead, a port with a NoOp and
no consumer is the #1312 shape (required, read by nothing), and the two seams that actually
protect the design — one lineage identity and one failure vocabulary — ship in 1.8 for the
scorecard's sake regardless. The port, its inert NoOp and the call site through
`plan_rejection_context` (`src/squadops/capabilities/context_assembly.py:119`, declared on six
task types on main) belong to **2.1**, which also owes one more thing: **a re-read of Phase 1's
value hypothesis against the recurrence evidence available at the 2.1 cut** — the mechanism may
still be right while the original metric, recurrence of plan-validation rejection classes, is no
longer the best workload for proving it.

**What this release does not do, stated here rather than implied.** It does not build
Campaign's continuation policy or Continuum surface, memory's recall port or its adapters, the
scorecard's console page or recommendations, SIP-0104 for stack #1 (#1122), the framing
surfaces (#949, #950, #194, #1031), or the executor's remaining spine (#1507). It does not
adopt Atlas. It does not promote a SIP on the strength of its own work except by amendment.

---

## 3. The content

### 3.1 Preconditions — the opening step, and before the first code PR

**The Scoped Code Revision design review — this plan's opening step, not a step beside it.**

- *Reviewer:* the owner, named here because the 1.7.4 plan's "beside this line" produced zero
  reviews across a whole line.
- *Outcome vocabulary, fixed:* **accepted** / **accepted with required revision** (the revisions
  named, folded into rev 3 on the PR before acceptance) / **rejected and reframed** (the plan is
  revised in the open; the lane's headline is then re-decided, not defaulted).
- *What the review must answer* — the draft's own §43, plus two the plan adds:
  1. reference representation (§43.1) and resolver selection per stack (§43.2) — the SIP
     specifies behaviour, not the library; the review names who picks the library and when;
  2. whole-file fallback policy for scaffold-owned files (§43.3) — the draft prefers the
     stronger policy; a ruling;
  3. `move` as a primitive (§43.4) — decided on repair evidence, not vocabulary completeness;
  4. correction-budget semantics (§43.5, §22) — **and #414 is answered here**: the draft's
     budget default and #414's priority-reserve option 2 touch one pool; the review rules on
     both or names why they are separate;
  5. the rollout's stack order (§38 step 5–6) against the counted-roll history: React is six of
     nine counted rolls and the demo arm, Next.js is where the slot-body path already ships.
- *Gate:* a completed decision recorded on the PR, then `update_sip_status.py … accepted` —
  **acceptance before the branch**. The feature's first PR does not open until the SIP has a
  number.

**The scorecard SIP, rev 2, then its review.** Written before review because rev 1 does not
describe the slice (§2.2). Rev 2 must: narrow the normative text to the four slice
deliverables (§3.4); move the console page out to SIP-0069's surface as a named later
consumer; make the attribution vocabulary one registry with the five that exist (§2.2) rather
than an eighth; rule the computation mechanical (no agent in the assessment path); define the
**single-model arm** — what the single model receives (the PRD, the scaffold, the same
verification contract?), what it does not (the framing sequence, the roles), and what "equal
scaffolding and cost" means in tokens and wall-clock on this box; and retarget off the stale
`v1.1` in its source idea (`docs/ideas/IDEA-cycle-evaluation-scorecard-framework.md`). Same
reviewer, same vocabulary, same gate. **Its review may run beside the SCR review; its
acceptance is independent.**

**#1444 — the first extraction, before the headline's first PR.** One `handle()` per output
shape behind the capability's `_output_shape(inputs)` hook (#1285's selector); the self-eval
follow-up loop extracted once, parameterised by shape; extraction only, byte-identical on the
stored qa and dev emissions in `tests/fixtures/roll_replays/` and `reference_fills/`; a wiring
test entering at the executor's dispatch asserting which `handle` a fill-mode task reaches. The
1.7.5 extraction rules apply unchanged: no behavioural change rides the PR, the rationale is
harvested into `docs/architecture/defended-bespoke-decisions.md` first, and the three
test-edit classes (imports, `monkeypatch.setattr`, `caplog.at_level(logger=…)` — the last one
fails silently) are grepped for by module path.

**Verify-then-close, no code** — each closes with a comment naming the evidence, or is
re-placed with what is missing named:

| item | evidence in hand | what closes it |
|---|---|---|
| **#1149** | register entries 16–38 landed with each extraction PR (#1451, #1482–#1486); the executor and correction-runner paths the issue named are harvested; `scaffold.py`'s was 1.7.1's | the entries cited; or the un-harvested path named |
| **#1443** | `run_correction_protocol` 536 → **151** lines (`adapters/cycles/correction_runner.py:777`), the file 2,145 → **1,331**, extracted by protocol step under the correction-context golden (map steps 4–5) | the measurement cited; the executor's own remainder is #1507, not this issue's |
| **#176** | recipe 1 (the pipeline invariants, machine-checked) landed in #1492; recipe 2 needs one `smoke`-squad launch of `hello_squad`/`selftest`, a state-changing op the owner authorises | one launch in the idle-box slot (§3.7), the invariants read; or the gap named |

**Issues filed with this plan:** #1506 (F1's re-registration, §3.2) and #1507 (the executor's
three remaining methods, 1.9 — §6). Both are named in §1 with their reasons.

### 3.2 The prelude — deploy A, behind a checkpoint pair

Everything that changes what a roll rejects on, what a record reads, or what the skeleton
ships, landed and read **before** the headlines move, so a red on deploy B has one owner. In
merge order:

| step | item | what lands | readout |
|---|---|---|---|
| 1 | **#1506** | the `contentless-builder` diagnostic becomes two: R1 keeps the `FIRST_ATTEMPT` fault; F1 gets `builder_emission_contentless_all_attempts` at `FaultScope.ALL_EMISSION_ATTEMPTS`, so the builder exhausts its emission retries and fails into correction; two readouts in `SEAM_READOUTS`, each reached on its own evidence | instrument — both run on the pinned deploy (§4) |
| 2 | **#1501** | the repeat rule terminates on a **stable failing core** across adjacent rounds beside the exact match — the intersection of the two signatures non-empty and unchanged over the round — proven by replaying 1.7.5 roll 3's eight stored `test_report.md` versions as a fixture (terminates after round 1) with roll 6 as the control (exact repeat, unchanged); the classification of a churning set as `plan_defect` versus a new candidate is the design question the PR answers, with the seam table | **a seam invariant, not a live hypothesis** — a fixture, and a live occurrence read as texture (a set may produce none) |
| 3 | **#1499** | `dl`/`dt`/`dd` rules in the baseline stylesheet, element-scoped like the rest; both stacks' expanders reach one constant (the #1463 invariant); the committed golden moves once, deliberately, cleared with the owner first | read on the pair: boot audit unchanged; the delivered app's record view styled, photographed for the package |
| 4 | **#80** | `framework_version`, `framework_git_sha` and the request-profile *name* on the `Cycle` record (`src/squadops/cycles/models.py:349`; today it carries `squad_profile_id`, `request_profile` and `resolved_config_hash`, no code lineage) — **the scorecard's benchmark registry needs code lineage on the row it grades**; additive, nullable for existing rows (no cosmetic migration) | texture: the pair's records carry the three fields |
| 5 | **#579** | the frontmatter parser extracted — four inline copies and one helper on the tree today, on every prompt render — byte-equivalent by test on every rendered prompt in the fixture set | CI; the pair proves the render path loaded |
| 6 | **the lineage seam** (§3.5) | `series_for(cycle)` extracted from inert detection into one module both it and the scorecard read; Campaign's rail, replaced in 2.0 | CI; inert detection's tests unchanged |
| 7 | **#598** | a SIP-0105 post-acceptance amendment first (the Dockerfile and nginx config are a **rendering** of the stack declaration, SIP-0102 §4.2's "environment definition is the contract"), then the rendering, with `container_packaging` re-pointed as the guard on the rendered files and the builder's role contract (SIP-0071) amended to stop authoring them | **a live prediction** (§4): zero `container_packaging` findings on the accepted emission of every counted roll; the boot audit unchanged |

**What the pair proves.** A red on deploy A belongs to this tranche and is identified per PR
by its signature: #1501's is a termination reason, #1499's a golden, #598's a packaging row,
#80's a null field, the lineage seam's an inert-detection test. The #598 prediction and
the #1506 readouts get their first reading here and their counted reading on deploy B.

### 3.3 Lane M — Scoped Code Revision

After acceptance (§3.1) and #1444. **The SIP is the acceptance source; this table places and
sequences its §38 rollout.** One PR per step, in this order, because each step's proof is the
previous step's invariant still holding:

| step | what lands (draft §38) | how it is proven |
|---|---|---|
| 1 | **the QA slot-body path generalised** — `verification_scaffold_fill` lifted into one revision-transaction type: grant carried, candidate identity assigned, `materialize(…, authorization=)` wired; the QA lane keeps working throughout | the Next.js fill fixtures byte-identical through; the fill-merge evidence (#999) unchanged on the checkpoint |
| 2 | **candidate identity** — `compute_revision_id` taken after materialization and compared at storage (§20); may land first, it is one call | `verified_revision_id == persisted_revision_id` in the evidence of every stored patch on the pair |
| 3 | **the dev grant** — `WriteGrant.for_dev_fill` propagated into the dev repair path so every lane carries an enforced grant (the draft's §3.3: today it is defined and unused, the largest exposure) | a dev repair outside its grant refused with evidence, at the same seams as QA and builder (§39.6); **a dev-lane fault is registered for it** (§4) |
| 4 | **exact anchored targets** inside the grant, strict uniqueness — **#1213 closes here** | a multi-match anchor fails rather than choosing (§39.5); the #451 fixture |
| 5 | **structural read and addressing** for the first stack (the review's ruling, §3.1 item 5), then replace / insert / remove with the preservation assertion (§17) | zero changed bytes outside accepted ranges (§39.2); zero restoration and an empty observed set on a scaffolded artifact (§39.3) |
| 6 | **the second stack**, equivalent semantics across different slot granularity (§39.7) | the same criteria on the other stack's fixtures |
| 7 | **the default** — scoped revision the normal path for supported existing artifacts, legacy whole-file emission the explicit fallback (§9.4) with the review's §43.3 policy | **gated by §39.8's N live transactions** — the counted set and diagnostics of §4 decide it; if N is not met at the cut, the SIP stays `accepted` with step 7 named open (SIP-0102 precedent) and the cut record says so |

**The core and the tail, for the cut.** Steps 1–5 on the first stack are the **core** — one
lane's transactions end to end, verified and persisted by identity; step 6 the second stack;
step 7 the flip. A core left incomplete stops the line. Step 6 and 7 re-place by name (§5) to
1.8.1 with the reason, and the SIP's status follows the evidence, never the calendar.

**Non-droppable.** The core.

### 3.4 Lane S — the Cycle Evaluation Scorecard, the 1.8 slice

After rev 2's acceptance (§3.1). Four deliverables, one PR each unless a seam forces two:

| # | what lands | how it is proven |
|---|---|---|
| a | **`CycleAssessment`** as a pure projection over `CycleOutcome` in `src/squadops/cycles/` beside `cycle_outcome.py`: the four dimensions (outcome, quality, coordination, efficiency) with **measurable indicators each of which is a reference into the record** — verdict and criteria coverage, correction rounds and re-dispatches, contentless emissions and refunds, framing re-rolls, tokens and wall-clock from the generation records (#929 made every call visible); computed on read, never stored as truth; **no agent in the path** | an architecture test: the projection performs no I/O and reads only `CycleOutcome` and the record; every dimension's evidence refs resolve on every 1.7.5 record |
| b | **one failure-attribution registry** — the SIP's seven categories become derivations over the vocabularies that exist (§2.2), declared in one registry with governance attributes in the #730 shape (declaration required, drift-guarded), and the plan-rejection classes, winnability classes, `FailureEvidenceCategory`, `FailureLocus` and the movement tokens each map to exactly one attribution id | a drift test that fails on a vocabulary value with no mapping; **no new string literal for a failure class anywhere else** |
| c | **the benchmark registry** — the counted rolls 1.6.3 through 1.7.5 (seventy-nine, from the stored per-roll records and the vault) re-graded deterministically, with each row carrying its lineage (#80's fields where they exist, the set's pins where they do not); replay-first, no new cycle (SIP-0101's records are an input, not a completion) | the re-graded 1.7.5 rows agree with the record's headline table; the preflight step (§7) states which of the seventy-nine are re-gradeable and why the rest are not |
| d | **the comparison harness** — the verification-set driver gains an *arm* axis (squad profile × request profile × model) and the pre-registration a comparison section; the **single-model arm** is what rev 2 defined; **one pre-registered squad-versus-single-model window** on `group_run`, N declared before roll 1, both arms on the same frozen deploy, graded by (a) with attribution from (b) | the window closes with its result stated in the record whichever way it goes — a negative never blocks the cut; an unrun window blocks it **only while (d) is in 1.8.0's scope at the loop set's pre-registration** (§3.9, §4.2) |

**Dependency distinction.** (a) and (b) are the judgement contract 2.0 consumes — Campaign's
prerequisite. (c) and (d) test and accumulate evidence *about* that contract; Campaign does not
depend on their completion, and neither does the cut's thesis. That is why (a) and (b) are
non-droppable, why (c) and (d) can move to 1.8.1 (§5), and why an unrun window blocks the cut
only while it is in scope (§3.9).

**Out of the slice, named so silence is not read as shipped:** the console Scorecard page
(SIP-0069's, later), rule-based recommendations, profile-weighting, any LLM in the assessment
path, and internal eval packs beyond what (a)–(c) need — the ROADMAP's "Dev, QA, Research,
Tool Executor" packs are rev 2's to keep or move, and this plan's recommendation is that they
move to 2.0 with the Campaign that would run them (§8 decision 4).

**Non-droppable.** (a) and (b) — a 1.8 without an assessment over honest evidence has a false
thesis. (c) and (d) may move to 1.8.1, together or independently, by a plan revision in the open
made **before the loop set's pre-registration is committed** (§5, §7 step 9); after that commit
the cut criteria are fixed and do not move.

### 3.5 The rails — two, not three

| rail | what lands | the rule it follows |
|---|---|---|
| **the lineage seam** | `series_for(cycle) -> SeriesKey` extracted from `inert_detection.py` into one module; inert detection and `CycleAssessment`'s baseline comparison read it — a stable consumer contract; Campaign in 2.0 may enrich the derivation behind it with its objective envelope, and no consumer migrates | intention 1 (one cycle-lineage identity); the mirror rule on the extraction (what inert detection's walk produced and who read it) |
| **the B1 baseline, emitted** | `emit_rejection_baseline.py` run over the thirteen recorded cycles and every counted roll since, committed beside this plan's record as the pre-memory picture — recurrence per class per cycle, and time-to-resolution — with the post-1.6.2 emptiness stated as a finding, not hidden as a zero — a finding about the proving workload, not about memory's value (§2.3) | intention 5; the 1.6.0 plan's B1 |

**The recall port is 2.1's, not a 1.8 rail** (§2.3, §8 decision 2). Its constraints — an inert
NoOp that answers *empty* (`NoOpMemoryPort`, `adapters/noop/ports.py:81`, raises: a guard
against accidental use, not an inert port); the root injecting it explicitly until a real
adapter earns a factory and a required selector (`docs/architecture/composition-roots.md` §8);
the call site extending `plan_rejection_context`'s source with the rendered prompt pinned
byte-identical under the NoOp — are recorded in the SIP's placement note so they survive this
plan's supersession.

### 3.6 The hardening list — CI-verified, in neither deploy's cycle path

| step | item | what lands | in the image? |
|---|---|---|---|
| 1 | **#1448** | the routes read their ports through `Depends` from `request.app.state`; the twenty module-level `_<port>` globals and their `set_*` retired (mirror rule: what each produced and who consumed it); two runtime apps in one process isolated | the runtime-api, start-up and request path — **not the cycle path**; a wiring failure is a 500 on the pair's first `cycles create`, the exact signature 1.7.5's deploy-B refusal taught (#1494/#1495), so the pair reads it |
| 2 | **#1449** | the eighteen factory selector defaults removed across eleven modules; every caller names its provider (the composition-roots standard §5 says every root already does) | **classified**, like #1180 was: its failure is a start-up `TypeError` on a root, distinct from every roll readout |
| 3 | **#1039** | the docs site's design pass — the architecture and cycle-flow diagrams, and the screenshots the release packages now ship (v1.7.5 is the first with any) | no — docs only |

Three items, deliberately: the headlines take the capacity the 1.7 lines gave to their lists.

### 3.7 The ops rider and the idle box — after the counted set, never between the checkpoint and it

| item | what | read where |
|---|---|---|
| **#1177** | the Atlas replay scripts routed through `arm.sh` so both arms cannot be resident at once (carried from 1.7.5 §7 step 12, not done) | on the box, after the set |
| **#176 recipe 2** | one `smoke`-squad launch (§3.1) | after the set; the invariants read; the issue closes |
| **#1176** | the experiment's cheap gate first: whether the served chat template accepts prior-turn thinking at all; if it strips it, the answer is recorded and the issue closes; if not, the cost is measured on one stored repair chain before any framework change | after the set; nothing lands in the framework from it in this release |
| **#1408, #1412** | the Flash-Next plan-authoring replay; the Atlas content-loop diagnosis — both need the box to themselves; nothing goes to the vendor without the owner's explicit go-ahead | after the set, on the same harness and gate as #1184's measurement |

### 3.8 The count this release owes the record

| item | release plans that scheduled it | times, incl. this plan |
|---|---|---|
| #567, #579 | 1.5.0, 1.7.0, 1.7.3, 1.7.4, 1.7.5, 1.8.0 | **6** each — #579 lands (§3.2); **#567 to 1.9 by decision** (§6) |
| #353 | 1.7.0, 1.7.2, 1.7.3, 1.7.4, 1.7.5, 1.8.0 | **6** — **to 1.9 by decision** (§6) |
| #176 | 1.7.0, 1.7.3, 1.7.4, 1.7.5, 1.8.0 | **5** — recipe 1 landed; recipe 2 closes here |
| #598 | 1.7.1, 1.7.4 §6a, 1.7.5 (reversed to the 1.8 lane), 1.8.0 | **4** — lands as a rendering (§3.2) |
| #1213, #1176, #1122 | 1.7.3 §6, 1.7.4 §6, 1.7.5 §6, 1.8.0 | **4** each — #1213 closes with §3.3 step 4; #1176 is an experiment (§3.7); **#1122 not scheduled** (§6) |
| #80, #949, #950, #194, #1039, #1031 | held "in the 1.8 lane" by 1.7.0 §3.1, 1.7.3, 1.7.4, 1.7.5; 1.8.0 | **5** each — #80 and #1039 land; #949, #950, #194, #1031 disposed of by name (§6) |
| #414, #557, #316 | "at design review" in every 1.7 plan; 1.8.0 | **5** each — #414 answered inside the SCR review; #557 stays; #316 moves with Campaign |
| #1443, #1444, #1448, #1449 | 1.7.5, 1.8.0 | **2** each |
| #1469, #1499, #1501, #1506, #1507 | 1.8.0 | **1** each |

Two items are on their sixth plan and leave this release by decision rather than land. Four
that were "held in the 1.8 lane" for five plans are disposed of here by name.

### 3.9 The cut criterion — three gates, so "landed" never stands in for "proven"

The version is gated by its headline SIPs, per the even-minor convention. Each SIP's status at
the cut follows its own evidence:

| gate | criterion |
|---|---|
| **implementation** | both SIPs accepted before their first feature PR; #1444 merged before §3.3 step 1; every §3.2 row merged and read on the pair; §3.3's core merged; §3.4 (a) and (b) merged, (c) and (d) merged or dropped by a plan revision naming the destination; §3.5's two rails merged; §3.6 merged or dropped |
| **experimental** | **L1 holds**; **§39.8's N scoped repair transactions observed across both stacks and every producer lane with zero** outside-grant changes, post-verification drops, identity mismatches, preservation violations, or restorations on a successful scoped transaction — N fixed in the pre-registration, its diagnostic share stated (§4); **the #598 prediction holds**; **every registered diagnostic reaches its seam on the pinned deploy**, F1 included; **the comparison window closed with its result stated, if (d) is in 1.8.0's scope at the loop set's pre-registration** — a negative result never blocks the cut; an unrun window blocks it while (d) is in scope, and is not a criterion once (d) has been re-placed to 1.8.1 by a plan revision in the open before that commit (§3.4, §5); a falsified prediction or an unreached seam stops the set and the plan is revised in the open, not amended after |
| **evidence** | every counted record carries a `CycleAssessment` whose attribution is a registry id and whose every dimension cites evidence that resolves; every field in the three-state vocabulary; the record reconstructs every counted/void/reset boundary from per-round evidence; deploy-to-tag drift named item by item, expected zero under `src/` and `adapters/`; the package captured with its screenshots — the showcase this release is **a scoped repair**, a delivered app plus the flow-run timeline where the correction round is legible, chosen and explained per rule 3 |

**The SIP sweep at the cut, stated now so the sweep does not read silence as shipped:** Scoped
Code Revision → `implemented` if §38 steps 1–7 land and §39 holds; otherwise `accepted` with the
open steps named (SIP-0102 precedent). The scorecard → `implemented` if rev 2 narrowed its
normative text to the slice and (a)–(d) land; if (c) or (d) moved to 1.8.1, `accepted` with
exactly that named — and 1.8.1's plan says it carries a measurement window (the 1.6.3 precedent)
rather than reading as a fix line. SIP-0105 amended by #598, status unchanged. Nothing else moves; §6 names what stays.

### 3.10 Merge discipline

One PR per row; `--head` on every PR; every job of main's run read after every merge; the seam
table in every PR that binds, removes or re-weights a check (#1501, #598's guard); the mirror
rule on every removal (#1448's globals, the lineage extraction); the characterization tests in
the same PR as the seam they characterise; the harvest before every extraction (#1444, the
lineage seam); **acceptance before the branch** for both headlines; **§5a amendments in the SIP,
in the PR that diverges** — not in this plan, which is superseded at the cut; **no merge to main
while a set or the comparison window is open**; a committed golden moves only with the owner's
prior clearance (#1499). The plan's own PR carries the ROADMAP pointer and the 1.7.5 plan §10
amendment.

---

## 4. The verification set — the loop's set, then the comparison window

Two windows, kept separable so a red in one never reads as the other's.

### 4.1 The loop's set — 6 + 3 on one frozen deploy, the fifth consecutive at that size

**Bar.** **L1** (#1268), unchanged: blocking on a counted roll whose contentless emission is not
recovered; the count tracked, never quoted as zero. It stays because it is the condition every
other reading is measured through, and because the headline changes what a repair *emits*.

**Live predictions:**

| claim | method | falsified by | what a clean set proves |
|---|---|---|---|
| **the revision invariant** (Scoped Code Revision §39.8): across every attempted repair transaction — counted rolls and diagnostics together — zero outside-grant changes, zero post-verification drops, zero candidate/persisted identity mismatches, zero preservation violations, zero restorations on a successful scoped transaction; **at least N scoped transactions observed**, N fixed before roll 1 | the per-repair readout: which resolver each transaction used (structural / anchored / region / whole-file), non-execution counted beside failure, per lane, per stack | one of the five defect classes on any transaction; **or fewer than N transactions, which is a budget failure the record states, not a pass** | that the contract holds where it was exercised — on this deploy, these stacks, these lanes — and nothing about repairs no roll or diagnostic produced |
| **the rendered packaging** (#598): zero `container_packaging` findings on the accepted emission of every counted roll | the check's rows per roll | one finding on an accepted emission | that the rendering is what the boot audit builds and that the builder no longer authors it on this deploy |

**The budget the first prediction actually needs, stated before roll 1.** 1.7.5's nine counted
rolls attempted five repair rounds in total, all on two rolls, both in the qa lane on one stack.
A counted set of the same shape yields roughly that again. So N is met by construction only if
the diagnostics supply the rest, and the pre-registration must table it: for each lane (qa,
dev, builder) on each stack, the fault that forces a repair, the transactions it is expected
to produce, and the sum against N. **A dev-lane fault does not exist today** — the registry
(`fault_injection.py:252–:299`) carries three `qa.test` faults, one `qa.test_repair`, one
`builder.assemble` and one `data.analyze_failure` — so one is registered in the prelude from a
shape a real roll produced (1.6.3's join-probe response floor failure, `participants` as bare
strings where the manifest declares a list, is the recorded candidate), and step 3 of §3.3 is
not proven live without it.

**Seam invariants — proven on the pinned deploy, no amendment.** The five 1.7.5 diagnostics
re-registered under a `1.8/` prefix, with `contentless-builder` now **two** (#1506: R1 at
`FIRST_ATTEMPT`, F1 at `ALL_EMISSION_ATTEMPTS`), and the dev-lane diagnostic above — **seven**
configs, a two-run budget each, recorded with the entry point each used. A seam not reached
after two runs stops the set. The #1501 fixture is CI; a live churning-set occurrence is texture.

**CI invariants, read live as texture:** the rewind invariant (W1), the locus invariant (D1),
the derived-rows invariant (F1 — now also live, above), the untouched-file rule (#1406).

**Texture — observed, never blocking, every field with its unaskable state declared before
roll 1:** the resolver mix per repair; emitted bytes and tokens per repair against the 1.7.5
whole-file figures (supporting evidence, not a gate — the draft's §39.8); correction rounds and
termination reasons (#1501's new one by name); `dl` styling in the boot audit's screenshot;
packaging rows; framing-run verdicts; fill-mode completion tokens; generation records per call
(#1206, expected equal); the three #80 fields on every record; **the `CycleAssessment` on every
record, with its attribution id** — texture here, the evidence gate's subject in §3.9.

**Shakeout loop** (`docs/plans/verification-sets/README.md`): deploy A one checkpoint pair (a
red is the prelude's); deploy B enters the loop — exit on a pair with no new seam finding,
**budget three pairs**; the record reports rounds taken and rounds attributable to the
headlines. **Early stop, one direction:** a falsified prediction or an unreached seam stops the
set; a good result never stops it early; a stop in one arm does not stop the other.

### 4.2 The comparison window — the scorecard's first question

A **separate pre-registration**, after the loop's set closes and on the same frozen deploy if
nothing has moved (else on its own, with the drift named): the squad arm is the loop set's own
React rolls where the pins allow, the single-model arm is what rev 2 defined, N per arm
declared, both graded by `CycleAssessment` with attribution from the one registry. The
question is pre-registered in the record's words — *at equal scaffolding and declared cost, does
the squad's assessment exceed the single model's on outcome and quality, and at what efficiency
cost?* — and the answer is stated whichever way it goes. **A negative is a result; it is 2.0's
problem and the thesis's, not this cut's. An unrun window blocks the cut while (d) is in 1.8.0's
scope; once (d) has been re-placed to 1.8.1 in the open, before the loop set's pre-registration,
the window is 1.8.1's criterion and not this cut's (§3.4, §3.9).**

**Drift the record must declare:** intended zero under `src/` and `adapters/` — the tag is the
measured deploy plus the pre-registrations, the records, the baseline and the package.

---

## 5. Capacity — what drops first, and what cannot

The 1.7.0 plan §3.1's ceilings, applied: **roll-verified items** — the revision invariant, the
rendered packaging, and #1499 as texture — three against a ceiling of six to eight, because a
headline's prediction has the width of six; **CI-verified issues** — #1444, #1501, #1506, #80,
#579, #1448, #1449, #1039, #1213 (closing with step 4), the lineage seam — ten, inside ten to
fifteen; plus two design reviews, two acceptances, one SIP amendment
(#598), three verify-then-closes, the baseline, and the comparison window's own
pre-registration.

**Calibration, as counts:** 1.6.0, the last even minor, carried two headlines from plan to tag
across two weeks and then needed six patch lines; the 1.7 line cut six releases in eleven
days. This plan's headlines are each larger than 1.6's individual tracks. The line closes when
§3.9 holds, and the calendar does not vote.

**If capacity forces a drop**, in this order, each to 1.8.1 by a plan revision in the open — and
for §3.4 (c) and (d) **before the loop set's pre-registration is committed**, so the cut criteria
never move after roll 1:
§3.4 (d) the comparison window → (c) the benchmark registry → §3.3 step 7 → step 6 → §3.6 in
reverse (#1039, #1449, #1448). **Non-droppable:** the prelude (§3.2), #1444, §3.3's core,
§3.4 (a) and (b), the two rails (§3.5), the verify-then-closes and the two reviews. If capacity
cannot carry these, 1.8 does not cut, and the plan says so rather than re-placing a headline.

---

## 6. Re-placements by name — nothing silently carried

Thirty open issues after the two this plan filed. **Twenty-two are in this release** (§3.1–§3.7:
#1444, #1149, #1443, #176, #1506, #1501, #1499, #80, #579, #598, #1213, #1448, #1449, #1039,
#1177, #1176, #1408, #1412, #414 (answered by the review), and the rails' and headlines' own
work; #1469 stays blocked on the corpus #1468 is now producing and is read at the cut). The
eight that are not:

**#1507 — 1.9, the stabilization minor.** The executor's `execute_cycle` (396), `execute_run`
(325) and `_reject_invalid_plan_before_workload_gate` (301): the completion boundary Campaign
lands through in 2.0, extracted under the 1.7.5 map's rules before anything builds on it.
Not beside a loop headline. **Handed to the 1.9 plan as its exit criterion and to the 2.0 plan
as its entry condition:** the 1.9 line leaves one named, extracted cycle-completion boundary
through which Campaign can observe terminal state and request continuation. Campaign does not
begin by decomposing the executor.

**#567 and #353 — 1.9 by decision, their sixth plan.** The fenced parser's CommonMark engine
sits under the emission path every roll runs through, and the headline changes what a repair
emits — refactoring the parser before the revision contract settles is work done twice. The
manifest hash stamped at build is a SIP-0084 amendment on the agent's boot path, moving
runtime behaviour beside a headline. Both are legitimate debts; neither is central to a 1.8
contract; both can move behaviour. Re-placed with the reason, so the 1.9 plan names them or
revises this in the open.

**#316 — 2.0, with Campaign** (its Phase 2 dependency).

**#1031 — 1.9 by name.** The manifest-authoring primer moves framing behaviour; 1.8's measured
pack is the loop and the judgement, and a framing change beside them makes a red ambiguous.

**#949, #950, #194 — SIP-0093's completion, at design review, unchanged.** The scorecard's
"what happened" question overlaps #950's review-packet synthesis; rev 2 notes it as a later
consumer and builds nothing for it.

**#557 — at design review, unchanged.** A SIP-first item by its own text; the review runs after
Scoped Code Revision settles what a repair *is*.

**#1122 — not scheduled.** Scoped Code Revision's §39.7 works across both current scaffold
styles, so SIP-0104 for stack #1 is not its precondition; it stays with SIP-0104, which stays
`accepted`.

**Campaign Orchestration (2.0's headline) and Cross-Cycle Memory (2.2) — §2.3, §8 decisions 1 and 2, ruled.**

**The SIP re-read the 1.7.5 plan §6 promised** (the runtime-modes cluster and the accepted
SIPs that carry open parts), so the sweep at the cut does not read silence as shipped:

| SIP | state on main | this release |
|---|---|---|
| SIP-0088 (umbrella) | children 0090 Phases 2–4 and 0091 untouched since the 2026-08-03 audit; the Embodiment Runtime direction is a post-1.8 extension SIP by the owner's own sequencing ("no second live runtime before the FAY baseline is banked" — it is banked; the SIP is still to be drafted) | stays `accepted`; no 1.8 work; target set with the 1.9 and 2.0 plans, not here |
| SIP-0090, SIP-0091 | Phase 1 shipped 1.2.0; the rest and all of 0091 zero code | as above |
| SIP-0092 | M3 unimplemented; M2 partial on 93.4 | **#1444 executes its `handle()` decomposition direction** (re-authored against main, as the direction requires); the rest is not 1.8 work; stays `accepted` |
| SIP-0093 | 93.4, §5.8 merge rules 2–5, two required tests | #194/#949/#950 at design review; stays `accepted` |
| SIP-0101 | minimum slice shipped in 1.5 | its records are an input to §3.4 (c); a consumer, not a completion; stays `accepted` |
| SIP-0102 | steps 3–7 open | **step 5** (clean-room verdicts into SIP-0096's derivation) is a scorecard input rev 2 must name as present or absent; #598's rendering is a §4.2 consequence landing in §3.2; stays `accepted` with the steps named |
| SIP-0104 | #1122 | stays `accepted` |
| SIP-0105 | the blueprint rewrite after #1131 | **amended by #598** (the rendering); stays `accepted` |

---

## 7. Sequencing

1. **This plan**, on its own PR, with the ROADMAP's 1.8 row pointing here and the 1.7.5 plan
   §10 amendment. Merges on the owner's review, with §8's rulings recorded in rev 2.
2. **The Scoped Code Revision design review** — the owner, the fixed vocabulary, the draft's §43
   plus #414 and the stack order; its outcome on PR #1325; **acceptance** (`update_sip_status.py`
   … `accepted`, the number assigned, the branch not before). In parallel: **the scorecard SIP
   rev 2**, then its review and acceptance.
3. **Verify-then-close** #1149, #1443; #176's recipe 2 waits for the idle box. **#1444**, the
   first extraction, harvested first.
4. **The prelude** (§3.2), one PR each in order — #1506 and #1501 first, #598 last (its SIP-0105
   amendment before its code) — and the **dev-lane fault** registered.
5. **Deploy A; one checkpoint pair** — a red belongs to the prelude; every driver field
   re-checked in the three-state vocabulary; the #598 prediction's first reading; #1506's two
   diagnostics reachable.
6. **The headlines** — Lane M by §3.3's order, Lane S by §3.4's — and **the hardening list**
   (§3.6) riding in CI beside them. Each SIP amended in place where implementation diverges.
7. **Deploy B; the shakeout loop** to the exit rule, budget three pairs — a red belongs to the
   headlines, because nothing else that can move runtime behaviour is on this deploy.
8. **The seven diagnostics on the pinned deploy**, two-run budget each. A seam not reached stops
   the line here.
9. **Pre-register the loop's set** — pins from the last shakeout; N fixed with its diagnostic
   share tabled; every field's producer and unaskable state as schema properties; **the scope of
   §3.4 (c) and (d) fixed at this commit** — after it the cut criteria do not move.
10. **Counted set 6 + 3** — no merges to main while it is open; the boundary reading at each roll.
11. **Pre-register and run the comparison window** (§4.2) — the same discipline; nothing merges.
    If (d) was re-placed to 1.8.1 before step 9's commit, this step is 1.8.1's.
12. **Close both; the live reads and the idle box** — #1177, #176 recipe 2, #1176's gate,
    #1408, #1412 — after, never between.
13. **The preliminary measurement conclusion**: §3.9's three gates read against the frozen
    deploy before anything else moves; the SIP sweep decided on that reading.
14. **Final record; cut 1.8.0 by the seven steps** — re-authenticate immediately before the
    capture (the 1.7.5 lesson), the preview read before `--write`, the screenshots of a scoped
    repair, zero drift named. **Then the 1.9 plan**, whose subject is the executor's completion
    boundary (#1507) and the debts §6 re-placed — the close of the 1.x line — so that 2.0 can
    open on Campaign.

The key property of this order: acceptance precedes every feature branch; the prelude and the
headlines are on different deploys with a checkpoint pair between; the diagnostics that supply
most of N run on the deploy the numbers come from; and the two windows never share a red.

---

## 8. Decisions made by recommendation — the owner overrules, not fills in

1. **Campaign Orchestration → 2.0 as its headline; its lineage rail in 1.8. Ruled by the owner,
   2026-09-12.** Rationale §2.3; the rail §3.5; the 2.0 entry condition §6. Rev 1's alternative
   (accept Campaign now, its Phase 1 as the rail) is closed. The former 2.0 pillars sequence
   behind Campaign in the 2.0 plan; the ROADMAP's 2.0 row is rewritten in this PR.
2. **Cross-Cycle Memory → 2.2; its integration rail → 2.1; the B1 baseline in 1.8. Ruled by the
   owner, 2026-09-12.** Evidence and rationale §2.3, which also states what the post-1.6.2 zero
   does and does not say; the rail's constraints §3.5. 2.1 re-reads Phase 1's proving workload
   before 2.2 activates the mechanism.
3. **Scoped Code Revision and the scorecard slice are the two headlines, by lane.** **Ruled by
   the owner, 2026-09-12.** Rev 1's alternative — the row as written, the scorecard and
   Campaign — is closed by the ruling. The loop's loss mode is measured and current (§1), the
   design is in hand at 1,143 lines with its acceptance criteria written, and Campaign's policy
   has nothing principled to continue on until the grades exist.
4. **The scorecard's 1.8 slice is headless and mechanical**: no console page (SIP-0069's, later),
   no recommendations, no agent in the assessment path, the four internal eval packs to 2.0
   with the Campaign that would run them. Rev 2 narrows the SIP's normative text to match, so
   the SIP can be `implemented` at this cut rather than staying `accepted` for a page.
5. **The single-model arm is rev 2's to define, and the comparison window is a separate
   pre-registration** from the loop's set, so a defect in either is attributable to one. Its
   result never blocks the cut; its absence does **only while (d) is in 1.8.0's scope at the loop
   set's pre-registration** — (d) may be re-placed to 1.8.1 before that commit (§3.4, §5).
6. **#598 lands as a SIP-0105 amendment plus the rendering, in the prelude, roll-verified** —
   the owner's 1.7.5 ruling executed, not re-opened. The builder's role contract (SIP-0071) is
   amended in the same PR that stops it authoring the files.
7. **#567 and #353 go to 1.9 by decision; #579 lands here.** Sixth plan for all three; the two
   that move runtime behaviour beside a headline leave, the pure extraction stays.
8. **#1031 to 1.9; #1122 not scheduled; #949/#950/#194/#557 stay at design review** — each with
   its reason in §6.
9. **v1.7.4's release page is missing twenty-five PRs** (the squash-merge blindness #1504 fixed
   applies from v1.7.5 forward). Packages are immutable evidence. **Recommendation: annotate,
   do not regenerate** — a one-line note on the page naming the count and the fix, because a
   regenerated page would claim a capture the deploy can no longer supply. The owner rules.
10. **#414 is answered inside the Scoped Code Revision review**, not left at design review a
    sixth time: the draft's §22 and #414's priority reserve draw on one pool.
11. **N for the revision invariant is fixed at pre-registration with its diagnostic share
    tabled** — the 1.7.5 evidence says a counted set alone cannot reach any honest N.
12. **When the memory recall port ships — 2.1, not this one — its NoOp
    answers empty rather than raising** (§3.5): `NoOpMemoryPort` today raises
    `NotImplementedError` on every call, a guard against accidental use, not an inert port.
    Recorded here and in the SIP so it survives this plan.
13. **The lineage seam is extracted, not designed** — it is inert detection's existing series
    walk given a name and a second reader; Campaign replaces its implementation in 2.0.
14. **Both design reviews have one reviewer and one vocabulary**, and acceptance precedes the
    branch — a feature PR opened against a proposed SIP is closed unmerged.

---

## 9. Findings from the review that produced this plan

Named here so they are not the next line's §6a. Each has a home above or a fix in this PR.

- **The 1.7.5 amendment's remedy pointed at a closed issue** — plan §3.9a "tracked on #1374";
  #1374 closed 2026-09-08 with no comment. Filed as **#1506**; the 1.7.5 plan §10 gains the
  pointer in this PR.
- **#1152 closed with a named remainder in a PR body only** (PR #1491: "the issue stays open with
  that remainder named" — it did not). Filed as **#1507**.
- **#1443 and #1149 are done and open** — `run_correction_protocol` at 151 lines, the register
  at entry 38. Verify-then-close (§3.1).
- **The ROADMAP's Stats header still reads "As of 2026-09-07 (v1.7.3)"** two cuts later — the
  1.7.5 plan §9 said the next ROADMAP edit would fix it and the 1.7.5 cut did not. Fixed in this
  PR, with the measured counts and their date. **The "Accepted (Next Up)" table** still listed
  SIP-0103 (implemented 2026-08-21) and omitted SIP-0104 and SIP-0105; brought to the state §6's
  re-read found.
- **The B1 baseline was recorded and never emitted**, and its inputs stop on 2026-08-23. Emitted
  in §3.5; the emptiness is decision 2's evidence.
- **`plan_rejection_context` is declared on six task types on main**, not the three the
  reconciliation counted in August — the recall call site, when it ships in 2.1, has twice
  the reach the design assumed, and its wiring test must enumerate all six.
- **No dev-lane fault exists**, so Scoped Code Revision's largest exposure (the unused
  `WriteGrant.for_dev_fill`) has no diagnostic today. Registered in the prelude (§4.1).
- **The scorecard SIP describes a console feature, not the slice** — rev 2 before review (§2.2).
- **The god-file measurement, 2026-09-12, main `3d18130b`:** the executor 4,741 lines with its
  three largest methods at 396/325/301 (#1507); the correction runner 1,331 with its largest at
  151 (no action); `qa_test.py` `handle()` 617 and `develop.py` `handle()` 332 (#1444);
  `patch_verification.py` 863 with `verify_patched_artifacts` at 207 and `task_plan.py` 1,397
  with `generate_task_plan` at 240 — both still watch items, no dominant unit.
- **The CLI token expires between login and capture** (the 1.7.5 cut's second hollow capture).
  CLAUDE.md step 7 does not yet say to re-authenticate immediately before capturing. Not this
  PR's; named so it is written before the next cut.

---

## 10. Revision history

- **Rev 3 (2026-09-12, later the same evening)** — on a written tightening review of rev 2, six
  of its ten points taken. **One contradiction fixed:** §3.4 and §5 made the comparison window
  droppable to 1.8.1 while §3.9 and §4.2 said an unrun window blocks the cut; now an unrun window
  blocks only while (d) is in 1.8.0's scope at the loop set's pre-registration, the scope of (c)
  and (d) is fixed at that commit (§7 step 9), and the sweep names 1.8.1 as a measurement patch
  line when they move. **Made explicit:** (a)/(b) are Campaign's prerequisite and (c)/(d) are
  evidence about it (§3.4); the memory rail's home is **2.1**, which also re-reads Phase 1's
  proving workload (§2.3, §3.5); the 1.9 completion-boundary extraction is 2.0's entry condition
  (§6); the lineage seam is a stable contract whose derivation Campaign enriches, not an
  implementation it replaces (§2.3, §3.5); the post-1.6.2 zero is a finding about the proving
  workload, not about memory's value (§2.3, §3.5). **Compressed:** a ladder block in the opening,
  §8 decisions 1–2 reduced to pointers at §2.3, §3.5's restatement cut. Declined from the review:
  a composition-root *selector* in 2.1 (with only a NoOp there is nothing to select — the
  selector arrives with the first real adapter, per the composition-roots standard) and 2.1/2.2
  rows on the ROADMAP beyond naming 2.1 inside the 2.0 row. No change to the headlines, the set,
  the gates' substance or the rulings.
- **Rev 2 (2026-09-12, the same evening)** — the owner's rulings on decisions 1–3 recorded:
  Campaign Orchestration to **2.0 as its headline** (rev 1 recommended the next even minor),
  Cross-Cycle Memory to **2.2** (rev 1 recommended 2.0), Scoped Code Revision and the scorecard
  slice the two headlines; the 1.x line closes on 1.8 and its 1.9 tail. Consequences applied:
  the memory recall port leaves the prelude and §3.5 (a port with no consumer for two even
  minors), leaving two rails — the lineage seam and the B1 baseline; the ROADMAP's 1.8 and 2.0
  rows and the three proposed SIPs' target lines are rewritten in the same PR. No change to the
  headlines' content, the set, the gates or the attribution structure.
- **Rev 1 (2026-09-12)** — written the day v1.7.5 was tagged, on the owner's ask, from the
  ROADMAP's 1.8 row, the post-1.5 reconciliation, the 1.7.5 plan and record, the 1.6.0 plan's
  B1, the three proposed SIPs the row names, the Scoped Code Revision draft on PR #1325, and
  every open issue (twenty-eight, every one placed by name; #1506 and #1507 filed with it).
  Structure: two headlines by lane behind their design reviews and acceptances, a prelude on
  deploy A behind a checkpoint pair, the three rails, a three-item hardening list, two
  verification windows kept separable, fourteen decisions by recommendation — the first three
  of which reshape the ROADMAP row and are the owner's to rule.
