# 2.5.0 — pre-registration of the first-call instruction check on QA calls that were not cut (#2253)

**Status: REGISTERED 2026-10-28, before any call.** Nothing in it has been sent to an engine.

**Why it exists.** The QA output-budget replay (`2-5-0-qa-budget-preregistration.md`, read in its §11) ended in its
decision rule 2. On the 46 QA calls production cut at 12,288 tokens, the re-ask's instruction sent on the first call
did best. Against today's cap resampled, it finished 39 against 14, passed 18 against 9, and spent 480,137 tokens
against 783,110. That rule says it does not ship on that evidence alone. The instruction would go on every QA first
call, and that population held only calls that were cut. This is the second check §8 named: the instruction on QA
first calls from the same window that were **not** cut.

**What had to be true before it was registered, all met:**
1. **The sample is fixed and committed:** `2-5-0-qa-first-call-instruction-population-2253.json` (§2).
2. **The plan is committed,** built by `engine_replay.py plan` from that sample (§3).
3. **The captured record is committed:** `2-5-0-qa-first-call-instruction-captured-2253.json` (§2). It holds each
   envelope's captured first call: tokens, latency, and whether the handler asked again. It holds no text.
4. **The tools are the first replay's,** unchanged: `--max-tokens`, `--first-call-note` with `--note-quote`, the arm
   manifest, the scorer (that replay's §9, on the branch this one stacks on).

---

## 1. The question

On QA first calls that already fit under 12,288, does sending the instruction cost first answers that pass? Does it
cost more passes than it gained on the calls that were cut?

**What it does not measure:**
- **Outcomes in a cycle,** for the reason the first replay gave: the reading is the handler's verdict on the first
  answer.
- **Small losses.** §6 says how small a loss this sample can see. A difference too small to read is not shown to be
  absent.
- **The `qa.test` calls with no stack:** 3 envelopes in the window, none of them cut. No decision can be read from 3
  envelopes, so they are left out.

## 2. The sample

**The population** is every `authoring_envelopes` row of task type `qa.test` or `qa.test_repair` with a stack, captured
on or after 2026-10-14T00:00Z, whose task's first LangFuse generation at or after the capture reported
`completion_tokens` below the envelope's `max_tokens` (12,288). It is the first replay's 2026-10-24 inventory, the
same envelopes, generations and matching, with the `at_cap` test reversed. That inventory read 423 envelopes. 46 were
cut, which leaves 377, and 374 once the 3 with no stack are left out.

**The sample** is 80 envelopes, drawn per stratum with `random.Random(22532).sample` over the sorted ids, strata in
sorted order:

| stratum | population | sampled | weight (population / sampled) |
|---|---|---|---|
| `qa.test`, FastAPI/React | 227 | 40 | 5.675 |
| `qa.test`, Next.js | 107 | 24 | 4.458 |
| `qa.test_repair`, FastAPI/React | 18 | 8 | 2.25 |
| `qa.test_repair`, Next.js | 22 | 8 | 2.75 |

The FastAPI/React `qa.test` stratum is sampled hardest. It is 229 of the window's 423 QA calls (54%), and only 2 of
those were cut, so the instruction can gain little there and any loss there costs the most.

**As captured:** a median of 6,632 completion tokens. 138.6 minutes of first-call latency in all. In 3 of the 80
(all Next.js `qa.test`), the handler made a later call before the next envelope, which means it asked again.

## 3. The fixed parts

| what | value |
|---|---|
| the sample | `docs/plans/verification-sets/2-5-0-qa-first-call-instruction-population-2253.json`, its own `sha256` field `fc7998722207942e…` (file sha256 `1e4c33f61964974e…`) |
| the plan | `docs/plans/verification-sets/2-5-0-qa-first-call-instruction-plan-2253.json`, from `engine_replay.py plan` with seed 2253: its own `sha256` field `4b6bad6cb0fb35bc…` (file sha256 `9ca54b0727e62dd2…`). Its drift panel is not run (§5) |
| the captured record | `docs/plans/verification-sets/2-5-0-qa-first-call-instruction-captured-2253.json`, sha256 `aae72d03f86f0446…` |
| generations | one per envelope per arm, seed 1001, so 80 calls an arm |
| the order | the plan's seeded shuffle, the same for both arms |
| the engine | the live `squadops-tensorfold` on `infra/tensorfold/recipes/candidates/qwen27b-nvfp4-parallel2.yaml` (#2742), the engine the first replay's arms ran on (its §10). It is shared with the nostromo crews. No restart, recipe change or engine switch during the run |
| the deploy | framework `5aaece83` in `squadops-eve`, the scorer's container. No deploy until the score is written. A rebuild before scoring is recorded, and each row carries the SHA it was scored on |
| each call's settings | the envelope's own, sent as in the first replay: production's sampling, reasoning on, and `parity_effort` sent as the TensorFold adapter sends it. Both arms at `max_tokens` 12,288. Only the note differs |
| the note | the first replay's §4.2, word for word: "keep any reasoning short so that the output fits." from `request.cycle_cap_truncated_retry.md`, as a last user message. Its folder ends `-note-f18fdf38` |
| a call's deadline | 1,800 s (`CALL_TIMEOUT`), as before. Each row records the captured deadline |
| the records | `var/engine_replay/2026-10-28-qa-first-call-instruction-2253/` in the main checkout |

## 4. The arms

- **The baseline:** the envelope at 12,288 with no note. Its folder is
  `tensorfold-qwen27b-nvfp4-parallel2-max12288`.
- **The instruction:** the envelope at 12,288 with the note. Its folder is
  `tensorfold-qwen27b-nvfp4-parallel2-max12288-note-f18fdf38`.

**Why a fresh baseline, not the captured answers.** The first replay's §8 named "their own captured answers'
verdicts" as this check's comparison. This check uses a fresh seeded call at today's cap instead, for two reasons
found in that replay's reading:
- **The handler changed.** In 45 of the first replay's 46 envelopes, today's handler did not rebuild the captured first
  call (`first_call_is_the_capture` false, its §11.4). A captured answer and a replayed one would differ in what they
  were asked as well as in the note.
- **Selection.** These envelopes were chosen because their captured call finished. A fresh call at the same cap can
  be cut by chance. Comparing the instruction's fresh calls with captured ones that were all finished would bias the
  check against the instruction, the mirror of the first replay's §4.4.

The captured record is still read, but described rather than used to decide (§6, reading 6).

## 5. The run

Both arms in one `--out`, in this order:

```bash
OUT=/home/jladd/Code/squad-ops/var/engine_replay/2026-10-28-qa-first-call-instruction-2253
PLAN=docs/plans/verification-sets/2-5-0-qa-first-call-instruction-plan-2253.json
RECIPE=infra/tensorfold/recipes/candidates/qwen27b-nvfp4-parallel2.yaml
# 1. the baseline: 80 calls
python scripts/dev/engine_replay.py run $PLAN --part held-out --engine tensorfold --recipe $RECIPE \
    --out $OUT --max-tokens 12288
# 2. the instruction: 80 calls
python scripts/dev/engine_replay.py run $PLAN --part held-out --engine tensorfold --recipe $RECIPE \
    --out $OUT --max-tokens 12288 \
    --first-call-note src/squadops/prompts/request_templates/request.cycle_cap_truncated_retry.md \
    --note-quote "keep any reasoning short so that the output fits."
# 3. the score
python scripts/dev/engine_replay.py score $OUT/tensorfold-qwen27b-nvfp4-parallel2-max12288 \
    $OUT/tensorfold-qwen27b-nvfp4-parallel2-max12288-note-f18fdf38 --out $OUT/scores.jsonl
# 4. the leak scan: no key or Bearer value anywhere under $OUT
```

- **No drift panel.** The first replay's 32 single-lane calls matched its two-lane calls 32 of 32, days apart.
- **Overlap.** The engine is shared. A call another client overlapped keeps its tokens, finish and verdict. Its wall
  time is reported apart, read from TensorFold's `done` lines that are not the run's own.
- **What stops it:** three failed calls in an arm (`THREE_FAILURES`), or a production cycle that needs the engine to
  itself. Either way it resumes with the same settings once the cause is read. The arm's manifest refuses a restart
  with other settings.
- **The estimate:** about 2.3 h an arm on the captured latencies, so about 4.5 to 5 h with the score.

## 6. The measures, fixed now

**Per call,** as in the first replay's §6: the finish or error, completion and reasoning tokens, wall time, time to
first token, decode rate, and the handler's verdict on the first answer (`pass`, or `asked_again`, `failed`, `raised`
or `error`, all of which fail).

**The denominator is every planned call:** 80 an arm. A failed call is neither finished nor passed.

**The readings,** each overall, by task type and by stack:
1. **Finished:** the count of `stop` per arm.
2. **Reasoning:** each arm's median reasoning tokens, and the count of envelopes whose instruction call reasoned less
   than its baseline call. A call with no count counts against.
3. **First answers that passed,** per arm, and the discordant envelopes (one arm passed, the other did not).
4. **The weighted difference in passes over the window,** `Δ_pass = Σ_strata weight × (instruction passes −
   baseline passes)`, with §2's weights. It estimates the passes the instruction would gain or lose over the
   window's 374 calls that were not cut. It is reported with a 90% interval from 10,000 bootstrap resamples of
   envelopes within each stratum (seed 2253).
5. **Tokens:** each arm's sum, and the weighted difference `Δ_tok`, computed the same way. A cut call costs 12,288
   plus a stand-in re-ask: the median completion tokens of the first replay's 38 finished re-asks (5,897).
6. **The captured record, described:** the 3 envelopes the handler asked again, and how each arm's call did on them.
   Each arm's median tokens and wall time are set beside the captured ones.
7. **Wall time:** each arm's median and total, and the count of `qa.test` calls past production's 300 s deadline.

**The net over the window** joins this check to the first replay. That replay ran its whole population: all 46 cut
calls, so its differences are counts, not estimates.
- **Passes:** `net_pass = +9 + Δ_pass`, the instruction's 18 passes against today's cap's 9 on the cut calls, plus
  this check's estimate on the rest.
- **Tokens:** `net_tok = −302,973 + Δ_tok`, its 480,137 against 783,110, plus this check's estimate.

**What this sample can see.**
- **The break-even:** the instruction gained 9 passes on the cut calls. It loses that much over the other 374 when
  it costs about 2.4% of their first answers (9 / 374).
- **The noise:** a difference that small is far below what 80 paired calls resolve. Two fresh samples of one envelope
  already disagree often, since a prompt that differs by one message changes every token after it. With a FastAPI
  `qa.test` discordant envelope weighted at 5.7, one envelope's change moves `Δ_pass` by more than half of the +9.
- **So:**
  - **a decision to keep the instruction** reads as "no loss this sample can see, and the point estimate favours
    it";
  - **a decision against it** reads as "a loss this sample can see, or a point estimate against it";
  - **the bootstrap interval** says how wide that is, and the record quotes it.

**"Clear"** is the first replay's: the exact two-sided sign test on the discordant envelopes, p < 0.05.

## 7. The predictions, about mechanism

- **P3. The instruction shortens reasoning on calls that fit, too:** in at least 54 of the 80 envelopes (two thirds),
  the instruction's call reasoned for fewer tokens than the baseline's. Fewer would mean the instruction's effect on
  the cut calls came from calls already reasoning long, not from the instruction in general.
- **P4. The instruction is not cut more often:** its count of `stop` is at least the baseline's. Fewer would mean a
  short-reasoning call writes a longer answer, enough to reach the cap.

**Read without a prediction:** the pass rates, and everything by stratum.

## 8. The decision rule

Applied in this order. The first that holds is the result:

1. **Propose the instruction on QA's first call,** when all four hold:
   - the baseline's first answers do not pass clearly more often than the instruction's (sign test, overall);
   - `net_pass` is above 0, so the point estimate gains more passes on the cut calls than it loses on the others;
   - the instruction finishes at least as often as the baseline;
   - `net_tok` is no more than 0.

   **A proposal, not a change.** It goes into the line's plan through the #2253 row and a PR of its own, since it alters
   every QA first call and what a regression roll measures. That PR names this record, its interval and its limit.
   The owner reads it there.
2. **A scoped proposal,** when rule 1 fails only because the FastAPI/React strata lose:
   - their weighted pass difference is below 0;
   - the Next.js strata's weighted difference plus the cut Next.js calls' +8 (15 passes against 7) is above 0;
   - every other condition of rule 1 holds when it is read on Next.js alone, with the cut Next.js calls' tokens
     (459,820 against 740,927, so −281,107).

   The instruction for Next.js QA only is then **named as an option for the owner,** not proposed. A stack-scoped
   prompt is a design question (stack specifics in shared code), not a measurement's call.
3. **Otherwise, no change.** The record says which condition fell short. #2253 then closes on "no change", the outcome
   its plan row allows.

**This run changes no profile, prompt or deadline.**

## 9. Changes after registration

None yet. A change to anything above after registration is recorded here with its reason, before the reading it
affects.
