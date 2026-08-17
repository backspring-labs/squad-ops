# SIP-0104 P6 window — the record

**Purpose.** V6, the viability run that gates V7 (plan step 4b). Six rolls of authored-mode
`group_run` cycles on stack `nextjs_ts`, against a frozen deploy, measuring whether the
deterministic verification scaffolding holds in production.

**This is not V7.** P6 rolls cannot be promoted into the FAY window: designating a window
after its results are visible is exactly what pre-registration exists to prevent. See
`1-6-0-v7-fay-window-preregistration.md` §9.

---

## Baseline

| | |
|---|---|
| Deploy — main commit | `d590f73c`, **frozen for the window's duration** |
| Image ids | runtime-api `08a965bfc923` · eve `2885cae9cfcb` · neo `e796b70237c8` · bob `248169e87ffc` · max `e98c905eeac6` · nat `ee0c72d3b7ff` · data `07362a2a227e` |
| PRD | `examples/03_group_run/prd.md` (v0.5) |
| Recipe | squad `full` · request `validated-fullstack` · `build_profile=nextjs_ts` · `dev_capability=nextjs_ts` |
| `resolved_config_hash` | `d4d4f66217d88324d449b0cc7c05dd4665e17dcb90c63f7cfcd544ab5fc122d2` — identical on every roll |

**Window reset, 2026-08-16.** An earlier ledger (1 banked / 5 lost / 1 void) measured a
different code baseline and is historical. The reset was owner-agreed rather than convenient:
the run that would otherwise have been banked ("diagnostic 2") passed everything, but its
deploy boundary carried four named changes plus a `GENERATOR_VERSION` bump that moved the
Gate 1 byte pins. Rolls of the old window were attributable because each boundary was one
named change; that one was not, so it stands as proof the pipeline produces a working
deliverable and **not** as a banked roll.

**Boot audit applies from roll 1.** The old window's "from roll 3" was grandfathering for
rolls authored before #902 shipped. A fresh window has nothing to grandfather.

**The freeze was verified, not assumed** (2026-08-17 00:40 ET, with roll 6 in flight). All
seven containers still carry the image ids recorded above, and every one reports
`StartedAt = 2026-08-16T16:16Z` — before roll 1. Nothing was rebuilt or restarted across the
window. This is checked rather than trusted because the failure it guards against is silent:
a rebuild exits 0 and leaves stale agents running, which is how a boundary moves without
anyone deciding it should. Recording the *start time* alongside the image id is what makes
the claim falsifiable — an identical id on a container restarted mid-window would still mean
the deploy moved under the measurement.

---

## Per-roll record

| # | Cycle | Framing | Verdict | Checks | Criteria | Corrections | Fills first try | Probes | Slots | Endpoint coverage |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `cyc_24aac7c22be1` | — | accepted | 29/29 | — | **0** | 8/8 | 5 | 8 | 5/5 |
| 2 | `cyc_2f63e2d841eb` | 62m30s | accepted | 26/26 | 9/9 | **0** | 5/5 | **2** | 5 | **3/4** |
| 3 | `cyc_0e07836b5baa` | 63m | accepted | 38/38 | 14/14 | **0** | 8/8 | 5 | 8 | 5/5 |
| 4 | `cyc_de20c33b7892` | 78m | accepted | 36/36 | 13/13 | **0** | 7/7 | 4 | 7 | 5/5 |
| 5 | `cyc_ac94b672fa63` | 56m39s | accepted | 38/38 | — | **0** | 8/8 | 5 | 8 | 5/5 |
| 6 | `cyc_085f992ad60d` | 71m51s | **rejected** | 35 / 1 failed | **12/13** | **3** | 8/8 ×3 | 5 | 8 | 5/5 | |

Endpoint coverage is the #951 report: declared endpoints reached by at least one probe or
scaffold slot. Roll 2's `3/4` is the endpoint that carried join **and** leave.

Roll 5 (implementation 44m55s) is the window's largest qa emission at 8,056 completion
tokens, and the only roll whose plan named a test file the author then **wrote**
(`extracted_files=1`, `expected=['__tests__/api/runs.test.ts']`) — the sixth consecutive
instance of #933, and the second of the reset window where the author volunteered the file
rather than omitting it. It also declared `validation_error: 422` where rolls 1–4 used 400,
which changed nothing: the duplicate-participant code still maps to 409, and that is what
buys the duplicate probe.

