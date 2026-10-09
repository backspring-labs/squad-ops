# 2.2.0 — SIP-0110 Phase 1's window: pre-registration (DRAFT, for the owner)

**Drafted 2026-10-08 by the supervisor, before any scored run. The owner adopts or amends it; the
window opens on the owner's word, never before** (the 2.2 plan §3 step 8, D8; the 2.2 standing
authority's stop list). It fixes everything SIP-0110 §0.12 says a pre-registration fixes, and it reads
the repeat report (D14). Each item marked **owner** is a choice this draft recommends and the owner
makes.

**Three decisions stay distinct, and all three are the owner's:**
- adopting this pre-registration;
- approving the lesson, for a bounded experiment (§1);
- opening the window.

**Revision 2 (2026-10-09), from the owner's review of the 2.2 shakeout and of revision 1.** These are the changes:
- the shakeout's claim (§0);
- the historical cases distinguished, with their annotations (§3);
- bounded approval of an exact revision, with a required disposition (§1);
- every paired case analysed, with no headroom filter (§5, §6);
- completeness and the already-satisfied objective (§2, §6);
- the evaluator's controls and the harm rules (§6, §10);
- approval before campaign 1 (§4);
- the validity wording and the seed (§2, §5, §9).

## 0. What the window rests on

- **The regression shakeout met its exit rule at rebuild 9 (`a84e085f`).** Both stacks were accepted with no
  correction round and no new seam finding, and 17 of 17 envelopes reconstruct byte for byte, each with its own exposure.
  The loop took five deploys, rebuilds 5 to 9. It stops there: no more unchanged ordinary pairs are run hoping a rare
  path occurs.
- **What that establishes, and what it does not.** The pairs were uncounted and memory-disabled. They establish that
  the deploy is ready for the window. They establish nothing about memory's effectiveness, and they are not the
  release's counted regression set.
- **Two live-coverage limits are disclosed:**
  - no task was re-dispatched in the last two pairs, so a second attempt's exposure (#2166) has been proven only by
    its integration test and the loaded check. A targeted diagnostic exercises it (below);
  - no dispute was raised live, so #2169's dispute reader is proven by its regression tests and a deployed check
    against the historical example, not by a live dispute lifecycle. That limit stays.
- **The redispatch diagnostic (before the window).**
  - One uncounted, memory-disabled cycle, with the fault `builder_emission_contentless` declared on its first attempt
    only, so `builder.assemble` is dispatched twice.
  - A fault-injected cycle is a diagnostic by construction, so its failures never become observations (SIP-0110 §0.3).
  - It must show two distinct exposures, attempts 1 and 2, each joined to its own exact envelope.
