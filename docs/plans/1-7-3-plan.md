# 1.7.3 — plan

**Revision 1, 2026-09-05.** Written while the 1.7.2 counted rolls run on the Spark, from the
1.7.2 plan (`docs/plans/1-7-2-plan.md` §3, §2.6, §6, §7), its pre-registration's shakeout log
and diagnostic results (`docs/plans/1-7-2-verification-set-preregistration.md` §2–§3), the
1.7.0 plan's Boundaries pack, line breakdown and close criteria (§2.4, §3.1, §6.2), the
ROADMAP's 1.7 identity, and the issues the 1.7.2 line filed (#1285, #1310, #1311, #1312,
#1316). **This plan is about one thing: the list.** Thirteen CI-verified boundary items that
every 1.7 plan has scheduled and no line has staffed are this release's whole content, with
three preconditions in front of them, measured by the previous line's verification set
re-registered with no new pack — so a red is the refactor's and nothing else's.

**The rulings that shape it** (owner): **2026-09-04** — the CI-verified list is frozen at three
in 1.7.2, and the eleven that did not ship must be 1.7.3's *subject*, not a rider beside a
headline (1.7.2 plan §3); **2026-09-05** — debt paydown is the direction. What this plan adds
is the consequence those rulings have for the two sections of the 1.7.2 plan written before
them (§2.6, §6, §7 step 8), which still promise 1.7.3 to Loop Honesty's second half and the
infrastructure rider: both are re-placed to 1.7.4 by name (§6), and the 1.7.0 plan §3.1's line
table is amended in the same PR.

**Rev 2 is owed the moment the 1.7.2 record exists**: §1's last row (the counted-roll
reading), #1285's decision (§8), and #1273's disposition at the cut.

---

## 1. What the 1.7.2 line says the release has to be

| what the line showed | evidence | what it says about this release |
|---|---|---|
| the 1.7.2 plan promises 1.7.3 three things in three sections — the CI list as its subject (§3), Loop Honesty's second half (§2.6, §7 step 8), the infrastructure rider (§6) — and the pre-registration adds #1312 with #1254 (§4) | 13 CI items + 7 roll-verified + 15 CI rider + 1 roll-verified, against §3.1's capacity of 6–8 roll-verified and 10–15 CI-verified per line | that is three lines, not one; §3 is the owner's ruling and the latest, so the other two yield to it |
| the line's own claim is unstarted: the ROADMAP's 1.7 identity is "every port is actually a port", and after three cuts every Boundaries and Composition Root issue is open | #154, #377, #381, #305, #559, #922, #218, #219, #225, #301, #286 — all open 2026-09-05 | 1.7.3 is the first line that works the claim; without it the line closes with its claim unmet |
| the shakeout budget went to the instrument, not the pack: four rounds against a budget of three, **zero attributable to the eight items**, six defects in diagnostic machinery that had never been run end to end | pre-registration §2 — #1292, #1296, #1298, #1300, #1304, #1305 | the instrument is fixed and exercised *before* the pack opens, on its own deploy, so this line's rounds go to the refactors |
| two of eight predictions were never exercisable as registered: the absent-suite fault stops at the emission retry and never reaches the repair-retest seam; L8 reads post-repair artifact names, so the extractor's half hides the prompt half | #1310, #1311; pre-registration §3 | L2 and L8 enter this line unexercised; their fixes are this line's preconditions, in the slot #1276/#1251 held in 1.7.2 |
| nine unit-test directories are outside the regression gate — 437 tests, `auth`, `memory`, `config`, `ports`, `core` among them — for the fourth time, each prior fix an append to the list | #1316 | a vocabulary or port refactor regresses in exactly those directories; #1316 lands before any refactor, inverting the default so a new directory is gated on creation |
| two of the eleven are not CI-verified in §3.1's sense: #1254 is now one change with #1312 by the ruling recorded there (the handoff becomes optional assembly notes, both check surfaces go, a presence-keyed appendix delivers it to `qa.test`), which changes what a cycle does; #1087/#1112 changes what the qa author is handed | #1312 (2026-09-05 comments); 1.7.1 plan §3 | #1254 leaves the list for 1.7.4 with #1312, where it has a prediction; #1087/#1112 stays and gets a readout (B1, §4) |
| #1285 is decided from the 1.7.2 record: read the fill-mode token cost from the emission-shape readout; if it is not material at the roll level, close it as a paper problem | #1285 | rev 2 carries the decision |
| #1273 is open after its seam shipped: PR #1288 landed two of its three parts and named the re-brief as #1260's, PR #1290 landed #1260, and L4/L5 held on the chained diagnostic (`cyc_9e217c266f5f`); the retry-with-fact backstop 1.7.2 §8a calls "a separate item" has no issue | #1273; 1.7.2 plan §8a | closed at the 1.7.2 cut with that trail, or its remainder named there; the backstop is filed and placed in 1.7.4 |
| **the counted-roll reading** — L1, verdict rate on each arm, contentless emissions, qa primary tokens by mode, whether #1312's signature was hit | *the 1.7.2 record, not yet written* | **rev 2** |

