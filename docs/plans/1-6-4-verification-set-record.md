# 1.6.4 — Verification Set: Record

**Closed 2026-08-26, 07:29 ET.** Eight counted rolls, no voids, no resets. Pre-registration:
`docs/plans/1-6-4-verification-set-preregistration.md` (commit `39f6abc0`, PR #1104, merged as
`ce65f859` before roll 1), in force from roll 1 and unchanged throughout. Deploy frozen at
`5a697dfa` (the seven image ids in the pre-registration §1) from shakeout 2 through roll 8; HEAD
pinned at `ce65f859`, which is the pre-registration merge and nothing else — **zero code drift
between the measured deploy and main.** Executed overnight under the owner's delegation
(pre-registration §5): every roll launched only after the previous record was read.

---

## 1. Headline

**8 of 8 functional — 100%, 95% CI [63.1%, 100%].** Every roll: verdict `accepted`, boot audit
PASS, zero manual intervention, **every criterion credited (14/14)**.

The 1.6.3 baseline on the same project, squad, request profile, overrides and config hash
(`d4d4f66217d8`) was 5 of 8 (62.5%, CI [30.6%, 86.3%]). The intervals overlap; per 1.6.3 §1.3
this set does not claim significance on the rate. **What it claims is in §2: every prediction the
pack made about its own mechanisms held on every roll that exercised it.**

| roll | cycle | framing | gate decider | verdict | audit | corrections | criteria | wall (ET) | `participants` declared |
|---|---|---|---|---|---|---|---|---|---|
| shk2 (non-counting) | `cyc_692a52a8ad1e` | 1 | agent, §6 constant | accepted | PASS | 0 | 14/14 | 22:19→23:15 (56m) | `list[string]` |
| 1 | `cyc_13ac22c47a6b` | 1 | `system:no_open_questions` | accepted | PASS | 0 | 14/14 | 23:17→00:18 (61m) | `list[string]` |
| 2 | `cyc_0f4d7f319c12` | 1 | agent, §6 constant | accepted | PASS | 0 | 14/14 | 00:19→01:19 (60m) | `list[Participant]` |
| 3 | `cyc_35fca7e65f89` | 1 | `system:no_open_questions` | accepted | PASS | 0 | 14/14 | 01:20→02:15 (55m) | `list[string]` |
| 4 | `cyc_e9e0ec669118` | 1 | `system:no_open_questions` | accepted | PASS | 0 | 14/14 | 02:16→03:09 (52m) | `list[Participant]` |
| 5 | `cyc_cf2a139701d3` | 1 | `system:no_open_questions` | accepted | PASS | 0 | 14/14 | 03:10→04:03 (54m) | `list[string]` |
| 6 | `cyc_bbc9da03c3c1` | 1 | `system:no_open_questions` | accepted | PASS | **1** | 14/14 | 04:05→05:17 (72m) | `list[string]` |
| 7 | `cyc_b7352b97cff9` | 1 | agent, §6 constant | accepted | PASS | 0 | 14/14 | 05:19→06:24 (65m) | `list[Participant]` |
| 8 | `cyc_8d262b968f58` | 1 | `system:no_open_questions` | accepted | PASS | **1** | 14/14 | 06:25→07:29 (64m) | `list[Participant]` |

Gate split (§6.1): 6 auto-approved by `system:no_open_questions`, 2 by the §6 constant — reported
as a count, used for nothing. **Zero framing re-rolls** across eight rolls and both shakeouts;
eighteen consecutive cycles have now framed on the first attempt.

---

## 2. The predictions — what the set was built to answer

