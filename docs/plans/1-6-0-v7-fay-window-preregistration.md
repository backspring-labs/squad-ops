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
| 2.1 | V6 complete (SIP-0104 P6 window closed) | **MET** — closed 2026-08-17 03:46 ET at 6 rolls: 5 banked, roll 6 rejected. Record: `sip-0104-p6-window-record.md` |
| 2.2 | **#952 and #953 fixed and deployed** — see §2.a, this is blocking | **MET** — merged (#956) and deployed 2026-08-17, loaded-module verified in runtime-api, eve and neo |
| 2.3 | Instrument defects either fixed or explicitly declared (§2.b) | **MET** — all three merged (#957/#958/#959) and deployed, loaded-module verified |
| 2.4 | Deploy frozen; commit and image ids recorded in §3 | pending — rebuilt again for #967, ids recorded at freeze |
| **2.7** | **#967 fixed and deployed** — see §2.d. Added after roll 6; blocking on the same argument as 2.2 | **fixed (#973), deploying** |
| 2.5 | Zero open focus leases immediately before roll 1 | check at launch |
| 2.6 | Every ruling in §7 closed | **MET** — 7.1, 7.2, 7.3 and 7.4 all closed; 7.4's remaining bands and the 1/6 split ruled 2026-08-17 |

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

### 2.b Instrument defects that must be fixed or declared — DECIDED

Each of these bounds what a green roll means. Fixing is preferred; declaring is acceptable if
the declaration is recorded here **before** roll 1 and repeated in the closing claim.

**Owner ruling 2026-08-16: fix all three open dispositions.** None is declared away.

| Issue | Effect on the number | Disposition |
|---|---|---|
| #951 | The scaffold covers a derived subset of declared behaviours and never reports the delta | **fix** — built, PR #958 |
| #948 | Probe derivation misses body-discriminated child actions | **fix** — built, PR #959 |
| #915 | An additive suite may mock `global.fetch` and assert its own mock, undetected | **fix** — built, PR #957 |
| #795 | `error_contract.shape` is authored and read by nothing; four of four P6 rolls declared an envelope the seam never emits | declare (already a known window artifact; unchanged by the ruling above, which covered the three open rows) |

**What "fix" costs, so the ruling is not read as uniform.** These are not three comparable
tasks, and #948 in particular is not a bug fix:

- **#951** is additive instrumentation — emit, per roll, which declared behaviours carry
  deterministic coverage and which do not. It changes no authored artifact and no verdict.
  It makes the delta legible, which is exactly what the issue asks for.
- **#915** is a static check over emitted additive suites for self-mocking (`vi.mock` of the
  fetch seam, stubbed `global.fetch`). Detection, not prevention.
- **#948 changes what the squad authors.** The correct fix — established on the issue and not
  reopened here — is to let `request_shapes` declare candidate **values** so a child action can
  be probed, rather than to relax the derivation regex, which would synthesize `{"action":
  "sample"}` and make a *correct* app fail. That reaches the manifest schema, the authoring
  brief, contract derivation, and the scaffold generator. It is the largest item in the queue
  and the only one that alters the artifact under measurement.

**Consequence to state plainly:** with #948 fixed, V7's manifests are authored under a schema
P6's were not, so the two windows are comparable on *recipe* (§3's config hash is unmoved) but
**not** on probe counts. The P6 distribution — 5 / 2 / 5 / 4 across four identical-recipe rolls
— is the measurement that motivated the fix, and it must not be reported as a baseline the
V7 numbers improve on. They are measurements of different instruments.

### 2.d Why #967 is blocking, added after roll 6 *(owner ruling 2026-08-17: fix before V7 opens)*

P6 roll 6 was **rejected with a working application.** It installed, built, booted and answered
all five contract probes over real HTTP. Its only defect was that the suite and the app guessed
different names for the in-memory store table — a free string nothing declared.

Every other item in §2.b bounds the number by letting something through *unverified*. This one
bounds it the other way: **it fails applications that work**, and it fires whenever two
independently-authored artifacts guess the undeclared name differently. Rolls 1–5 guessed
alike. That is a coin flip sitting underneath the measurement, and it can only push the figure
down.

Fixed in #973 by deriving the table names from the manifest's entities and typing them, so a
mismatch is a compile error that `next build` fails on — before the suite runs. Roll 6's exact
key now produces `error TS2345: Argument of type '"run_store"' is not assignable to parameter
of type 'Table'`, measured against real tsc.

**One consequence for the closing claim.** A bare "N of 6" invites the reading that the missing
rolls shipped broken software. Roll 6 did not, and neither will a future roll that fails this
way. The closing record states what each failure *was*, not only how many there were — the
same category error the roll's own three failure analyses made.

### 2.e The pre-window shakedown — DECLARED NON-COUNTING BEFORE IT RAN *(2026-08-17)*