---

## 2. Why this line, on the roadmap

- **The 1.7 identity.** 1.7.0, 1.7.1 and 1.7.2 were correction-loop lines. This is the one
  that fixes where the machinery meets the outside world — the claim the odd minor was
  assigned (`docs/plans/post-1-5-roadmap-reconciliation.md`; ROADMAP "v1.7").
- **The 1.8 scorecard grades over stable seams.** #377/#381 are the concrete version: a grade
  over `CycleOutcome` today is keyed on Prefect's `State` words living inside domain objects.
  Translated at the adapter boundary, a grade is a statement about the cycle rather than
  about the workflow engine.
- **Capability packs (2.0) need the word first.** #922 has the ordering constraint the ROADMAP
  states: "capability" must be disambiguated before packs publish against it, because a name
  frozen into a distribution format cannot be renamed afterwards.
- **The Atlas migration, half.** The ROADMAP blocks it on vendor vocabulary in domain objects
  *and* on the composition root bypassing the factories. This line clears the first; #301 is
  1.7.5 (§6), so Atlas stays blocked after this cut, and the cut record says so.

**What it does not do, stated here rather than implied.** It moves no verdict rate — nothing
in the list changes what the loop does after a failure. It builds none of the Campaign's ops
floor (#1147, #330, #300: 1.7.4's rider). It does not touch the ~9% builder rejection (#1312:
1.7.4). A reader who wants the number to move is reading the wrong plan; this one is the debt
the last five plans rolled forward.

---

## 3. The content — the list is the subject

### 3.1 Preconditions — before the first list PR

| item | what | verified by |
|---|---|---|
| **#1316** | the regression gate runs `tests/unit` with an explicit `EXCLUDED_DIRS` (each entry carrying a reason) instead of a hand-written include list, and a guard asserts every `tests/unit/*` directory is either run or named excluded | the guard; the pass count moves from ~8,867 to ~9,300 and the PR states both numbers, since the count is quoted as evidence in release records |
| **#1310** | a fault declares the *scope* of "once": `first_attempt` (today's rule) or `all_emission_attempts` (every emission of the target task, never the repair), so `qa_suite_absent` exhausts the emission retries and fails into correction; the diagnostic asserts the **seam reached**, not that the fault fired | unit + a wiring test entering at the executor; then the diagnostic itself on a dev deploy |
| **#1311** | the driver counts the extractor's `fence path placeholder` strips per roll beside the stored-name check; L8 becomes two claims (§4) | driver test; the path-prefix diagnostic re-run and read from the new count |

The three diagnostics run on a dev deploy after #1310/#1311 merge and before the list's first
PR, recorded as diagnostics with the entry point each used. That is the 1.7.2 lesson applied:
the instrument is proven on its own, so a shakeout round on this line's deploy is about the
list.

