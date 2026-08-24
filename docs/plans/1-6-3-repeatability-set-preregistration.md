# 1.6.3 — Repeatability Set: Pre-Registration

**Status: DRAFT — not in force until every §2 precondition holds.** Once in force, nothing in
this document changes until the set closes.

**Owner:** maintainer · **Question:** on a frozen config and a frozen deploy, at what rate does
the post-1.6.2 system produce a **working** application? · **Prior:** none usable — see §1.2.

---

## 1. Design

### 1.1 Why this set exists

1.6.2 merged roughly twenty fixes against a corpus of observed loss modes. **None of them has
been measured.** The line's evidence is one green roll (`cyc_79eebcb82205`, verdict accepted +
boot audit PASS) — the first time verdict and oracle have ever agreed — and a single green roll
is not a rate.

A loss-mode census over the seventeen rejected implementation runs from 2026-08-14 to 08-23
makes the case sharper. Classified by round-0 analysis and, where banked, by the test report:

| Loss class | N | Fix status at 1.6.2 |
|---|---|---|
| Unfilled scaffold slots | 5 | shell-imports-TABLES fix landed 08-17; last instance 08-18 |
| Error envelope disagreement | 2 | #795 closed 08-22 — both instances predate it |
| Status 200/201 disagreement | 2 | #1067 / #1042 / #1070A, shipped 1.6.2 |
| Store mutation | 2 | #1064 `update()` seam, shipped 1.6.2 |
| Truncated emission | 2 | **#998 open, no fix** |
| Repair-induced regression | ≥1 | #994 open |
| Residual app defects | remainder | — |

**Eleven of seventeen belong to classes that have since been fixed.** The corpus describes a
system that no longer exists: it records what was killed, not what kills the next roll. That is
the argument for measuring rather than for continuing to fix.

### 1.2 Why there is no prior to beat

Two candidate baselines, both unusable:

- **On the frozen config `d4d4f662…`: 1 of 4 accepted.** Four rolls, identical
  `resolved_config_hash`, same deploy, same day (2026-08-23) — three rejected, one accepted.
  The squad profile is not an input to that hash, so the four are not a single arm: three ran
  `full-38` (1 accepted, 2 rejected) and one ran `full` (rejected). **On the profile this set
  uses, the prior is 1 of 3.** Direct evidence of variance rather than drift, and far too small
  to serve as a comparator.
- **Verdict acceptance across 2026-08-13→23: 20 accepted / 17 rejected / 3 blocked (~50%).**
  Mixed configs and both squad profiles, and flat — the daily figure swings between 0% and 71%
  with no trend across the whole 1.6.2 fix program. It also measures the wrong thing: verdict
  `accepted` and *works* have coincided exactly once.

**This set therefore establishes a baseline; it does not beat one.** The 1.6.4 set compares
against this one.

### 1.3 The honest limits of N=8

**Owner ruling 2026-08-23: N=8.**

| N | result | 95% Wilson CI | width |
|---|---|---|---|
| 6 | 3/6 (50%) | [18.8%, 81.2%] | 62 pts |
| 8 | 4/8 (50%) | [21.5%, 78.5%] | 57 pts |
| 10 | 5/10 (50%) | [23.7%, 76.3%] | 53 pts |
| 8 | 8/8 (100%) | [67.6%, 100%] | 32 pts |

Headline precision barely moves with N in this range. **The set cannot distinguish a 50% system
from a 65% one** — that needs N in the hundreds, and the closing claim must say so rather than
implying the figure is sharper than it is.

What N=8 does buy, and why it was chosen over 6:

- **A clean sweep means more.** 6/6 puts the lower bound at 61%; 8/8 puts it at 68%.
- **Texture coverage.** A defect class firing at 25% never appears at all in 18% of six-roll
  sets, versus 10% at eight. **The texture fields (§4) are the real instrument at this N** —
  they say whether a specific fix bit, which the headline cannot — so a class going unobserved
  is the expensive failure mode.