- **The deploy.** The window opens on the deploy its manifest records (§9), after the normal required checks
  (`verify_loaded`, the health probes, main's CI read).

## 1. The primary target, and the lesson's bounded approval

- **Seam:** proposal writing (`strategy.propose_increment`, role `strat`).
- **Target behavior:** `criterion_already_satisfied`: *a proposed new acceptance criterion is already
  satisfied by the accepted application* (§0.4, the one supported target behavior).
- **The lesson under test: its exact revision is settled before approval.**
  - `pat_0b4aef8aea974e06@1` was frozen on 2026-10-08 (text sha256 `2f555e49…`, 1,005 characters, drafted by
    `claude-opus-5-5`). It cites the two classified returns of counted campaign 1:
    - `proposal_ruling:cmp_c4b81554bd59:ctl_0d94790c5185`;
    - `proposal_ruling:cmp_c4b81554bd59:ctl_55e3c2f87ae5`.
  - If the reviewed annotations of #2160 (§3) are cited, the citations change, and so does the text, which describes
    the returns it rests on. **Then @1 is kept as it stands, and a new revision is drafted and frozen.** The revision
    the owner is asked to approve is named here once it is settled, with its text hash.
  - **The replay check (§8) and the combined-guidance check are run on that exact revision,** and the approval records
    both.
- **Its applicability is limited to what was tested:** `group_run`, `strategy.propose_increment`, `strat`,
  `fullstack_fastapi_react`, and the `qwen3.8` configuration recorded in the manifest (§9). Wider applicability needs
  evidence on that stack or model.
- **The approval is a bounded experimental approval, not standing activation.**
  - It holds for the window's campaigns.
  - At the window's end, the lesson gets an explicit disposition: **retained** within its tested applicability;
    **disabled**; **revised and sent back for retesting**; or **continued in a bounded extension**, with its
    applicability, its end point and what ends it (SIP-0110 §0.13).
  - **An inconclusive finding never makes the activation permanent by default.** Without a recorded disposition, the
    approval is revoked when the window closes.
- **Why this target** (§0.12): the proposal seam holds the most independent cases of one target behavior. The repeat
  report substantiates no plan-review or correction-round target (§7).

## 2. The eligible opportunity (fixed before any output is seen)

A **campaign's first proposal**: the first `strategy.propose_increment` authoring of a campaign admitted after the
window opens. To be eligible, all of these hold:
- the authoring's task is inside the lesson's applicability (§1);
- it is an increment's proposal on an accepted application (a calibration has none);
- its envelope was captured;
- **it passes the instrument-validity check, in two steps** (the replay tool's `validity`,
  `src/squadops/memory/replay.py`):
  1. **the actual captured prompt is reconstructed byte for byte,** re-rendered from the inputs the handler was handed,
     including any lesson supplied live;
  2. **the comparison arms have identical ordinary inputs and differ only by the lesson's section.** The baseline arm
     renders the task's own inputs alone, and the memory arm inserts the section and nothing else.

  A case captured with a live lesson is **prospective**; one captured without is **counterfactual**. The label comes
  from the capture, and the two are reported apart (§5).
- **Its objective has legitimate remaining work** (below).

**The objective check, before any arm generates.**
- Proposals cannot say that an objective is already met: the rails refuse a proposal with nothing to build
  (`nothing_to_build`), and only the campaign decides `objective_met`. So for each captured case, before its replay
  arms run, the evaluator reads the case's accepted application (its manifest, its frozen criteria and its frozen
  conventions, as the proposer was shown them). It records, with the elements that settle it, whether the
  objective still holds legitimate authorized work. The record is made blind to every output.
- **A case whose objective is already wholly satisfied leaves the primary comparison.** It is reported as
  `objective already satisfied`, with its evidence, and is never counted as a mistake or as a win. Recognizing that
  an objective is met must not force a proposer to invent scope, and inventing scope is not a pass either.
- **Objective 2 (name normalization) is the one at risk.** The frozen request models already trim names (§4). Its
  remaining work (duplicate checks on normalized values, display casing kept) is checked like any other.

Revisions (v2+), later increments' proposals and re-rolls carry a within-campaign rung or lineage, and are reported
separately, never pooled with the primary cases (§0.11).

