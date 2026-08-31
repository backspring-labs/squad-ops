# 1.7.0 — the reasoning budget re-read and the #924 split replay

The measurement §6.1 criteria 1 and 2 ask for, taken on the post-#1203 deploy
(runtime-api `bbc6506df517`, Python 3.12, HEAD `fd4e4a9e`) using the two shakeout
cycles run on it: `cyc_b2bbbc234d12` (nextjs_ts) and `cyc_c70eeb8f9459`
(fullstack_fastapi_react), both accepted.

Criterion 1 asks that "#924's budget half [be] re-read against the new distribution and
recorded either way". Criterion 2's first sub-clause asks for "the #924 probe replayed
through the port with the `none`/`high` split reproduced from our own telemetry".

**Criterion 1 is met and the answer is negative — there is no budget pressure.**
**Criterion 2's sub-clause is NOT met: the split does not reproduce, and could not have
been sourced from telemetry as written.** Both are recorded below with the evidence.

## 1. Why this was measurable now and not before

The reasoning channel was invisible until three fixes landed in sequence: #410 put
`reasoning_text` on the port, #1194 made the *streaming* path actually populate it (the
path every handler calls — #410 had fixed only `chat()`), and #1195 rendered its length
in the emission log, which is the only place the figure exists on Ollama at all. Ollama
reports no separate thinking token count; `eval_count` is the total.

So every prior reading of "how much of a completion budget does thinking consume" was an
inference from token counts against stored output length. This is the first direct one.

## 2. The budget re-read (criterion 1)

35 emissions across the two cycles, each scored against the cap that applies to it: 8,192
from the `qwen3.8:27b` registry clamp, 12,288 for the qa role under the `full-38` profile's
`max_completion_tokens` override (#998).

**No emission came within 10% of its cap. The maximum was 89%.**

| handler | cap | completion | % of cap | thinking (est. tok) | % thinking |
|---|---:|---:|---:|---:|---:|
| `plan_authoring_service` | 8192 | 7317 | 89% | 4516 | 62% |
| `plan_authoring_service` | 8192 | 7185 | 88% | 3596 | 50% |
| `development.develop` | 8192 | 6511 | 79% | 3775 | 58% |
| `development.design_plan` | 8192 | 6495 | 79% | 620 | 10% |
| `development.author_manifest` | 8192 | 6185 | 76% | 4541 | 73% |
| `governance.prepare_plan_authoring_brief` | 8192 | 5427 | 66% | 2866 | 53% |
| `data.research_context` | 8192 | 5406 | 66% | 662 | 12% |
| `qa.define_test_strategy` | 12288 | 5417 | 44% | 344 | 6% |
| `qa.test` | 12288 | 3657 | 30% | — | — |
| `governance.correction_decision` | 8192 | 199 | 2% | — | — |

(Ten of 35 shown, ordered by cap utilisation; the full set is reproducible from the agent
container logs' `emission shape:` lines.)

### What it says

- **The pressure #998 responded to is absent.** That override was added because the qa
  author "sat at or within 3% of the 8,192 cap on four of ten emissions in the 1.6.4 set".
  In this set the qa emissions peaked at 5,417 tokens — 44% of the 12,288 cap, and only 66%
  of the old 8,192. **The override is currently unused headroom.** It should not be removed
  on this evidence alone: one set on one workload is not the ten-emission distribution that
  justified it, and the failure it prevents is expensive. But it is no longer load-bearing
  here, and that is worth knowing before anyone treats it as a tuned constant.
- **Thinking genuinely consumes the budget, so #924's premise holds.** Present on 29 of 35
  emissions, median ~1,100 tokens, maximum ~4,541 — up to 73% of a single emission
  (`development.author_manifest`). The caps simply absorb it.
- **`plan_authoring_service` is the one to watch.** Both its emissions are the top two by
  utilisation (89%, 88%) and both are thinking-dominated (62%, 50%). It has the only
  plausible path to truncation in this distribution.

### The estimate, stated as an estimate

Thinking tokens are derived as `reasoning_chars / 4`. Ollama reports no thinking token
count — that is #1195's entire reason for existing — so this is a conversion, not a
measurement. The ordering of handlers is robust to the divisor; the exact percentages are
not. A reader wanting exact figures needs a provider that reports the count (Atlas or vLLM,
neither currently in service).

## 3. The #924 split replay (criterion 2, sub-clause 1)

### It does not reproduce

Identical prompt, identical model, through the deployed adapter, three runs per level:

| level | completion tokens | content chars | fences | reasoning chars |
|---|---:|---:|---:|---:|
| `none` | 665 | 2,230 | 16 | — |
| `high` | 950 | 2,197 | 16 | 1,158 |

**Ratio 1.4×. #924 measured 13.9×** (5,727 tokens with the channel on, 413 with it off, on
the deployed qa fill brief).

The accounting is internally coherent, which is the part worth keeping: the *content* is
the same size at both levels (2,230 vs 2,197 chars, 16 fences either way — the deliverable
does not change), and the extra 285 tokens is almost exactly the thinking text at
1,158 chars ≈ 290 tokens. The channel costs what it produces.

### Two readings, not separated by this evidence

1. **The 13.9× was the defect, and it is fixed.** #1173 (the completion budget ignored the
   declared reasoning level) and #927 (the cycle/CRP reasoning override) both landed after
   that measurement. A channel that no longer runs away with the budget is what they were
   for.
