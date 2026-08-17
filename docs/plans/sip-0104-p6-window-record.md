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
| 6 | `cyc_085f992ad60d` | *in flight* | | | | | | | | |

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

Rolls 1–3 carry an operator `--as-agent` approval with an earlier wording. Roll 4
**auto-approved** via `system:no_open_questions` — the first of the window. Rolls 5–6 carry
the V7 pre-registration's §7.3(c) constant text.

Note the irony on roll 4: "no unresolved decisions" was true only of *declared* uncertainty.
The thing it left unspecified was the duplicate-join rule, whose absence cost it a probe.

---

## What the window established

**The scaffold holds when the author gets it right.** 28 of 28 slots filled on the first
attempt across four banked rolls, zero correction rounds, zero mechanical suite failures.

**It did not establish that the system recovers when the author gets it wrong.** Zero
corrections across every roll means the repair path — including #942 and #943 — is
**unexercised in production**. Six clean rolls leave that exactly as untested as four do.
This is the window's largest gap and it must be stated rather than allowed to read as
"corrections work."

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