### 3.2 The list, in merge order

One PR per item; each PR's Evidence names the structural test or guard that proves it, per
the 1.7.0 plan §3.1's definition of CI-verified. The order minimises rebases — the widest
rename first — and keeps each regression attributable in CI.

| step | item | what lands | how CI proves it |
|---|---|---|---|
| 1 | **#922** | the two host-internal meanings of "capability" renamed for what they are — `capability_id` is the task type, `dev_capability` is a stack-settings bundle — leaving the word for bindable agent competence | the rename is complete: a grep guard for the retired spellings; the suite green |
| 2 | **#559** | task-type identifiers: strings at the boundary, constants at the core, properties over identity (97 literals across 23 files at filing) | the enum-shadow family of structural tests extended to task types; a literal outside the boundary fails CI |
| 3 | **#377** | `terminal_status` retired: `RunStatus` is the domain vocabulary everywhere, translated to Prefect's `State` at the `WorkflowTracker` adapter boundary only | the leaked vocabulary anywhere outside the Prefect adapter fails CI |
| 4 | **#381** | `TaskResult.status` typed on `TaskStatus`; the uppercase bare-string twin retired at its eleven comparison sites and its producers | the #380 enum-shadow guard, which found it, has nothing left to flag |
| 5 | **#1241** | `adapters/capabilities/aci_executor.py` imports `squadops.tasks.models`, or the dead executor and its factory entry are deleted — decided in the PR from whether anything is still meant to construct it | `import adapters.capabilities` succeeds; the #582 mirror test's documented exception is removed and its two-sided check passes |
| 6 | **#154** | the forbidden-imports guard extended from four directories to every `src/squadops` package with a declared allowlist of composition roots; the known domain→adapter sites moved — the NoOp observability adapter injected from the composition root, the secrets factory out of the config loader, the bootstrap check into wiring; the route-built `OllamaAdapter` stays with #301 (1.7.5) | the all-packages guard — #1241 lands first because a guard that imports every package needs every package importable |
| 7 | **#218** | the URL-prefix and versioning standard written where CLAUDE.md's API Conventions point, **and a test that enumerates the routes and asserts the lanes** | the route-lane test |
| 8 | **#219** | `/api/chat/*` and `/api/agents/messaging` onto `/api/v1` — router prefixes, console BFF handlers, Caddy rules, the one Svelte consumer | the route-lane test admits no unversioned authenticated route; the chat tests |
| 9 | **#305** | `runtime_status` always populated and the `runtime_status \|\| network_status` fallback removed (Part A); `network_status` no longer computed or stored (Part B — a migration under the applier; the issue's soft-gate on #158 is cleared, #158 being closed) | unit + the migration under the applier; the shakeout pair's agent-status views are the live check |
| 10 | **#225** | the comms agent's id reconciled to `joi` in the heartbeat env and the instances registry | CLI/console chat-routing tests; **the edit to `docker-compose.yml` needs the owner's explicit OK, recorded on the PR** (CLAUDE.md "Docker") |
| 11 | **#999** | the qa task's `fill_merge` assertion-strength evidence persisted somewhere queryable per run | a persistence round-trip test; the record's texture reads it (§4) |
| 12 | **#1087/#1112** | the frozen store exports handles for root persisted entities only — embedded shapes and single-object response projections (`RunDetail`, `RunWithParticipants`) get none — rebuilt from main, not from the stale branch (`fix/1087-root-tables-react-store`: one commit, 120 behind, ten regression failures by its own message) | the generator's reference fixtures; **prediction B1** (§4) |

Twelve PRs carrying thirteen items, plus three preconditions: sixteen CI-verified changes, at
§3.1's ceiling.

**Deliberately not in the list:** #1254 (to 1.7.4 with #1312, §6); the identity-permutation
test the 1.7.0 plan §2.4 named with no issue behind it — filed and placed in 1.7.4's rider
rather than carried here as plan text; #301's route-built adapter (Composition Root, 1.7.5).

