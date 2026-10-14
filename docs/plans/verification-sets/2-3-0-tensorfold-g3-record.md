# 2.3.0 — the 27B on TensorFold in cycles, against production Ollama: record (SIP-0111 G3, #2229)

The record that §7 of `2-3-0-tensorfold-g3-preregistration.md` commits to. It reports; G4 is the owner's decision
(§8 there). Every number here is read from the per-roll records under `var/verification_sets/2-3-0-g3/`, the per-call
lines `calls-all.log` kept there, Prefect's task runs, and Prometheus over each roll's window.

**In one paragraph.**
- **Results:** all eight measured rolls were accepted with their boot audits passing, as were both TensorFold shakeouts.
- **Speed:** TensorFold's median cycle took 0.45 of Ollama's on FastAPI+React and 0.61 on Next.js+TS. Per 1,000
  completion tokens it took 0.49 of Ollama's wall-clock on both stacks, and it decoded at 2.04× Ollama's rate over
  every call.
- **Predictions:** two of the seven were falsified. P1 (decode at least 1.8× on every task type) failed on two task
  types, and P4 (completion tokens within ±20%) on several. The other five held, and so did the guide's four lines.
- **The finding that most qualifies the result (§6.1):** TensorFold repeats its answer to a repeated prompt, and the
  squad sets no seed. So **TensorFold's two rolls on each stack planned identically.** The arm holds one planning draw
  per stack, not the two that were registered.

## 1. What ran

**The deploy:** `dep_268949794186` at framework `cd1fca1d`, unchanged from the first shakeout to the last roll, with
every roll's image ids asserted by the driver. Main did not move while the set ran (`a136ee7e` throughout).

| order | ET (2026-10-13) | what | cycle | result |
|---|---|---|---|---|
| shakeout | 10:20–10:47 | TensorFold, FastAPI+React | `cyc_0afd11d92d15` | accepted 19/19, audit PASS, 0 rounds, 26.1 min |
| shakeout | 10:47–11:17 | TensorFold, Next.js+TS | `cyc_dc6a142e426f` | accepted 15/15, audit PASS, 0 rounds, 28.3 min |
| — | 11:18–11:23 | the switch to Ollama failed, then ran clean after an operator step (below) | | |
| 1–4 | 11:23–14:09 | React: Ollama 1, TensorFold 1, Ollama 2, TensorFold 2 | §2 | |
| 5–8 | 14:10–17:14 | Next.js: Ollama 1, TensorFold 1, Ollama 2, TensorFold 2 | §2 | |
| — | 17:14 | the switch back to Ollama | | exit 0 |

**The shakeouts:** both TensorFold shakeouts met the exit rule, a pair on one deploy with no new seam finding. They
are flagged, and they are not G3's rolls.

**The operator step:**
- **What failed:** the first `to-ollama` before the measured rolls (11:18 ET) exited 2. Ollama was already serving
  after the shakeouts' own switch back, and the switch then failed its own check that the memory was released.
- **What I did:** stopped Ollama by hand (`docker stop squadops-ollama`; 105.6 GiB released, no GPU process left) and
  resumed the chain. No roll had started.
- **The fix:** `to-ollama` now stops a serving Ollama before it stops TensorFold (#2273, which waits to merge until
  this record is read).

**The switch count:** twelve invocations, eleven clean. The budget's ten, plus the failed one and its re-run.

## 2. The rolls

| arm | stack | roll | cycle | verdict | criteria | boot audit | correction rounds | emission retries | handler retries | min |
|---|---|---|---|---|---|---|---|---|---|---|
| Ollama | FastAPI+React | 1 | `cyc_b48d3945f156` | accepted | 20/20 | PASS | 0 | 0 | 0 | 56.8 |
| TensorFold | FastAPI+React | 1 | `cyc_a2f48076bbd3` | accepted | 19/19 | PASS | 0 | 0 | 0 | 25.6 |
| Ollama | FastAPI+React | 2 | `cyc_f8722aef18d3` | accepted | 20/20 | PASS | 0 | 0 | 0 | 53.3 |
| TensorFold | FastAPI+React | 2 | `cyc_b0e8fd5a7d54` | accepted | 19/19 | PASS | 0 | 0 | 0 | 24.1 |
| Ollama | Next.js+TS | 1 | `cyc_4049d420743f` | accepted | 17/17 | PASS | 0 | 0 | manifest 2 | 57.2 |
| TensorFold | Next.js+TS | 1 | `cyc_9d49e3a947eb` | accepted | 15/15 | PASS | 0 | 0 | manifest 1, brief 1 | 27.5 |
| Ollama | Next.js+TS | 2 | `cyc_2f495505b507` | accepted | 15/15 | PASS | 0 | 0 | manifest 2 | 51.9 |
| TensorFold | Next.js+TS | 2 | `cyc_e329c6500018` | accepted | 15/15 | PASS | 2 (1 refunded) | 1 | manifest 1, brief 1 | 39.2 |