2. **The probe is too small to provoke deep thinking.** #924 measured the *deployed* qa fill
   brief; the real one runs ~8,600 prompt tokens against this probe's few hundred. Thinking
   scales with prompt complexity.

The in-situ distribution in §2 leans toward the first and does not settle it: `none`-level
capabilities ran 2,193–2,750 completion tokens against ~5,000 for `high`/`medium` — roughly
2×, nowhere near 13.9×. But that is a comparison across different capabilities doing
different work, not an A/B on one task, so it cannot carry the conclusion either.

**What would settle it:** replaying a real qa fill brief at both levels. That requires
reconstructing the prompt through PromptService against a stored task's inputs — see §4,
because telemetry cannot supply it.

### Why "from our own telemetry" was never achievable

Stored prompts are capped. Every generation record in LangFuse for these two cycles holds
at most ~10,300 characters of input, against real prompts of ~8,600 tokens median (≈34k
chars) and up to 25,992 tokens. **Roughly 70% of every prompt is discarded before storage**
by `MAX_OBSERVABILITY_TEXT_LENGTH`.

There is therefore no replayable prompt in telemetry, and the sub-clause could not have been
satisfied as worded regardless of what the ratio turned out to be. This is a property of the
observability design, not a gap opened by any recent change.

## 4. Two findings for whoever reads this next

**The emission log is authoritative for reasoning length; LangFuse is not.**
`log_emission_shape` receives `response.reasoning_text` straight from the adapter, so
`reasoning_chars` is the true length. `build_generation_record` caps text at 10,000
characters before it reaches LangFuse. Any budget analysis run through LangFuse silently
floors every long reasoning trace at 10k — which for `development.author_manifest`'s ~18k
characters would have understated it by nearly half.

**Generation coverage in LangFuse is partial (#1206).** Ten of seventeen
`chat_stream_with_usage` call sites never record a generation. For these two cycles: 35 LLM
calls, 35 emission-shape lines, 26 LangFuse generations. The unrecorded seams include
`governance.define_done` and `data.analyze_failure`, both declared `ReasoningLevel.HIGH`.
This is a second reason §2 is computed from the emission log rather than from telemetry.

## 5. Disposition

- **Criterion 1: met.** The budget half is re-read and recorded, negatively — no pressure
  in this distribution, and #998's override is currently unused headroom.
- **Criterion 2, sub-clause 1: not met.** The split does not reproduce (1.4× against
  13.9×), and the sub-clause's "from our own telemetry" is not achievable at all given
  prompt truncation.

The wording of criterion 2's first sub-clause is therefore a decision for the owner, not a
measurement outcome. A version this evidence would support: *the `none`/`high` split
re-measured on the deployed stack, and any divergence from #924's figure explained.* That is
proposed here, not applied — changing a cut criterion mid-line is a ruling, and §6.1 is
unedited by this document.