Not chosen for comparability with V7 or V38: those measured authored-mode FAY and a model swap.
This measures a repeatability rate. Matching their N was never a constraint.

**Cost.** Roughly 2.5–3h per roll (the green roll: 2h38m including two rejected framings), so
20–24h of rolling. **Sequential** — parallel fan-out on the single GB10 runs at approximately
sequential speed against the memory-bandwidth ceiling, so concurrency does not shorten the set.

---

## 2. Preconditions

| # | Precondition | State |
|---|---|---|
| 2.1 | **Shakeouts read out**, both NON-COUNTING by declaration before launch (§2.a) | **MET** — see §2.d |
| 2.2 | **#1079 parity half landed** — `audit_delivered_app.py` implements every probe expectation kind, or calls `probe_runner` instead of re-implementing it. **Blocking, per §2.b** | **MET** — PR #1084; `evaluate_expectations` extracted, both callers use it, parity asserted as function identity |
| 2.3 | Stack landed and each fix verified LOADED in-container, not merely built | **MET** — #971 (#1081), #1082 (#1083), #1079 (#1084). Verified at RUNTIME in all seven agents + runtime-api, not by grep: the injected-check tuple resolves to `('undefined_names', 'unterminated_source')` and the shared probe judge answers |
| 2.4 | **#947 / #936 read complete** — is the unfilled-slot class dead or lucky? If alive it enters the stack and this set re-registers | **MET** — dead, and it was never what the census called it. See §2.e |
| 2.5 | Deploy frozen; commit + all seven image ids recorded in §3 | **MET** — §3 |
| 2.6 | Zero unreleased focus leases; nothing in flight | checked at each launch by the driver's preflight |
| 2.7 | `resolved_config_hash` re-verified `d4d4f662…` at roll 1 | **MET** — both shakeouts created at `d4d4f66217d8`; the driver aborts the roll if it ever differs |

### 2.a The shakeout is non-counting by declaration

**Owner ruling 2026-08-23**, made before the roll's outcome was known — which is the only point
at which such a declaration is worth anything.

