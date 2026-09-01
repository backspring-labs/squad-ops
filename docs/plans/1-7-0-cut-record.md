# 1.7.0 — the cut record

§6.1 criterion 5's artifact: what the shakeouts did **not** exercise, where every
remaining pack sits by name, and where Atlas stands. Written before the tag, from the
rolls rather than from the plan.

## 1. The deploy this cut is gated on

**`bbf42f8d`**, images `81d7a33b287f` (runtime-api) and the six agents rebuilt with it,
Python 3.12.14, Ollama `qwen3.8:27b` under the `full-38` profile.

**Zero code drift**: `git diff bbf42f8d..HEAD -- src/ adapters/` is empty at the cut. The
deploy *is* the tag, which is criterion 4 and the thing v1.6.2 could not say.

Gating pair, roll 6 of the line:

| stack | cycle | verdict | criteria | corrections | boot audit | wall clock |
|---|---|---|---|---|---|---|
| `nextjs_ts` | `cyc_2a88dabad94b` | accepted | 15/15 | 0 | PASS | 55 min |
| `fullstack_fastapi_react` | `cyc_cb49b16c2fa6` | accepted | 15/15 | 0 | PASS | 46 min |

Both functional (verdict AND audit AND zero intervention), P0 held, zero banked emissions.

## 2. What the shakeouts did not exercise

The section that matters. A green pair is evidence about what ran, and these did not run.

