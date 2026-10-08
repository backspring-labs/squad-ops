# 2.2.0 — SIP-0110 Phase 1's window: pre-registration (DRAFT, for the owner)

**Drafted 2026-10-08 by the supervisor, before any scored run. The owner adopts or amends it; the
window opens on the owner's word, never before** (the 2.2 plan §3 step 8, D8; the 2.2 standing
authority's stop list). It fixes everything SIP-0110 §0.12 says a pre-registration fixes, and it reads
the repeat report (D14). Each item marked **owner** is a choice this draft recommends and the owner
makes.

## 1. The primary target

- **Seam:** proposal writing (`strategy.propose_increment`, role `strat`).
- **Target behavior:** `criterion_already_satisfied`: *a proposed new acceptance criterion is already
  satisfied by the accepted application* (§0.4, the one supported target behavior).
- **The lesson under test:** `pat_0b4aef8aea974e06@1`, drafted by the supervisor (D15) and frozen in
  the store on 2026-10-08. It is a comparison step, not a restated rule (§5e). Its applicability is
  `group_run`, `strategy.propose_increment`, `strat`, `fullstack_fastapi_react`, `qwen3.8`, and it
  cites two observations:
  - `proposal_ruling:cmp_c4b81554bd59:ctl_0d94790c5185`;
  - `proposal_ruling:cmp_c4b81554bd59:ctl_55e3c2f87ae5`.

  Its replay check on the development cases is §8. **The owner approves it, or doesn't**, at a
  campaign boundary inside the window (§4).
- **Why this target** (§0.12): the proposal seam holds the most independent cases of one target
  behavior. The repeat report substantiates no plan-review or correction-round target (§7).

## 2. The eligible opportunity (fixed before any output is seen)

A **campaign's first proposal**: the first `strategy.propose_increment` authoring of a campaign
admitted after the window opens. To be eligible, all four hold:
- the authoring's task is inside the lesson's applicability above;
- it is an increment's proposal on an accepted application (a calibration has none);
- its envelope was captured;
- its replay passes the instrument-validity check: the baseline reproduces the captured prompt
  exactly, and the memory arm differs only by the lessons section.

Revisions (v2+), later increments' proposals and re-rolls carry a within-campaign rung or lineage, and
are reported separately, never pooled with the primary cases (§0.11).

## 3. The cases, and the split

