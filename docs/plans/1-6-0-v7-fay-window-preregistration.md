# V7 — Authored-Mode FAY Window: Pre-Registration

**Status: DRAFT. Not in force.** The window may not open until every item in §2 holds and
every ruling in §7 is closed. Once in force, nothing in this document changes until the
window closes — that is the whole point of writing it before the rolls exist.

**Owner:** maintainer · **Instrument:** `group_run` authored-mode cycles on stack `nextjs_ts`
· **Consumes:** 1.6 plan steps 4a (decided), 4c (§7.1 below) · **Gated by:** V6

---

## 1. What is being measured

**Functional App Yield (FAY)** — the proportion of pre-registered rolls that reach
`verified_functional` **with zero manual intervention**, where `verified_functional` requires
all three levels: structural, executable, functional.

The number is banked as the baseline 1.8 re-measures against. That is what makes this window
evidentiary rather than diagnostic, and it is why the standing rule applies without exception:

> **A shakedown is a diagnostic — fix what it finds. A window is evidence — fix nothing until
> it closes.**

A defect detected mid-window is recorded and left alone. Promotion of a detection into a fix
is a separate, deliberate act taken after the window closes.

---

## 2. Preconditions — the window may not open until all hold

| # | Precondition | State |
|---|---|---|
| 2.1 | V6 complete (SIP-0104 P6 window closed) | in progress |
| 2.2 | **#952 and #953 fixed and deployed** — see §2.a, this is blocking | open |
| 2.3 | Instrument defects either fixed or explicitly declared (§2.b) | open |
| 2.4 | Deploy frozen; commit and image ids recorded in §3 | pending |
| 2.5 | Zero open focus leases immediately before roll 1 | check at launch |
| 2.6 | Every ruling in §7 closed | open |

### 2.a Why the audit defects are blocking, not cosmetic

A window that measures *zero manual intervention* cannot require manual intervention to score
itself.

Both #952 and #953 concern `audit_delivered_app.py`, which decides the **functional** level.
As of the P6 window:

- **#953** — the UI data-path check issues a GET to every call site regardless of the verb the
  UI uses, and classifies the resulting 405 as `PAGE_NOT_API`. Rolls 3 and 4 both failed the
  audit on correct applications; both required a human to boot the deliverable and issue POSTs
  by hand to establish that the failure was false.
- **#952** — the same extractor scans line by line, so a call whose path wraps to the next
  line is silently never probed. Roll 1 passed with its join and leave call sites unverified.

Left unfixed, any roll whose manifest expresses child actions as path segments — three of four
P6 rolls chose that shape — produces an audit failure that only manual verification can
resolve. Scoring the window would then depend on the very intervention the metric forbids.

### 2.b Instrument defects that must be fixed or declared

Each of these bounds what a green roll means. Fixing is preferred; declaring is acceptable if
the declaration is recorded here **before** roll 1 and repeated in the closing claim.

| Issue | Effect on the number | Disposition |
|---|---|---|
| #951 | The scaffold covers a derived subset of declared behaviours and never reports the delta | fix / declare |
| #948 | Probe derivation misses body-discriminated child actions | fix / declare |
| #915 | An additive suite may mock `global.fetch` and assert its own mock, undetected | fix / declare |
| #795 | `error_contract.shape` is authored and read by nothing; four of four P6 rolls declared an envelope the seam never emits | declare (already a known window artifact) |

---

## 3. Fixed parameters — complete before roll 1, unchanged thereafter

| Parameter | Value |
|---|---|
| **N** (rolls) | _____ (recommendation: 6 — see §7.2) |
| **FAY bar** | _____ (1.4 precedent: ≥4/6) |
| PRD | `group_run_v0.5.md`, sha `_____` |
| Squad profile | `full` |
| Request profile | `validated-fullstack` |
| Overrides | `build_profile=nextjs_ts`, `dev_capability=nextjs_ts` |
| `resolved_config_hash` | `_____` |
| Deploy — main commit | `_____` |
| Deploy — image ids | runtime-api `_____`; max, neo, nat, bob, eve, data `_____` |
| Gate policy | see §7.3 |

---

## 4. Per-roll record

Recorded for every roll, whatever its outcome. Fields marked **non-gating** are observations,
never thresholds.

| Field | Source |
|---|---|
| verdict | `run_verification_summaries` |
| executed / passed check counts | same |
| `criteria_total` / `criteria_verified` / `unverified` | same |
| **probe count** — non-gating | derived contract |
| **scaffold slot count** — non-gating | scaffold manifest |
| correction rounds | `runtime_activities` |
| fills on first attempt / slots | eve emission-parse log line |
| boot audit result | `audit_delivered_app.py`, recorded **separately** |
| gate disposition and decider | `cycle_gate_decisions.decided_by` |

