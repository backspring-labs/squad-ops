# V7 FAY Window — Record

**Pre-registration:** `1-6-0-v7-fay-window-preregistration.md` (frozen; §6 prohibits changing it
mid-window, so the per-roll record accumulates here). **Deploy:** `4fa74525`, images per §3.
**N=6, bar ≥4/6 functional.** A roll scores functional iff verdict `accepted` AND
`audit_delivered_app.py` passes (incl. UI data-path) AND zero manual intervention (§7.3).
Validity per §5.1: void / reset / counted. Mechanical result and boot audit are recorded as
distinct facts, never collapsed (SIP-0104 §13a).

This file lives on a branch for the duration of the window (no merges to main, §6). Times UTC
in tables; the closing claim will restate in ET.

---

## Roll 1 — cyc_8b569ce34074

| Field | Value |
|---|---|
| Launched | 2026-08-18 23:48 UTC |
| Framing run | `run_c86f7911fe8c` — completed, 64 min, 11 artifacts |
| Gate | `progress_plan_review` → approved, `system:no_open_questions` (§7.3 rule 2 — zero manual touches) |
| Implementation run | `run_29b53b6e3d4b` — **failed** 02:37 UTC (1h45m), "Rewinding to checkpoint after development.develop failure" |
| Verdict | `blocked_unverified` |
| Executed / passed | 12 / 11 |
| criteria_total / verified | 14 / 2; failed: `acceptance:frontend_compiles`; required unmet: frontend_build, required_files, tests_pass |
| Probe count (non-gating) | 5 (contract `6357b2cbf288`) |
| Correction rounds | 1 completed repair (accepted), then develop re-dispatch failed 3 emissions → 1800s task timeout |
| Fills / assertion strength | n/a — `qa.test` never dispatched |
| Boot audit (separate fact, run as triage) | **PASS** — the stored tree (acceptance-aware assembly) installs, builds, boots, answers all 5 probes, UI data-path clean |
| Manual interventions | none (gate auto-approved) |
| §5.1 validity | **VOID** — never reached `qa.test`; neither counts nor resets; re-launched |
| Score | not scored (void) |

