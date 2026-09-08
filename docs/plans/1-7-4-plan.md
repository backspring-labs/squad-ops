# 1.7.4 — plan

**Revision 2, 2026-09-07.** Written the evening the 1.7.3 line closed, from the 1.7.3 plan (rev 4
§6, §8, §9), the 1.7.3 record (`docs/plans/1-7-3-verification-set-record.md` §0, §5, §8), the
1.7.2 plan §8/§8a and record §8, the 1.7.0 plan §3.1 (as amended by the 1.7.3 plan) and §6.2,
the ROADMAP's 1.7 identity, and the issues the 1.7.3 line filed and placed here (#1369, #1372,
#1373, #1374); revised the same evening on the owner's review (§9).

**1.7.4 closes the recovery half of Loop Honesty.** A failed attempt must produce an accurate
fact, a correction must be composed only from accepted state, and accepted repaired state must
survive the remainder of the cycle. The release removes the unused builder-to-qa handoff that
has become the dominant live rejection cause, makes contentless emissions retry with their
actual failure fact, and closes the remaining recovery seams carried from 1.7.2. **The contract
is three-part — truthful failure → truthful correction → durable repaired state** — and every
row of the core pack is tested against that sentence. It is the last behavioural line of 1.7;
1.7.5 closes the line with Composition Root and the deferrals. The infrastructure rider rides
beside it, split by whether it can touch the environment a cycle runs in (§3.3).

Rules carried from 1.7.3 without discount, and three added at this review:

- **a measured pack and a rider do not land on one deploy without a checkpoint between them**;
- **every registered readout maps to a typed evidence field, or an explicit structured
  evidence relation, before the set opens, checked against a real record** — a producer in
  the loose sense (a LangFuse prompt read by hand) is not a field; 1.7.3's B1 was read by grep
  and that is the example that defines this rule;
