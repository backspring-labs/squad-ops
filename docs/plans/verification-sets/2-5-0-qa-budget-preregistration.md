# 2.5.0 — pre-registration of the QA output-budget replay (#2253)

**Status: REGISTERED 2026-10-24, before any call. RUN 2026-10-27 on the two-lane engine (§10), READ 2026-10-28 (§11):
rule 2 holds, so the instruction goes to the second check on first calls that finished. Nothing ships on this run.**

**What had to be true before it was registered, all met:**
1. **The population is fixed and committed:** `2-5-0-qa-budget-population-2253.json` (§2).
2. **The plan is committed,** built by `engine_replay.py plan` from that population (§3).
3. **The control's record is committed:** `2-5-0-qa-budget-control-2253.json`, each envelope's original call and
   the re-ask after it (§2, §4.3).
4. **The tool changes the run needs are committed, with their tests** (§9).

---

## 1. What the run measures

The 2.5 plan's #2253 row: "Before any change: compare, for both task types, the suites' outcomes and the time spent
under the two remedies the read names, a higher cap (a replay of the cut envelopes at it) and a lower reasoning level
for test authoring. 'No change' is a valid outcome."

The two remedies are those of #2253's headroom read (2026-10-18):
- **Raise QA's budget**, here to 16,384. It saves the re-ask when the uncut answer fits under the new cap, and costs
  the extra thinking time when it doesn't.
- **Lower QA's reasoning for test authoring,** here by sending the re-ask's own instruction to keep reasoning short on
  the first call. It costs whatever the reasoning was buying in suite quality.

**The question:** on the `qa.test` and `qa.test_repair` calls production's engine actually cut at 12,288, does either
remedy get a finished, accepted first answer clearly more often than today's cap, and at what cost in tokens and time?

**What it does not measure:**
- **The instruction's cost on calls that weren't cut.** The instruction would go on every QA first call. This population
  holds only calls that were cut, so a decision for it needs a second check on calls that finished (§8).
- **A literal lower reasoning level.** Production's TensorFold adapter sends `reasoning_effort: medium`, the recipe's
  `parity_effort`, for every call with thinking on, whatever level the call names
  (`adapters/llm/tensorfold.py:336-341`). The Next.js QA envelopes name `low` and the FastAPI/React ones `medium`; both
  are sent `medium`. So a level set in a profile or the reasoning policy changes nothing on production's engine. The
  instruction is the only first-call lever this run can measure. Sending a real `low` would be an adapter or recipe
  change, and a different measurement.
- **Outcomes in a cycle:** correction rounds, acceptance, the suites' own results when run. The reading is the handler's
  verdict on the first answer, as the 2.3 replay's validity gate read it.
- **Ollama.** Every envelope here was captured on TensorFold, the engine production runs.

## 2. The population: every QA call production's engine cut since 2026-10-14

**The rule:** an `authoring_envelopes` row of task type `qa.test` or `qa.test_repair`, captured on or after
2026-10-14T00:00Z, whose task's first LangFuse generation at or after the capture reported `completion_tokens` at the
envelope's `max_tokens` (12,288). The envelope is the task's first call (SIP-0110 §0.11), so a generation is matched by
task id and call order. In the 28 tasks with more than one envelope (a task dispatched again), each envelope gets the
generations before the next one's capture.

**How it was read** (2026-10-24, read-only):
- **The envelopes:** 423 rows, all on `qwen3.8-27b-tf-nvfp4`, all at `max_tokens` 12,288, captured 2026-10-14 to
  2026-10-23.