Contract artifact: `art_746df747bf41`. **The void roll's delivered application works** — the cycle
possessed an accepted, working repair at 01:38 UTC and failed anyway (#994). Failure chain,
verified against neo logs (the banked analysis is wrong — #995): real defect in `app/page.tsx`
(server-component prerender fetch, #996) → correct accepted repair (`force-dynamic`) → rewind
re-dispatched develop for the same subtask → three re-authored variants each failed
`frontend_compiles` → task timeout at 1800s → run failed.

## Launch 2 — cyc_18931c371a55

| Field | Value |
|---|---|
| Launched | 2026-08-19 03:0x UTC, notes record roll-1 void |
| Framing run | `run_e2d85438f3fe` — in flight |
| Config hash | matches §3 pin |

### Launch 2 gate (§7.3 rule 3 observation)

The manifest carried one unresolved dev question — *"PRD §4.1 lists capacity as Tier 1
expansion; should the MVP schema include capacity fields but skip enforcement, or defer
entirely until expansion?"* — and lead's planning artifact marked it a blocker. Per rule 3
the standing text was applied **verbatim** at 03:59 UTC ("open questions deferred; core PRD
scope only"), which happens to address this question's shape exactly (defer; core scope).
Logged as: the standing policy DID address this roll's question. Zero manual intervention;
decided_by records the agent decision. Implementation run `run_591987c9df8d` chained.

### Launch 2 — scored

| Field | Value |
|---|---|
| Framing | 73 min; gate REQUIRED approval (1 dev question) → §7.3(c) verbatim text, `decided_by: agent:0051…`, 03:59 UTC |
| Implementation | `run_591987c9df8d` — completed, 59 min |
| Verdict | **`accepted`** — 34/34 executed and passed; 11/11 criteria verified; nothing failed, nothing unmet |
| Probe count (non-gating) | 2 |
| Correction rounds | **0** — 7 develop tasks clean, builder clean, qa first attempt |
| Fills first-attempt / slots | 5/5, 0 duplicates, `scaffold_bound=true` |
| Any fill asserts on store (#980) | **yes** — 2 of 5 slots, `expect(all(TABLES.Run)).toHaveLength(…)` (the exact taught form); 16 expect() lines in fill regions; 2 additive suites (`api_flows`, `participant_validation`) |
| Assertion-strength method | recomputed from stored merged shells — the banked path does not exist (#999) |
| Boot audit (separate fact) | **PASS** — installs, builds, boots, answers both probes, UI data-path clean |
| Manual interventions | none (gate = pre-declared constant, recorded as agent decision) |
| §5.1 validity | **COUNTED** |
| Score | **FUNCTIONAL** |

## Launch 3 — cyc_c8af2a288e59 — COUNTED, not functional; and the reset-class detection

| Field | Value |
|---|---|
| Framing | 55 min; gate auto-approved (`system:no_open_questions`) |
| Implementation | `run_82dc31768f7d` — **failed** 08:20 UTC, "Max correction attempts (3) exhausted" |
| Verdict | `rejected` — 36 executed / 34 passed; 10/11 criteria verified |
| Genuine failure | `tests_pass` (required): the additive suite `__tests__/runs.test.ts` calls `api()` over HTTP — no live server exists in-process (the #877 class the appendix prohibits); three qa-side repairs did not converge |
| Locus routing | all three repairs went to **qa.test_repair** — the suite's author, never the app (the #988-era routing behaving correctly) |
| Fills | 6/6, 0 duplicates, `scaffold_bound=true` — the scaffold layer was never the problem |
| Boot audit (separate fact, run as triage) | **PASS** — the delivered app installs, builds, boots, answers all 3 probes, UI data-path clean. **Second working application rejected tonight** — this time by its own additive suite |
| Manual interventions | none |
| §5.1 validity | **COUNTED** (reached qa.test) |
| Score | **not functional** |

**Phantom row (the reset-class find, #1000):** launch 3's `failed_detail` also carries
`no_stub_fallback_tests` with an empty reason, `required: false` — a false FAILED row from a
CLEAN suite. Mechanism: #989 banks the authenticity row on every qa validation (pass or fail);
`verification_normalize.py:82` still assumed presence-implies-failure and records FAILED on
sight; the verdict rule rejects on ANY failed check. Launch 3's rejection was independently
genuine — but **a roll whose qa fails once, is repaired, and passes on retest would be falsely
REJECTED by the phantom alone.** That is the standard green-roll recovery path, so continuing
would waste every roll needing a single qa correction.

**NIGHT SHIFT HALTED at this detection (08:5x UTC / ~04:55 ET)** per the standing rule: reset
vs abort-and-re-register is the owner's decision (§5.1, §6). Fix stacked unmerged: PR #1001.
Nothing in flight; deploy untouched at `4fa74525`.

---

# ATTEMPT 2 — re-registered 2026-08-19, deploy `61a12e38`

Owner ruled abort-and-re-register at the morning report (§2.i of the pre-registration).
Deploy carries #1001 (the reset-class fix) + #997 (prerender teaching); both loaded-module
verified. PRD sha and config hash re-verified unchanged — comparable on recipe, not on the
dev authoring surface. **Count restarts: 0 of 6.** Attempt 1's rolls above are recorded
evidence, not pooled.

## Attempt 2, Roll 1 — cyc_6495d9870587 — COUNTED, not functional

| Field | Value |
|---|---|
| Framing | 54 min; gate auto-approved (`system:no_open_questions`) |
| Implementation | `run_44c68d150155` — failed 15:53 UTC, "Max correction attempts (3) exhausted" |
| Verdict | `rejected` — sole failed check `tests_pass` (required, genuine: exit 1, 10 test files). **No phantom row — #1001 confirmed live** |
| Correction rounds | 3 qa-side; none converged. Dev phase clean (first roll with #997's prerender teaching) |
| Fills | 8/8 first attempt, 0 duplicates, scaffold_bound |
| Boot audit (separate fact) | **PASS** — 5/5 probes, UI data-path clean. **4/4 working apps across both attempts** |
| Manual interventions | none |
| §5.1 validity | **COUNTED** |
| Score | not functional |

Failure texture: the additive suites are where the rolls die. This roll's stored mid-round
`ui-flows.test.ts` spy-mocks `global.fetch` with no route import — the deployed detector flags
it when handed the file, yet it never fired in-cycle, and the record cannot show what each
attempt inspected (#1002: `inspected` dies at the normalize seam; family of #995/#999 —
evidence computed at the handler, dropped before the record). Not reset-class: the roll's
rejection was genuine, and a false green from this gap cannot corrupt the FAY headline (the
boot audit is the functional oracle).

**Attempt 2 tally: 0 functional / 1 counted.**

## Attempt 2, Roll 2 — cyc_5fb50579c418 — COUNTED, FUNCTIONAL

| Field | Value |
|---|---|
| Framing | 65 min; gate auto-approved (`system:no_open_questions`) |
| Implementation | `run_9676a04a4c87` — completed, **41 min** |
| Verdict | **`accepted`** — 26/26 executed and passed; nothing failed, nothing unmet |
| Correction rounds | **0** |
| Fills | 8/8 first attempt, 0 duplicates; store asserted in the taught form (`all(TABLES.Run)` length checks; 15 expects across sampled slot regions); 1 additive suite (13.7 KB) |
| Boot audit (separate fact) | **PASS** — 5/5 probes, UI data-path clean. **5/5 working apps across both attempts** |
| Manual interventions | none |
| §5.1 validity | **COUNTED** |
| Score | **FUNCTIONAL** |

(Triage note for honesty: an initial fills-dropped scare was my sampling error — I read the
builder's seeded `source` copies; qa's merged `test`-type artifacts are properly filled.)

**Attempt 2 tally: 1 functional / 2 counted.**

## Attempt 2, Launch 3 — cyc_16bbfe29464f — VOID (framing-gate system rejection)

Framing completed (58 min); `progress_plan_review` **rejected by `system:plan_validation`**:
the authored plan's Task 7 declared a `command_exit_zero` check running `node` directly
against a `.tsx` file — node refuses the extension before parsing
(`ERR_UNKNOWN_FILE_EXTENSION`), so the check could never pass. Plan validation refused the
plan at the gate rather than letting it burn the roll mid-implementation (the #846/#707
unrunnable-check-form machinery doing its job). No implementation run; never reached qa.test.

§5.1: the **canonical void** — neither counts nor resets; recorded and re-launched. Zero
manual intervention (the rejection is a system decision). Observation, not an issue: the
squad authored an unrunnable check form and the gate caught it — this is the designed
two-layer behavior; the residual question (why authoring proposed it at all) is #846's
standing territory.

**Attempt 2 tally unchanged: 1 functional / 2 counted.**

## Attempt 2, Roll 3 (launch 4) — cyc_6b2af126b68d — COUNTED, FUNCTIONAL

| Field | Value |
|---|---|
| Framing | 54 min; gate auto-approved (`system:no_open_questions`) |
| Implementation | `run_ad61f9e464d6` — completed, 77 min |
| Verdict | **`accepted`** — 44/44 executed and passed; nothing failed, nothing unmet |
| Correction rounds | **1 — and it converged**: qa failed once, one repair, retest green. **The repair-then-pass path the #1000 phantom would have falsely rejected — survived on the fixed deploy. Live proof of #1001, end to end** |
| Boot audit (separate fact) | **PASS** — 5/5 probes, UI data-path clean. **6/6 working apps across both attempts** |
| Manual interventions | none |
| §5.1 validity | **COUNTED** |
| Score | **FUNCTIONAL** |

**Attempt 2 tally: 2 functional / 3 counted.** Path to bar: 2 functional needed from the 3
remaining counted slots.

### Launch 5 gate (§7.3 rule 3 observation)

Framing 65 min; gate required approval — one unresolved dev question: *"PRD §5.2 does not
specify a sort order for the runs list; defaulting to insertion order (newest first) unless
the reviewer directs otherwise."* Standing text applied verbatim 23:4x UTC; the question's
own stated default (proceed unless directed) composes cleanly with "open questions deferred."
Zero manual intervention; agent decision recorded.

## Attempt 1 close-out

HALTED pending owner decision. **Tally: 1 functional / 2 counted** (launch 2 functional;
launch 3 counted-not-functional); roll 1 void. Delivered-app ground truth so far: **3 of 3
completed builds pass the boot audit** — every failure tonight was machinery- or suite-side.

## Mid-window detections (recorded, left unfixed per §6)

| # | Detection | Source |
|---|---|---|
| #994 | Rewind after a successful repair re-dispatches develop, discarding the repaired state — cycle rejected a working deliverable | roll 1 (void) |
| #995 | Task timeout mid self-eval banked as "zero response chars", erasing 2 substantive rounds; analysis names a disproven mechanism | roll 1 (void) |
| #996 | Authoring surfaces teach the api() client seam but not the server-component prerender constraint | roll 1 (void) |
| #998 | Thinking-cap exhaustion (8192 completion tokens, 0 extractable chars) banks as generic emission failure — undetectable as its own class | roll 1 (void) |
| #999 | #982's assertion-strength evidence is computed then never persisted — `execution_evidence` has no home; §4's "read from banked evidence" unsatisfiable as deployed | launch 2 (counted) |
| **#1000** | **RESET-CLASS**: normalizer presence-implies-failure vs #989's unconditional row → phantom FAILED on clean suites; would falsely reject repair-then-pass rolls. Fix stacked: PR #1001 | launch 3 (counted) |
| #1002 | Self-mocking file never flagged in-cycle; `inspected` doesn't survive normalization — the detector-coverage question is unanswerable from the record | attempt 2 roll 1 (counted) |

**#995 corrected in-issue:** there was a third develop dispatch (02:18–02:30) that genuinely
emitted zero chars — 8,192 completion tokens, the exact generation cap, all spent on reasoning
(#998). The banked analysis correctly described that final attempt; the surviving defect is
that it describes ONLY the final attempt, erasing the timeout attempt's two substantive
rejected emissions. Fix stacked (unmerged, post-window): PR #997 for #996.

## Night-shift log (2026-08-18/19 ET)

- 21:10 ET — night shift armed: cycle-level watcher, mechanical scorer, this record. Routine:
  on each roll terminal → pull §4 fields → boot audit → score → triage (issues filed; fixes
  stacked on branches as unmerged PRs) → lease check → launch next roll on the identical §3
  recipe. Gate policy: §7.3(c) pinned text verbatim on any gate that opens; auto-approvals
  recorded as-is. A reset-class detection (new harness-attributable mechanical failure) HALTS
  the night shift — abort-and-re-register is an owner decision (§6), not a night-shift one.
