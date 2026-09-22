# 1.8.2 — plan (draft)

**Draft rev 0, 2026-09-22 — written at the 1.8.1 deploy-A N reading, not for merge until deploy
B′ closes.** The 1.8.1 plan's step 13 places this plan after the 1.8.1 cut; the owner asked on
2026-09-22 when it should be developed and the answer was: drafted at the N reading, because the
headline is known then, and finalized after B′, because the window's inheritance is not. This
revision is the first half. Every section that depends on B′ says so and stays open. Written from:
the 1.8.1 pre-registration (`docs/plans/1-8-1-verification-set-preregistration.md`) rev 5 with
§10a–§10e — the twenty-two diagnostic records, the six counted rolls and the reading; the 1.8.1
plan (`docs/plans/1-8-1-plan.md`, rev 4) §2.3, §3.3, §3.4, §6, §7 step 13 and §8 decisions 2 and
3; SIP-0086 §12a and SIP-0096 §17a as drafted 2026-09-15 and re-targeted 2026-09-17; SIP-0107
§38 step 7 and §39.8; the three findings deploy A's shakeout filed (#1623, #1626, #1631) and the
two it left open (#1621, #1632); and the tracker on the day of writing — twenty-four open
issues, every one placed by name (§5).

**1.8.2 is the model-capability tranche, and it is also the line that answers what deploy A
found.** The 1.8.1 plan handed it two capability amendments — SIP-0086 §12a (the self-evaluation
pass becomes the model's compile loop) and SIP-0096 §17a (a contested result: the producer's
dispute becomes evidence) — with their diagnostics' shapes fixed and #1581 beside them. Deploy A
then read **N = 4 of 6 with qa × Next.js empty** and, in reading it, surfaced the mechanism
behind the empty cell: on this deploy the loop answers a qa own-frame failure by **re-authoring
the suite, not by scoped repair**, on both stacks. That is a capability question of exactly the
kind §12a and §17a were drafted for — *does the framework constrain the model it runs* — so it
belongs here and not in a hardening line. Beside those three, only what they need: the crash
bound #1626 still owes (containment, not the bound), two driver guards the set's own failures
named, and a registration rule the reading taught.

Three facts shape it, stated once:

1. **The flip's precondition is unmet twice, on two deploys, for the same cell.** 1.8.0 read 5 of
   6 with qa × Next.js empty and its supply unregistered; 1.8.1 registered the supply, ran it
   five times across four registrations, and read 4 of 6 with the same cell empty. SIP-0107 step
   7 stays open. **Whether 1.8.2 re-supplies N is a decision, not a default** (§7 decision 1):
   a third count on an unchanged qa lane would be the retry §39.8 forbids in spirit; a count on
   a deploy that carries a fix for the mechanism is a new measurement.
2. **Every scoped qa repair of an own-frame failure on the line failed its retest**, and the
   only unfaulted qa repair on Next.js spent the whole flat completion cap on reasoning and
   emitted nothing (§1). Four verifier-accepted qa edits, four failed retests, four re-authored
   suites. The verifier and the contract worked; the repair did not fix what it edited. 1.8.2
   instruments that before it fixes it (§3.2), because the cause cannot be read from stored
   state — the retest report says "still fails", not which assertion.
3. **The amendments' diagnostics are fixed and are not re-derived.** `compile-loop` and
   `false-criterion` are as the 1.8.1 review settled them (1.8.1 plan §6), reproduced in §4.1
   verbatim so this plan carries them without a pointer into a superseded document.

Rules carried from the 1.8.1 line without discount: one kind of change per measured deploy; no
fault, no prediction; every field three-state; every diagnostic reaches its seam on the pinned
deploy; §5a amendments in the SIP, in the PR that diverges; a counted set is a shakeout round;
**and two the 1.8.1 set added** — a seam reached is not a cell supplied, and the per-cell tally is
read when each diagnostic clears, not at the end (§4.4).

---

## 1. What the 1.8.1 line says this release has to be

Rows from deploy A are read; rows from B′ are placeholders until the window closes.

| what the line showed | evidence | what it says about this release |
|---|---|---|
| **N read 4 of 6, qa × Next.js empty** — the registered supplier (the ninth diagnostic, five runs) produced no scoped qa transaction; the two Next.js counted rolls produced none | 1.8.1 pre-registration §10e; `cyc_bce374af7e89`, `cyc_4d9602ce0a66`, `cyc_5bbf85db4622` | the flip does not land in 1.8.1; **whether it is re-counted here is §7 decision 1**, and only on a deploy that changes the qa lane |
| **the loop re-authors instead of repairing**: on React, three accepted anchored qa edits (5%, 3%, 3%) each failed its retest and the qa task re-emitted the suite; on Next.js the qa repair never produced a patch | `cyc_3ba9057e5cdf` (retests at 15:04, 15:16, 15:24 ET, re-emissions at 15:07, 15:21, 15:29 ET); `cyc_38cbb5b54693`; `cyc_9e47702af705` | **an instrument first** (§3.2 item 1): the retest's failing assertions against the repair's edited region, so "still fails" becomes "the edit did not touch the failing test" or "the edit broke a passing one" — then the fix the reading names |
| **two cap-exhausted emissions, one per stack**: React roll 1's self-eval pass and Next.js roll 1's qa repair each spent 12,288 completion tokens (the flat cap, #1619/#1620) on 44,894 and 49,254 reasoning characters and emitted zero | `cyc_b98c45fcd5c8`, `cyc_4d9602ce0a66`; `loop_texture.contentless_emissions` | **the reasoning budget is separated from the emission budget, or a cap-exhausted pass is retried with its fact** (§3.2 item 2) — the R1 shape #1372 already gives the builder; a count of two is stated as a count |
| **the qa repair's second attempt is a re-emission, not a repair** — §3c's supply forecast "the second repair, after the prose one is refunded" assumed the re-take was a repair; the refund re-runs the qa task | the ninth diagnostic, both rev-4 runs; §10b | §12a's "the pass sees what it edits" applies to the re-take too: a re-taken qa task that is shown its own suite and asked for edits is a scoped transaction; one that is asked to author again is not (§3.3) |
| **a wrong-locus round**: the lead routed a qa-suite failure to a dev repair whose patch broke the frontend build and was discarded; the re-authored suite passed on the unpatched tree | `cyc_5bbf85db4622`, §10d′ | #1581's shape from the other side; **§17a's dispute is the mechanism** — a dev asked to repair a suite defect emits a typed dispute instead of a patch (§3.4) |
| **the SIGSEGV is bounded, not contained** — #1627 turns a redelivery into a typed `FAILED`; #1628 moves the crash rather than stopping it; subprocess isolation is validated (child `-11`, parent survives) and not built | #1626; the 1.8.1 pre-registration §3d, §10c | **containment in the prelude** (§3.2 item 3), ~180 lines across one seam, with a `redelivery` diagnostic that exercises the assertion 1.8.1 left uncovered (§4.1) |
| **two instrument defects found on the first diagnostic of two rounds** (#1623, #1631) and a class-closing test that could not be made sound (#1632) | §3d, §6 of the pre-registration | **a runtime self-check at set launch** replaces the static test: every collector's marker, passed through the runtime filter, reaches its reader (§3.2 item 4) |
| **a stale identity pin** copied from 1.8.0 refused the first counted roll (#1634) | pre-registration rev 5 | the counting-set test asserts a line's pins differ from every prior line's unless annotated (§3.2 item 5) |
| **the §3d "N cell" column read as a restriction until the owner ruled it a forecast**; the cells were not read when the diagnostics cleared | §10e's ruling; the review of 2026-09-22 | the 1.8.2 pre-registration states the per-cell supply as a §3b-class prediction with its falsification condition, and reads the tally at each diagnostic's clearance (§4.4) |
| **the window's result and its inheritance** | *pending B′* | *this row is written at the 1.8.1 cut* |
| **SIP-0108 (d)'s status and Han's teardown** | *pending B′* | *this row is written at the 1.8.1 cut* |

---

## 2. Why this release, on the roadmap

### 2.1 The tranche — two amendments, each with the diagnostic that forces its mechanism

The 1.8.1 review's reason for moving them here stands: a release whose central contract change
is meant to be easy to interpret should not gain two behaviour-changing mechanisms at the same
point, and the window should measure the substrate 1.8.0 measured. 1.8.1 did that. 1.8.2 is
where the substrate changes, and the change is measured the same way — one fault per mechanism,
one prediction per fix, read on a pinned deploy.

### 2.2 The empty cell is a capability finding, not a supply accident

1.8.0 could not fill qa × Next.js because the supply was unregistered. 1.8.1 registered it and
the cell stayed empty for a reason the records now state: the qa repair on the App Router stack
produced no patch in any of its opportunities, and where the React qa repair produced one, the
retest failed every time and the loop re-authored. §12a was drafted because the compile loop is
one shallow pass on truncated evidence; the same shallowness shows here as a repair that edits
the named file without fixing the named failure, and a re-take that is asked to write again
rather than to edit. **The amendment and the finding are one question.** That is why the qa-lane
work is in this line and not deferred to 1.9's hardening.

### 2.3 The flip — the second count, ruled here (§7 decision 1)

SIP-0107 step 7 is open after two lines. The plan recommends: **1.8.2 re-supplies N once more,
under its own pre-registration, on a deploy that carries §12a and the qa-lane fix — and the flip
lands on that line's deploy B iff the count is met.** The argument for: the mechanism that
starved the cell is the thing this line changes, so the count is a new measurement rather than a
retry. The argument against, stated so the owner can weigh it: it puts a third measured
pre-condition on the same cell, and a line that fails it a third time has spent three releases
on one contract step. The alternative is to leave step 7 open until 1.9 closes the 1.x line and
to name it there as a 2.0 decision.

---

## 3. The content

### 3.1 Preconditions — before the first code PR

- The 1.8.1 line cut by its seven steps; the window closed and its inheritance written into §1.
- This plan at rev 1 or later, merged on the owner's review, with the SIP sections' target lines
  amended (§12a and §17a already say 1.8.2; the amendment is the date and this plan's path).
- Main's every CI job green at the branch point.

### 3.2 The prelude — deploy A, behind the diagnostics and a counted set

One PR per causal unit, in this order.

1. **The retest readout — instrument only, `scripts/dev/`.** For every patch retest the driver
   reads the retest's `test_report.md` against the repair's revision form: which tests failed
   after the patch, whether the failing test's frame lies inside the edited region, and whether a
   test that passed before the patch fails after it. Three typed fields on `loop_texture`
   (`retest_failures_in_edited_region`, `retest_failures_outside`, `retest_regressions`), each
   with its unaskable state. **Predicted reading on the 1.8.1 corpus, replayed:** the four failed
   qa retests are read before any fix is scoped. This is the instrument-before-fix rule; the fix
   is item 6 and is scoped from what this reads.
2. **A cap-exhausted pass is retried with its fact, or the budgets are separated.** Two
   readings on main decide which, and are read before the PR is scoped: whether the provider's
   completion limit counts reasoning tokens (the ledger's `reasoning_chars` beside
   `completion_tokens` at the cap says it does on this model — *to be confirmed against the
   adapter*), and whether the flat cap is the request profile's or the squad profile's (#1619
   put it on the squad profile's roster entry). The fix follows the R1 shape (#1372): an emission
   that hit the cap with zero fenced output is retried once with the fact "your previous
   response reached the output limit before any file", with the retry recorded in the ledger.
   **Predicted silent on a clean roll; read on the two 1.8.1 cycles replayed.**
3. **#1626 containment.** The JSX structural parse runs in a subprocess; a child that dies
   (`-11`) returns `None` to the parent, which the repair path already treats as a structural
   miss. ~180 lines, one seam (`structural_jsx.py`'s entry), the validated shape from the issue.
   #1627's interim rule stays; #1626 closes when the `redelivery` diagnostic (§4.1) reads the
   parent surviving a child crash on the real repair path.
4. **The marker self-check, at set launch — driver only.** Replaces #1632's unsound static test
   with a dynamic one: at preflight the driver feeds one synthetic line per collector marker
   through `_runtime_lines_of_interest` and asserts each reader returns non-empty. A marker
   dropped by the filter refuses the launch by name. Closes #1632.
5. **The pin-staleness assertion — driver test.** `test_the_counting_sets_are_fully_pinned`
   asserts that a line's `expected_config_hash_prefix` and `expected_squad_snapshot_prefix`
   differ from every prior line's set config unless the config carries an annotation naming the
   prior line and why the value is unchanged. Would have refused rev 1's copy of 1.8.0's hash at
   authoring time.
6. **The qa-lane fix, scoped from item 1's reading.** Not designed here. The plan names the two
   shapes the records make likely and commits to whichever item 1 reads: (a) the repair's edit
   lands outside the failing test's frame — a targeting defect, fixed in the repair brief (the
   brief names the failing test and its frame, §46m's "show the file" extended to "show the
   failing assertion"); (b) the edit lands in the frame and the suite still fails on the
   re-authored assertion — a fill-mode interaction (#1603's target set) on Next.js, fixed at the
   fill seam. Either way the re-take after a refund becomes an edit request on the shown suite,
   not an authoring request (§12a change 3, applied to the qa task's re-take).
7. **#1621 and the title case — tooling.** `check_pr_closure.sh` reads the title and the commit
   messages beside the body and refuses a closing keyword in any of them that the body's `Refs`
   contradicts. Small, `scripts/dev/` and `.github/`.

### 3.3 SIP-0086 §12a — the compile loop

As drafted (four changes on the self-evaluation seam: depth from the request profile; every
error, not the first; the pass sees what it edits; one evaluation per pass on the verifier's
tree), amended as built in the PR that builds it. **One addition from deploy A's reading, to be
folded into the amendment in that PR:** change 3 applies to the qa task's re-take after a
refunded repair — the re-taken task is shown its own suite and asked for edits in the edit-fence
form. Diagnostic: `compile-loop` (§4.1). Prediction: both planted type errors fixed inside the
task, zero correction rounds, every pass in the ledger.

### 3.4 SIP-0096 §17a — the contested result, with #1581

As drafted (a typed `disputed_checks` block; `contested` on the row, never a fourth family; the
analyzer answers each dispute; a confirmed dispute refunds through `blocked_unverified`; the
driver counts contested rows per cell). #1581 closes here: the dev's correct refusal of a qa
suite defect becomes a dispute the framework reads, not an empty emission. Diagnostic:
`false-criterion` (§4.1). **A second prediction from deploy A:** the wrong-locus round of Next.js
roll 2 — a qa-suite failure routed to the dev — reads as a dispute naming the suite, not as a
35% patch that breaks the build.

### 3.5 The flip — deploy B, iff §7 decision 1 is ruled as recommended

SIP-0107 §38 step 7 exactly as the 1.8.1 plan §3.3 specified it — the authority path, the
historical replay, the §30.2 negative fixtures, the positive control, one checkpoint pair
predicting zero refusals. Nothing in that section is re-derived here; it is applied on this
line's deploy B if this line's N is met. If §7 decision 1 is ruled the other way, this section
is struck and step 7 is named for 1.9's plan.

### 3.6 #1039 — the docs site design pass

Handed by the 1.8.1 plan §3.7. Prose and assets only; sequenced after the counted set, never
between; never a cut blocker.

### 3.7 The cut criterion — three gates

| gate | criterion |
|---|---|
| **implementation** | §3.2 items 1–7 merged and read on A; §12a and §17a merged with their SIP sections amended as built; the flip merged iff A's N read as met (§3.5) |
| **experimental** | L1 holds on every counted roll; `compile-loop` and `false-criterion` read as predicted; the `redelivery` diagnostic reads the parent surviving; **N** as §7 decision 1 places it — met on A if the flip is this line's, else reported as a count with the cell named |
| **evidence** | every record three-state; the retest readout's three fields on every patch; the marker self-check passed at every launch; the SIP sweep stated before the sweep |

**The SIP sweep, stated now.** SIP-0086 → §12a amended as built, stays `implemented`. SIP-0096
→ §17a amended as built, stays `implemented`. SIP-0107 → `implemented` iff the flip landed and
§39 holds on this line's records; else `accepted` with step 7 named and the count stated.
SIP-0108 → as the 1.8.1 cut leaves it (*pending B′*).

### 3.8 Merge discipline

The 1.8.1 plan §3.11 verbatim: one causal change per PR; `gh pr view` before every push; every
job of main's run after every merge; the seam table in every PR that binds or removes a check;
the mirror rule on every removal; no merge to main while a window is open — with two additions
from this session: **a PR title never carries an issue number after a closing keyword, however
negated** (#1628's title closed #1626), and **a body edit and a merge never share a breath**
(the re-armed required check).

---

## 4. The verification sets — two deploys

### 4.1 Deploy A — the tranche's diagnostics, and N re-fixed

The 1.8.1 nine, unchanged, plus three:

| diagnostic | fault | invariant | readout | N cell |
|---|---|---|---|---|
| `compile-loop` | two independent, non-cascading TypeScript type errors in one existing file on `nextjs_ts`, each with a unique marker and each reported by `tsc` (a string assigned to a numeric declaration, a number to a string one); no missing imports, no syntax errors, no error produced by another, one build system | §12a: the task compiles until clean and is no longer constrained by truncated first-error evidence | both faults present before the task; the verifier's evidence exposes both; self-evaluation receives it; both repaired before the task completes; the final compile clean; zero correction rounds; every pass in the usage ledger. **Success is both errors fixed inside the task, however many passes** | none |
| `false-criterion` | a valid `@/lib` alias import (the repository's own configuration proves it resolves) against a **planted** verification row that rejects it — planted by the fault, since the original false positive was fixed on main | §17a: the producer disputes, the framework reads it | the producer leaves the correct implementation unchanged and emits a typed dispute naming the check; the row reads `contested`; the analyzer confirms from repository evidence; the round refunds through `blocked_unverified`; the terminal record names the disputed check. **Falsified by** a refunded round with no dispute (the #1053 coincidence) or a dispute the framework never read | none |
| `redelivery` | the qa agent's process is killed mid-repair on the roll's own path (the fault injected in the producing role's container, #1251), producing an unacked delivery | #1627's rule and #1626's containment | a typed `FAILED` for the original task id; the queue drains; the handler is not broker-run again; **the run leaves `running` through correction or termination** — the fourth assertion 1.8.1 could not cover; with item 3 built, a child parse crash on the same path returns `None` and the parent survives | none |

The `redelivery` diagnostic is the shape the 1.8.1 shakeout said a live run needed and could not
produce on a clean round; it is registered here so the assertion is read rather than assumed.

**N** — re-fixed in this line's pre-registration at 6 with one per required cell, on this deploy
only, with the ninth diagnostic and the counted set as supply, **iff §7 decision 1 is ruled as
recommended.** Otherwise the per-cell tally is read and reported as a count and no gate hangs
on it. Counted rolls: four React, two Next.js, as 1.8.1 — the diagnostics carry the supply.

### 4.2 Deploy B — the flip alone

Only if §4.1's N is met. The 1.8.1 plan §4.2 verbatim: the pre-registration, one checkpoint
pair predicting zero refusals, the shakeout loop to its exit rule, budget three rounds.

### 4.3 What this line does not measure

The Squad-versus-Solo question is 1.8.1's, and its successor questions (Free-Solo, placement) are
2.0 planning inputs by the 1.8.1 ruling. No arm axis is exercised on this line's deploys; every
config carries `arm` empty.

### 4.4 Two registration rules this line adds, before its first launch

1. **A seam reached is not a cell supplied.** The pre-registration's supply table states the
   expected transactions per cell as a §3b-class prediction with a falsification condition, and
   the driver's readout prints the per-cell tally — retest-passed, identity-held transactions
   only — at every diagnostic's clearance, not at the set's end. A cell whose registered
   supplier clears with zero is a finding at that moment.
2. **The counting definition governs and the supply column forecasts.** Written into §3c so no
   ruling is needed mid-set.

---

## 5. Re-placements by name — nothing silently carried

Twenty-four open issues on the day of writing. **In this release:** #1626 (containment, §3.2
item 3), #1632 (§3.2 item 4), #1621 (§3.2 item 7), #1581 (§3.4), #1039 (§3.6). **Read at the
cut, stays open by design:** #1469, as 1.8.0 and 1.8.1 read it. **1.9, unchanged from the 1.8.1
plan §6:** #1507, #567, #353, #1031, #1448, #1522, #414. **2.0, with Campaign:** #316. **At design
review, unchanged:** #949, #950, #194, #557. **Not scheduled:** #1122. **The ops rider's five,
carried with the rider, after the set:** #1177, #176, #1176, #1408, #1412 — #1176 (carry the
reasoning trace across repair attempts) is the one this line's cap finding touches, and it is
read beside §3.2 item 2 rather than closed by it.

Five on the line, one read at the cut, seven to 1.9, one to 2.0, four at design review, one not
scheduled, five with the rider: twenty-four, each placed once. *Recounted at rev 1 against the
tracker of that day.*

---

## 6. Sequencing

1. **This plan** at rev 1, after the 1.8.1 cut, with §1's two pending rows written.
2. **The prelude** (§3.2), items 1 and 4 and 5 first (instrument and guards, no deploy), then 3
   and 7, then 2, then 6 once item 1 has read the corpus.
3. **§12a**, then **§17a**, each with its diagnostic registered before its PR merges.
4. **Deploy A. The 1.8.2 pre-registration** — the twelve diagnostics, the supply table as
   predictions (§4.4), N re-fixed if ruled, the pins read from the deploy and asserted unequal to
   1.8.1's — committed before the first launch. Then the diagnostics, then the counted set.
5. **N read.** The flip PR iff met; **deploy B; its pair**.
6. **#1039**, then the ops rider on the idle box, bounded.
7. **Final record; cut 1.8.2 by the seven steps.** Then the 1.9 plan.

---

## 7. Decisions — recommended for the owner to overrule, not fill in

1. **1.8.2 re-supplies N under its own pre-registration on a deploy that changes the qa lane,
   and the flip lands on this line's deploy B iff met.** Recommended (§2.3). The alternative —
   step 7 open until 1.9 names it for 2.0 — is stated beside it.
2. **The qa-lane fix is scoped from the retest readout, not designed in this plan.** Recommended
   (§3.2 items 1 and 6): the instrument first, because the cause is not readable from stored
   state.
3. **The cap finding is fixed by the R1 retry shape unless the adapter reading shows the budgets
   can be separated.** Recommended (§3.2 item 2); the reading precedes the PR.
4. **#1626 closes on the `redelivery` diagnostic, not on the containment PR's tests.**
   Recommended (§3.2 item 3, §4.1): the crash is memory-state dependent and does not reproduce
   outside the agent container.
5. **The two registration rules of §4.4 are written into the 1.8.2 pre-registration before its
   first launch.** Recommended.
6. **The crew reviews the pre-registration at every revision and the cut record before the tag**,
   one round, all blockers together, record-only corrections marked. Recommended from the
   2026-09-22 review: five 1.8.1 registration revisions merged unreviewed, and the cell
   shortfall was in the records for a day before anyone read the retests.

---

## 8. What this draft does not decide — pending B′

- **The window's inheritance** — SIP-0108 (d)'s status, Han's teardown, and any finding the six
  pairs file. Written into §1 and §5 at rev 1.
- **Whether the 1.8.1 cut moves any SIP** — the sweep is the cut's, and §3.7's table takes its
  starting state from it.
- **The 1.8.2 pre-registration's text** — the pins, the field producers, the supply predictions
  and their falsification conditions; the rules are fixed in §4.4.
- **The qa-lane fix's design** — §3.2 item 6, scoped from item 1's reading.

---

## 9. Revision history

- **Rev 0 (2026-09-22)** — drafted at the 1.8.1 deploy-A N reading (4 of 6, qa × Next.js empty)
  on the owner's ask, from the 1.8.1 pre-registration §10, the 1.8.1 plan's hand-off (§2.3, §3.4,
  §6, §7 step 13), SIP-0086 §12a, SIP-0096 §17a and the tracker. Not for merge until B′ closes;
  §1's two window rows and §5's recount are rev 1's.