- **Development cases** (used to draft the lesson and replay-check it; never scored):
  - the 8 historical proposal rulings in the store. Five are this target:
    - two classified, which the lesson cites;
    - three classified only in prose: `cmp_58d4e3b0a5d3`, `cmp_b3a681c4f994` and `cmp_51919765933d`. They can't be cited until #2160's annotation path, or its amendment, is decided. **Owner.**

    None of the eight was captured before authoring, so none is replayable (§5e, #2106);
  - the 4 captured proposal envelopes from before the window: `run_f976b8bb444f`, `run_13a50d4e7dbc`, `run_358783264874` and `run_643af239100c`.
- **Held-out cases:** every eligible opportunity (§2) captured inside the window. They are kept apart
  from the development cases before any tuning: a lesson revised after the window opens is an
  intervention (§6), not a tuning step.
- **Counted separately in every readout:** unique cases (envelopes), cycles, campaigns, and repeated
  generations of one case.

## 4. The window's campaigns

- **Five campaigns, one objective each, so first proposals are independent.** The exploratory replay
  showed why: on one objective, every arm and generation proposed the same first Tier 1 item. The
  objectives are the PRD's expansion items (`examples/03_group_run/prd.md` §4.1), in this order:
  1. a per-run capacity limit (Tier 1, item 1);
  2. participant name normalization for join and leave (Tier 2, item 5);
  3. datetime sorting of the runs list (Tier 1, item 2);
  4. improved error messaging in the UI (Tier 1, item 4);
  5. a seed sample run action (Tier 1, item 3).

  Items 1 and 2 are where this target has occurred, or is likely to:
  - capacity is the clean historical case;
  - the frozen request models already trim names.

  That is a property of the objectives, fixed here before any output.
- **Each campaign:**
  - a calibration and one increment (`target_accepted_increments: 1`), as the capture proof;
  - stack `fullstack_fastapi_react`, squad profile `full-38`, memory enabled;
  - its own new definition file, which declares `plan_gate: supervised` (D3: the tier activates after the window; #2146 makes the declaration required).
- **Rulings:** proposal rulings stay supervised (D3). Each return carries its class (D2's rail), so the window's own returns are classified observations.
- **The lesson's approval** is the owner's, at a campaign boundary (§0.7: never inside a running campaign). **Recommended: after campaign 2 closes.** Campaigns 1–2 then give counterfactual cases (no lesson in their snapshot), and campaigns 3–5 prospective ones (the lesson in their snapshot). **Owner.**

## 5. Comparisons

- **Confirmatory, on the primary cases:**
  - each case is replayed under **baseline** and **scoped memory**, 3 generations per arm, seed 7, paired, with the arm order balanced;
  - every output is read by the rubric `lesson.criterion_already_satisfied@1` (`scripts/dev/replay_rubrics/criterion_already_satisfied.md`), blind to the arm;
  - a case's outcome is, per arm, how many of its generations are **present**.
- **Reported apart (§0.11):**
  - counterfactual cases: authored before approval, with the lesson supplied only in the replay;
  - prospective cases: the lesson was in the live unit's snapshot.

  A counterfactual result never reads as a prospective one.
- **Exploratory:**
  - the static-guidance arm (selectivity and token cost);
  - revisions and later proposals;
  - the live rulings beside the rubric's verdicts;
  - the app-build indicators beside every exposure (observed only, §0.10).

## 6. Effect, uncertainty, missing results, the cap and the stop

- **Headroom first.** A primary case has headroom when its baseline arm is `present` in at least one
  generation. The lesson can be measured only where the baseline makes the mistake.
- **Minimum worthwhile effect** (**owner**): across the cases with headroom, the memory arm removes the
  target (no generation `present`) in a majority of them, and no guardrail is breached.
- **Uncertainty:** the corpus is small (§0.13), so the readout gives the per-case paired counts and
  an exact sign test over the cases with headroom, and makes no claim beyond them.
- **Inconclusive:**
  - fewer than 3 primary cases with headroom at the cap is `inconclusive` (too few opportunities), whatever the counts;
  - the exploratory run and the lesson's replay check (§8) both found no headroom on today's cases, so this is a likely finding.
- **Missing and invalid results:**
  - a case that fails the validity check is excluded, and counted by reason;
  - an `unassessed` generation is counted, never imputed;
  - a case with every generation `unassessed` in either arm leaves the paired comparison, and is counted.
- **Budget cap** (**owner**; D8 proposes about five campaigns): the five campaigns of §4, or 48 hours
  of window wall-clock, whichever comes first.
- **Stopping rule:** the window stops at the cap. It stops early only for harm:
  - a guardrail breach the lesson caused in a prospective proposal (another return class growing under it, an empty or scope-avoiding proposal);
  - that invokes revocation (D9), sets the affected measurements apart, and the finding reads `harm`.

  There is no early stop for benefit.

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

## 8. The lesson's replay check (development cases)

`var/replays/lesson-check-criterion-already-satisfied-r1` (2026-10-08, 18:35–19:21Z, on rebuild 5,
`76a29c86`):
- **The setup:** the four captured proposal cases (§3), baseline and scoped memory, 2 generations each, seed 7, `qwen3.8:27b`.
- **Instrument validity: 4 of 4 cases.** Every baseline reproduced its captured prompt exactly. Every memory arm differed only by the lessons section.
- **16 of 16 authorings parsed.** Scored blind by the rubric (seeded shuffle; the key was joined after the verdicts; the records are under `scoring/`):

  | case | what it proposed | baseline `present` | scoped memory `present` |
  |---|---|---|---|
  | `d91da940b33e` (first increment) | capacity | 0 of 2 | 0 of 2 |
  | `2b9392a50e7b` (first increment) | capacity | 0 of 2 | 0 of 2 |
  | `ef51c555bbb2` (first increment) | capacity | 0 of 2 | 0 of 2 |
  | `cd0e5c799a25` (second increment; T1–T4 frozen) | datetime sorting | 0 of 2 | 0 of 2 |

- **No headroom.** The baseline doesn't make the mistake on any development case, so this check can't show an effect, only its absence of harm.
- **No guardrail breached in either arm:**
  - every output proposes a PRD expansion item;
  - every output keeps new criteria that fail on its accepted app;
  - no other return class appears. One output declares `capacity_reached` at 403 and asserts 403, which is consistent.
- **The context cost:** the rendered section is 1,542 characters (253 words), against prompts of about 26,000 characters.
- **The combined check:** no approved lesson exists, so nothing is supplied beside it.

## 9. The experiment manifest (recorded as the window opens)

Each input is recorded by version or hash, in `var/replays/<window>/manifest.json`, with a copy committed beside this file when the window closes:
- **the deploy:** its commit and image ids, read from the running deploy;
- **the prompts and fragments:** a hash of `src/squadops/prompts/`;
- **configuration:**
  - `config/`;
  - the request profiles;
  - the squad profile as stored in Postgres;
  - the campaigns' definition files;
- **model settings:** the model, `max_tokens` and reasoning level;
- **the policies;**
- **the evaluator:** the replay tool's sha (`scripts/dev/run_authoring_replay.py`, `authoring_replay.py`) and the rubric file's sha;
- **the PRDs:** `examples/03_group_run/prd.md`;
- **the referenced evidence;**
- **the store's lessons and approvals:** revision ids and text sha256.

**No rebuild during the window.** A merge that changes a listed input waits. Any other merge is free. A
change that must land inside restarts the window under a new manifest, or is recorded as an
intervention (§0.12).

## 10. Guardrails (§0.12), read with every verdict

As the rubric states them:
- the output advances the objective;
- scope and meaningful criteria remain;
- other serious defects do not grow;
- context cost is reported as measured;
- memory cannot win with an empty or avoiding output.

## 11. For the owner, before the window opens

1. Adopt or amend this pre-registration.
2. The budget cap (§6).
3. The minimum worthwhile effect (§6).
4. #2160: annotate the three prose-classified returns, or amend §0.4 to leave them `unclassified`.
5. The lesson's applicability: FastAPI only, as tested, or wider. Wider needs evidence on that stack.
6. The evaluator: the supervisor, blinded (as drafted), or another.
7. When to approve the lesson (§4).