One `group_run` cycle on the frozen deploy, at the same recipe, launched **before** roll 1 and
**not part of this window**. Declared here before launch, and again in the cycle's own `notes`
at creation, because a declaration written after a result is worth nothing — the same reason
§9 forbids promoting the P6 rolls into V7.

**Why it is worth two hours.** §2.c raised the boundary risk and its mitigation was
loaded-module verification, which was done: seven containers, module-level checks in
runtime-api, eve and neo. But a module import is not a cycle. This boundary absorbed **eight
merged changes and a GENERATOR_VERSION bump** — the widest this line has had — and §5.1 resets
the window on a *new* mechanical suite failure attributable to the harness. Discovering one at
roll 4 costs every roll before it. The shakedown converts that from a risk carried through six
rolls into a fact known before the first.

**What it may and may not do.**

- It **may** reveal a machinery defect, which is then fixed before roll 1 — that is a
  diagnostic, and fixing what a diagnostic finds is the standing rule.
- It **may not** be counted, banked, or referred to as a FAY result, whatever it produces. A
  green shakedown is not evidence of yield; it is evidence the boundary is not broken.
- Its outcome **does not** move the bar, N, or any §3 parameter.

**If it fails on the squad's output rather than the harness**, that is not a machinery finding
and nothing is fixed on its account — the window opens as planned. The distinction is the same
one §5.1 draws, and it is the reason this is declared as a boundary check rather than a
practice run.

### 2.f Shakedown #2 — DECLARED NON-COUNTING BEFORE IT RAN *(2026-08-17)*

Same terms as §2.e, on the deploy that carries #979. Not part of this window; may not be
counted, banked, or cited as a FAY result whatever it produces.