### 3.3 The count this line owes the record

The 1.7.2 plan §3 started this table so that a plan scheduling an item for the fifth time
says so. Incremented for this plan, and corrected where its count missed a plan:

| item | release plans that scheduled it | times, incl. this plan |
|---|---|---|
| #559 | 1.4.3, 1.4.4, 1.5.0, 1.7.0, 1.7.2, 1.7.3 | **6** |
| #154 | 1.1.x, 1.4-evidence-arc, 1.5.0, 1.7.0, 1.7.2, 1.7.3 | **6** — the 1.7.2 table missed 1.1.x |
| #999 | 1.6.4, 1.7.0, 1.7.1, 1.7.2, 1.7.3 | **5** |
| #218, #219 | 1.1.x, 1.2.0, 1.7.0, 1.7.2, 1.7.3 | **5** each |
| #1087 (stack-#1 half), #1112 | 1.6.4 / 1.6.5, 1.7.0, 1.7.1, 1.7.2, 1.7.3 | **5** each |
| #377, #381, #305 | 1.5.0, 1.7.0, 1.7.2, 1.7.3 | **4** each |
| #225 | 1.1.x (as a decision item), 1.7.0, 1.7.2, 1.7.3 | **4** |
| #922 | 1.7.0, 1.7.2, 1.7.3 | **3** |

### 3.4 The cut criterion — the list, with no escape

**1.7.3 cuts when every row of §3.1 and §3.2 is merged and the set (§4) has closed with no
falsified prediction.** There is no "re-placed by name" disposition for a list item in this
line: the 1.7.0 plan §6.2 allows that for the Hardening remainder, and it is exactly the
mechanism by which #559 reached six. If capacity forces a drop, **this plan is revised in the
open** — a new revision with §3.3 incremented and the reason stated — never the cut record
after the fact. The structural reason the list has slipped five times is that CI-verified
work gates nothing; this section is what makes it gate something.

### 3.5 Merge discipline

- **Nothing merges to main while the 1.7.2 set is open** (its pre-registration §8). This
  plan's PR and the queue behind it wait for the 1.7.2 cut; the queue is built on branches
  meanwhile.
- Each list PR carries `Closes #N`, its structural test, and — for #305 and #1087/#1112, the
  two that change behaviour a shakeout can see — the entry point the shakeout exercises.