`cyc_3ba9dc0f67da` is the first exercise of three fixes that rode the v1.6.2 tag untested
(#1064 store update seam, #1067 manifest status warrant, #1070A plan restatement removal), on a
deploy many merges ahead of the one the green roll ran on. A new deploy is a new failure
surface. The shakeout converts "a machinery defect discovered at roll 5 costs every roll before
it" from a risk carried through the whole set into a fact known before roll 1.

It **may** reveal a machinery defect, which is then fixed before roll 1. It **may not** be
counted, banked, or cited as a repeatability result, whatever it produces. Its outcome does not
move N or any §3 parameter. If it fails on the squad's output rather than the harness, that is
not a machinery finding and nothing is fixed on its account.

### 2.d Both shakeouts, and what they do and do not establish

| | shakeout 1 `cyc_3ba9dc0f67da` | shakeout 2 `cyc_d6c48bab51e9` |
|---|---|---|
| deploy | pre-stack | frozen `5c6c64f7`, full stack |
| verdict | accepted | accepted |
| boot audit | PASS | PASS (5 probes, UI reaches every path) |
| framing runs / re-rolls | 1 / 0 | 1 / 0 |
| correction rounds | 0 | 0 |
| gate decided by | `system:no_open_questions` | `system:no_open_questions` |
| wall clock | 52 min | 62 min |

Shakeout 2 was required because **#1082 is the only stack item that changes squad-facing
behaviour** — a framework-injected check that can fail a task. V7 §2.f's reasoning applies
unchanged: declining a second shakedown because the first went well treats it as ritual
rather than a check.

**What it establishes:** the guard does not reject healthy work in flight. That was the
risk the 4,513-file corpus sweep could not close, because a sweep reads stored bytes and a
roll produces new ones. #971 likewise banked nothing spurious.

**What it does NOT establish, and the closing claim must not imply otherwise:** that #1082
catches anything. Nothing in either shakeout was truncated, so the guard was never asked.
Its catching behaviour rests on the corpus sweep (8 flags, all genuine) and its unit tests,
not on either shakeout.

**Neither shakeout may be counted, banked, or cited as a repeatability result** (§2.a).

### 2.e The #947 / #936 read — dead, and misnamed in the census

The "unfilled scaffold slots" class (5 of the census's 17, its largest) was **not** the qa
author omitting fills. **#987** (`52ed447f`, merged 08-18) is the cause: a language-prefixed
fill fence — ```` ```typescript:fill:slot-X ```` instead of the taught ```` ```fill:slot-X ````
— did not match the exact-form parser, so the fills were stripped as an unaddressed file,
the shells rendered the failing states a missing fill is *defined* to produce, and **the
analyzer wrote a parse rejection up as an authoring failure**. §1.1's census inherited that
misreading wholesale.

Dead on the numbers: **4 of 17 implementation runs before 08-19, 0 of 25 on and after** — at
the prior 23.5% rate, P(0 in 25) ≈ 0.13%.

The method lesson is recorded because it generalises: **a census built on analyzer prose
inherits the analyzer's misattributions.** #968 exists for this reason. Date each class
against its fixing commit and read the fix.

#947 stays out of the stack, correctly: it is real and live (qa self-eval burns 68% of the
task's wall clock emitting a file the guard discards) but it is wasted work, never a
rejection reason — it appears in no loss row. #936's guard exists and is green
(`tests/unit/capabilities/test_fill_vocabulary_is_in_scope.py`).

### 2.b Why #1079 is blocking rather than cosmetic

Inherited verbatim from V7 §2.a: **a set that measures zero manual intervention cannot require
manual intervention to score itself.**

`audit_delivered_app.py` decides the functional level — the headline metric of this set. It
re-implements probe checking inline (`audit_delivered_app.py:188-204`) and covers two of the
three expectation kinds the in-cycle runner covers, silently omitting `json_has`. An oracle that
skips an expectation kind makes a green set unfalsifiable in precisely the direction least
worth trusting. The precedent is exact: #952/#953 were audit-script defects and V7 ruled them
blocking for this reason.

The **producer** half of #1079 is deliberately *not* a precondition — it moves the contract
hash, and landing it inside the set voids the freeze. It is a post-set decision.

### 2.c Stack — **owner ruling 2026-08-23: as below**

| Item | Why | Order |
|---|---|---|
| **#971** persist failed-task emissions | Instrumentation. 13 of 17 historical rejections have no banked test report and are permanently unreadable; a set that reproduces that teaches nothing | first |
| **#998 + #939** deterministic emission guards for nextjs — reject a source file that does not parse, or carries unresolved names, at emission | The only corpus loss class with open issues and no landed fix. A `leave/route.ts` ending mid-token and a 691-byte handoff doc, both banked as complete, both found only when the suite tried to run them | second |
| **#1079** parity half | §2.b | any |

Dropped with reasons: **#795** (closed 08-22; the sweep doc's 1.6.4 entry is stale).
**#947/#936** become a read, not a fix (§2.4). Held for measurement rather than fixed:
#1054, #994, #969, #968/#788/#1015A, #995, #924.

---

## 3. Fixed parameters — complete before roll 1, unchanged thereafter

| Parameter | Value |
|---|---|
| N (rolls) | **8 counted**; §5.1 validity rules inherited from V7 verbatim |
| Bar | **none** — this set has no pass/fail bar. It establishes a rate |
| Project / PRD | `group_run` — `examples/03_group_run/prd.md`, sha to be re-verified at roll 1 |
| Squad profile | `full-38` (`qwen3.8:27b`) — matches the green roll |
| Request profile / overrides | `validated-fullstack`; `build_profile=nextjs_ts`, `dev_capability=nextjs_ts` |
| `resolved_config_hash` | expect `d4d4f662…`; re-verify at roll 1 |
| Deploy — commit | `5c6c64f7` (the commit the images were BUILT from; HEAD may sit ahead of it for a docs-only change made before roll 1, as #1085 did — what is frozen is the deploy) |
| Deploy — 7 image ids | runtime-api `c0cae4d1ea8a` · max `964cde436e5f` · neo `669a9d536366` · nat `8189b36e464a` · bob `befdaca21f31` · eve `98130be6ce7e` · data `1a3d4df7afdd`. The driver asserts all seven at every launch: a rebuild changes these even when the commit does not, and "rebuild exits 0 with stale agents" is a known failure here, so identity beats provenance |
| Gate policy | §6, pre-declared verbatim text, applied identically to every roll |
| Audit instrument | `scripts/dev/audit_delivered_app.py` at the frozen deploy commit, carrying #1079's parity fix |

---

## 4. Per-roll record

**Headline (per roll):** verdict · boot audit PASS/FAIL as a **separate fact** · manual
intervention yes/no · §5.1 validity.

**Texture — the real instrument at N=8.** Each keyed to a measured loss class, so the set says
whether a specific 1.6.2 fix bit:

| Field | Answers |
|---|---|
| Framing re-rolls consumed | the framing tax; #1013/#1030/#1067/#1070A |
| Correction rounds consumed, and terminal reason | did the loop converge or exhaust |
| Repair routing: dev vs qa task types dispatched | #1054 — did any roll repair only the suite |
| Unfilled scaffold slot events | is the largest historical class dead (§2.4) |
| Truncated-emission events | #998 — should be 0 once the guard lands |
| Error-envelope disagreements | #795 — should be 0 |
| Status-disagreement events | #1067/#1042/#1070A |
| Store-mutation defects | #1064 |
| Repair-induced regressions | #994 |
| `criteria_verified` / `criteria_total`, and unevidenced count | #1021 — **confounded, see below**; recorded because the drop is itself the signal, not because the ratio is a clean quality measure |
| Completion tokens by role · cycle wall clock | cost, and #998-class cap-exhaustion events |
| Gate `decided_by`, verbatim | which approval path ran (§6.1) — never inferred |

**The criteria ratio is confounded and is reported as such.** Two shakeouts on ONE frozen
deploy, same config, gave 12/12 with nothing unevidenced and 9/14 with five — all five
`vc-compiles-*`, the #1021 signature. So the ratio moves with #1021's unexplained
variability as much as with anything the squad did, and the closing claim may not read it as
a quality measure. It is recorded because **the drop is the signal**: #1021's mechanism is
unexplained, and eight rolls on a frozen deploy is the largest same-configuration sample the
question has ever had.

**Contract size**, non-gating, no floor, read from stored artifacts (V7 §7.1 inherited): probe
count from `behavioral.probes`, slot count from the `verification_scaffold_manifest`.

---

## 5. Scoring and the closing claim

A roll is **functional** iff verdict `accepted` **AND** the boot audit passes **AND** zero
manual intervention (V7 §5, inherited). Verdict alone is not the metric — verdict and working
have coincided once in the line's history, and conflating them is the error this set exists to
correct.

**No re-rolls to improve the figure. Eight rolls, done** (V7 §7.4 rule 2, inherited).

The closing claim reports: the headline with its confidence interval, the texture table, an
explicit statement of what N=8 does and does not support (§1.3), and — per the release-cut
standard — exactly what the measured deploy does and does not cover relative to the tagged tree.

### 5.1 Roll validity — inherited from V7 §5.1 verbatim

- **Void** — a cycle that never reaches `qa.test` (for example a framing-gate system
  rejection). A void roll **neither counts nor resets**; it is recorded and re-launched.
- **Reset** — a *new* mechanical suite failure attributable to the harness rather than to the
  squad's output resets the set, and the closing record names the surface.
- **Counted** — everything else, **including rolls that fail**. An unfiltered set counts its
  failures; that is what unfiltered means.

---

## 6. Gate policy — a pre-registered constant

V7 §7.3(c), inherited: gate approval under a pre-declared policy applied identically to every
roll is a constant, not an intervention, and does not count against §5's zero-intervention
requirement. A constant applied uniformly cannot bias one roll relative to another.

**The rule is mechanical, deliberately.** Approve `progress_plan_review` **iff** system plan
validation passed. No additional human judgment — judgment exercised unevenly across rolls
injects exactly the variance this set measures. Framing re-rolls are recorded separately (§4)
rather than being smuggled into the gate decision.

**Verbatim approval text** — copied exactly, no substitution of any kind:

```
1.6.3 repeatability set. Approved under the pre-registered gate policy
(pre-registration §6) — identical text applied to every roll of this set.
System plan validation passed; no additional judgment applied.
```

Recorded `--as-agent`.

### 6.1 Two approval paths, and why the record must name which one ran

The rule above assumes a gate opens for a decision. **It does not always open.** Shakeout 1
(`cyc_3ba9dc0f67da`) auto-approved via `system:no_open_questions` — the manifest declared no
unresolved decisions, so nothing was ever put to a human. V7 saw the same split within one
window: its rolls 1–3 carried an operator approval and roll 4 auto-approved, which is what
made §7.3 a ruling rather than an afterthought.

Left unstated, "zero manual intervention" would silently mean two different things inside one
set, and the difference would track **whether the manifest happened to declare an open
question** — an authoring accident, not a capability difference. That is precisely the
objection §7.3 raised against candidate ruling (b), and it applies here whether or not the
approval is counted.

**Therefore, and pre-registered rather than decided later:**

- **Both paths satisfy §5's zero-intervention requirement.** `system:no_open_questions` is the
  framework deciding under a rule; the §6 constant is the operator applying a fixed text under
  a rule. Neither is judgment about *this* roll's content, which is the only thing that could
  bias one roll relative to another.
- **The per-roll record names the decider verbatim** — the `decided_by` value from
  `cycle_gate_decisions`, so `system:no_open_questions` and `human:<id>` are distinguishable
  after the fact without inference.
- **The split is reported in the closing claim**, as a count. If the set divides across the two
  paths, that division is a fact about the rolls and is stated; it is not smoothed over, and it
  is not used to reweight anything.
- A `system:plan_validation` **rejection** is neither path: the framing re-rolls under
  `framing_max_rerolls`, and §4 counts it as framing tax.

---

## 7. Prohibited while the set is open

V7 §6 inherited: **no merges to main. No image rebuilds. No edits to the expander, any prompt
asset, any plan asset, or the scaffold fixture. No change to the gate policy. No change to this
document.**

Detections are recorded as issues and left unfixed. If a detection is severe enough that
continuing would waste the remaining rolls, the correct action is to **abort and re-register**,
not to fix and continue.

This is the release-cut rule ("nothing else merges between opening the release PR and merging
it") applied to measurement, and for the same reason: a tag and its notes that disagree, and a
measurement and its deploy that disagree, are the same defect.

---

## 8. Provenance

Owner rulings of 2026-08-23, in order: **1.6.3 is about repeatability** (reframing the
2026-08-21 sweep's "correction-loop evidence completion" pack); **the first roll after the
1.6.2 rebuild is a shakeout**, declared non-counting before launch; **N=8**; **file the #1029
oracle residue** (#1079).

The loss-mode census in §1.1 was run against `cycle_registry`, `cycle_runs`,
`run_verification_summaries` and the banked artifacts under `data/artifacts/group_run/` on
2026-08-23. Its central caveat is recorded here rather than in a footnote: **only 4 of the 17
rejected runs have a banked test report.** #1017 (failed retests discard their report) closed
2026-08-21, so for the other 13 the classification rests on the analyzer's own round-0 claim —
and #968 exists precisely because nothing verifies those claims against the source. That
limitation is why #971 leads the stack.