**Two of the columns are additions to §4.**
- **"Handler retries"** counts a handler's own validation retries (`retry_yaml_call`'s "attempt N/M failed"), read
  from each cycle's Prefect warnings. The driver's record does not count them, and they were the only retries in seven
  of the eight rolls.
  - **manifest** is `development.author_manifest`, which allows four attempts.
  - **brief** is `governance.prepare_plan_authoring_brief`, which allows two.
- **"Emission retries"** is the driver's `failed_emissions_banked`.

**The medians:**

| stack | Ollama median | TensorFold median | TensorFold / Ollama |
|---|---|---|---|
| FastAPI+React | 55.0 min | 24.9 min | 0.45 |
| Next.js+TS | 54.5 min | 33.4 min | 0.61 |

## 3. Speed

**Decode rate by role over both stacks,** token-weighted: each role's completion tokens over its decode seconds, so a
20-token call does not count as much as a 6,000-token one.

| role | calls Ollama | t/s Ollama | calls TensorFold | t/s TensorFold | TensorFold / Ollama |
|---|---|---|---|---|---|
| strategy | 4 | 22.4 | 4 | 40.8 | 1.83 |
| data | 4 | 22.1 | 6 | 40.9 | 1.85 |
| dev | 29 | 28.9 | 28 | 61.6 | 2.13 |
| qa | 10 | 27.6 | 13 | 61.0 | 2.21 |
| lead | 16 | 26.3 | 20 | 50.1 | 1.91 |
| builder | 4 | 21.6 | 4 | 40.0 | 1.85 |
| **all roles** | **67** | **26.8** | **75** | **54.7** | **2.04** |

**Where it is fastest:** writing code (`development.develop` 2.52×, `qa.test` 2.21×). Prose and planning tasks run
at about 1.8–1.9×.

**One mechanism is visible,** a retry that re-sends a rejected answer. The brief's retry call copies most of its
prompt and decoded at 308.6 t/s. Such calls lift the per-call mean (in the appendix) and barely move the
token-weighted rate.