- The Spark lane lands on main between pulls; the wide renames (#922, #559) go first so that
  lane and the remaining PRs rebase once.

---

## 4. The verification set — no new pack

Two counting sets on one frozen deploy, with the 1.7.2 pre-registration's predictions
**re-registered verbatim**: L1–L8, R1/R3/R5/R6/R7, S0–S3, Q0, Q3, Q5, P0. Nothing in the list
adds a loop prediction, and that is the point: a red on this deploy is attributable to the
refactors because nothing else changed — the argument the 1.7.2 plan §3 used to quarantine
them.

**Three changes from 1.7.2, each from its diagnostics:**

- **L8 is two claims** (#1311): **L8a** — the model does not emit under the placeholder; read
  from the extractor's `fence path placeholder` count per roll; falsified by a non-zero
  count. **L8b** — an emission that does is repaired rather than spent; read from stored
  artifact names, as before.
- **L2 is exercisable** (#1310): the absent-suite diagnostic declares `all_emission_attempts`
  scope, the task fails into correction, and the record asserts the repair-retest seam was
  reached.
- **One new prediction, B1** (#1087/#1112): no stored qa suite declares a fixture table for an
  entity that is not a root persisted entity; falsified by one such table; read from the
  stored suites against the manifest's entities. The one list item that shapes an emission
  gets the one new readout.

**Diagnostics before roll 1**, on this line's deploy once the exit rule is met: the three
from 1.7.2 as repaired — absent-suite (L2), own-frame-then-prose chain (L7, L4, L5),
path-prefix (L8b; L8a is read as the count on every counted roll). A diagnostic is never a
roll.

**Size.** FastAPI+React **N = 4**, Next.js+TS **N = 2** — down from 6 and 3, with the reason
stated: this set exercises carried predictions rather than reading a new one; L1, L3, B1 and
L8a are reached by every roll, and the rest by the diagnostics. 1.6.6 §1.3 holds: exercise,
not a rate. *(§8 — the owner overrules.)*

**Bar.** L1 remains the one bar, for the reason 1.7.2 §4 gives: a contentless first attempt
is the condition every other prediction is measured through. A falsified L1 on this deploy
would mean a refactor reached the reasoning declaration or the emission path, and it blocks
the cut.

**Known non-pack rejection cause, declared before roll 1:** #1312's signature — packaging
files emitted, `qa_handoff.md` absent, `required_files` and `acceptance:sections_present`
failing, boot audit passing — as the 1.7.2 pre-registration §4 states it. Expected on the
order of one roll in six; cited when it occurs; not evidence about any prediction.

**Texture, no prediction attached:** verdict rate against 1.7.2's (no bar); correction
rounds; contentless emissions per roll; qa primary tokens by mode (the #1285 reading);
`checks_by_environment`; fill assertion strength per run (#999 — the first record that can
read it); tables declared per suite (B1's denominator); packaging findings.

**Shakeout loop** (`docs/plans/verification-sets/README.md`): exit on a pair on one deploy
with no new seam finding; **budget three pairs**; the cut record reports **two numbers —
rounds taken, and rounds attributable to the list**. This line expects the second number to
be non-zero for the first time: a refactor of this width has regressions the structural tests
do not reach, and the pair is where they are found. That is the loop doing what it is for,
and the record says so rather than reading it as instability.

**Early stop, one direction.** A falsified prediction stops the set; a good result is never
grounds to stop early; a stop in one set does not stop the other.

**Drift the cut record must declare:** intended zero — the tag is the measured deploy plus
the pre-registration and the record.

---

## 5. Hardening — nothing pulled forward

The infrastructure rider (#1147, #575, #577, #576, #578, #330, #300, #581, #560, #372, #352,
#353, #574, #1204, #1205) is 1.7.4's, in full (§6). The 1.7.2 plan §6 gave the reason and it
holds with more force here: no roll has reached any of it, and landing it beside thirteen
refactors would make a shakeout regression unattributable between the list and the rider.
The one considered and not taken is again #1147; no roll in three lines has hit either bound.

---

## 6. Re-placements by name — nothing silently carried

The 1.7.0 plan §6.2 requires every remaining item re-placed by name before the line closes.
This is the placement; the 1.7.0 plan §3.1 is amended to point here.

**1.7.4 — Loop Honesty, second half.** The measured pack, eight: **#1312 with #1254 leads**
(one change — `qa_handoff.md` becomes an optional `assembly_notes.md` defined by exclusion
from the stack's declared surfaces, both check surfaces removed, a presence-keyed seventh
appendix in `qa_test.py`, a derived guard over the registered stacks; prediction: no run is
rejected for an absent handoff, and the qa prompt carries the notes when present), then
#994, #995, #968, #1054, #1070, the retry-with-fact backstop (1.7.2 §8a; to be filed), and
#936/#933 verify-then-close. **#1285 joins the pack only if rev 2's reading says the fill-mode
cost is material.** The rider, at the quota: #1147, #575, #577, #576, #578, #330, #300, #581,
#560, #372, #352, #353, #574, #1204, #1205, plus the identity-permutation test once filed.

**1.7.5 — what the 1.7.0 plan called 1.7.4.** Deferrals #820, #376; **Composition Root**
after its design note — #301, #286, #1152 with #1149 first; extractions #567, #579; the test
items #198, #157, #176, #580, with #1180/#1182 (integration tests and the deployment DSN);
#1197 (the sandbox image tag that names one stack and serves both); **plus #929 with #1206**,
which the 1.7.1 plan §2.4 said must be designed together and which do not fit 1.7.4's rider.

**Placed by this plan for the first time** (open, named in no 1.7 plan): #1213 (anchored
repair edits) and #1176 (carrying the reasoning trace across repairs) are enhancements — the
1.8 lane, with #1122; #1158 (Atlas on the Spark) goes with the Atlas SIP's
revision-and-acceptance decision the 1.7.0 plan §2.7 routes to design review; #1177, #1178
and #1184 are Spark host and A/B-rig work outside any line's quota — named here so the
line-close sweep does not find them unplaced.

**Still at design review, unchanged:** #414, #557, #316; and #80, #950, #949, #194, #1039,
#1031 in the 1.8 lane (1.7.0 plan §2.8).

---

## 7. Sequencing

1. **This plan**, on its own PR, with the 1.7.0 plan §3.1 amendment and the 1.7.2 plan's
   §2.6/§6/§7 pointers. Opened now; **merges after the 1.7.2 set closes.**
2. **The 1.7.2 cut** by the seven steps in `CLAUDE.md`; its record fills §1's last row —
   **rev 2** here (the counted-roll reading, #1285's decision, #1273's disposition).
3. **#1316** — the first merge on the new line.
4. **#1310, #1311**; the three diagnostics on a dev deploy, recorded.
5. **The list, in §3.2's order**, one PR each.
6. Rebuild; verify the loaded modules in-container as live calls with their controls;
   shakeouts to the exit rule; pre-register (set configs `1-7-3-<arm>.yaml`); roll — **no
   merges to main while the set is open**.
7. Record from the per-round evidence; cut 1.7.3 by the seven steps. Then 1.7.4.

---

## 8. Decisions made by recommendation — the owner overrules, not fills in

- **1.7.3 carries the list and nothing beside it.** No roll-verified pack; B1 is a readout on
  a list item, not a headline.
- **#1254 leaves the list for 1.7.4 with #1312** — one change by the ruling on #1312, and a
  change to what a cycle does.
- **N = 4 + 2** (§4), with the reason stated; 6 + 3 stands if the reason is not accepted.
- **L1 stays the bar.**
- **The cut criterion is the list, with no re-place-by-name escape** (§3.4); a drop revises
  this plan in the open.
- **A 1.7.5 exists**, carrying what §3.1 called 1.7.4. The alternative — folding Composition
  Root into 1.7.4 — puts a design-gated runtime-initialisation change beside a measured pack,
  which §3.1 forbids.
- **Merge order: the widest rename first** (#922, then #559), so the Spark lane and the
  remaining PRs rebase once.
- **#1285 is decided at rev 2** from the record's qa-token texture by mode, as the issue asks
  — built in 1.7.4 if material, closed if not.
- **#1273 is closed at the 1.7.2 cut** with the #1288 → #1290 trail and the chained diagnostic
  named, unless the record shows a re-take briefed without its cases — then the remainder is
  named and placed in 1.7.4.
- **The retry-with-fact backstop and the identity-permutation test are filed** as issues
  before 1.7.4's plan is written, so neither is carried as plan text (the #1251 lesson:
  "three lines of plan text, never filed").

---

## 9. Revision history

- **Rev 1 (2026-09-05)** — written while the 1.7.2 counted rolls run, on the owner's ask, from
  the 1.7.2 plan and pre-registration, the 1.7.0 plan §2.4/§3.1/§6.2, the ROADMAP's 1.7
  identity, and the issues the 1.7.2 line filed. Reconciles the 1.7.2 plan's three placements
  for 1.7.3 to its §3 ruling: the Boundaries list is the subject; Loop Honesty's second half,
  #1312/#1254 and the infrastructure rider go to 1.7.4; Composition Root and the deferrals to
  1.7.5; #1316 and the #1310/#1311 instrument fixes are preconditions. §3.3 carries the
  scheduling count, corrected for #154. Rev 2 is owed at the 1.7.2 cut (§1's last row, #1285,
  #1273).