| # | prediction | result | read from |
|---|---|---|---|
| **P0** | the seeded frozen tree agrees with the floor (#1096 / #1087 / #1079) | **held, 8/8** — read against each roll's own manifest: four rolls declared `list[Participant]` and were given `Participant[]`, four declared `list[string]` and were given `string[]`; `TABLES` matched the root set every time; the harness addressed a root table; every contract carried `json_has` on its three success probes | the `scaffold.expand` artifacts and the framing's `verification_contract.yaml` |
| **Coverage** | a green roll credits every criterion (#1021) | **held, 8/8** — 14/14 on every roll; every 1.6.3 roll and shakeout 1 had read 8/14–13/15 | `run_verification_summaries` |
| **P2** | the audit and the suite agree on the response floor (#1079) | **held, 8/8** — no roll red on the floor; the audit judged 5 probes with `json_has` every roll | verdict + audit |
| **P4** | every zero-character repair emission carries a signature (#998) | **held, 1/1** — roll 8's repair emitted 0 chars at 8,192 tokens; the runner and the executor both named it `cap_exhausted`, and the attempt was refunded (#1053) | runtime-api log, roll 8 |
| **P1** | no phantom-table assertion reaches a retest (#1087) | **unexercised** — no fill referenced a non-root table; no rejection recorded | fill dispositions, final shells |
| **P3** | no candidate rejected on a fill the floor contradicts (#1094) | **unexercised** — no kind contradiction authored | fill dispositions |
| **P5** | a repair round's target is the owning slot alone (#1015-A) | **unexercised** — neither correction was a dev repair; both were own-artifact qa repairs with no failing probe | runtime-api `correction_repair_target` lines (none emitted) |

Unexercised is not passed (pre-registration §3). The three loss modes P1/P3/P5 were built
against did not occur in eight rolls; the set says nothing about what happens when they do.

---

## 3. What the loop did when it ran

Two rolls entered the correction loop; both recovered to green in one round; **neither was a dev
repair**, and both were the same shape: the qa author's primary emission hit the 8,192-token
completion cap.

**Roll 6** (`cyc_bbc9da03c3c1`). The qa primary emission (prompt 16,750 tokens) wrote the additive
suite file first and hit the cap with **zero fills**; all eight shells rendered "no fill received".
The self-eval pass re-emitted eight valid fills, but that path discards them (**#947, observed
live**). The correction classified the failure as own-artifact and the `qa.test_repair` re-produced
only `__tests__/runs.test.ts` — a repair cannot reach fills (**#969/#970, observed live**). The
patch retest failed. **The executor then re-dispatched the original `qa.test` task**, whose fresh
attempt authored eight fills in 5,498 tokens and passed. Cost: ~20 minutes.

**Roll 8** (`cyc_8d262b968f58`). The qa primary emission (prompt 16,962 tokens) extracted all eight
fills but the additive `__tests__/api.test.ts` was truncated at the cap; **#1082 caught it**
(`unterminated_source` failed, blocking) and triggered the self-eval, which re-emitted a complete
file. **The suite then ran against the truncated file anyway** — `Transform failed: Unterminated
string literal at 293:40` — and the task failed. The stored artifact is the self-eval's complete
file (content hash `ef53ca9d…`); the correction's repair emitted nothing (`cap_exhausted`,
refunded); the retest ran the stored suite **unchanged, same hash, and passed**. The correction
round rediscovered a fix the task already held. Cost: ~7 minutes.

**Neither round exercised the loop-side fixes.** The pack's repair-targeting, fill-gate and
signature work sat unexercised or, in P4's case, worked once. The mechanism the loop actually spent
time on this set is the completion cap on qa emissions — three cap hits in eight rolls (roll 6
primary, roll 8 primary, roll 8 repair) plus one on a develop emission (roll 2, m004, recovered by
the aimed retry).

---

## 4. Texture

- **Emission failures, all recovered in-task or in-round:** roll 2 develop m004 `cap_exhausted`
  (8,192 tokens, 0 chars; aimed retry, 80 s); roll 7 develop m003 `unextractable` (a malformed fence
  info string `tsx:'use client' at app/runs/…`; aimed retry); rolls 6 and 8 as in §3. #998's
  signatures were readable on every one; whether the aimed-retry prompt *rendered* the signature
  line is unobservable from stored state (LangFuse's 10k-character cap; the executor's retry log line
  does not echo the marker).
- **The root-table rule's known edge, twice:** shakeout 1 and roll 8 declared a single-object
  response entity (`RunWithParticipants`, `RunDetail`) and the store gave it a table. Nothing
  asserted on it; the qa fills touched only `Run` in every roll.
- **Wall clock:** greens with no correction 52–65 min; the two corrected rolls 64 and 72. Framing
  31–42 min, implementation 20–37.
- **Instrument defect, recorded:** the set driver's P4/P5 log window used `docker logs --since`
  without a timezone suffix and read the wrong window; the P4 result above is from the log read
  directly. The driver is not a frozen surface; the record is the evidence.
- **Record inconsistency, minor:** on both corrected rolls the qa task's own `test_report.md`
  is re-stored at run end in its failed form (last-writer-wins) while the passing report lives under
  the retest task id.

---

## 5. Findings for the owner — raised, not filed

1. **Suite run vs self-eval ordering in `qa.test`** (roll 8): a self-eval re-emission that fixes a
   blocking typed check is stored as the task's artifact, but the suite has already run — or runs
   against a workspace that does not include it — so the task fails on a stale run and the loop
   pays a correction round to rediscover the fix. Deterministic; one instance; the content hashes
   prove it.
2. **The qa completion cap is now the measured next fix.** Three cap hits on qa emissions with
   16.7–17k-token prompts. #998's ask 2 (the cap, the prompt shape, or "fills first") has its data.
3. **#947, #969, #970 observed live** in roll 6, exactly as filed; recovery came from the executor's
   re-dispatch, not from the repair path.
4. **1.7's slate gains nothing new from this set** beyond the above; the pack's items P1/P3/P5 stay
   unexercised and should be read by the next set that produces a dev-side failure.

---

## 6. What this set does not claim

- **Not a general rate.** Same scope as 1.6.3 §5: `full-38` (qwen3.8:27b), `nextjs_ts`, `group_run`.
- **Not a claim about the unexercised predictions** (§2).
- **Not a significance claim** on 8/8 against 5/8 (1.6.3 §1.3, inherited). The honest statement:
  the three loss modes that produced 1.6.3's reds did not recur, and the frozen tree, the ledger and
  the probes now say what the manifest says.