**Wall-clock per 1,000 completion tokens** (P4's fallback, §4.1):

| stack | Ollama s | TensorFold s | TensorFold / Ollama |
|---|---|---|---|
| FastAPI+React | 40.9 | 20.3 | 0.50 |
| Next.js+TS | 41.6 | 20.1 | 0.48 |
| both | 41.3 | 20.2 | 0.49 |

Per roll the figure is 40.6–41.7 s on Ollama and 20.0–20.5 s on TensorFold. TensorFold's last Next.js roll wrote
117,669 tokens, against 70,598–81,280 for its others, because of its correction rounds. Its 39.2 minutes is still 20.0 s
per 1,000 tokens.

## 4. The predictions, read

Read in the Atlas A/B's order, as §4 fixes it: tokens first, then the paired wall-clock, then the rates, then the
quality half.

**A deviation from §5 comes first.** §5 says a falsified prediction stops the set for a read. At 14:09 ET, with
React's half in, P1 and P4 read falsified on that half's medians.
- **What I did:** I read both as set-level, since their medians are taken over the whole set, and did not stop. I
  told the owner, with the offer to stop before the Next.js pair launched (#2229, issuecomment-6152055799).
- **What followed:** the owner did not stop the set.
- **The final readings below** are over all eight rolls.

### 4.1 P4, volume: FALSIFIED

B's median completion tokens were registered to fall within ±20% of A's for each task type. Read over both stacks:

| task type | Ollama | TensorFold | TensorFold / Ollama |
|---|---|---|---|
| builder.assemble | 48.5 | 523.0 | 10.78 |
| development.author_manifest | 4,949 | 6,886 | 1.39 |
| governance.merge_plan | 9,857 | 6,562.5 | 0.67 |

Every other task type falls inside the band (0.85–1.15).

**What the outliers are:**
- **`builder.assemble`** writes a 61-byte assembly note. Ollama emitted 20–78 tokens for it and TensorFold 20–838,
  with no reasoning tokens on TensorFold. The extra is answer text that the handler does not keep.
- **`governance.merge_plan`:** TensorFold's merged plans are not shorter. They run 9.6–11.1 kB against Ollama's
  10.0–12.4 kB, with 23–31 acceptance criteria against 26–34 and similar description lengths. The token gap is in
  reasoning, not in the plan.
- **`development.author_manifest`:** its Ollama median mixes first attempts with retries. Ollama's Next.js manifests
  took three attempts each, TensorFold's two.

**The fallback §5 requires,** "speed is compared per token before any claim", is §3's second table: 0.49 on both
stacks. The speed claim survives it.

### 4.2 P2, the paired wall-clock: held

TensorFold was faster in all four pairs: 56.8 → 25.6, 53.3 → 24.1, 57.2 → 27.5 and 51.9 → 39.2 minutes.

### 4.3 P3, size: held

TensorFold's median cycle took 0.45 of Ollama's on FastAPI+React and 0.61 on Next.js+TS, both within the registered
0.70. The registered estimate was about 0.55. Next.js's median is the mean of 27.5 and 39.2 minutes, and the second
of those carries two correction rounds (§6.3).

### 4.4 P1, decode: FALSIFIED

B's median decode rate was registered at 1.8× A's or more on every task type with two or more calls on each arm.

| task type | TensorFold / Ollama |
|---|---|
| builder.assemble | **1.40** |
| governance.prepare_plan_authoring_brief | **1.71** |
| data.research_context | 1.81 |
| governance.assess_readiness | 1.81 |
| strategy.frame_objective | 1.82 |
| qa.define_test_strategy | 1.86 |
| governance.merge_plan | 1.87 |
| governance.define_done | 1.88 |
| development.design_plan | 1.94 |
| development.author_manifest | 1.98 |
| qa.test | 2.21 |
| development.develop | 2.52 |

**Why it varies (unverified).** The pattern is code against prose: code-writing runs at 2.2–2.5×, and prose and planning
at 1.7–1.9×.
- **The likely mechanism:** TensorFold's drafter has more of its draft tokens accepted on code than on prose.
- **Why I could not read it:** the engine's own `/metrics` was read once, a minute after a restart, and showed only
  the warm-up's counters (30 drafted, 0 accepted). The engine is now stopped, so whether its counters cover streamed
  calls at all is not established.
- **`builder.assemble`:** its outputs are 20–838 tokens, where fixed per-call costs weigh most. Ollama's own rate on
  it ranged from 18.7 to 36.8 t/s.

### 4.5 P5, no engine-attributable failure: held

**What I read:** each TensorFold roll's handler warnings and errors, and the per-round evidence of the one roll with
rounds (§6.3).
- **Engine-path errors:** none. The client containers logged no error or warning from the engine path in any
  TensorFold roll's window, with no stream error, no infrastructure hold, no 401, no unconfirmed release and no
  deadline.
- **Terminations:** 74 of TensorFold's 75 calls ended `stop`, and one ended `length` at the QA profile's own
  12,288-token budget (§6.3, #2253). That is the squad's budget, not the engine's.
- **The empty repair:** the second correction repair came back empty, with 2,884 tokens, 2,444 of them reasoning, and
  `termination=stop`. That is what the model wrote, delivered whole.

### 4.6 P6, the window holds: held

No TensorFold task was held for a context overflow. The largest prompt was 28,753 tokens, against a window of 65,536.

### 4.7 P7, quality parity: held

In each pair, TensorFold's verdict, criteria and boot audit were no worse than Ollama's. All eight were accepted with
every criterion verified and the audit passing.

**The criteria counts differ for a reason.** On FastAPI+React, TensorFold's apps carry 19 criteria against Ollama's 20.
Every TensorFold run on that stack put the "create a run" form on the list page instead of on a page of its own:
- **TensorFold:** 2 declared client routes, in all three runs on the stack (the shakeout and both rolls);
- **Ollama:** 3 routes, in both rolls.

The API is the same five endpoints in every roll. The form is present and posts: `create-run-form` is in the
TensorFold apps' list views, in roll 1 on each stack. Read with §6.1, TensorFold's React rolls are one planning draw,
so "every run" here is that one draw seen three times.

## 5. The guide, read

1. **Every TensorFold roll accepted, with its boot audit passing:** held, 4 of 4.
2. **TensorFold's correction rounds within the stack's baseline range:** held. React 0 and 0 (range 0–1); Next.js 0
   and 2 (range 0–2). Two is the top of Next.js's range.
3. **TensorFold's median cycle wall-clock below Ollama's, on each stack:** held, 24.9 against 55.0 min and 33.4
   against 54.5 min.
4. **No task type's median completion time on TensorFold worse than Ollama's by more than 10%:** held. None of 12 task
   types was slower. TensorFold's time over Ollama's runs 0.36–0.64 over both stacks, and 0.33–0.73 per stack.

## 6. Findings

### 6.1 TensorFold repeats its answer to a repeated prompt, and the squad sets no seed (#2281)

SIP-0111 records the engine's rule: "`seed` is per request. Without one, the seed is derived from the prompt, so a
repeated request repeats its sample." The adapter sends a seed only when a call sets one
(`adapters/llm/tensorfold.py:317`), and no production call does. The pre-registration did not account for this: its
§10 notes only that no call sets a seed, as a reason Ollama's path is unchanged.

**Prompt and completion tokens, per call, in TensorFold's two rolls on each stack:**

| task | React 1 | React 2 | Next.js 1 | Next.js 2 |
|---|---|---|---|---|
| data.research_context | 4,247 → 6,129 | 4,247 → 6,129 | 4,332 → 5,451 | 4,332 → 5,451 |
| strategy.frame_objective | 4,352 → 4,442 | 4,352 → 4,442 | 4,441 → 5,120 | 4,441 → 5,120 |
| development.design_plan | 4,568 → 6,624 | 4,568 → 6,624 | 4,660 → 7,006 | 4,660 → 7,006 |
| development.author_manifest | 16,321 → 7,353 | 16,321 → 7,353 | 17,887 → 6,886 | 17,887 → 6,886 |
| qa.define_test_strategy | 4,512 → 5,354 | 4,512 → 5,354 | 4,604 → 4,103 | 4,604 → 4,103 |
| governance.prepare_plan_authoring_brief | 25,944 → 5,836 | 25,944 → 5,836 | 25,760 → 5,931 | 25,760 → 5,931 |
| governance.merge_plan | 11,511 → 6,113 | 11,511 → 5,460 | 11,563 → 8,005 | 11,563 → 7,012 |

**How far the repeat goes:**
- Every planning call repeats exactly up to the merge.
- The merge is the first call whose answer differs, though its prompt has the same length in both rolls. Why it
  differs there is not yet read.
- Ollama's pairs differ on every row.
- The first briefs LangFuse recorded for the two Next.js rolls match line for line in the lines read (86–97).

**What it changes about this record:**
- **TensorFold's arm holds one planning draw per stack, not two.** Its shakeouts most likely repeat the same draw: the
  Next.js shakeout's brief failed with the identical error, at the identical line.
- **The quality readings (P7 and the guide's first two lines) rest on fewer independent draws than §2 registered.**
- **The speed readings do not depend on which sample was drawn,** and stand.
- **The build phase did diverge.** After the merge, the rolls' plans differ: 8 against 6 tasks on Next.js. The
  implementation tasks that follow differ too, so the two TensorFold Next.js rolls do not repeat each other from there
  on.

**What it would change in production:**
- **Every independent-roll measure needs a seed per call.** As things stand, two cycles on the same request would
  plan identically on TensorFold, and that includes the 2.3 cut set's rolls.
- **A retry with feedback is fine.** A retry that carries the error changes the prompt and draws afresh. That is why
  the brief's malformed first attempt was fixed on retry each time.
- **A path that re-sends an unchanged prompt repeats its answer.** A framing reroll, a re-taken round and a blind
  retry may each do this. Which paths do so is not yet inventoried.

**The shape of a fix (a SIP-0111 design question, the owner's):** when a call sets no seed, the adapter sends a fresh
one per request and logs it on the call's line, as Ollama samples afresh without one. The replay tool and the G0/G1
harness keep setting theirs.

### 6.2 The lead's Next.js brief is malformed on its first attempt

**Where it failed:** in all 3 TensorFold Next.js runs (the shakeout and both rolls), in no TensorFold React run, and in
none of the 4 Ollama rolls.

**The same defect each time:** `governance_prepare_plan_authoring_brief_handler: attempt 1/2 failed … line 94, column
2: _integration_build_and_smoke: 10`. The key is mis-indented by one space inside `time_budget_guidance`. Read from
LangFuse for both rolls:

```yaml
time_budget_guidance:
  foundation_types_store_validation: 15
  api_route_handlers: 20
  frontend_pages_components: 25
  vitest_suite: 20
 _integration_build_and_smoke: 10
  expansion_tier1_conditional: 10
```

**How it ended:** the retry, which carries the parse error, produced a valid brief all three times.
- **The risk:** the handler allows two attempts, so if the retry also failed, the cycle's framing would fail.
- **Why the rate is unknown:** under §6.1 this prompt fails the same way every time it is sent. How often the defect
  occurs across prompts cannot be read until calls draw independently.
- **What the prompt shows:** the key is the model's. The prompt's example for `time_budget_guidance` is
  `{backend_api: 30, persistence: 20, frontend: 30, tests: 20}` (its fragment,
  `task_type.governance.prepare_plan_authoring_brief.md`).

### 6.3 TensorFold's last Next.js roll: two correction rounds

From its Prefect warnings and per-call lines (ET):

| time | event |
|---|---|
| 17:01 | QA's first `qa.test` call ran out at the 12,288-token budget (7,511 tokens of reasoning); the cut `disputed_checks` block was dropped, never taken as written (#2149) |
| 17:03 | the suite failed `tests_pass`, starting round 1: analyze, decide, repair (3,203 tokens, 65 of them answer) |
| 17:06 | the retest failed again, starting round 2: analyze, then the decision moved from continue to patch |
| 17:08 | the repair came back empty (2,884 tokens, 2,444 of them reasoning), and the round was refunded and re-taken (#1053) |
| 17:12 | the suite passed; the run completed at 17:13 |

**Where it stands:**
- **Baseline:** two rounds is within Next.js's baseline range (0–2).
- **Not yet read:** whether the token-budget cut caused the rounds. The cut is recorded on #2253, the QA budget's
  headroom issue.

### 6.4 The box

Read from Prometheus over each roll's window: minimum `MemAvailable`, maximum swap in use, the board's hottest
thermal zone (`acpitz`), and the GPU's temperature.

| window | MemAvailable min | swap max | board max | GPU max |
|---|---|---|---|---|
| Ollama rolls (4) | 53.0–58.5 GiB | 0 | 93.5–95.9 °C | 84–86 °C |
| TensorFold rolls (4) | 58.5–75.5 GiB | 0 | 81.2–85.0 °C | 66–76 °C |
| TensorFold shakeouts (2) | 68.4–71.3 GiB | 0 | 85.3–91.5 °C | 65–73 °C |

**Against the limits:**
- **Memory:** nothing approached S's floor (16 GiB available with TensorFold loaded), and nothing swapped.
- **Heat:** TensorFold ran 9–12 °C cooler on the board than Ollama. Ollama's rolls came within 2–5 °C of the board's
  98 °C warning line (#2277's panel).
- **TensorFold's own log:** no error or warning in the last container's run. The earlier containers' logs went with
  each switch.

## 7. What this record does not cover

- **Independent draws on TensorFold** (§6.1). Its quality evidence is one planning draw per stack, then two divergent
  builds.
- **Application quality beyond the verdict, its criteria and the boot audit,** as §1 of the pre-registration excludes.
  The page-count difference (§4.7) and the merged-plan comparison (§4.1) are read from artifacts, not judged.
- **The drafter's acceptance rate** (§4.4).
- **A counted result.** These rolls count for G3 only.

## 8. For G4

G4 is the owner's decision. This record reports what G3 measured.

- **Speed:** about 2× on decode, and about half the wall-clock per token and per cycle. The squad would see most of it.
- **Quality:** at parity on everything §5 and the guide read.
- **What remains open:** §6.1, the repeated sample, which bears on how the 2.3 cut set would be read on TensorFold,
  and §6.2, the brief's first-attempt defect, whose rate §6.1 hides.

---

## Appendix: the per-task and per-role tables

Medians over the measured rolls: time is Prefect's task duration; tokens are completion tokens; decode is the
per-call rate; prefill is from `squadops_llm_prefill_seconds`, the bucket median and the exact mean over the window.
**A** is Ollama and **B** is TensorFold. `governance.assess_readiness` and `governance.review_plan` have no Prefect
task or model call of their own on one side, so their cells are blank.

### Per task type, both stacks

| task type | time A s | time B s | B/A | tokens A | tokens B | decode A | decode B | B/A | prefill A s (median, mean) | prefill B s (median, mean) | calls A/B |
|---|---|---|---|---|---|---|---|---|---|---|---|
| builder.assemble | 28.7 | 18.5 | 0.64 | 48.5 | 523.0 | 28.1 | 39.2 | 1.40 | 25.0, 25.59 | 7.50, 7.13 | 4/4 |
| data.analyze_failure | — | 55.8 | — | — | 2259.0 | — | 45.1 | — | —, — | 5.00, 5.75 | 0/2 |
| data.research_context | 267.0 | 145.9 | 0.55 | 5675.0 | 5790.0 | 22.2 | 40.1 | 1.81 | 6.25, 5.44 | 1.50, 1.57 | 4/4 |
| development.author_manifest | 402.1 | 181.8 | 0.45 | 4949.0 | 6886.0 | 28.6 | 56.6 | 1.98 | 5.00, 11.95 | 5.62, 4.54 | 8/6 |
| development.correction_repair | — | 66.8 | — | — | 3043.5 | — | 50.2 | — | —, — | 6.25, 5.65 | 0/2 |
| development.design_plan | 247.5 | 143.2 | 0.58 | 5981.5 | 6815.0 | 24.9 | 48.2 | 1.94 | 6.25, 5.88 | 1.50, 1.66 | 4/4 |
| development.develop | 140.0 | 57.0 | 0.41 | 3648 | 3389.0 | 31.4 | 79.2 | 2.52 | 14.25, 14.49 | 3.80, 3.90 | 17/16 |
| governance.assess_readiness | — | — | — | 3379.0 | 3301.5 | 23.8 | 43.0 | 1.81 | —, — | —, — | 4/4 |
| governance.correction_decision | — | 6.50 | — | — | 175.5 | — | 36.7 | — | —, — | 1.50, 1.60 | 0/2 |
| governance.define_done | 79.9 | 45.5 | 0.57 | 1857.5 | 2136.0 | 25.7 | 48.4 | 1.88 | 4.00, 4.58 | 1.50, 1.25 | 4/4 |
| governance.merge_plan | 358.7 | 129.7 | 0.36 | 9857.0 | 6562.5 | 28.0 | 52.3 | 1.87 | 12.5, 14.7 | 4.00, 4.18 | 4/4 |
| governance.prepare_plan_authoring_brief | 276.6 | 153.1 | 0.55 | 6145.5 | 5836.0 | 25.4 | 43.5 | 1.71 | 37.5, 34.5 | 11.25, 7.24 | 4/6 |
| governance.review_plan | 149.6 | 78.6 | 0.53 | — | — | — | — | — | 6.25, 6.10 | 1.50, 1.76 | 0/0 |
| qa.define_test_strategy | 261.1 | 117.5 | 0.45 | 5595.5 | 4728.5 | 22.0 | 40.9 | 1.86 | 6.25, 5.82 | 1.50, 1.65 | 4/4 |
| qa.test | 252.4 | 122.5 | 0.49 | 7277.5 | 7887 | 31.5 | 69.6 | 2.21 | 17.5, 17.6 | 4.75, 5.03 | 6/9 |
| strategy.frame_objective | 214.1 | 118.9 | 0.56 | 4676.5 | 4781.0 | 22.4 | 40.8 | 1.82 | 6.25, 5.62 | 1.50, 1.59 | 4/4 |

### Per task type, FastAPI+React

| task type | time A s | time B s | B/A | tokens A | tokens B | decode A | decode B | B/A | prefill A s (median, mean) | prefill B s (median, mean) | calls A/B |
|---|---|---|---|---|---|---|---|---|---|---|---|
| builder.assemble | 25.8 | 18.5 | 0.72 | 49.0 | 523.0 | 28.7 | 42.2 | 1.47 | 25.0, 22.36 | 6.25, 5.81 | 2/2 |
| data.research_context | 267.0 | 155.7 | 0.58 | 5542.0 | 6129.0 | 21.6 | 39.8 | 1.84 | 6.25, 5.41 | 1.50, 1.55 | 2/2 |
| development.author_manifest | 379.8 | 144.7 | 0.38 | 9636.0 | 7353.0 | 27.1 | 53.0 | 1.96 | 25.0, 21.88 | 6.25, 5.99 | 2/2 |
| development.design_plan | 236.6 | 142.4 | 0.60 | 5544.0 | 6624.0 | 24.1 | 47.1 | 1.95 | 6.25, 5.82 | 1.50, 1.64 | 2/2 |
| development.develop | 134.3 | 53.3 | 0.40 | 3692.5 | 3751.0 | 31.6 | 79.3 | 2.51 | 13.333333333333332, 14.12 | 3.50, 3.50 | 8/6 |
| governance.assess_readiness | — | — | — | 2774.5 | 3380.0 | 23.4 | 43.8 | 1.87 | —, — | —, — | 2/2 |
| governance.define_done | 80.9 | 45.4 | 0.56 | 1967.0 | 2136.0 | 26.1 | 48.5 | 1.86 | 4.00, 4.70 | 1.50, 1.25 | 2/2 |
| governance.merge_plan | 358.7 | 116.7 | 0.33 | 9857.0 | 5786.5 | 28.9 | 51.5 | 1.78 | 12.5, 14.76 | 4.00, 4.17 | 2/2 |
| governance.prepare_plan_authoring_brief | 308.7 | 144.4 | 0.47 | 6854.5 | 5836.0 | 25.1 | 43.5 | 1.73 | 37.5, 35.52 | 12.5, 10.07 | 2/2 |
| governance.review_plan | 126.2 | 78.9 | 0.63 | — | — | — | — | — | 6.25, 6.06 | 1.50, 1.71 | 0/0 |
| qa.define_test_strategy | 288.6 | 132.8 | 0.46 | 6219.5 | 5354.0 | 22.1 | 40.8 | 1.85 | 6.25, 5.79 | 1.50, 1.63 | 2/2 |
| qa.test | 200.3 | 108.8 | 0.54 | 5591.0 | 7208.0 | 31.5 | 71.0 | 2.25 | 15.0, 14.88 | 4.00, 3.79 | 4/4 |
| strategy.frame_objective | 259.2 | 111.6 | 0.43 | 5668.5 | 4442.0 | 22.4 | 40.5 | 1.81 | 6.25, 5.56 | 1.50, 1.58 | 2/2 |

### Per task type, Next.js+TS

| task type | time A s | time B s | B/A | tokens A | tokens B | decode A | decode B | B/A | prefill A s (median, mean) | prefill B s (median, mean) | calls A/B |
|---|---|---|---|---|---|---|---|---|---|---|---|
| builder.assemble | 32.3 | 20.0 | 0.62 | 48.5 | 429.0 | 27.1 | 37.6 | 1.39 | 25.0, 28.81 | 8.75, 8.45 | 2/2 |
| data.analyze_failure | — | 55.8 | — | — | 2259.0 | — | 45.1 | — | —, — | 5.00, 5.75 | 0/2 |
| data.research_context | 279.2 | 136.2 | 0.49 | 6130.5 | 5451.0 | 22.4 | 40.5 | 1.81 | 6.25, 5.47 | 1.50, 1.58 | 2/2 |
| development.author_manifest | 402.1 | 219.0 | 0.54 | 3517.5 | 6306.5 | 30.5 | 60.4 | 1.98 | 4.00, 8.64 | 1.00, 3.81 | 6/4 |
| development.correction_repair | — | 66.8 | — | — | 3043.5 | — | 50.2 | — | —, — | 6.25, 5.65 | 0/2 |
| development.design_plan | 259.8 | 143.9 | 0.55 | 6393.0 | 7006.0 | 25.2 | 49.3 | 1.96 | 6.25, 5.93 | 1.50, 1.68 | 2/2 |
| development.develop | 145.6 | 59.6 | 0.41 | 3504 | 3119.5 | 31.4 | 79.2 | 2.52 | 15.625, 14.83 | 4.00, 4.14 | 9/10 |
| governance.assess_readiness | — | — | — | 3902.5 | 3223.0 | 24.2 | 42.2 | 1.74 | —, — | —, — | 2/2 |
| governance.correction_decision | — | 6.50 | — | — | 175.5 | — | 36.7 | — | —, — | 1.50, 1.60 | 0/2 |
| governance.define_done | 79.3 | 45.5 | 0.57 | 1799.5 | 2136.0 | 24.3 | 48.3 | 1.99 | 4.00, 4.47 | 1.50, 1.26 | 2/2 |
| governance.merge_plan | 361.7 | 144.9 | 0.40 | 9412.0 | 7508.5 | 27.1 | 53.3 | 1.97 | 12.5, 14.65 | 4.00, 4.18 | 2/2 |
| governance.prepare_plan_authoring_brief | 223.2 | 161.9 | 0.73 | 4878.0 | 4558.0 | 25.7 | 175.6 | 6.83 | 37.5, 33.47 | 2.00, 5.82 | 2/4 |
| governance.review_plan | 168.0 | 78.3 | 0.47 | — | — | — | — | — | 6.25, 6.13 | 1.50, 1.80 | 0/0 |
| qa.define_test_strategy | 236.7 | 102.0 | 0.43 | 5014.0 | 4103.0 | 21.9 | 41.0 | 1.87 | 6.25, 5.86 | 1.50, 1.67 | 2/2 |
| qa.test | 397.9 | 171.9 | 0.43 | 10685.0 | 9312 | 31.4 | 69.6 | 2.22 | 25.0, 23.05 | 6.25, 6.02 | 2/5 |
| strategy.frame_objective | 174.3 | 126.2 | 0.72 | 3744.5 | 5120.0 | 22.3 | 41.2 | 1.85 | 6.25, 5.67 | 1.50, 1.59 | 2/2 |

### Decode rate by role, FastAPI+React (with the per-call mean)

| role | calls A | tokens A | avg t/s A | per-call mean A | calls B | tokens B | avg t/s B | per-call mean B | B/A |
|---|---|---|---|---|---|---|---|---|---|
| strategy | 2 | 11,337 | 22.4 | 22.4 | 2 | 8,884 | 40.4 | 40.5 | 1.81 |
| data | 2 | 11,084 | 21.7 | 21.6 | 2 | 12,258 | 39.7 | 39.8 | 1.84 |
| dev | 12 | 59,416 | 28.5 | 29.8 | 10 | 50,091 | 60.8 | 71.8 | 2.13 |
| qa | 6 | 36,699 | 27.6 | 28.3 | 6 | 40,324 | 58.6 | 61.0 | 2.12 |
| lead | 8 | 42,906 | 26.5 | 25.9 | 8 | 34,277 | 46.6 | 46.8 | 1.76 |
| builder | 2 | 98 | 22.6 | 28.7 | 2 | 1,046 | 42.0 | 42.2 | 1.86 |
| all roles | 32 | 161,540 | 26.7 | 27.5 | 30 | 146,880 | 52.4 | 56.8 | 1.97 |

### Decode rate by role, Next.js+TS (with the per-call mean)

| role | calls A | tokens A | avg t/s A | per-call mean A | calls B | tokens B | avg t/s B | per-call mean B | B/A |
|---|---|---|---|---|---|---|---|---|---|
| strategy | 2 | 7,489 | 22.3 | 22.3 | 2 | 10,240 | 41.1 | 41.2 | 1.85 |
| data | 2 | 12,261 | 22.4 | 22.4 | 4 | 15,420 | 41.8 | 42.9 | 1.86 |
| dev | 17 | 66,175 | 29.2 | 30.3 | 18 | 75,630 | 62.1 | 68.2 | 2.12 |
| qa | 4 | 31,398 | 27.6 | 26.6 | 7 | 52,483 | 63.0 | 61.6 | 2.28 |
| lead | 8 | 39,984 | 26.0 | 25.3 | 12 | 44,318 | 53.3 | 88.6 | 2.05 |
| builder | 2 | 97 | 20.7 | 27.1 | 2 | 858 | 37.8 | 37.6 | 1.82 |
| all roles | 35 | 157,404 | 27.0 | 27.6 | 45 | 198,949 | 56.5 | 67.8 | 2.09 |

### Decode rate by role, both stacks (with the per-call mean)

| role | calls A | tokens A | avg t/s A | per-call mean A | calls B | tokens B | avg t/s B | per-call mean B | B/A |
|---|---|---|---|---|---|---|---|---|---|
| strategy | 4 | 18,826 | 22.4 | 22.4 | 4 | 19,124 | 40.8 | 40.8 | 1.83 |
| data | 4 | 23,345 | 22.1 | 22.1 | 6 | 27,678 | 40.9 | 41.8 | 1.85 |
| dev | 29 | 125,591 | 28.9 | 30.1 | 28 | 125,721 | 61.6 | 69.5 | 2.13 |
| qa | 10 | 68,097 | 27.6 | 27.7 | 13 | 92,807 | 61.0 | 61.3 | 2.21 |
| lead | 16 | 82,890 | 26.3 | 25.6 | 20 | 78,595 | 50.1 | 71.9 | 1.91 |
| builder | 4 | 195 | 21.6 | 27.9 | 4 | 1,904 | 40.0 | 40.0 | 1.85 |
| all roles | 67 | 318,944 | 26.8 | 27.6 | 75 | 345,829 | 54.7 | 63.4 | 2.04 |

### Wall-clock per 1,000 completion tokens, per roll and per task type

| arm | stack | roll | completion tokens | min | s per 1k tokens |
|---|---|---|---|---|---|
| A | fastapi-react | 1 | 83,768 | 56.8 | 40.6 |
| B | fastapi-react | 1 | 76,282 | 25.6 | 20.1 |
| A | fastapi-react | 2 | 77,772 | 53.3 | 41.1 |
| B | fastapi-react | 2 | 70,598 | 24.1 | 20.5 |
| A | nextjs | 1 | 82,683 | 57.2 | 41.5 |
| B | nextjs | 1 | 81,280 | 27.5 | 20.3 |
| A | nextjs | 2 | 74,721 | 51.9 | 41.7 |
| B | nextjs | 2 | 117,669 | 39.2 | 20.0 |

| stack | median s per 1k tokens A | B | B/A |
|---|---|---|---|
| FastAPI+React | 40.9 | 20.3 | 0.50 |
| Next.js+TS | 41.6 | 20.1 | 0.48 |
| both stacks | 41.3 | 20.2 | 0.49 |

| task type | s per 1k tokens A | B | B/A |
|---|---|---|---|
| builder.assemble | 595.8 | 40.4 | 0.07 |
| data.analyze_failure | — | 24.7 | — |
| data.research_context | 46.8 | 25.2 | 0.54 |
| development.author_manifest | 37.8 | 18.2 | 0.48 |
| development.correction_repair | — | 21.9 | — |
| development.design_plan | 41.6 | 21.0 | 0.50 |
| development.develop | 39.2 | 17.0 | 0.43 |
| governance.assess_readiness | — | — | — |
| governance.correction_decision | — | 36.9 | — |
| governance.define_done | 42.5 | 21.3 | 0.50 |
| governance.merge_plan | 37.4 | 19.7 | 0.53 |
| governance.prepare_plan_authoring_brief | 45.3 | 20.5 | 0.45 |
| governance.review_plan | — | — | — |
| qa.define_test_strategy | 46.8 | 24.8 | 0.53 |
| qa.test | 36.4 | 21.1 | 0.58 |
| strategy.frame_objective | 46.1 | 24.9 | 0.54 |