**The two criteria are never collapsed.** SIP-0104 §13a: the mechanical result and the boot
audit are recorded as distinct facts, and the closing claim states both rather than a single
merged pass rate.

---

## 5. Scoring

A roll scores **functional** if and only if all three hold:

1. verdict `accepted`;
2. `audit_delivered_app.py` passes, including the UI data-path check;
3. zero manual intervention, per the §7.3 ruling.

Anything else scores **not functional**. There is no partial credit and no post-hoc
reclassification.

### 5.1 Roll validity

- **Void** — a cycle that never reaches `qa.test` (for example a framing-gate system
  rejection). A void roll **neither counts nor resets**; it is recorded and re-launched.
- **Reset** — a *new* mechanical suite failure attributable to the harness rather than to the
  squad's output resets the window, and the closing record names the surface. This is the
  clause that keeps the window honest about its own instrument.
- **Counted** — everything else, including rolls that fail. An unfiltered window counts its
  failures; that is what "unfiltered" means.

---

## 6. Prohibited during the window

No merges to main. No image rebuilds. No edits to the expander, the fill-only appendix, the
scaffold fixture, any prompt asset, or any plan asset. No change to the gate policy. No change
to this document.

Detections are recorded as issues and left unfixed. If a detection is severe enough that
continuing would waste the remaining rolls, the correct action is to **abort and re-register**,
not to fix and continue.

---

## 7. Open rulings — all required before the window opens

### 7.1 Contract size per roll (plan step 4c)

**Recommendation: record probe count and scaffold slot count per roll, non-gating, with no
floor.**

The evidence is now considerably stronger than the 29-versus-57-checks observation that raised
this. Four P6 rolls at an **identical** `resolved_config_hash`, same PRD, frozen deploy:

| roll | probes | slots | cause of the difference |
|---|---|---|---|
| 1 | 5 | 8 | join/leave as path segments, conflict mapped to 409 |
| 2 | 2 | 5 | join/leave folded into one endpoint, action in the request body (#948) |
| 3 | 5 | 8 | as roll 1 |
| 4 | 4 | 7 | path segments, but **no code mapped to 409**, so no duplicate probe derived |

Two distinct mechanisms, neither of them machinery drift: the squad authors the exam it sits.
A floor would invite padding; silence would let a FAY average combine rolls that verified
materially different amounts of behaviour. Recording without gating is the only option that
neither distorts the authoring nor overstates the number.

### 7.2 N, and the FAY bar

Recommendation **N = 6**, bar declared explicitly here before roll 1. The 1.4 arc used ≥4/6.
Both numbers are the maintainer's call; what this document fixes is that they are chosen
**now**, in ignorance of the results.

### 7.3 Does gate approval count as manual intervention?

Unavoidable and currently unruled. In the P6 window, rolls 1–3 carried an operator approval
and roll 4 auto-approved via `system:no_open_questions` — so the same window handled its rolls
two different ways.

Three candidate rulings:

- **(a) Approval is not intervention.** The gate is a designed checkpoint; `--as-agent` already
  records who decided. Simple, but "zero manual intervention" then means something weaker than
  it says.
- **(b) Only auto-approved rolls score zero-intervention.** Strictest reading, and it makes the
  score depend on whether the manifest happened to declare an unresolved decision — an
  authoring accident, not a capability difference.
- **(c) Pre-declare the approval policy here, apply it identically to every roll, and treat it
  as a constant rather than an intervention.** *(Recommended.)* The exact notes text is fixed
  in this document before roll 1, every gate that opens receives it verbatim, and the decision
  is recorded `--as-agent`. A constant applied uniformly cannot bias one roll relative to
  another, and the record stays truthful about who decided.

If (c) is chosen, the verbatim approval text goes here: `_____`.

### 7.4 Exit clause

Recommendation: if FAY is still 0 after N rolls, the window closes at 0 and the claim is
narrowed rather than the window extended. Extending a window after seeing a zero is the same
error as designating one after seeing greens.

---

## 8. What this window does *not* establish

- **Not a claim that verification is complete.** §2.b's declared defects bound it, and #951 in
  particular means a green roll does not imply every declared behaviour was verified
  deterministically.
- **Not a claim about the repair path** unless a roll actually enters a correction round. Four
  P6 rolls produced zero corrections, so the correction machinery — including #942 and #943 —
  remains unexercised in production. If the window also produces none, the closing record must
  say so rather than let "no corrections needed" read as "corrections work."
- **Not transferable to another stack or PRD.** One PRD, one stack, one recipe.

---

## 9. Provenance

Drafted against the state of the SIP-0104 P6 window at 4 of 6 banked rolls, all on frozen
deploy `d590f73c`. The P6 rolls are **not** V7 and cannot be promoted into it: designating a
window after its results are visible is precisely what pre-registration exists to prevent.