- **LangFuse:** its public API, read from inside `squadops-eve`, whose environment holds the keys (the runtime
  container's holds only the host). 3,047 generations from 2026-10-14 on. Every one of the 423 envelopes had one.
- **TensorFold's server log,** from its start at 2026-10-14T00:00Z: each call's `finish=` and its warning that a reply
  "reached max_tokens while still thinking". All 46 cut calls matched one line each (by prompt and completion tokens,
  within 15 minutes), and every one says `finish=length`.
- **The QA agent's own per-call line** (`reasoning_tokens=`, `termination=`), from the eve logs saved under
  `~/squadops-deploy-logs/` and the campaigns' `var/` records. They cover only part of the window: 10 of the 46 calls.

| task type | stack | envelopes | cut at 12,288 |
|---|---|---|---|
| `qa.test` | Next.js | 145 | **38 (26%)** |
| `qa.test` | FastAPI/React | 229 | 2 (0.9%) |
| `qa.test` | none | 3 | 0 |
| `qa.test_repair` | Next.js | 27 | **5 (19%)** |
| `qa.test_repair` | FastAPI/React | 19 | 1 (5%) |
| **all** | | **423** | **46** |

So 43 of the 46 are Next.js. The FastAPI/React cells hold 3 envelopes, too few to read alone.

**How the 46 were cut:**
- **21 never reached the answer.** TensorFold warned that the reply was still thinking at the cap, and LangFuse holds
  no answer for them. Production re-asked them with the empty-response asset (`request.cycle_cap_exhausted_retry`):
  13 of those re-asks finished, and 8 were cut again.
- **25 were cut mid-answer.** Production dropped the cut block and re-asked with #2149's asset
  (`request.cycle_cap_truncated_retry`). All 25 re-asks finished.
- **Where the agent's log has the split** (8 of the 25 mid-answer cuts), reasoning took 7,863 to 10,921 of the 12,288
  tokens, a median of 8,758. On the same 8 prompts, #2149's re-ask, told to keep reasoning short, reasoned for 229 to
  2,738 tokens, a median of 1,711.
- **The 38 re-asks that finished** used a median of 5,897 tokens.

**What they cost** (LangFuse's latency, which runs from the handler's start):
- the 46 cut first calls: a median of 233 s (155 to 291), 170 minutes in all, every token of it discarded;
- the 46 re-asks: a median of 116 s, 102 minutes in all.

**The decode rate** on those calls (TensorFold's log): a median of 54.8 tokens/s (43.2 to 82.7). It was 50.9 on calls
cut while thinking and 67.8 on calls that reached the answer.

**The deadline, a second cap.**
- **`qa.test` sends `timeout_seconds: 300`** with every call: the handler's `generation_timeout`, at its default, since
  no profile in the window set one (`src/squadops/capabilities/handlers/cycle/qa_test.py:2073`). Every one of the 377
  `qa.test` envelopes carries it. The TensorFold adapter holds the whole call to it (`adapters/llm/tensorfold.py:539`).
- **`qa.test_repair` sends none,** so the adapter's own deadline applies: the agent's `llm.timeout`, 1,800 s on
  `squadops-eve` (read 2026-10-24).
- **No TensorFold call since 2026-10-14 ran more than 300 s** of engine time (time to first token plus decode, from
  its log). The slowest cut first call took 290.9 s.
- **At the population's median rate,** 16,384 tokens take about 299 s to decode, before the prompt is read.
- **A call past its deadline is not a cut.** It raises `LLMTimeoutError`, and the call loop re-raises it without
  asking again with the fact (`src/squadops/capabilities/handlers/cycle/base.py:1487`).

So a raised cap for `qa.test` ships with a raised deadline or not at all, and §6 measures what it would need.

## 3. The fixed parts

| what | value |
|---|---|
| the population | `docs/plans/verification-sets/2-5-0-qa-budget-population-2253.json`, sha256 `9c03eb4ca8f18967…` (its own `sha256` field `4dd2873fafcf9ef9…`): the 46 envelopes in `engine_replay.py select`'s shape, all held out |
| the plan | `docs/plans/verification-sets/2-5-0-qa-budget-plan-2253.json`, sha256 `9c8b264183b4fb16…` (its own `sha256` field `3dd3a2a93f52164b…`), from `engine_replay.py plan` with seed 2253. Its drift panel is not run (§5) |
| the control's record | `docs/plans/verification-sets/2-5-0-qa-budget-control-2253.json`, sha256 `373f45602ded5ca2…` |
| generations | one per envelope per arm, seed 1001 (the plan's), so 46 calls an arm |
| the order | the plan's seeded shuffle, the same for every arm |
| the engine | production's: `squadops-tensorfold`, running since 2026-10-14T00:00Z on the frozen recipe `infra/tensorfold/recipes/qwen27b-nvfp4.yaml` (sha256 `a3d260ecd24ca895…`): TensorFold 0.6.6 `cb2ebf05`, the NVFP4 checkpoint, the DFlash2 drafter, `parity_effort: medium`. No restart, recipe change or engine switch during the run |
| the deploy | framework `4b982d6d` in `squadops-eve`, the scorer's container. A rebuild before scoring is recorded, and the score runs on whatever the container then holds, its SHA recorded per row |
| each call's settings | the envelope's own: messages, reasoning on, and production's sampling (temperature 1, top_p 0.95, top_k 20, min_p 0), sent as the TensorFold adapter sends them. Only the cap and, in one arm, the note differ (§4) |
| a call's deadline in the replay | 1,800 s (`engine_replay.py`'s `CALL_TIMEOUT`). Production's deadline is **not** enforced. Each row records it (`captured_timeout_seconds`), and §6 compares every call's wall time with it |
| the validators | each task type's own handler in `squadops-eve`, through `engine_replay.py score` (`authoring_score.py`) |
| the records | `var/engine_replay/<run date>-qa-budget-2253/` in the checkout that runs it, copied to the main checkout's `var/engine_replay/` after the reading if that is another checkout |

## 4. The arms

### 4.1 The raised cap

The envelope as captured, at `max_tokens` 16,384 (`--max-tokens 16384`). Its folder is
`tensorfold-qwen27b-nvfp4-max16384`.

### 4.2 The instruction on the first call

The envelope at 12,288 (`--max-tokens 12288`), with one user message after its own:

> keep any reasoning short so that the output fits.

- **The text** is #2149's re-ask's own instruction, word for word, from its asset:
  `src/squadops/prompts/request_templates/request.cycle_cap_truncated_retry.md` (sha256 `192cd8d9610b369d…`). It is
  sent through `--first-call-note` with `--note-quote`. The tool refuses a quote the asset does not hold, so the note
  can't be a paraphrase.
- **Only that clause is quoted.** The rest of the asset states that a previous response was cut off, names its tokens
  and its cut block, and asks for the answer "again" with every block closed. None of that is true of a first call,
  and closing blocks is a second instruction. The clause keeps its lowercase first word, as written.
- **It is sent the way the re-ask sends its fact:** a user message after the envelope's own messages
  (`base.py:1576`: `[*messages, ChatMessage(role="user", content=retry_fact)]`).
- **Its folder** is `tensorfold-qwen27b-nvfp4-max12288-note-f18fdf38` (the note's sha256 begins `f18fdf38`).

### 4.3 The control: the original cut call

The call production made, cut at 12,288 by selection, and the re-ask that followed it, from the control's record.
Its first answer is asked again by construction, so its first-answer pass count is 0 of 46. Its re-asks are
summarised in §2.

### 4.4 Today's cap, resampled: read from the raised cap's own samples

**Why it is needed.** The population was chosen because its calls were cut. A fresh sample at the same cap may finish
by chance, so any new sample is expected to beat the control by selection alone. The fair comparison for either
remedy is a fresh sample at today's cap, with the same seed.

**How it is read without a third arm of 46 calls.**
- Every call carries an explicit seed, and TensorFold's sampling is reproducible from it: the 2.3 replay's panel calls
  were byte-identical hours apart at temperature 1.
- `max_tokens` only says where to stop, so it should change no token before the stop.
- If so, a seeded 16,384 call's first 12,288 tokens are what a 12,288 call with that seed would have produced.
- Read from the raised cap's sample, today's cap would have:
  - **finished** where that sample finished within 12,288 tokens, with the same answer and so the same verdict;
  - **cut** where the sample ran past 12,288. The handler then asks again: not a pass.

**The prefix check.** This rests on the engine behaving as described, so it is checked first.
- **The calls:** the plan's first three envelopes, run at 12,288 with seed 1001 and no note (`--max-tokens 12288
  --only …`). Their folder is `tensorfold-qwen27b-nvfp4-max12288`.
- **It passes when,** for each of the three, the 12,288 call's thinking and answer are each a prefix of the raised-cap
  call's, and equal to them where the 12,288 call finished. This is read from the raw stream files.
- **If any of the three fails,** the resampled arm is run in full: the other 43 envelopes, the same way. It is then
  read from its own calls before any reading is made, at about 2.5 h more.

## 5. The run

All three arms in one `--out`, in this order:

```bash
OUT=var/engine_replay/<run date>-qa-budget-2253
PLAN=docs/plans/verification-sets/2-5-0-qa-budget-plan-2253.json
RECIPE=infra/tensorfold/recipes/qwen27b-nvfp4.yaml
# 1. the raised cap: 46 calls
python scripts/dev/engine_replay.py run $PLAN --part held-out --engine tensorfold --recipe $RECIPE \
    --out $OUT --max-tokens 16384
# 2. the prefix check: 3 calls
python scripts/dev/engine_replay.py run $PLAN --part held-out --engine tensorfold --recipe $RECIPE \
    --out $OUT --max-tokens 12288 --only \
    d50f97d015df3fdfeb1e8772bf797132a2a4e548853f3b76666d00545730b5a6 \
    f9501530a1f06b24b87ddc6fd1653dfdaa69901dea906c44c82f9e4f95053c7d \
    6e00ac9f2d2e3768f91f7d591bf3aa262ef993087de784d4ebcef980badbdb01
# 3. the instruction: 46 calls
python scripts/dev/engine_replay.py run $PLAN --part held-out --engine tensorfold --recipe $RECIPE \
    --out $OUT --max-tokens 12288 \
    --first-call-note src/squadops/prompts/request_templates/request.cycle_cap_truncated_retry.md \
    --note-quote "keep any reasoning short so that the output fits."
# 4. the score: both arms' first answers, through their handlers in squadops-eve
python scripts/dev/engine_replay.py score $OUT/tensorfold-qwen27b-nvfp4-max16384 \
    $OUT/tensorfold-qwen27b-nvfp4-max12288-note-f18fdf38 --out $OUT/scores.jsonl
```

**No drift panel.** Every arm runs on one engine, which stays loaded throughout. On this engine and recipe, the 2.3
replay's panel was 14 of 14 identical between the start and the end of its arm, hours apart. The prefix check, run
between the two arms, is a
drift check too: a mismatch there is either the property failing or the engine drifting, and either way the resampled
arm is then run in full.

**The engine is shared with production.** The supervisor confirms before the run that nothing else needs it.
- **Each arm's wall times are read only for calls no other client overlapped,** checked afterwards from TensorFold's
  log: its `done` lines that are not the arm's own.
- **A call another client overlapped** keeps its tokens, finish and verdict. Its wall time is reported apart.

**What stops it:**
- **Three failed calls in an arm** (`THREE_FAILURES`, the replay's own stop) stop that arm. It is reported, and
  resumed with the same settings once the cause is read.
- **A restart with other settings is refused** by the arm's manifest (§9).
- **A production cycle needing the engine** stops the run between calls, at the supervisor's word. It resumes where
  it stopped.

**The estimate:**
- the raised cap: 46 calls of up to 16,384 tokens at about 55 to 65 tokens/s alone on the engine, about 3 to 3.5 h;
- the prefix check: about 12 minutes;
- the instruction: 46 calls of at most 12,288 tokens, about 2 h;
- the score: about 10 minutes.

About 5.5 to 6 h in all.

## 6. The measures, fixed now

**Per call:**
- the finish (`stop` or `length`), or the error;
- completion tokens, and reasoning tokens (TensorFold's `completion_tokens_details.reasoning_tokens`);
- wall time on the replay's own clock, time to first token, and decode rate;
- the handler's verdict on the first answer. `pass` is a first answer the handler accepted without asking the model
  again; `asked_again`, `failed`, `raised` and `error` all fail. Each row also records whether today's handler asks
  the question the answer was written for (`first_call_is_the_capture`).

**The denominator is every planned call:** 46 an arm. A failed call is neither finished nor passed, and is never
dropped.

**The readings,** each overall, by task type, and by stack:
1. **Finished:** the count of `stop` per arm, the resampled arm included.
2. **Reasoning:** each arm's median reasoning tokens, and the count of envelopes whose instruction-arm call reasoned
   less than its raised-cap call. A call with no count counts against.
3. **What the raised cap bought.** Its samples fall into three groups:
   - finished within 12,288: the resample alone;
   - finished between 12,289 and 16,384: bought by the raise;
   - cut at 16,384.
4. **First answers that passed,** per arm.
5. **Tokens to an answer,** per envelope and summed, under each of three regimes: today's cap resampled, the raised
   cap, the instruction.
   - **A finished call** costs its completion tokens.
   - **A cut call** costs its cap plus the completion tokens of the re-ask production made for that envelope (the
     control's record), standing in for the re-ask the replay does not run.
6. **Wall time:** each arm's median and total. For the raised cap's `qa.test` calls, the count whose wall time
   passed production's 300 s deadline, and the longest finished one.
7. **The control,** fixed now from its record:
   - 46 of 46 cut, and 0 first answers passed;
   - 38 of 46 re-asks finished;
   - 170 minutes of cut first calls and 102 minutes of re-asks.

**Uncertainty, and "clear".** N is 46 and the comparisons are paired. **A difference is clear** when the exact
two-sided sign test on the discordant envelopes gives p < 0.05, in that remedy's favour. Discordant envelopes are those
where one regime finished, or passed, and the other did not. For example, with no envelope going the other way, it
takes 6. Every reading by task type or stack below the whole population is reported as observed, never as clear.

## 7. The predictions, about mechanism

Fixed before any call, in SIP-0111 §4's style for a small N. Each names what would falsify it:
- **P1. Under the raised cap, most envelopes finish:** at least 24 of the 46 end `stop` at 16,384. Fewer would mean
  the cut calls think past 16,384 too, so the cap is not what limits them.
- **P2. Under the instruction, most finish at 12,288, reasoning less than under the raised cap:**
  - at least 24 of the 46 end `stop` at 12,288;
  - in at least 24 of the 46 envelopes, the instruction's call reasoned for fewer tokens than the raised cap's.

  Fewer would mean the instruction, which shortens the re-ask's reasoning (§2), does not shorten a first call's.

**Read without a prediction:**
- the pass rates;
- the resampled arm's finish count (reading 3's first group);
- the split of the raised cap's finishes between the resample and the raise;
- everything by stack and task type.

## 8. The decision rule

Applied in this order. The first that holds is the result:

1. **Raise the cap,** when all four hold:
   - the raised cap finishes clearly more often than today's cap resampled. That needs at least 6 envelopes bought by
     the raise, since today's cap can't finish where the raised cap was cut;
   - it finishes clearly more often than the instruction;
   - its first answers pass at least as often as the instruction's;
   - its tokens to an answer, summed over the 46, are no more than today's cap resampled. The re-asks it saves must
     pay for the tokens it adds.

   The decision names the `qa.test` deadline it needs, since 300 s does not cover a 16,384 call at these rates. As a
   floor, that is the longest finished `qa.test` call's wall time, rounded up to the next minute. Production shares the
   engine, so it may need more, and the profile change carries both values.
2. **Keep the instruction on QA's first call,** when all three hold:
   - the instruction finishes clearly more often than today's cap resampled;
   - its first answers pass at least as often;
   - its tokens to an answer, summed, are no more.

   **It does not ship on this evidence alone.** It changes every QA first call, and this population holds only calls
   that were cut. So it opens a second pre-registered check first, the plan row's "first calls that finished": the
   instruction on a seeded sample of `qa.test` and `qa.test_repair` envelopes from the same window whose first call
   was not cut, against their own captured answers' verdicts.
3. **Otherwise, no change.** That includes a remedy that finishes more but passes less, and one whose difference is
   not clear. The record then says which reading fell short.

**Either change alters what a regression roll measures,** as #2253 says. So it goes in a line's plan, through the plan
row and a PR of its own. This run changes no profile, prompt or deadline.

## 9. Changes to the tools, committed with this registration

Committed in `f008e304`, before this registration and before any call, each with a test that names the bug it
catches:
- **`--max-tokens N`** sends every call at N, above the envelope's cap or below it. The draft check's
  `--max-tokens-cap` only lowers a cap. A raised-cap arm run with it would have sent 12,288 and measured nothing.
- **`--first-call-note ASSET` with `--note-quote TEXT`** appends the asset's text, or the quoted part of it word for
  word, as a last user message. A quote the asset does not hold is refused, and so is a body with a template variable
  left in it.
- **Each arm's `manifest.json`** records its settings on its first call: the cap, the note with its asset's sha256,
  the recipe's and the plan's sha256s, and the script's own. A restart with other settings is refused. Without it, the
  restart would append to the first arm's summary and skip every call that arm had made.
- **The arm's folder names both overrides.** So two arms in one `--out` stay apart.
- **`score` refuses answers that share a key,** two arms under one name, whose verdicts it would otherwise hand to
  both.
- **The scorer hands the handler the engine's termination,** as production's TensorFold adapter does. Without it, the
  handler's cap check read the token count against the envelope's 12,288. An answer that finished past it under the
  raised cap, its last block left open (#431), would have been scored as cut.
- **Each row records** the call's captured deadline, the number of messages sent and the note's sha256.

A change to any of these after registration is recorded here with its reason, before the reading it affects.

## 10. Amendment, 2026-10-27: the arms run on the two-lane engine

**What changed.** The first arm stopped on 2026-10-24 at 32 of 46 calls when the owner's usage limit paused the work.
By 2026-10-27 the live TensorFold was serving `infra/tensorfold/recipes/candidates/qwen27b-nvfp4-parallel2.yaml`
(#2742). That recipe differs from the frozen `qwen27b-nvfp4.yaml` only by `--parallel 2`, and other clients share the
engine. The owner asked why the run couldn't stay on the parallel engine, and had its reproducibility checked first. On
that check's result, every arm is run again from its first call on the two-lane engine, into a fresh `--out`:
`var/engine_replay/2026-10-27-qa-budget-2253-parallel2`. The commands are §5's, with that recipe. §5's rule still holds:
every arm runs on one engine, which stays loaded throughout.

**The evidence.** §4's derived arm needs a seeded call to reproduce exactly. The check
(`var/engine_replay/2026-10-27-parallel2-repro-2253/PREREG.md`, its rule written before its calls) re-ran recorded
envelopes on the two-lane engine:
- **alone:** the plan's first three envelopes (d50f97d0…, f9501530…, 6e00ac9f…), plus a fourth lone repeat of d50f97d0…;
- **together:** d50f97d0… and f9501530…, launched at once, decoding side by side for about 4.3 minutes;
- **the result:** every call matched its single-lane record: the same `token_sha`, finish and completion tokens, and
  byte-identical reasoning and content. Sharing changed only the decode rate (56.7 against 67.9 tok/s, and 40.3
  against 44.6). One repeat was served from the prefix cache and reproduced as well.

**What the 32 single-lane calls become.** They are a reproducibility panel, read against the same envelopes in the new
first arm: the `token_sha` match count, and each mismatch with its overlap. They enter no reading in §6.

**Wall times.** These are now the two-lane engine's. §5's rule is unchanged: a call another client overlapped keeps
its tokens, finish and verdict, and its wall time is reported apart. Decision rule 1's `qa.test` deadline floor is read
from calls nothing overlapped, and the record says it was measured on two lanes.

**The resumed first call.** It sent the whole multi-entry key file as one header because the branch predated #2742's
key reader. h11 refused it before sending, and the refusal's text carried the key. The three rows it wrote were
removed, and nothing reached the engine. The defect is #2744.

## 11. The reading, 2026-10-28

The run went as §10 set it out, from 19:42Z on 2026-10-27 to 01:37Z on 2026-10-28: 46 raised-cap calls, the 3 prefix
calls, 46 instruction calls, then the score in `squadops-eve` at framework `5aaece83`. No call failed. The leak scan
after it found nothing. The records are in `var/engine_replay/2026-10-27-qa-budget-2253-parallel2/`:
`scores.jsonl` (sha256 `58fc7ae4c6e75a1e…`), and `readout.txt` (`ad08f69e7ec02a40…`), which `read_2253.py` beside it
prints from the summaries, the scores and the control's record.

**Nothing else used the engine.** TensorFold's log over the run holds 95 `done` lines, which are the run's 95 calls,
and three `GET /v1/models`. So every wall time below is a call alone on the two-lane engine.

**The prefix check passes.** All three 12,288 calls were cut at 12,288, and each one's thinking and answer are a prefix
of its raised-cap call. The raised cap ran past 12,288 on all three (one finished at 15,086 tokens, two were cut at
16,384), so §4.4 predicts a cut for each, and that is what happened. So the resampled arm is read from the raised cap's
samples, as §4.4 says.

**The reproducibility panel (§10) matches 32 of 32.** Each of the 32 single-lane calls from 2026-10-24 has the same
`token_sha`, finish and completion tokens as the same envelope's call in the new first arm.

### 11.1 The readings (§6)

| reading, all 46 | today's cap, resampled | raised cap (16,384) | instruction (12,288) |
|---|---|---|---|
| 1. finished (`stop`) | 14 | **36** | **39** |
| 2. median reasoning tokens | the raised cap's | 9,514 | 6,252 |
| 4. first answers passed | 9 | 17 | **18** |
| 5. tokens to an answer, summed | 783,110 | 705,493 | **480,137** |
| 6. wall time, median / total | (not run) | 231 s / 179 min | 159 s / 128 min |

- **Reasoning (2):** the instruction's call reasoned less than the raised cap's in 43 of the 46 envelopes.
- **What the raised cap bought (3):** 14 finished within 12,288, which is the resample alone. 22 finished between
  12,289 and 16,384, bought by the raise, and 8 of those passed. 10 were cut at 16,384.
- **The deadline (6):** 8 of the raised cap's 40 `qa.test` calls ran past production's 300 s, the longest 373.5 s.
  The longest that finished took 318.6 s. None of the instruction's calls passed 300 s.
- **Cut while thinking:** 2 of the raised cap's 10 cuts and 2 of the instruction's 7 had no answer at all.
- **Decode rate:** a median of 57.9 tok/s for the raised cap and 55.7 for the instruction.
- **The control (7)** is §6's: 0 of 46 passed, 38 of 46 re-asks finished, 170 minutes of cut first calls and
  102 minutes of re-asks.

**By group, as observed** (none of these is read as clear):

| group | n | resampled fin / pass | raised cap fin / pass | instruction fin / pass |
|---|---|---|---|---|
| `qa.test` | 40 | 11 / 6 | 32 / 13 | 35 / 14 |
| `qa.test_repair` | 6 | 3 / 3 | 4 / 4 | 4 / 4 |
| Next.js | 43 | 12 / 7 | 33 / 14 | 36 / 15 |
| FastAPI/React | 3 | 2 / 2 | 3 / 3 | 3 / 3 |

### 11.2 The predictions (§7)

- **P1 holds:** 36 of 46 ended `stop` under the raised cap (at least 24 needed).
- **P2 holds,** both halves: 39 of 46 ended `stop` under the instruction, and the instruction's call reasoned less in
  43 of 46 (at least 24 each). The re-ask's instruction shortens a first call's reasoning too.

### 11.3 The decision rule (§8)

Each comparison is the exact two-sided sign test on the discordant envelopes.

| comparison | first only | second only | p |
|---|---|---|---|
| raised cap vs resampled, finished | 22 | 0 | 4.8e-7, **clear** |
| raised cap vs instruction, finished | 2 | 5 | 0.45 |
| instruction vs resampled, finished | 27 | 2 | 1.6e-6, **clear** |
| instruction vs resampled, passed | 11 | 2 | 0.022, **clear** |

- **Rule 1, raise the cap, does not hold.** It finishes clearly more often than today's cap, but not more often than
  the instruction: it finished alone on 2 envelopes, and the instruction on 5. It also passed less (17 against 18). So no
  deadline is named.
- **Rule 2, keep the instruction on QA's first call, holds.** All three conditions are met:
  - it finishes clearly more often than today's cap resampled;
  - its first answers pass more often (18 against 9);
  - it spends fewer tokens in all (480,137 against 783,110).

**The result is rule 2's.** As §8 says, it does not ship on this evidence. It opens the second pre-registered check:
the instruction on a seeded sample of `qa.test` and `qa.test_repair` first calls from the same window that were not
cut, against their own captured answers' verdicts. Until that check reads, no profile, prompt or deadline changes.

### 11.4 What the reading does not cover

- **The verdicts come from today's handler, which no longer asks the captured question exactly.** In 45 of the 46
  envelopes, `first_call_is_the_capture` is false: today's handler, given the captured inputs, builds a first call whose
  messages differ from the capture's (a digest comparison, `scripts/dev/authoring_score.py:99`). What differs was not
  read. The comparison is still paired, since one handler reads every arm's answer to an envelope. But the pass counts
  are not a production pass rate.
- **The resampled arm's verdicts are the raised cap's,** on the 14 envelopes it finished within 12,288. The prefix
  check makes that exact for the tokens. The verdict follows from the same answer.
- **Two lanes, used one call at a time.** The wall times are the two-lane engine's with nothing else running. Production
  shares the engine with the nostromo crews, so a call there can take longer.
- **The FastAPI/React cells** hold 3 envelopes, too few to read alone, as §2 said.