**No unresolved-name checking on `.ts` emissions (#939, open).** `undefined_names` is
pyflakes and covers `.py` only. No JS/TS scope analyser exists in the agent image —
measured: `tsc` is not on PATH, and eslint 6.4.0 exits 2 without a config. Roll 4's nextjs
rejection was exactly this: a fill used `created` without declaring it and reached test
execution. Roll 6 simply did not emit one. **The gap is declared** (#1216) and renders in
`docs/architecture/typed-check-menu.md` with its reason, so a green from here carries what
it did not check — but declared is not fixed.

**A dev repair on `nextjs_ts` still cannot be verified (#1221, option C).** The criteria
owning a `.ts` emission need node, which `runtime-api` does not have, so patch verification
returns `unverifiable`. #1225 stops the loop re-dispatching an identical task three times
and names the reason; it does not make the verdict obtainable. Roll 6 took zero correction
rounds, so this path did not execute at all. Moving verification to where the toolchain
exists is deliberately after this cut.

**LangFuse holds roughly three-quarters of generations (#1206, deferred).** Ten of
seventeen `chat_stream_with_usage` call sites record no generation. Any per-cycle cost read
from LangFuse is a lower bound, and `gens_per_task` reading exactly `1.00` is the second
call being dropped, not an invariant. The emission log covers all seventeen seams, uncapped,
and is authoritative for token and reasoning accounting. Deferred to #929, which collapses
recording to one seam and fixes this as a side effect.

**Prompts are not replayable from telemetry.** Stored prompts cap at ~10,300 characters
against real prompts of ~8,600 tokens median and up to 25,992 — roughly 70% of every prompt
discarded before storage. Any future work planning to replay a stored prompt should read
`1-7-0-reasoning-budget-reread.md` §3 first.

**One stack, one model, one provider.** Both rolls ran `full-38` on `qwen3.8:27b` through
Ollama. Nothing here is evidence about Atlas or vLLM (§5), about the `full` 27b profile, or
about any model not in this squad.

**Fill coverage is one-sided.** The verification-scaffold emitter registry holds a single
entry, `nextjs_ts`. `fullstack_fastapi_react` emits no fill slots, so Q0 (fills before
additive files) held on the stack that has them and is not applicable on the other. #1122
would close it and is an `enhancement`, which an odd minor cannot carry.

## 3. What this line actually cost

Recorded because the plan's calibration assumes a line's rolls mostly pass, and this one did
not. Six rolls; rolls 3–5 produced five rejections across four distinct causes, every one a
real defect the shakeouts surfaced rather than noise:

| cause | disposition |
|---|---|
| `unresolved_imports` refused `from package import submodule` — valid Python | #1211 fixed |
| a crashed app left an empty boot reason — the container was `--rm` | #1214 fixed |
| a test imported an undeclared npm package, reaching vitest | #1217 fixed |
| the fix for the above rejected `@/` path aliases as scoped packages | #1222 fixed |
| a failing probe rejected the run and asked nobody to fix it | #1223 fixed |
| a dev repair that could never be verified was retried until the budget ran out | #1221 fixed |
| a `.ts` fill used an undeclared identifier | **#939 open, declared** |

Two of those were introduced during the line (#1217's alias regression, caught by the roll it
broke), and one had been latent five weeks (#1211, since 2026-07-25). The pattern worth
carrying forward: **three of the four original causes were emission defects a check should
have caught, and all three sat on the JS/TS side** — Python emissions are well guarded and
TypeScript emissions were barely guarded. #1216 exists so the next such gap is visible before
a roll pays for it.

## 4. Remaining packs, by name (§3.1)

Unchanged from the plan except where noted. 1.7.0 is the first line, not the last.

- **1.7.1 — Stack Seams:** #1149 (harvest, precondition) then #1131, the kind gate #1153,
  #1130, #1123, #668, **#939**, #1022. Rider: #1087 (stack-#1 half), #1112; packaging #582,
  #637, #598, #1144, #1151.
- **1.7.2 — Loop Honesty, first half:** #788, #994, #995, #999, #1110, #968. Rider:
  **Boundaries** — #154, #377, #381, #305, #559, #922, #225, #218, #219, the
  identity-permutation test; #1148, #1150.
- **1.7.3 — Loop Honesty, second half:** #1054, #1070, with #936/#933 verified-then-closed.
  Rider: **Hardening (infra)** — #1147, #575, #577, #576, #578, #330, #300, #581, #560,
  #372, #352, #353, #574.
- **1.7.4 — Deferrals:** #820, #376. Rider: **Composition Root** after its design note —
  #301, #286, #1152; extractions #567, #579; #198, #157, #176, #580.

**Added to the slate by this line, not yet placed:** #1204 (nothing refreshes
`ci-constraints.txt`, and #1203 made it the single source every image follows), #1205 (no
dependency vulnerability scanning exists), #1206 (generation coverage — folds into #929),
#1216 is closed but #939 remains its open instance, #1221's option C (verify where the
toolchain exists), #1217's sibling #1122 (fill slots for stack #1, blocked on parity).

**#929 moved out of 1.7.0's rider** and is deferred to be designed with #1206 — both must
choose a value for `prompt_layer_set_id`, and settling it twice would move the LangFuse
grouping twice (§6.1a).

## 5. Where Atlas stands

**Not adopted. The switch was not taken.**

- **#1157 landed** — the provider selector is required config, no schema or factory default.
- **#1159 landed** — the `AtlasAdapter` is in the tree, inert, selected by nobody. The
  dark-ship rule of SIP-0106 §4 is what makes that safe and why no revert is needed.
- **#1160 landed as a negative result** — the A/B was stopped without counted rolls: 0
  accepted plans of 44 emissions across 14 serve configurations, 41 stopped by Atlas's
  content-loop guard, every one below the completion cap. Recorded in
  `1-7-0-atlas-ab-record.md` and amended into SIP-0106 §1.2a.
- **#1158 remains open** — Atlas serving on the Spark. Its facts are not in writing, which
  under §3.1's own rule is what would have moved #1159/#1160 to 1.7.1; they landed instead,
  so the rule is satisfied by outcome rather than by deferral.

**The deploy the next line's preflight runs on is this one** — Ollama, `full-38`,
`qwen3.8:27b`. No provider switch was taken, so nothing about the next line's baseline
changes.

**SIP-0106 stays `accepted`, not promoted.** #1157/#1159/#1160 are all merged, which is
§6.1 criterion 6's stated condition, but its headline phases returned a negative: Atlas is
not adopted (§1.2a) and the A/B is re-placed on vLLM (§1.2b), which is parked on measurement
(#1184). CLAUDE.md's rule is that a phased SIP with open children stays `accepted` with the
gap named. Promoting a SIP whose P4/P5 produced a negative would tell the next reader the
opposite of what happened.

## 6. Issues closed in this line

#237, #410, #901, #924, #927, #930, #944, #1041, #1099, #1135, #1145, #1168, #1181, #1194,
#1195, #1196, #1211, #1214, #1216, #1217, #1221, #1223, #242.

Twenty-three, against §3.1's ceiling of 6–8 roll-verified plus 10–15 CI-verified. The count
is not the achievement — six of them were filed and fixed inside the line because the rolls
found them.