**Why a second one is not ceremony.** Shakedown #1 worked: it found a machinery defect that
would have failed *every* roll of the window. The fix (#979) **changes the shell spine's own
import line** — `GENERATOR_VERSION` 3 → 4, both pinned hashes moved. So the artifact under
measurement is different from the one #1 exercised, and the argument that justified #1 applies
unchanged to #2. Declining the second because the first went well would be treating the
shakedown as a ritual rather than a check.

**What #1 established, and what it did not.** It established that the boundary breaks loudly
and where. It did **not** establish that a cycle completes on the fixed shells, because it
never ran on them — it ran on the broken ones and recovered by a route we would not want
repeated (§2.g).

**The bar for #2 is narrower and stated in advance:** a `qa.test` that passes on its **first**
attempt with fills that reference the store. #1's eventual pass came on a third attempt from
fills that had retreated to response-only assertions, so "it went green" is not the thing being
checked. First attempt, store touched — anything less and the boundary is not clear.

### 2.g What shakedown #1 exposed about a green roll *(2026-08-17, #980)*

Recorded here because it changes how a V7 result must be read, not merely what to fix.

Shakedown #1 finished `accepted`, 41 verified, 14 of 14 criteria — and it got there by
**retreating**. Three `qa.test` attempts:

| attempt | fills | completion tokens | what they assert |
|---|---|---|---|
| 1 | 8/8 | **4,896** | response **and store effects** (used `TABLES`, hit #979) |
| 3 | 8/8 | **711** | `body.id`, `body.title`, `body.datetime` — **response only** |

The winning emission is a seventh the size and touches the store nowhere. The per-roll record
in §4 reads `8 of 8 fills` for both, identically.

**So a green roll can be a retreat, and §4 cannot currently tell.** #980 carries the fix and
the recommended split: **instrument before roll 1** (fill emission size, and whether any fill
references a store symbol — both derive from data already logged), and **do not change the
authoring behaviour** before the window, since the retreat was *induced* by a machinery defect
that is now fixed and attempt 1's unprompted behaviour was the behaviour we want.

Until the instrumentation lands, the closing claim may not assert anything about assertion
strength — only that the slots were filled.

### 2.c The size of the deploy boundary is itself a risk *(raised 2026-08-16)*

Six PRs now sit ready for the single rebuild that separates P6 from V7: #956 (two audit
defects), #957, #958, #959, and the docs. Each is individually justified — five are
preconditions this document itself imposes. Together they are a **large** boundary
immediately before an evidentiary window, and §5.1 resets the window on a *new* mechanical
suite failure attributable to the harness. A defect introduced by this batch and discovered
at roll 4 costs the whole window.

Two things follow, and neither is a reason to skip the fixes:

1. **Merge what this document requires, and nothing else.** #933, #935, #939 and #946 are
   real defects with no bearing on what a green roll *means*; landing them in the same
   boundary buys nothing the measurement needs and adds surface. They wait for V7 to close.
2. **Deploy-prove before roll 1, in-container, per the 1.5 precedent** — the loaded-module
   verification, not the rebuild's exit code. The rebuild has exited 0 with stale agents
   before.

The alternative — one change per boundary, as the old P6 window ran — buys attribution this
window does not need, since V7 measures a deploy rather than a change.

---

## 3. Fixed parameters — complete before roll 1, unchanged thereafter

| Parameter | Value |
|---|---|
| **N** (rolls) | **6** — owner ruling 2026-08-16, §7.2 |
| **FAY bar** | **≥ 4/6** — owner ruling 2026-08-16, §7.2 |
| PRD | `examples/03_group_run/prd.md` (declares **v0.5**), sha256 `f744843dfd14d2be71d30ddaa2e6d5c3fe0b574cd42aec168802bde58ac40005` — measured 2026-08-16 at `136fffb7` |
| Squad profile | `full` |
| Request profile | `validated-fullstack` |
| Overrides | `build_profile=nextjs_ts`, `dev_capability=nextjs_ts` |
| `resolved_config_hash` | `d4d4f66217d88324d449b0cc7c05dd4665e17dcb90c63f7cfcd544ab5fc122d2` — **re-verify at roll 1**, see below |
| Deploy — main commit | `_____` *(unknowable until the fix queue lands)* |
| Deploy — image ids | runtime-api `_____`; max, neo, nat, bob, eve, data `_____` *(unknowable until the rebuild)* |
| Gate policy | **pre-declared constant** — owner ruling 2026-08-16, §7.3(c) |

**On the PRD filename.** The draft named `group_run_v0.5.md`, which is not a path that exists;
the file is `examples/03_group_run/prd.md` and *declares* v0.5 in its header. Corrected because
a sha recorded against a wrong filename is worse than no sha — it looks verifiable and is not.

**On the config hash, and why it is re-verified rather than assumed.** `compute_config_hash`
(`cycles/lifecycle.py:243`) is a function of the request profile's `defaults` merged with the
execution overrides, and of **nothing else** — no deploy state, no image, no commit. So this
value is stable across the rebuild that separates the P6 window from this one, and it is the
same hash the six P6 rolls carried, which is what makes the two windows comparable on recipe.
It is nonetheless re-verified immediately before roll 1, because anything landing in the fix
queue that touches the `validated-fullstack` CRP defaults would move it silently. Recomputed
locally at `136fffb7` via `compute_config_hash(load_profile('validated-fullstack').defaults,
{'build_profile': 'nextjs_ts', 'dev_capability': 'nextjs_ts'})`.

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
| **whether any fill asserts on the store** — non-gating (#980) | `fill_merge.assertion_strength.any_fill_touches_the_store` |
| **fill body size, and which slots assert on state** — non-gating (#980) | `fill_merge.assertion_strength` |
| boot audit result | `audit_delivered_app.py`, recorded **separately** |
| gate disposition and decider | `cycle_gate_decisions.decided_by` |

**Why assertion strength is recorded and not gated.** Shakedown #1 banked `accepted` with
14 of 14 criteria after its qa author retreated — 4,896 tokens of fills asserting response
values *and* store effects on attempt 1, 711 tokens asserting response values alone on
attempt 3, recorded identically as "8 of 8 fills". An author may legitimately have nothing to
say about the store for a given behaviour, so this may not reject a roll. What it makes
impossible is a closing claim that describes assertion strength the window never recorded.
Read from banked evidence rather than a log line, because logs rotate and the closing record
is written later.

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

### 7.1 Contract size per roll (plan step 4c) — DECIDED

**Owner ruling 2026-08-16: record probe count and scaffold slot count per roll, non-gating,
with no floor.** This is the decision plan step 4c requires to be made *in the window record*,
so ruling it here satisfies 4c by construction.

**What is counted, exactly:**

- **probe count** — entries under `behavioral.probes` in the roll's derived
  `verification_contract.yaml`;
- **slot count** — behaviour slots in the roll's `verification_scaffold_manifest`, one per
  emitted shell file.

Both are read from stored artifacts, so they are recoverable after the fact and cannot be
mis-transcribed.

**Non-gating means non-gating.** Neither number may reject a roll, trigger a re-roll, or be
fed back into authoring. A roll with 2 probes counts exactly as much as a roll with 5.

**The closing record reports the distribution, not a mean.** "6 rolls, probes 5/2/5/4/x/y" is
the honest form; a single averaged figure would conceal precisely the variation this ruling
exists to expose.

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

### 7.2 N, and the FAY bar — DECIDED

**Owner ruling 2026-08-16: N = 6, bar ≥ 4/6.** Chosen before roll 1 and before any V7 roll
exists, matching the 1.4 arc's precedent. Neither number moves once the window opens; in
particular the window does not stop early on a good run and does not extend on a bad one.

**Consequence that must be settled with it (see §7.4): this bar is stricter than the 1.6 cut
gate.** The gate requires *authored-mode FAY repeatably > 0*, which two successes satisfy. A
result of 2/6 or 3/6 therefore **clears the cut gate and misses this window's own bar**. That
is a legitimate outcome, not a contradiction — the gate asks whether the capability exists, the
bar asks whether it is reliable — but which of the two the release claims must be fixed now
rather than argued after the number is known.

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
  as a constant rather than an intervention.** The exact notes text is fixed in this document
  before roll 1, every gate that opens receives it verbatim, and the decision is recorded
  `--as-agent`. A constant applied uniformly cannot bias one roll relative to another, and the
  record stays truthful about who decided.

**Owner ruling 2026-08-16: (c).** Gate approval under this policy is a pre-registered constant
and does not count as manual intervention for §5's scoring.

#### The policy, in force for every roll of this window

**Verbatim approval text** — copied exactly, with no substitution of any kind:

```
V7 FAY window. Open questions deferred; core PRD scope only. Approved under the
pre-registered gate policy (pre-registration 7.3c) — identical text applied to every
roll of this window, recorded as an agent decision.
```

Issued as `squadops runs gate <project> <cycle> <run> progress_plan_review --approve
--as-agent --notes "<text above>"`.

The text carries **no roll number and no commit hash**, deliberately: anything that varies per
roll is not a constant. The roll is identified by its run id in the window record.

**Rules that make (c) hold:**

1. **Every gate that opens receives this text, verbatim.** No paraphrase, no addition, no
   response tailored to what the manifest asked.
2. **A roll that auto-approves via `system:no_open_questions` is not treated differently and is
   not disadvantaged.** Both dispositions are consistent with zero manual intervention, because
   the policy — not the operator — decided in advance. The disposition is recorded per §4.
3. **If a manifest asks a question the standing text does not address, the text is still applied
   verbatim.** The questions are recorded in the window record, and "the standing policy did not
   address this roll's questions" is logged as an observation. It is never grounds to deviate:
   the moment the answer varies with the question, approval becomes a judgment and the metric
   loses its meaning.
4. **Any deviation voids the roll.** Not the window — the roll. It is re-launched and the
   deviation is recorded.

Rule 3 is the one that will be tempting to break, and breaking it is the failure mode this
ruling exists to prevent.

### 7.4 Exit clause, and what each outcome band claims — DECIDED

The window always closes at 6 rolls. It is never extended on a poor result and never stopped
early on a good one.

**Owner ruling 2026-08-16 on the middle band** (2–3 of 6). **All remaining bands ruled
2026-08-17**, including the 1/6 split, so every cell below is decided and none is a draft.

| Result | Cut gate (*repeatably > 0*) | This window's bar | Claim the release may make |
|---|---|---|---|
| **≥ 4/6** | met | met | A squad-authored design produces a working application with no human intervention, at a rate of N of 6 on a pre-registered window against a frozen deploy. *(**owner-ruled 2026-08-17**)* |
| **2–3 / 6** | met | missed | The release claims that a squad-authored design **can** produce a working application with no human intervention, and does **not** claim it does so reliably. The figure is banked as the authored-mode baseline for 1.8 to measure against. *(**owner-ruled**)* |
| **1 / 6** | **not met** — see below | missed | Same as 0/6: a single success is not repetition. The release claims the path has been observed to complete end to end, not that the capability is demonstrated. The figure is banked. *(**owner-ruled 2026-08-17**)* |
| **0/6** | not met | missed | The release makes no authored-mode FAY claim. The window is reported at 0 with its per-roll failure classes named, and 0 is the baseline. *(**owner-ruled 2026-08-17**)* |

**Two rules attach to every band, and they matter more than the wording.**

1. **The figure is banked whatever it is.** 1.8's memory and campaign work has to beat
   something real. A number discarded because it disappointed is worse than no number, because
   the next window then has nothing to be compared against and will quietly become the first.
2. **The window is never re-run to improve the figure.** This is most tempting at exactly
   3/6, where one more roll could tip it over the bar. That is the move pre-registration
   exists to block. Six rolls, whatever they say, done.

**Why 1/6 is separated from the 2–3 band** *(**owner-ruled 2026-08-17**, on the reasoning
below; it was raised as the one band most open to a different reading and settled deliberately
while the number is unknown)*. The cut gate's wording is *repeatably > 0*, and one success is not repetition.
Grouping 1/6 with 2–3 would let a single green satisfy a gate whose whole point is that one
green is not evidence. The conservative reading is taken because the alternative claims more
than the data supports, and because at 1/6 the pressure to argue the generous reading will be
at its highest.

A 0/6 result closes at 0 and narrows the claim; extending after seeing a zero is the same
error as designating a window after seeing greens.

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