**Audit instrument, stated because it is not uniform.** Rolls 3, 4 and 5 were failed by
`audit_delivered_app.py` on their join and leave call sites and are recorded as passing.
Rolls 3 and 4 were cleared by a human booting the deliverable and issuing real POSTs; roll 5
was cleared by re-running the **corrected** audit (#952/#953, PR #956), which also re-clears
rolls 1, 3 and 4. Roll 1's original pass was *vacuous* — the broken extractor found 2 of its
5 call sites. Under the corrected instrument every banked roll passes on every call site.
**No roll is re-scored on this**; the instrument's version is recorded rather than the
verdicts revised.

### Gate handling was not uniform, and the closing claim must say so

**Three distinct handlings across six rolls**, which is exactly the incoherence §7.3 of the
V7 pre-registration exists to end:

| rolls | how the gate closed |
|---|---|
| 1–3 | operator `--as-agent` approval, earlier free-text wording |
| **4, 6** | **auto-approved** by `system:no_open_questions` — no human or agent decision at all |
| 5 | `--as-agent` with the pre-registration's §7.3(c) constant text |

So a third of this window never had its gate *decided*. That is not a defect — a manifest
declaring no unresolved decision has nothing to ask — but it means "approved" does not denote
the same act across the six rolls, and any claim resting on uniform handling would be false.
V7 resolves it by making approval a pre-declared constant and recording an auto-approval as
itself rather than normalising it away.

Note the irony on roll 4: "no unresolved decisions" was true only of *declared* uncertainty.
The thing it left unspecified was the duplicate-join rule, whose absence cost it a probe. A
gate that fires on declared uncertainty cannot see the uncertainty an author did not notice
they had.

### Roll 6 is the window's most informative roll, and it failed on a working application

Terminal: `rejected`, `failure_reason: Max correction attempts`, three correction rounds, zero
open leases. **Its delivered application passes the boot audit** — measured 2026-08-17 03:23 ET
on the stored workspace:

> `PASS — delivered app installs, builds, boots, answers 5 contract probe(s), and its UI reaches
> every path it requests`

All five probes answer over real HTTP, join and duplicate-join and leave included.

**The only defect in the roll is an undeclared literal.** `lib/store.ts` is a generic keyed
table store — `all(table)` / `insert(table, row)` — and nothing declares the table name: not the
manifest (`persistence: in_memory`, no more), not the contract (which freezes the file but binds
no key). The application chose `'run_store'` and used it in every route, consistently. The suite
guessed differently and read an empty array. Rolls 1–5 guessed alike; this is a coin flip that
had been sitting under every roll.

**Third sighting of the #913 / #948 family** — after the `join`/`leave` path literals the qa
author invented from prose and agreed with dev by luck.

#### All three failure analyses assert things the source disproves

| round | claim | source |
|---|---|---|
| 1 | handlers declare "a local shadow store array" instead of importing the frozen store | the import is on line 3 |
| 2 | fill assertions "receive undefined values from route handlers" | POST returns `insert(...)`'s row — `id`, `title`, `participants` all present |
| 3 | POST "fails to mutate" the store; join/leave "omit expected fields"; routes are "unimplemented" | `insert('run_store', run)`; join returns the whole run; the routes work |

The subject oscillated app → tests → app on identical evidence, and nothing in the chain ever
established **which side of the disagreement was wrong** — which is the capability it lacks, and
no amount of better routing supplies it. **#788 class, three times in one roll.**

#### The repair path introduced defects rather than fixing one

Both repairs emitted `fences={'fill': 0, 'path': 1}` — a whole file, no fills — and rewrote the
suite to call the HTTP client seam (`api('/api/runs', …)`) in a suite that runs in-process with
**no server**: the #877 class. Two verified causes, both instances of one recurring pattern:

- `qa_test_fill_mode_appendix` is referenced only at `qa_test.py:503`; the repair handler never
  receives it. The scaffold fill-only appendix (`repair_handlers.py:284`) is **dev-role only**.
  So a repair of a scaffold-bound qa task does not know the fill protocol exists.
- #667 already fixed this exact shape once, for the DOM anchor inventory, in a comment that
  describes it: *"qa.test_repair re-authors the suite with none of the anchor inventory the
  original qa.test dispatch carried."* #946/#947 found it in `_build_self_eval_prompt`. **Third
  instance in the same handler family.**

#### Two defects are currently cancelling — do not fix one alone

The fills were never weakened; the deterministic layer held. But it held **accidentally**:
fill-blindness stops the repair editing fills, and the `expected_artifacts`-pinned aim
(`correction_runner.py:461`) stops it being pointed at them.

> **Teaching the repair path the fill protocol without also fixing what it is aimed at converts a
> repair that cannot help into a repair that can erase the evidence.** The qa author's cheapest
> route to a passing assertion is a weaker assertion, and fills are its legal surface.

Fix the diagnosis and the aim first; grant fill capability only once something above decides
whether the assertion or the app is wrong.

#### What it means for the number

Roll 6 is **functional** and **rejected**, so it scores not-functional. The metric is not wrong —
FAY asks whether the system delivers a working application unaided, and this system could not
tell that its own deliverable worked. But **a bare "N of 6" would invite the reading that the
missing rolls shipped broken software**, and here the software was fine and the verifier was
wrong. The closing claim states what each failure was, not only how many there were.

---

## What the window established

**The scaffold holds when the author gets it right.** 36 of 36 slots filled on the first
attempt across the five banked rolls, zero correction rounds, zero mechanical suite failures.
Roll 6 filled 8 of 8 on each of three attempts, so the fill protocol is 60 for 60 across the
window.

**The repair path does not work, and roll 6 is the only reason we know.** The gap this record
was originally going to report as *unexamined* is now examined: three rounds, three wrong
diagnoses, two repairs that each introduced a new defect, and a working application rejected at
the end of it. Five clean rolls would have closed the window recommending V7 with this entirely
unseen.

**Five green rolls did not mean five sound rolls.** Four of the six named a qa deliverable in
`expected_artifacts`, which is what arms the mis-aimed repair branch; rolls 1, 4 and 5 were one
failure away from roll 6's routing and looked perfectly healthy. The exposure was present in
four rolls and visible in none.

**Coverage varied 5 / 2 / 5 / 4 / 5 at an identical recipe hash**, through two distinct
authoring mechanisms, neither of them machinery drift:

- roll 2 folded join and leave into one endpoint discriminated by a request-body field
  (#948) — the deriver cannot synthesize a legal body from a field name alone;
- roll 4 used separate paths but declared **no error code mapping to 409**, so no
  duplicate-action probe derived. Its manifest is perfectly derivable; the author simply
  declined to declare the behaviour, so no derivation fix can reach it.

**The squad authors the exam it sits.** That is the finding, and it is why the V7
pre-registration records contract size per roll (§7.1) and reports a distribution rather
than a mean.

---

## Defects the window found

All filed, all fixed after the window closed — never during it, per the standing rule that a
window is evidence and a shakedown is a diagnostic.

| Issue | What it was | Where |
|---|---|---|
| #952 | UI data-path extractor scanned line by line; a wrapped call was silently never probed. Roll 1 passed on **2 of 5** call sites | PR #956 |
| #953 | The same check GETs every call site and read the resulting 405 as "this is a page" — failing correct apps. Rolls 3 and 4 each needed a human to boot the app and POST by hand | PR #956 |
| #951 | The scaffold covers a derived subset and never reported the delta | PR #958 |
| #948 | Probe derivation missed body-discriminated child actions | PR #959 |
| #946 | The self-eval trigger was unlogged — 3,574 tokens on roll 1 with no record of why | PR #960 |
| #935 | No record of whether the suite executed | PR #962 |
| #945 | Two criteria in `criteria_total` but in neither bucket. Did **not** recur on rolls 2–4 | open |
| #947 | The self-eval pass is fill-blind. Trigger is **variance, not determinism** — roll 4 refuted the inferred chain | open |
| #933 | The plan authors a qa deliverable that competes with fill mode. **Seven consecutive rolls** | open |
| #795 | `error_contract.shape` declared by the manifest and read by nothing — **five of five** rolls declared an envelope the seam never emits | open |

### Two corrections to the ledger itself

**Roll 1's audit pass was weaker than banked.** #952 meant its join, leave and detail-page
reads were never probed — it passed on 2 of 5 call sites. Under the corrected instrument it
passes on 5 of 5. **No roll is re-scored**; a roll is never re-graded on an instrument change
after the fact. But the closing record states which rolls were audited by which version.

**My own first diagnosis of #947 was wrong** and is corrected on the issue. Roll 4 reproduced
roll 1's setup exactly and produced the opposite emission, which turns a deduction into a
measurement — and is why #946 (log the trigger) is worth more than it looks.

---

## Plan items this record bears on

- **4b (V6)** — served by the counting rolls, subject to the 1e caveat below.
- **1e** — credited to "the first roll that passes the audit including the UI data-path
  check." **Needs a ruling.** Before #952/#953 no roll cleanly met that bar: roll 1's check
  was vacuous, rolls 3 and 4 were failed by the tool and passed by a human. Under the
  corrected instrument roll 1 passes on all five call sites. The evidence moved after the
  rule was written, so crediting it is a judgment rather than bookkeeping.
- **4c** — closed by the V7 pre-registration §7.1.