- **no fault, no prediction** — a claim no counted roll is likely to reach is proven by a
  fault or a CI invariant and reported as texture, never registered as a live hypothesis that
  reads green by absence (1.7.2's lesson, applied uniformly this time);
- **rolls measure emergent behaviour; faults prove reachable seams; CI proves deterministic
  mappings** — §4 sorts every claim into one of those, plus texture.

---

## 1. What the 1.7.3 line says the release has to be

| what the line showed | evidence | what it says about this release |
|---|---|---|
| the builder's short first emission is the loop's live rejection cause: two of six counted React rolls began with a Dockerfile-only emission of 373 and 642 tokens (normal 1,391–2,382); one recovered, one did not; with the two shakeouts and the void roll, four of the last nine React builder first emissions on the line were short, at the same prompt size | 1.7.3 record §1.1, §5 | **#1312 with #1254 leads, as the 1.7.3 plan §6 placed it.** The builder's repair also emitted ten unaddressed fences on roll 1 — the same emission-shape class from the repair side. The rate (1.7.2 one in seven, 1.7.3 two in six counted) is why the line carries an explicit contentless-builder fault; it is **not** a prediction of what the counted set will show, because #1312 changes the output contract that rate was measured under (§4) |
| two void counted rolls in two lines on one mechanism: the accepted-patch path composes a corrected result from whatever rows an earlier stage happened to write, and #1318 then #1364 each patched one gate | 1.7.2 record §0; 1.7.3 record §0, §4.1 | **#1374**: every framework row a task's contract declares is derived from the accepted candidate by contract. Design first, then the fix, then the fault that exercises it — a contentless builder attempt has no fault today and was reached only by chance |
| the one contentless emission of the line was the builder's, and the builder has no emission-retry path; the qa retry re-rolls blind | 1.7.3 record §0, §2 | **#1372**, the retry-with-fact backstop 1.7.2 §8a named and did not build: one mechanism for every producer, read as a new texture field |
| the shakeout loop reported as two numbers: three pairs, zero attributable to the sixteen items; every supersede came from the instrument or the loop's own accounting; two readouts had been wrong for a whole line (the kind gate, the pytest own-frame fault) | 1.7.3 record §0 | the instrument is proven on its own deploy before the pack's first PR (§7), and **a readout that cannot see its own miss is a finding** (1.7.2 §7) — §4 asks that question of every new claim before roll 1 |
| main's integration job was red for six merges before it was read — not a required check | 1.7.3 record §4.6 | **`integration` becomes a required check** (§3.1) — a repository control-plane invariant, proven from the protection configuration, not waited for |
| #1285's producer exists (#1334); the reading: qa emissions cost ~10.2k completion tokens each in fill mode (Next.js) against ~5.8k on React, reasoning characters in the same ratio, `reasoning_tokens` unreported on every one | 1.7.3 record §5, §8 | the fill-mode cost is visible and roughly double; **ruled material** (§8) — Q1's half is built here |
| B1 was read by hand: a grep over 43 stored suites, because the driver produced no field for it | 1.7.3 record §2 | a declared readout with no field is the #1285 shape again; **B1 gets a driver field** before this set opens, and the rule it defines is in the preamble |
| the release package's cycle count was the number of `--cycle` flags typed; the script labels in-place SIP amendments as moves and lists a PR twice | #1369; 1.7.3 cut | the rider carries #1369; the cut procedure in CLAUDE.md names the full cycle list as step 7's input |

---

## 2. Why this line, on the roadmap

- **The 1.7 identity has a loop half.** "Every port is actually a port" is 1.7.3's and 1.7.5's;
  the 1.7.0 plan §3.1 split Loop Honesty across 1.7.2 and this line because the recovery path
  is the part of the framework the 1.8 scorecard grades most directly — a grade over
  `CycleOutcome` is a grade over what the loop reported, and two lines have now shown the loop
  reporting a booting app as a failure.
- **The handoff is the design fault the last eight issues were symptoms of.** #1312's ruling
  (2026-09-05) names it: a required file with no consumer generates assertors, the assertors
  disagree, and every fix moves the disagreement. Removing the requirement removes the class.
- **1.8 needs the emission shape settled.** **Scoped Code Revision** (PR #1325; formerly
  Slot-Scoped Emission, and it explicitly subsumes #1213) is the 1.8 lane's headline; its
  design review runs beside this line (§7) so 1.8.0 opens with an accepted design rather than
  a draft. §6 names the evidence that review should carry from here.

**What it does not do, stated here rather than implied.** It does not touch the boundaries
(1.7.3 shipped them; 1.7.5 closes them). It does not build Composition Root (#301, 1.7.5). It
does not adopt Atlas (SIP-0106 stays accepted and not adopted until #301). It does not change
the reasoning budget (1.7.0's) except for #1285's second declaration, the stack seams (1.7.1's)
or the recovery-path seams 1.7.2 shipped, except where §3.2 says a seam lied.

---

## 3. The content

### 3.1 Preconditions — things that must simply be true before measurement starts

Two kinds, kept apart: a **control-plane invariant** of the repository, and the **instrument**
— the faults and fields every claim in §4 is read through. The instrument ships first and is
proven on a deploy built before the pack's first PR (§7), as 1.7.3 did with deploy A; the
instrument rounds are counted apart from the shakeout rounds.

**Control plane**

| item | what | exit criterion |
|---|---|---|
| **`integration` required** | the `integration` job joins `closing reference present`, `lint + regression` and `scaffold skeleton gate` as a required status check on `main`; CLAUDE.md's merge rule names it; the job's own comment saying it is safe to skip is rewritten | **deterministic, not waited for:** `gh api repos/backspring-labs/squad-ops/branches/main/protection` lists `integration` among the required contexts, **and a controlled negative check** — a throwaway draft PR carrying one deliberately failing integration test — shows the merge blocked, then is closed unmerged. The plan does not rely on a future accidental red |

**Instrument** — each row is a fault or a field, and each names the claim it serves (§4)

| item | what | proven by |
|---|---|---|
| **B1 field** | the driver reads the stored qa suites against the manifest's root-persisted entities into a `non_root_fixture_tables` texture field, so B1 is a record field rather than a grep | driver test on the 1.7.3 roll records (43 suites, zero mentions) |
| **`retried_with_fact` field** | the driver reads the emission-retry feedback lines for the fact (R1's readout), so the hypothesis has a field before the fix exists | driver test on a synthetic line and on the 1.7.3 void roll's stored lines |
| **the contentless-builder fault** | `builder_emission_contentless` in `FAULTS` (scope `first_attempt`, target the builder's assemble task) reproducing 1.7.3 roll 1's shape (160 tokens, no fences); its `seam_readouts` entry reads the six steps below | fault tests; the guard that every fault has a readout |
| **the rewind fault** (W1) | a develop first-attempt fault reproducing #994's own sequence — an emitted defect the acceptance check catches, so the task fails into correction, the repair fixes it, and the seam under test is what the rewind protocol then does with the accepted repair; scope `first_attempt` | fault tests; the readout pairs the rewind lines with `applied_patches` |
| **the analyzer fault** (A1) | a `data.analyze_failure` emission fault reproducing #968's shape — a factual claim about the source that the source refutes — so the correction decision is seen refusing to inherit it; the analyzer's emission seam is made to call the injector if it does not (an `UnreachableFault` today is a finding, not a blocker) | fault tests; the readout reads the checked-source rows #968 adds against the decision |
| **#1369** | the package script reads a SIP's status transition, not its path in the diff; the PR table de-duplicated | script tests; the v1.7.3 package re-rendered as a check, not re-committed |

**The contentless-builder diagnostic proves both the negative and the positive behaviour**, in
one deterministic sequence, so the #1374/#1372 seam is exercised together rather than as two
adjacent observations:

1. the builder's first attempt is forced contentless;
2. no false successful corrected result is composed from it;
3. the retry receives the actual emission-shape fact (chars, fence counts, the head);
4. the task's expected artifacts remain in the retry context;
5. a successful retry **replaces** the failed attempt rather than coexisting with it;
6. every framework row in the corrected result derives only from the accepted retry result.

Steps 2 and 6 are F1's exercise; 3 and 4 are R1's; 5 is the identity claim the 1.8 design
(§6) will need stated. A step the readout cannot see is a finding before roll 1.

**If an honest fault cannot be built** for the rewind or the analyzer seam, the claim it serves
becomes a CI-only invariant and is declared so in the pre-registration before roll 1 — it does
not become a live hypothesis (preamble, third rule).

### 3.2 The pack, in merge order — what this line is trying to prove

**The recovery transaction, stated once.** A recovery is one transaction:

`attempt` → `failure fact` → `correction` → `candidate` → `derived framework rows` → `accept / retry`

**A failed attempt must not leak stale state into a correction, and an invalid correction must
not be accepted without enough fact to retry.** #1312 governs what the builder is asked to
emit into the transaction's input; **#1374 governs candidate truth** (the rows a corrected
result carries derive from the accepted candidate and nothing older); **#1372 governs retry
truth** (a contentless emission's retry carries the fact of what it did); **#994 governs the
persistence of accepted correction truth** (an accepted repair survives the rest of the
cycle). Those four are the recovery contract. The next three are decisions the loop makes
*about* a failure — fidelity items, legitimate recovery work that does not define the contract.

**Recovery contract — the record's first question: did the recovery contract become truthful?**

| # | item | what | claim (§4) |
|---|---|---|---|
| 1 | **#1312 with #1254** | `qa_handoff.md` stops being required. The builder's deliverable becomes **`assembly_notes.md`: optional builder-to-qa context containing only assembly facts not already represented by the stack's deterministic contracts** — the environment contract's operation commands, the app invocation, the qa test namespace and the manifest. The exclusion list rendered from those declarations ("already supplied, do not restate") *enforces* that definition; it does not carry it. Both check surfaces go (`required_files` on the handoff, the planner's `regex_match`/`sections_present` family, #1254's doubled `harness_boundary`); `qa_test.py` gains a seventh, presence-keyed appendix that carries the notes when they exist; a derived guard over the registered stacks asserts the rendered exclusion list equals each stack's declarations. **Why one PR — the atomic invariant:** *there must never be an intermediate main state in which the old required handoff is gone but the replacement consumer contract is incomplete, or vice versa.* A main with the requirement removed and no appendix has a builder emitting notes nothing reads (the #1312 generator shape again); a main with the appendix and the requirement still on has two consumers of one file. The changes stay together for that reason and no other; the PR's Evidence states it. **The mirror rule on removal:** the 1.7.3 record says what consumed the handoff — nothing — and the PR's Evidence names every check row that disappears and who read it | **H1** (bar); **H2** (seam invariant, CI) |
| 2 | **#1374** | the accepted-patch path derives every framework row the task's contract declares (`required_files`, `tests_pass` via the retest, `frontend_build`, the two suite-integrity rows) from the accepted candidate tree, through the same rule the producing handler uses, and supersedes the failed attempt's rows with them — regardless of what the failed attempt carried; the seam table in the PR names which stage's rule derives each row and on which tree | **F1** |
| 3 | **#1372** | a contentless emission's retry carries its own emission-shape fact and the task's expected artifacts, at the shared emission seam, for every producer — the classes it covers are named below | **R1** |
| 4 | **#994** | a rewind after an accepted correction repair does not re-dispatch the task and discard the repaired state | **W1** (seam invariant, fault) |

**Recovery decision fidelity — the record's second question: did the remaining
recovery-decision debts close without disturbing the contract?**

| # | item | what | claim (§4) |
|---|---|---|---|
| 5 | **#995** | a task timeout mid self-eval banks the attempt's real history, not "zero response chars" | **T1** (texture) |
| 6 | **#968** | the failure analyzer's factual claims about source are checked against the source before the correction decision inherits them | **A1** (seam invariant, fault) |
| 7 | **#1054** | a correction decision naming dev task types dispatches a dev repair — the locus classifier's conservative default is read against the decision's own `affected_task_types` | **D1** (seam invariant, CI) |

**Closure rows**

| # | item | what | claim (§4) |
|---|---|---|---|
| 8 | **#1070** | the plan's restatement of `success_status` collapsed; the manifest's field is the one copy | CI (goldens) |
| 9 | **#936 / #933** | verify-then-close against the tree — both were fill-mode window blockers whose fixes may already have landed with SIP-0104's later phases | CI |
| 10 | **#1285** | the qa task's two output shapes get two reasoning declarations. **Its relationship to the subject, in one sentence:** the qa task authors the evidence every recovery decision reads, and its fill-mode output shape roughly doubles the completion burden, so a single reasoning declaration that describes only the cheaper shape misreports the cost of the loop's own verifier | **Q1** |

The order is the dependency order: #1312 changes what the builder is asked for, #1374 what the
loop composes, #1372 what happens when it produces nothing. **#1312 → #1374 → #1372 is the
opening sequence** and is not reordered.

**The emission taxonomy #1372 and R1 are read against.** The plan does not use "contentless"
as shorthand for the whole builder failure family; a 373-token Dockerfile-only response is
not contentless. Four classes:

| class | definition | the loop's path today | this line |
|---|---|---|---|
| **short emission** | a statistical shape: a first emission well under the producer's normal token range | none — a size, not a verdict | texture only (`emission_tokens_by_handler`) |
| **incomplete emission** | validly parsed output missing artifacts the task's contract requires | the `required_files` row fails; the attempt fails into correction | #1374's path (the corrected result derives the row from the candidate); **not** an emission retry |
| **contentless emission** | no usable artifact body after parsing — the code's `empty`, `cap_exhausted`, `unextractable` and `no_fenced_blocks` shapes | the emission retry, re-rolled blind (qa); no retry path at all (builder) | **#1372: `retried_with_fact`**, every producer |
| **invalid emission** | a response that cannot satisfy the emission contract although it carries content — a fence with no path, a Python artifact the syntax gate refuses | the emission-integrity retry, already carrying the gate's fact for the syntax case | the #1372 PR's seam table states which invalid shapes reach the retry with a fact today and which do not; any it adds are named there, not assumed here |

So R1's builder-side exercise is the **contentless** class, by the fault; the short and
incomplete classes are what the builder's Dockerfile-only emissions were, and they are read by
F1 and the texture, not by R1. This distinction is kept deliberately because Scoped Code
Revision changes the response contract in 1.8 and will need it.

### 3.3 The rider — never roll-verified, split by whether it can move the environment

The 1.7.3 plan §5 kept all of these out of that line so a shakeout regression would be
attributable. A checkpoint pair gives attribution of a gross regression; it does not guarantee
a rider has not altered latency, retries, startup timing or failure frequency in ways that
change the experiment. So the rider is two riders:

**Behaviour-orthogonal — lands before the pack, behind a checkpoint pair.** Nothing here runs
on the cycle path, changes what a container installs, or changes a line the driver reads.

| item | what | verified by |
|---|---|---|
| #575 | placeholder trace/span ids and truncated uuid4 ids in lineage | CI |
| #1373 | the identity-permutation test over the roster | CI (a test) |
| #1205 | dependency vulnerability scanning | CI (a scan; a finding it makes is a refresh, which is the other rider) |
| #1369 | the package script (§3.1) | CI |

**Runtime-affecting — lands after the counted set closes, before the cut.** Each of these can
change the environment a cycle executes in, even with no dedicated roll readout.

| group | items | why it is runtime-affecting | verified by |
|---|---|---|---|
| timeouts | #1147 (one setting bounds two things) | changes the timeout the cycle path runs under | CI + one rebuild |
| persistence and API shape | #577 (shared asyncpg pool + JSONB codec), #576 (domain-error handlers, the per-route envelope blocks deleted), #578 (graphlib for the plan DAG; decide `depends_on`) | the registry the run writes through; the error shapes the driver reads; the plan DAG the cycle executes | CI + one rebuild |
| ops | #581 (compose healthchecks, `up --wait`), #560 (log hygiene), #574 (AMQP URL parsing), #300 (migration advisory lock), #330 (Prefect loop starvation) | startup timing; **the log lines the driver's readouts grep**; the broker connection; runtime-api startup; the orchestrator's loop | #581/#560/#574 CI + one rebuild; #300 and #330 **live** on the dev deploy |
| prompt registry | #352 (runtime staleness guard), #353 (manifest hashes stamped at build) | a runtime guard on the prompts every producer renders; the build that stamps them | CI + one rebuild |
| realm and deps | #372 (Keycloak realm export reaches existing realms), #1204 (refresh `ci-constraints.txt`) | the realm the CLI logs into; **#1204 is not CI-only** — since #1203 that file is the pin set every image installs | #372 live; #1204 CI + one rebuild |
| evidence | #1324 (the boot audit keeps the response it judged) | on the boot-audit path of every cycle | CI + one rebuild |

Fourteen items. They land in this line, after the measurement window, on one rebuild (deploy
D) with **one shakeout pair as their live check** — attribution only, no readout, not counted
— and then the three live-verified ops items. **The cost, stated:** the tagged tree will differ
from the frozen deploy by exactly this rider, so the record names that drift item by item and
classifies each as additive or behavioural (CLAUDE.md, "say what the cut evidence does not
cover"); 1.7.3 could record zero drift and this line cannot.

None of the eighteen has a roll-level readout and none gets one.

### 3.4 The count this line owes the record

| item | release plans that scheduled it | times, incl. this plan |
|---|---|---|
| #1147, #330, #300 | 1.7.0 (rider), 1.7.2 (rider), 1.7.3 (rider, deferred), 1.7.4 | **4** each |
| #575–#578, #581, #560, #372, #352, #353, #574 | 1.7.0, 1.7.2, 1.7.3, 1.7.4 | **4** each |
| #994, #995, #968 | 1.7.0 (1.7.2's half), 1.7.2 (step 8), 1.7.3 §6, 1.7.4 | **4** each |
| #1312 | 1.7.2 (pre-registration §4 as 1.7.3's), 1.7.3 (reversed to here), 1.7.4 | **3** |
| #1254, #1054, #1070, #936, #933 | 1.7.0 (1.7.3's half), 1.7.3 §6, 1.7.4 | **3** each |
| #1285, #1324, #1204, #1205 | 1.7.3 §6, 1.7.4 | **2** each |
| #1369, #1372, #1373, #1374 | 1.7.4 | **1** each — filed on the 1.7.3 line |

Every rider item is on its fourth plan. That is the number this section exists to print — and
it is governance evidence, not a technical reason. **Repeated deferral increases the
requirement to dispose of each item by explicit decision; it does not override experiment
isolation.** The runtime-affecting rider landing after the counted set is not a fifth deferral:
it closes in this line, after the measurement window.

### 3.5 The cut criterion — three gates, kept apart

"Landed" is not shorthand for "proven". The cut needs all three:

| gate | criterion |
|---|---|
| **implementation** | all ten pack rows are merged, or explicitly removed through a plan revision that gives the reason — never a re-place-by-name at the cut; the rider disposed of item by item |
| **experimental** | **L1 and H1 hold**; no registered live hypothesis is falsified; every registered hypothesis has either a deterministic exercise or a live occurrence according to its pre-registered method, and the record says which; every seam invariant's diagnostic reached its seam on the pinned deploy |
| **evidence** | every field §4 names is populated on every counted record; the record can reconstruct every counted/void/reset boundary from per-round evidence; the deploy-to-tag drift is named item by item |

### 3.6 Merge discipline

One PR per row; the seam table in every PR that binds or removes a check (CLAUDE.md, typed
checks); the mirror rule on every removal; `--head` on every PR; every job of main's run read
after every merge; no merge to main while a set is open. The plan's own PR carries the 1.7.0
plan §3.1 amendment pointing here.

---

## 4. The verification set — bars, live hypotheses, seam invariants, texture

Two counting sets on one frozen deploy. Four categories, and the word "prediction" is reserved
for the first two:

- **release bars** — properties whose violation blocks the release;
- **live hypotheses** — behaviour expected across counted rolls, each exercised by every
  counted roll or by a guaranteed live occurrence;
- **seam invariants** — deterministic properties proven through diagnostics or faults on the
  pinned deploy, or by CI, and checked continuously; reported in the record, never read as a
  roll's pass or fail;
- **texture** — observations with no pass/fail implication, each with the field that produces
  it.

Every bar and hypothesis names its falsification, its field, and — the 1.7.2 §7 question —
what the readout would say if the claim were false for a reason not yet thought of.

**The 1.7.3 set re-registered**, each carried claim sorted by the same test into the same four
categories (exercised by every roll → hypothesis; needs a fault → invariant; neither →
texture). L1 stays a bar; L2, L4, L7 and L8 are invariants read by their diagnostics; B1 is a
hypothesis now that it has a field. The 1.7.3 set's own R-series keeps its names under a
`1.7.3/` prefix in the pre-registration so this line's R1 does not collide with it.

### Release bars

| bar | claim | falsified by | read from |
|---|---|---|---|
| **L1** | no contentless qa first attempt on a counted roll — **the loop remains able to produce a valid running result**, the condition every other claim is measured through (1.7.2 §4) | one contentless qa first attempt | `contentless_emissions` |
| **H1** (#1312) | no counted roll is rejected or blocked on the handoff — **this line's specific rejection class is gone**: `required_files` names no `qa_handoff.md`, no `sections_present` row exists for it | one such row on a counted roll | the roll-up's `required_unmet` and the typed rows by check; **its own miss**: a *new* required file the profile derives would fail the same way with a different name — the readout lists every required file, not the handoff's |

Two bars because they are two layers: L1 is the loop's ability to produce a result at all,
H1 is the removal of the rejection class this line exists for. Every counted roll exercises
both; neither depends on a rare event.

### Live hypotheses

| hypothesis | claim | falsified by | read from |
|---|---|---|---|
| **F1** (#1374) | **derivation consistency, not absence of rejection:** for every accepted patch on a counted roll, each framework-owned row the task's contract declares equals the value derived from the accepted candidate tree, and no superseded failed-attempt value survives into the corrected result | one corrected result carrying a row whose value differs from the candidate-derived one, or a row the failed attempt wrote and the candidate did not — **whether or not the roll rejects on it** | the corrected result's rows against a re-derivation over the stored accepted tree, per row; the contentless-builder diagnostic proves the one concrete case (§3.1 steps 2 and 6); **its own miss**: a row the contract does not declare and the roll-up still requires — the readout lists the contract's rows beside the roll-up's required set |
| **R1** (#1372) | every **contentless** emission on a counted roll (§3.2's class, not the short or incomplete ones) is retried with its emission-shape fact and the task's expected artifacts | one contentless retry whose feedback carries no fact | `retried_with_fact` beside `contentless_emissions`. **Exercise:** 1.7.3 observed two short builder first emissions in six counted rolls, but #1312 changes the builder's prompt and output contract, so that rate is not treated as a prediction of live occurrence. **The contentless-builder fault is the required exercise; live occurrences are additional evidence.** L1 keeps the qa side at zero, so a counted set with no live contentless emission leaves R1 proven by the fault alone, and the record says so |
| **B1** (carried) | no stored qa suite names a fixture table for a non-root entity | one such suite | `non_root_fixture_tables` |
| **Q1** (#1285) | each qa output shape is measured under its own reasoning declaration | one fill-mode emission reported under the free-authored declaration | `emission_tokens_by_handler` by shape; every Next.js roll exercises it |

### Seam invariants — proven deterministically, reported as texture on live rolls

| invariant | claim | proven by | live texture |
|---|---|---|---|
| **H2** (#1312) | when the builder emits `assembly_notes.md`, the qa prompt carries it, paired with the producing artifact's id; when it does not, the qa prompt carries nothing in its place; a notes file from an earlier attempt is never rendered — **stale or wrong provenance is a correctness defect and a CI invariant**, not a thing counted rolls assure | CI: the appendix renderer under present / absent / superseded notes | appendix presence per task, with the producing artifact id |
| **W1** (#994) | a rewind after an accepted repair never re-dispatches the repaired task | the rewind fault's diagnostic on the pinned deploy (§3.1); CI on the rewind protocol | rewind occurrences against `applied_patches` |
| **A1** (#968) | no correction decision inherits an analyzer claim the source refutes | the analyzer fault's diagnostic on the pinned deploy (§3.1); CI on the source check | analyzer/source disagreements per correction round |
| **D1** (#1054) | a decision naming dev task types dispatches a dev repair — a deterministic mapping, a contract test, not a stochastic claim | CI: the locus classifier under decisions naming each task-type family | `affected_task_types → correction_repair_locus` pairs per round |
| **L2, L4, L7, L8** (carried) | the 1.7.3 diagnostics' claims | the absent-suite, own-frame chain and path-prefix diagnostics re-run on the pinned deploy | as in 1.7.3 |

### Texture — observed, never blocking

| observation | field |
|---|---|
| **T1** (#995): a timed-out attempt banks its real history | the banked failure analysis against the emission-shape lines, when a timeout occurs |
| the builder's first emission size (the short-emission rate) | `emission_tokens_by_handler` |
| correction rounds, refunded rounds | `correction_rounds`, `refunded_rounds` |
| the qa tokens by shape | `emission_tokens_by_handler` (Q1's producer) |
| the fill assertion strength per run | `fill_merge_evidence` |
| packaging findings (`npm_ci_without_lockfile`, 4 of 9 rolls on 1.7.3) | reporting-only, as in 1.7.3 |
| B1's denominator; `checks_by_environment` | `non_root_fixture_tables`; `checks_by_environment` |
| the seam invariants' live occurrences | the fields in the table above |

**Diagnostics before roll 1**, on the pinned deploy, each read by the seam it reached: the
1.7.3 three re-run; the contentless-builder diagnostic (F1, R1); the rewind diagnostic (W1);
the analyzer diagnostic (A1). A diagnostic that does not reach its seam is a finding, and the
set does not open on it.

**Size — 6 + 3, the 1.7.3 sizes held.** Six counted React rolls preserve comparability with
1.7.3; three Next.js rolls extend observation across the same frozen deploy without changing
the hypothesis set. The faults provide guaranteed seam exercise where natural occurrence
cannot be assumed, so the size is not justified by an expected number of short emissions —
H1 needs none, every counted roll exercises it.

**Known non-pack rejection cause, declared before roll 1:** none is carried from 1.7.3 — #1312
was that cause and is the pack.

---

## 5. Hardening — the rider is here, not pulled forward

§3.3 is the infrastructure rider the 1.7.2 and 1.7.3 plans deferred, in full, at the quota. The
1.7.0 plan §3.1 named it 1.7.3's; the 1.7.3 plan §5 gave the reason it moved — no roll reaches
any of it, and landing it beside a measured pack makes a red unattributable — and this plan
keeps that reason and adds the finer one: the behaviour-orthogonal four land before the pack
behind a checkpoint pair, and the runtime-affecting fourteen land after the counted set
closes, behind one shakeout pair of their own, with the drift named at the cut.

---

## 6. Re-placements by name — nothing silently carried

**1.7.5 — Composition Root and the close of 1.7.** Unchanged from the 1.7.3 plan §6: #820, #376;
#301, #286, #1152 with #1149 first; #567, #579; #198, #157, #176, #580, #1180/#1182; #1197;
#929 with #1206. Plus, from this line: whatever §3.3's live-verified ops items leave unverified
at the cut, named in the record.

**The 1.8 lane — Scoped Code Revision** (PR #1325; formerly Slot-Scoped Emission; subsumes
#1213; #1176 beside it). Its design review starts during this line (§7 step 2). The evidence
it should carry is no longer mainly #1323:

- #1213 — correction repairs re-emit whole files to change a few lines;
- the 1.6.5 rolls 5 and 6 — two of six died on whole-file rewrites of an unslotted file, one
  of them carrying the correct fix (1.6.5 record);
- #451 — the anchored-replacement uniqueness lesson (an unanchored global replace corrupted
  the manifest);
- the shipped qa slot-body fill primitive (SIP-0104) as the authorized-region replacement that
  already exists;
- #1332 / #1354 — authorization before verification, already landed, the precedent the SIP
  builds on;
- the candidate-revision identity gap — a verified candidate has no identity before the patch
  is materialised (§3.1 step 5 states it for the contentless case);
- this line's builder and retry emission evidence as it accrues (§4's texture).

#906 (the Next.js baseline stylesheet) stays post-window. #1122 stays with SIP-0104.

**Still at design review, unchanged:** #414, #557, #316; #80, #950, #949, #194, #1039, #1031.

---

## 7. Sequencing

1. **This plan**, on its own PR, with the 1.7.0 plan §3.1 amendment. Merges on the owner's
   review.
2. **The Scoped Code Revision design review opens** (PR #1325) — a review, not a build; it runs
   beside this line and gates nothing here.
3. **§3.1**: the required check first (the protection change, the CLAUDE.md line, the
   controlled negative check); then the instrument — the three faults, the two fields, #1369.
4. **Deploy A**; every fault and field proven on it: the seven diagnostics (the 1.7.3 three,
   contentless-builder, rewind, analyzer) read by the seam reached, and the fields checked
   against a real record. The instrument rounds, counted apart.
5. **The behaviour-orthogonal rider only** (§3.3's four), one PR each.
6. **Deploy B; one checkpoint pair** — a red here is the rider's.
7. **The pack, in §3.2's order**, one PR each.
8. **Deploy C**.
9. **Shakeouts** to the exit rule — a pair on one deploy with no new seam finding; budget three
   pairs; the record reports rounds taken and rounds attributable to the pack.
10. **Pre-register** (`1-7-4-<arm>.yaml`, pins from the last shakeout); the diagnostics on the
    pinned deploy.
11. **Counted set 6 + 3** — no merges to main while a set is open; the counted/void/reset
    reading at each boundary.
12. **Close the set and write the preliminary measurement conclusion** — the three gates of
    §3.5 read against the frozen deploy, before anything else moves.
13. **The runtime-affecting rider** (§3.3's fourteen), one PR each; deploy D; one shakeout pair
    as its live check; the live-verified ops items (#330, #300, #372) on the dev deploy.
14. **Final record; cut 1.7.4 by the seven steps**, step 7's capture named with every cycle the
    record cites and its role; the deploy-to-tag drift named. Then 1.7.5.

The key property of this order: nothing that can affect runtime timing, infrastructure
behaviour or producer execution moves under the counted set.

---

## 8. Decisions — ruled by the owner, recorded here

**Ruled at the first review, 2026-09-07 evening:** #1285 is material and Q1's half is built in
this line; two bars, L1 and H1; `integration` becomes a required check.

**Ruled at the second review, the same evening (rev 2):**

- **The release identity stands**: the recovery-half line, measured at the seams the prior
  two lines found the loop lying; #1312 → #1374 → #1372 remains the opening sequence.
- **The pack is two strata** — recovery contract (1–4) and recovery decision fidelity (5–7) —
  so the record answers two questions in order, not one blurred one.
- **#1312 with #1254 stays one PR** for the atomic invariant §3.2 states, and for no other
  reason; `assembly_notes.md` has a positive definition the exclusion list enforces.
- **F1 tests derivation consistency**, not absence of rejection: a wrong derived value that a
  roll happens not to reject on is still a falsification.
- **The emission taxonomy is explicit** (short / incomplete / contentless / invalid) and
  `retried_with_fact` is claimed for the contentless class; the 1.7.3 short-emission rate is
  the reason for the fault, not an expected live exercise, because #1312 changes the contract
  it was measured under.
- **No fault, no prediction, applied uniformly:** W1 and A1 get faults and become seam
  invariants; D1 and H2 are CI invariants; all four report live occurrences as texture. A
  fault that cannot be built honestly leaves its claim CI-only and declared so before roll 1.
- **The rider is split** by whether it can move the cycle's environment: four
  behaviour-orthogonal items before the pack behind a checkpoint pair; fourteen
  runtime-affecting items after the counted set closes, behind one shakeout pair, with the
  deploy-to-tag drift named at the cut. This supersedes the first review's "rider first" in
  part: the governance count (§3.4) does not override experiment isolation.
- **6 + 3** is justified by comparability with 1.7.3 and observation across one frozen deploy,
  not by an expected number of short emissions.
- **The cut is three gates** — implementation, experimental, evidence — so "landed" never
  stands in for "proven".
- **Scoped Code Revision** is the 1.8 lane's name everywhere, subsuming #1213, and its review
  carries the evidence §6 lists.

Standing recommendations not overruled: #1374 and #1372 ahead of the 1.7.2 step-8 items (two
void counted rolls in two lines is the loop's most expensive habit); the Scoped Code Revision
review starts now so that 1.8.0's headline is not designed in 1.8.0.

---

## 9. Revision history

- **Rev 1 (2026-09-07)** — written the evening the 1.7.3 line closed, on the owner's ask,
  from the 1.7.3 plan and record, the 1.7.2 plan §8/§8a, the 1.7.0 plan §3.1 and §6.2, and the
  issues filed on the 1.7.3 line (#1369, #1372, #1373, #1374 — the last three filed with this
  plan so nothing is carried as plan text). Placement against the 1.7.3 plan §6's re-placements
  by name, with the pack reordered to put the two void-roll mechanisms second and third. The
  owner ruled the same evening: #1285 material, two bars, the rider first, `integration`
  required.
- **Rev 2 (2026-09-07)** — on the owner's written review of rev 1, twelve changes: the pack
  split into recovery contract and recovery decision fidelity, with the recovery transaction
  stated once; the #1312/#1254 atomic invariant and a positive definition of
  `assembly_notes.md`; F1 strengthened to candidate-derived-row equivalence; the four-class
  emission taxonomy; the 1.7.3 short-emission rate demoted from expected exercise to the reason
  for the fault; W1/A1 given faults and D1/H2 made CI invariants, none a live hypothesis; the
  rider split into behaviour-orthogonal (before the pack) and runtime-affecting (after the
  counted set), #1204 reclassified as runtime-affecting because `ci-constraints.txt` is what
  every image installs; the 6 + 3 justification rewritten; every Slot-Scoped Emission reference
  renamed Scoped Code Revision with #1213 subsumed and the review's evidence list; §4 sorted
  into bars / live hypotheses / seam invariants / texture; the cut split into three gates; the
  `integration` precondition given a deterministic exit criterion; the §3.4 count named as
  governance evidence that does not override isolation; the thesis sharpened to the three-part
  contract. The sequencing is the owner's fourteen steps.