A re-dispatch of the first proposal (an emission retry) is another invocation, with its own envelope and its own
exposure (§0.2; #2162, fixed by #2163). The primary case is the first envelope. A re-dispatch is counted beside it,
and never as a second case.

## 3. The cases, and the split

- **Development cases** (used to draft the lesson and replay-check it; never scored):
  - **five historical returns of this target, across four campaigns** (#2160):
    - **counted campaign 1** (`cmp_c4b81554bd59`), increment 2. Its **version 1** is the one clean case under today's
      prompt: the rule (#1947) was stated, the evidence was on screen, and the reasoning failed (SIP-0110 §5e). Its
      **version 2** was a missing fact, since supplied by #2013. Both are classified, and the lesson cites both;
    - **two shakeouts, each a version 1,** before #1947: `cmp_b3a681c4f994` (T2 held because the FastAPI request model
      ignores an undeclared field; a missing instruction and a missing stack fact) and `cmp_51919765933d` (T3 held
      because the app has no capacity concept; a missing instruction). Classified only in prose;
    - **`cmp_58d4e3b0a5d3`** (T4 restated T3, frozen by increment 2). Classified only in prose, and not among §5e's
      four inspected returns. It is inspected when it is annotated.

    **The three prose-classified returns are cited only through #2160's reviewed annotations** (§1).
    - Each annotation keeps the original ruling and its observation's identity: it adds no occurrence.
    - Each records its classification, its reviewer, its time, its evidence, and the case's original prompt and deploy
      context.
    - **An annotation improves traceability. It reconstructs no missing pre-authoring envelope, and it turns no
      historical diagnostic case into a held-out replay case.**
  - **These are historical observations under older prompts, not independent failures of today's baseline.** Only one
    is a reasoning failure under today's prompt. The other four were a missing instruction or a missing fact, each since
    supplied. None of the five was captured before authoring, so none is replayable (§5e, #2106).
  - **The four captured proposal envelopes from before the window:** `run_f976b8bb444f`, `run_13a50d4e7dbc`,
    `run_358783264874` and `run_643af239100c`.
- **Held-out cases:** every eligible opportunity (§2) captured inside the window. They are kept apart from the
  development cases before any tuning. A lesson revised after the window opens is an intervention (§6), not a tuning
  step.
- **Counted separately in every readout:** unique cases (envelopes), cycles, campaigns, and repeated generations of one
  case.
- **The scope of what the window can show:** at most **five cases, from one application, one stack and one model
  configuration**. Different objectives reduce duplicate opportunities. They do not show generalization across
  applications or models.

## 4. The window's campaigns

- **Five campaigns, one objective each, so first proposals are independent.** The exploratory replay showed why: on
  one objective, every arm and generation proposed the same first Tier 1 item. The objectives are the PRD's expansion
  items (`examples/03_group_run/prd.md` §4.1), in this order:
  1. a per-run capacity limit (Tier 1, item 1);
  2. participant name normalization for join and leave (Tier 2, item 5);
  3. datetime sorting of the runs list (Tier 1, item 2);
  4. improved error messaging in the UI (Tier 1, item 4);
  5. a seed sample run action (Tier 1, item 3).

  Items 1 and 2 are where this target has occurred, or is likely to: capacity is the clean historical case, and the
  frozen request models already trim names. That is a property of the objectives, fixed here before any output, and
  §2's objective check guards item 2.
- **Each campaign:**
  - a calibration and one increment (`target_accepted_increments: 1`), as the capture proof;
  - stack `fullstack_fastapi_react`, squad profile `full-38`, lessons enabled;
  - its own new definition file, which declares `plan_gate: supervised` (D3: the tier activates after the window;
    #2146 makes the declaration required).
- **Rulings:** proposal rulings stay supervised (D3). Each return carries its class (D2's rail), so the window's own
  returns are classified observations.
- **When the lesson is approved** (**owner**; never inside a running campaign, §0.7):
  - **Recommended: before campaign 1,** once the exact revision is frozen and checked (§1).
    - Campaigns 1 and 2 hold the objectives most likely to expose the target.
    - Every case's replay already supplies its paired memory-off arm, so withholding the lesson from live campaigns buys
      no comparison.
    - All five cases are then prospective.
  - **The alternative: after campaign 2,** only if showing the activation boundary is itself an objective. Campaigns 1–2
    would then give counterfactual cases and 3–5 prospective ones. **Campaigns 1–2 against 3–5 is never read as a causal
    before-and-after comparison,** because their objectives differ.

## 5. Comparisons

- **Confirmatory, on every eligible paired case** (§2; no headroom filter):
  - each case is replayed under **baseline** and **scoped memory**, **3 generations per arm**, paired.
  - **The arm order is balanced by the arm-scheduling seed, 7.** It shuffles which arm runs first within each
    generation (`src/squadops/memory/replay.py`, the schedule). **The model's generation settings** (the model and its
    version, temperature, `top_p`, `max_tokens` and reasoning level) are separate, and are recorded in the manifest
    (§9). Three generations are repeated outputs of one case, never three cases.
  - Every output is read by the rubric `lesson.criterion_already_satisfied@2`
    (`scripts/dev/replay_rubrics/criterion_already_satisfied.md`), blind to the arm.
  - **A case's outcome, per arm, is the number of its generations assessed `present`,** out of its generations that are
    valid and assessed (§6).
  - **Each case is then an improvement** (the memory arm has fewer `present`), **a worsening** (more), **or a tie.**
- **Reported apart (§0.11):**
  - counterfactual cases, captured without the lesson, with the lesson supplied only in the replay;
  - prospective cases, where the lesson was in the live unit's snapshot.

  A counterfactual result never reads as a prospective one.
- **Exploratory:**
  - the static-guidance arm (selectivity and token cost);
  - revisions and later proposals;
  - the live rulings beside the rubric's verdicts;
  - the app-build indicators beside every exposure (observed only, §0.10).

## 6. Effect, uncertainty, completeness, the cap and the stop

**Every eligible paired case is in the primary comparison.**
- The readout reports, for every case, the paired counts. It then gives the number of improvements, worsenings and
  ties, and the total `present` count in each arm.
- **Headroom is descriptive only:** the cases where the baseline made the mistake at least once are reported as a
  count. They are never a filter chosen from the same results the benefit is read from.
- **The worked example the rule must not pass.** Take baseline counts `[1, 1, 1, 0, 0]` and memory counts
  `[0, 0, 1, 2, 2]`:
  - a "majority of the cases with headroom removed" reading would call it a benefit, with two of three removed;
  - under this rule it is 2 improvements, 2 worsenings and 1 tie, with total `present` rising from 3 to 5;
  - it reads **not benefit**, and the worsenings are reviewed as a possible harm signal (below).

**What a supported-benefit finding needs** (**owner**; written before any scored run). All of these:
1. at least four eligible, complete cases (below);
2. **no worsening;**
3. improvements in at least three cases;
4. the memory arm's total `present` at most half the baseline's, and at least three fewer;
5. every guardrail held (§10).

**A majority of improvements in this small pilot is not by itself a supported benefit.** With five cases at most, an
exact sign test cannot reach a conventional threshold. It is reported, beside the per-case counts, as uncertainty,
never as the decision.

**The other findings:**
- **No demonstrated useful benefit:** complete and valid, but short of the bar above, with no harm.
- **Harm:** below.
- **Inconclusive:** fewer than four complete cases at the cap, or the completeness rules not met. The development
  check and the exploratory run both found no headroom on today's cases, so this remains a likely finding.

**Completeness: missing evidence never earns a win.**
- **A complete case:** every planned generation in both arms is valid (it parses as a proposal) and has a verdict:
  `present`, `absent after assessment` or `not applicable`.
  - An `unassessed` generation makes its case **partly assessed**. A partly assessed case is reported by arm and
    reason, and leaves the primary comparison: it is never counted as an improvement, a worsening or a tie.
  - A case failing the validity check (§2), or excluded by the objective check, leaves too, counted by reason.
- **`not applicable`** (a proposal with no new criterion) is reported by arm, and never counted as `absent`. If the
  memory arm's `not applicable` outputs outnumber the baseline's, that is an avoidance signal, read with the
  guardrails.
- **A complete-removal claim for a case** ("the lesson removed the target") requires all of its memory-arm outputs to be
  valid, applicable, assessed `absent after assessment`, and within the guardrails. "No generation marked `present`" is
  not enough.

**The evaluator, and its controls** (**owner**).
- **Preferred: a separate blinded evaluator,** another frontier model or a person, who did not draft the lesson.
- **At minimum, if the supervisor evaluates:**
  - it is blind to the arm, as the rubric prescribes;
  - **every apparent win, every worsening and every ambiguous verdict is adjudicated independently** by a second
    evaluator who did not draft the lesson, and disagreements are recorded;
  - the supervisor drafted the lesson, and every readout says so.
- **The rubric is checked first** against known positive and negative examples: the clean historical case's returned
  criteria as positives, and the window-independent accepted criteria as negatives. These examples are never counted as
  held-out evidence.

**Budget cap (owner):** the five campaigns of §4, or 48 hours of window wall-clock, whichever comes first. **It is not
extended in response to the results.** An extension is a new pre-registration, decided before its data.

**Stopping and harm.**
- The window stops at the cap. There is no early stop for benefit.
- **A clear harmful replay result blocks activation:**
  - a guardrail breach the lesson caused in the development check or a counterfactual replay;
  - worsenings that outnumber improvements, with the excess in `present` attributable to the lesson's arm.

  Before approval, the lesson is not approved. During the window, it is revoked (D9), the affected measurements are
  set apart, and the finding reads `harm`.
- **Credible suspected live harm permits a precautionary pause** while it is investigated:
  - another return class growing under the lesson;
  - an empty or scope-avoiding proposal in a prospective case.

  The pause does not need a causal harm finding first, and it is recorded with its reason. The investigation decides
  between resuming, revoking, and a `harm` finding.

## 7. The repeat report, read here (D14)

Read 2026-10-08 against the deploy's store: `group_run`, 84 observations, 5 rounds with a failure
shape.
- **One repeated shape, `vitest:not_a_function`, in 2 independent cycles.** The auditor's reading of
  each round's artifacts finds two different mistakes, which is the case §0.4 warns about:
  - `cyc_168a3703f000`: the qa suite called `mockResolvedValue` on an import it had not mocked, its own suite's defect;
  - `cyc_7117a8c25e2c`: `res.json is not a function` on a route response. The dev's routes there answer through `errorResponse`, so it is a different mistake.
- **No recurring target behavior is substantiated** at plan review or a correction round. So there is no
  secondary build-side comparison in this window. The report is read again at the cut.
- **Noted for that reading:** the rebuild 5 nextjs regression cycle (`cyc_9e9770706fdd`) had the dev's route fills drop the scaffold's `try/catch → errorResponse` (#2152's case).
  - It is one cycle, so it's not recurring.
  - Its failure message (`Error: … not found`) matches no row of the sorter's table, so it is backlog.
- **At the cut,** the record names the next build-side experiment, or the evidence that would trigger one and the review
  point where it is read again (SIP-0110 §0.13).

## 8. The lesson's replay check (development cases)

**On @1** (`var/replays/lesson-check-criterion-already-satisfied-r1`, 2026-10-08, 18:35–19:21Z, on rebuild 5,
`76a29c86`):
- **The setup:** the four captured proposal cases (§3), baseline and scoped memory, 2 generations each, arm-scheduling
  seed 7, `qwen3.8:27b`.
- **Instrument validity: 4 of 4 cases.** Every captured prompt was reconstructed exactly. Every memory arm differed from
  its baseline only by the lessons section.
- **16 of 16 authorings parsed.** Scored blind by the rubric's version 1 (seeded shuffle; the key was joined after the
  verdicts; the records are under `scoring/`):

  | case | what it proposed | baseline `present` | scoped memory `present` |
  |---|---|---|---|
  | `d91da940b33e` (first increment) | capacity | 0 of 2 | 0 of 2 |
  | `2b9392a50e7b` (first increment) | capacity | 0 of 2 | 0 of 2 |
  | `ef51c555bbb2` (first increment) | capacity | 0 of 2 | 0 of 2 |
  | `cd0e5c799a25` (second increment; T1–T4 frozen) | datetime sorting | 0 of 2 | 0 of 2 |

- **What it shows: no harm observed on these four cases.**
  - It shows no benefit: the baseline didn't make the mistake on any case, so there was no headroom.
  - It does not establish an absence of harm.
- **No guardrail breached in either arm:**
  - every output proposes a PRD expansion item;
  - every output keeps new criteria that fail on its accepted app;
  - no other return class appears. One output declares `capacity_reached` at 403 and asserts 403, which is consistent.
- **The context cost:** the rendered section is 1,542 characters (253 words), against prompts of about 26,000 characters.
- **The combined check:** no approved lesson exists, so nothing is supplied beside it.

**On the revision to be approved,** if it is not @1: the same check is re-run on that exact revision, on the window's
deploy, with the rubric's version 2. The combined-guidance check is run for the same revision. Both are recorded here
and in the approval.

## 9. The experiment manifest (recorded as the window opens)

Each input is recorded by version or hash, in `var/replays/<window>/manifest.json`, with a copy committed beside this
file when the window closes:
- **the deploy:** its deploy record, read from the running deploy: the record's id, its source revision (which carries
  `docker-compose.yml`), every service's image id and the models' digests;
  - **the deploy as of this draft** (2026-10-09): `dep_34b4117e7ede`, source `747584c3`. All 21 running containers
    match the record's image ids. It is the shakeout's last deploy (`a84e085f`, rebuild 9) plus #2172, which gives
    nat, eve and han each a memory volume (#2112). The two differ only in `docker-compose.yml` and one unit test, so no
    file under `src/`, `adapters/` or `agents/` differs from what the shakeout validated. The changes to come before the
    window (#2160, the §24bl correction) make a new deploy, and the manifest records the deploy the window actually
    opens on;
- **the prompts and fragments:** a hash of `src/squadops/prompts/`;
- **configuration:**
  - `config/`;
  - the request profiles;
  - the squad profile as stored in Postgres;
  - the campaigns' definition files;
- **model settings,** recorded separately from the arm-scheduling seed: the model and its digest, temperature, `top_p`,
  `max_tokens` and reasoning level, for the live campaigns and for the replay;
- **the arm-scheduling seed** (7) and the generations per arm (3);
- **the policies;**
- **the evaluator:**
  - the replay tool's sha (`scripts/dev/run_authoring_replay.py`, `authoring_replay.py`);
  - the rubric file's sha (version 2);
  - who evaluates, and who adjudicates;
- **the PRDs:** `examples/03_group_run/prd.md`;
- **the referenced evidence,** with the historical annotations (§3);
- **the store's lessons and approvals:** revision ids and text sha256.

**No rebuild during the window.** A merge that changes a listed input waits. Any other merge is free. A change that
must land inside restarts the window under a new manifest, or is recorded as an intervention (§0.12).

## 10. Guardrails (§0.12), read with every verdict

As the rubric states them:
- the output advances the objective;
- scope and meaningful criteria remain;
- other serious defects do not grow;
- context cost is reported as measured;
- memory cannot win with an empty or avoiding output.

## 11. For the owner, before the window opens

1. **Adopt or amend this pre-registration.**
2. **The budget cap (§6):** five campaigns or 48 hours, not extended in response to results.
3. **The supported-benefit bar (§6):** the five conditions as drafted, or amended, before any scored run.
4. **The evaluator (§6):** a separate blinded evaluator (preferred), or the supervisor with independent adjudication
   of wins, worsenings and ambiguous verdicts.
5. **The lesson's exact revision and its bounded approval (§1).**
   - This depends on #2160's annotations, which the owner reviews.
   - The approval is a separate decision from adopting this document.
6. **When to approve (§4):** before campaign 1 (recommended), or after campaign 2 if the activation boundary is itself
   an objective.
7. **Opening the window:** a separate decision, after the readiness work in §0.
