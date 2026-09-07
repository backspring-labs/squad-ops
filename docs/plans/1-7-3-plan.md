# 1.7.3 — plan

**Revision 2, 2026-09-06.** Rev 1 was written while the 1.7.2 counted rolls were still running;
this revision closes it against the finished record (`docs/plans/1-7-2-verification-set-record.md`)
and the cut. What changed is listed in §9. Written from the
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

**Rev 2 is this revision.** §1's last row now carries the counted-roll reading; #1273 is closed
with its trail; and #1285 turns out to be **undecidable from that set** — the texture field it
needed was declared and never produced, which is itself a finding this line acts on (§4).

---

## 1. What the 1.7.2 line says the release has to be

| what the line showed | evidence | what it says about this release |
|---|---|---|
| the 1.7.2 plan promises 1.7.3 three things in three sections — the CI list as its subject (§3), Loop Honesty's second half (§2.6, §7 step 8), the infrastructure rider (§6) — and the pre-registration adds #1312 with #1254 (§4) | 13 CI items + 7 roll-verified + 15 CI rider + 1 roll-verified, against §3.1's capacity of 6–8 roll-verified and 10–15 CI-verified per line | that is three lines, not one; §3 is the owner's ruling and the latest, so the other two yield to it |
| the line's own claim is unstarted: the ROADMAP's 1.7 identity is "every port is actually a port", and after three cuts every Boundaries and Composition Root issue is open | #154, #377, #381, #305, #559, #922, #218, #219, #225, #301, #286 — all open 2026-09-05 | 1.7.3 is the first line that works the claim; without it the line closes with its claim unmet |
| the shakeout budget went to the instrument, not the pack: **five rounds against a budget of three, zero attributable to the eight items**, and **twelve** instrument defects in machinery that had never been run end to end | 1.7.2 record §0 — #1292, #1296, #1298, #1300, #1304, #1305, #1310, #1311, #1318, the P0 nullable false positive, #1321, and the driver's `refused_patches` truncation | the instrument is fixed and exercised *before* the pack opens, on its own deploy, so this line's rounds go to the refactors |
| two of eight predictions were never exercisable as registered: the absent-suite fault stops at the emission retry and never reaches the repair-retest seam; L8 reads post-repair artifact names, so the extractor's half hides the prompt half | #1310, #1311; pre-registration §3 | L2 and L8 enter this line unexercised; their fixes are this line's preconditions, in the slot #1276/#1251 held in 1.7.2 |
| nine unit-test directories are outside the regression gate — 437 tests, `auth`, `memory`, `config`, `ports`, `core` among them — for the fourth time, each prior fix an append to the list | #1316 | a vocabulary or port refactor regresses in exactly those directories; #1316 lands before any refactor, inverting the default so a new directory is gated on creation |
| two of the eleven are not CI-verified in §3.1's sense: #1254 is now one change with #1312 by the ruling recorded there (the handoff becomes optional assembly notes, both check surfaces go, a presence-keyed appendix delivers it to `qa.test`), which changes what a cycle does; #1087/#1112 changes what the qa author is handed | #1312 (2026-09-05 comments); 1.7.1 plan §3 | #1254 leaves the list for 1.7.4 with #1312, where it has a prediction; #1087/#1112 stays and gets a readout (B1, §4). **This reverses a merged placement** — the 1.7.2 pre-registration §4 (PR #1313) says of #1312 and #1254 "and both are 1.7.3" — and §8 records the reversal rather than leaving two merged documents disagreeing |
| #1285 was to be decided from the 1.7.2 record; it cannot be — the texture field it needs was declared and never produced (row below) | #1285; 1.7.2 record §8 | the readout is built in this line's instrument slot, or #1285 is closed as undecidable on the evidence available |
| #1273 is open after its seam shipped: PR #1288 landed two of its three parts and named the re-brief as #1260's, PR #1290 landed #1260, and L4/L5 held on the chained diagnostic (`cyc_9e217c266f5f`); the retry-with-fact backstop 1.7.2 §8a calls "a separate item" has no issue | #1273; 1.7.2 plan §8a | **closed at the 1.7.2 cut with that trail** (record §8): L4 held in the counted set — two 0-case briefs, both with `tests_pass_rows: 0`, so no row carried cases — and L4/L5 held on the chained diagnostic. The remainder is the retry-with-fact backstop, which has no issue; it is filed before 1.7.4's plan |
| **the counted-roll reading**: nine counted rolls, React 5 of 6 and Next.js 3 of 3 functional; **L1 held at 0 contentless of 172 emissions**; **five of eight predictions never fired**; #1312's signature not hit once; `npm_ci_without_lockfile` on 8 of 9 rolls | `docs/plans/1-7-2-verification-set-record.md` §1–§2, §5 | the pack's condition holds, so this line may re-register it; but five predictions are carried on diagnostics alone, and the set says so rather than letting nine greens imply coverage (§4) |
| **qa primary tokens has no producer** — the 1.7.2 pre-registration declared it as texture and no roll record carries a token field | 1.7.2 record §8 | **#1285 cannot be decided from that set**; the readout is added before this line's set or the field leaves the texture list (§8) |

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
| **#1323** | the failed-attempt storage route authorizes what it banks. `_store_failed_emission` performs no write authorization while `_collect_artifacts_and_checkpoint` does, so a builder that fails *because of* a file it was not allowed to author banks that file unguarded — and the repair that fixes it is then dropped for touching it | a wiring test entering at the failure-storage caller: a builder task failing while emitting a net-new `.py` outside the fill slots has that emission dropped with evidence, and no unauthorized path reaches the repair overlay |

**#1323 is here for the reason this block exists — it degrades what a red means.** §4's whole
argument is that the predictions are re-registered verbatim and nothing else changes, so *a red
is the refactor's*. A live #1323 can admit an unauthorized file into the workspace, drop a repair
that fixes a real defect, and supersede a failing check so it vanishes from the report. Any of
those on a counted roll makes a red ambiguous between the refactor and the defect. Cost checked
rather than assumed: `bound_record` is already built at `dispatched_flow_executor.py:1512`, in
the same scope as the loop that calls `_store_failed_emission`, and is already passed to the
success path — the failed path simply does not use it.

**#1310 and #1311 differ in kind, and §7 must sequence them apart.** #1311 is driver-only: no
rebuild, and by the 1.7.2 pre-registration §2 an instrument fix does not supersede a deploy.
#1310 changes `fault_injection.py`, which is baked into the agent images, so its diagnostic
cannot run until a rebuild. #1323 is deployed code and rebuilds with it.

The three diagnostics run on a dev deploy after #1310/#1311/#1323 merge and before the list's first
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

Twelve PRs carrying thirteen items, plus four preconditions: **seventeen CI-verified changes,
two above §3.1's ceiling of 10–15** — stated rather than described as "at" it, because this
plan's own thesis is that capacity claims have been soft for five lines. The two over are the
preconditions added after rev 1 (#1316 was always one; #1323 is new), and preconditions protect
the measurement rather than consuming the list's budget. If the ceiling is to be held literally,
the drop comes from §3.2 by the §3.4 rule — a revision in the open, not a silent re-place.

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

**The claim holds in one direction only, and this plan does not assert the other.** A red is the
refactor's. A **green is not evidence about the list**: the re-registered predictions measure the
correction loop, and twelve of the thirteen items have no roll-level readout at all (only
#1087/#1112 does, via B1). **The set is a regression check on the loop; the list's proof is CI and
the structural test named on each row of §3.2.** The 1.7.2 record is the reason to be exact about
this — nine greens there sat beside five predictions that never fired, and the record had to say
so in its headline rather than let the greens imply coverage.

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

**Size — revised at rev 2 to 6 + 3, the 1.7.2 sizes held.** Rev 1 proposed 4 + 2 on the
grounds that this set exercises carried predictions rather than reading a new one. The 1.7.2
record argues the other way, and against rev 1's own paragraph below: this section expects the
rounds-attributable-to-the-list number to be **non-zero for the first time**, because a refactor
of this width has regressions the structural tests do not reach. If those are expected, fewer
counted rolls is the wrong direction — and the shakeout pair is not the counted set. The 1.7.2
set is the concrete case: **five of its eight predictions never fired in nine rolls**, so cutting
to six would have left even less exercised. 1.6.6 §1.3 still holds — exercise, not a rate — which
is precisely why the exercise should not shrink. *(§8 — the owner overrules; 4 + 2 stands if
wall-clock is the binding constraint, and the record then says the set was sized for time.)*

**Bar.** L1 remains the one bar, for the reason 1.7.2 §4 gives: a contentless first attempt
is the condition every other prediction is measured through. A falsified L1 on this deploy
would mean a refactor reached the reasoning declaration or the emission path, and it blocks
the cut.

**Known non-pack rejection cause, declared before roll 1:** #1312's signature — packaging
files emitted, `qa_handoff.md` absent, `required_files` and `acceptance:sections_present`
failing, boot audit passing — as the 1.7.2 pre-registration §4 states it. Expected on the
order of one roll in six; cited when it occurs; not evidence about any prediction.

**Texture, no prediction attached:** verdict rate against 1.7.2's (no bar); correction
rounds; contentless emissions per roll; `checks_by_environment`; fill assertion strength per
run (#999 — the first record that can read it); tables declared per suite (B1's denominator);
packaging findings — **which 1.7.2 recorded on 8 of 9 rolls** (`npm_ci_without_lockfile`), a
frequency at which it is a standing defect in what the squad builds rather than noise.

**Every texture field named here has a producer, and that is a new requirement.** The 1.7.2
pre-registration listed "qa primary tokens" and no roll record carried a token field, so #1285
could not be decided from a set that appeared to measure it (1.7.2 record §8). A declared
readout with no producer is the #1312 shape — it reads as measured and is not. **The
fill-mode/token readout is built in this line's instrument slot alongside #1310/#1311, or the
field does not appear in this list.** Before the set opens, each texture field is checked against
a real record, not against the driver's source.

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

**Placed at rev 2, filed after rev 1 was written** (the 1.7.2 line's last three): **#1323** is a
precondition of this line (§3.1) — it degrades what a red means. **#1324** (the boot audit
discards the response it judged, so a failed probe cannot be root-caused from the record) is
**1.7.4's rider** — it costs triage time but does not make a red ambiguous. **The Slot-Scoped
Emission draft** (PR #1325, unmerged at this revision — emit the slot body, not the file; the
path is deliberately not cited until it lands, since a plan must not reference a file that is
not in the tree) is feature-shaped by its own §6 and goes to **the 1.8 lane** with #1213/#1176,
where it subsumes #1323's class rather than patching it: with emission scoped to
`{path, slot_id, body}` an unauthorized path has no slot id to emit against. **#1318** shipped in
1.7.2 and is closed; it is named here only because it voided a counted roll and the record
carries it. The driver's `refused_patches` truncation is filed before this line's set opens.

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
4. **#1311** (driver-only — no rebuild), then **#1310 and #1323** (both deployed code) with a
   rebuild and the loaded-module check before their diagnostics; the three diagnostics on a dev
   deploy, recorded with the entry point each used.
5. **The list, in §3.2's order**, one PR each.
6. Rebuild; verify the loaded modules in-container as live calls with their controls;
   shakeouts to the exit rule; pre-register (set configs `1-7-3-<arm>.yaml`); roll — **no
   merges to main while the set is open**.
7. Record from the per-round evidence; cut 1.7.3 by the seven steps. Then 1.7.4.

---

## 8. Decisions made by recommendation — the owner overrules, not fills in

- **1.7.3 carries the list and nothing beside it.** No roll-verified pack; B1 is a readout on
  a list item, not a headline.
- **#1254 and #1312 leave the list for 1.7.4 — and this reverses a merged placement.** The
  1.7.2 pre-registration §4 (merged as PR #1313) says of them "and both are 1.7.3". The reason to
  diverge is that they are one change that alters what a cycle does, so they are not CI-verified
  in §3.1's sense and belong beside a prediction — but the divergence is recorded here rather
  than left as two merged documents disagreeing, per CLAUDE.md's amendment discipline. **The
  owner overrules.**
- **#1254 leaves the list for 1.7.4 with #1312** — one change by the ruling on #1312, and a
  change to what a cycle does.
- **N = 6 + 3** (§4), revised at rev 2 from rev 1's 4 + 2: this section expects list-attributable
  regressions for the first time, and fewer counted rolls is the wrong instrument for that. 4 + 2
  stands if wall-clock is the binding constraint, and the record then says the set was sized for
  time rather than for exercise.
- **#1323 is a precondition, not a list item and not 1.7.4's** (§3.1) — it is in the block that
  exists for things that would otherwise confound the measurement.
- **Every texture field must have a producer before the set opens** (§4), checked against a real
  record rather than the driver's source — the #1285 lesson.
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

- **Rev 4 (2026-09-07, overnight)** — under the same delegation, extended by the owner to
  "proceed all the way to running the cut roll set": **#1351 added as a fourteenth item** by
  default decision (the owner may veto; a veto is one revert), instrument round 2's findings
  (#1350, #1352 — fixed; #1351 — this item), the migration-1150 regression the integration
  job caught (#1343's, fixed), and a mis-titled docs merge disclosed. Each is in the rev 4
  section below.

- **Rev 3 (2026-09-06)** — at the line's opening, under the owner's delegation of the whole
  line: the decisions that diverged from or filled in rev 2, recorded in §9 so the plan and
  the tree do not disagree — the checkpoint pair between the two blocks, instrument rounds
  counted apart from shakeout rounds (round 1 found #1347), #1323's wider mechanism, #999's
  artifact, #1087's rebuild by cherry-pick, #154's null object in the domain, #225's compose
  OK, the post-#922 set configs. Each is the owner's to overrule.

- **Rev 2 (2026-09-06)** — closed against the finished 1.7.2 record and cut. **#1323 added as a
  fourth precondition** (§3.1) with the reason the block exists — it degrades what a red means —
  and #1310/#1311/#1323 separated by whether they need a rebuild (§3.1, §7). §1's shakeout row
  corrected from four rounds and six defects to **five and twelve**; §1's last row filled with the
  counted-roll reading, and a new row records that **"qa primary tokens" had no producer**, so
  #1285 cannot be decided from that set. **N revised from 4 + 2 back to 6 + 3** (§4), because this
  plan expects list-attributable regressions for the first time and fewer rolls is the wrong
  instrument for that. §4 now states that **the attribution claim holds in one direction only** —
  a red is the refactor's; a green is not evidence about the list — and that **every texture field
  must have a producer**, checked against a real record. §3.2's count corrected to **seventeen,
  two above the ceiling**, rather than "at" it. The #1312/#1254 move to 1.7.4 is recorded in §8 as
  **a reversal of the merged pre-registration §4 placement**. #1324 placed in 1.7.4 and the
  Slot-Scoped Emission draft (PR #1325) in the 1.8 lane (§6). Review by the session that ran the
  1.7.2 set (PR #1317 comments).

- **Rev 1 (2026-09-05)** — written while the 1.7.2 counted rolls run, on the owner's ask, from
  the 1.7.2 plan and pre-registration, the 1.7.0 plan §2.4/§3.1/§6.2, the ROADMAP's 1.7
  identity, and the issues the 1.7.2 line filed. Reconciles the 1.7.2 plan's three placements
  for 1.7.3 to its §3 ruling: the Boundaries list is the subject; Loop Honesty's second half,
  #1312/#1254 and the infrastructure rider go to 1.7.4; Composition Root and the deferrals to
  1.7.5; #1316 and the #1310/#1311 instrument fixes are preconditions. §3.3 carries the
  scheduling count, corrected for #154. Rev 2 is owed at the 1.7.2 cut (§1's last row, #1285,
  #1273).

## 9. Rev 3 — at the line's opening (2026-09-06), decisions taken under the owner's delegation

The owner delegated the whole line on 2026-09-06 ("do it all and merge once CI completes")
after merging rev 2. What follows diverged from, or filled in, the plan above; each is
recorded here so the plan and the tree do not disagree, and each is the owner's to overrule.

- **A checkpoint pair between the structural block and the behavioural block** (deploy B),
  added to §7 step 5/6. §4's attribution claim — a red is the refactor's — names the list,
  not the item; with thirteen items on one deploy the loop cannot narrow a red. One pair
  after the eight structural items costs a round and buys the split: a red on the final
  pair belongs to the five behavioural items, a red on the checkpoint to the eight whose
  guards do the bisecting. Recorded in the pre-registration §2.
- **Instrument rounds are counted apart from shakeout rounds.** Phase 1's three diagnostics
  ran on deploy A, built from the last precondition commit (`2b75c3e5`) — a pre-list deploy —
  while the list's PRs merged on main. The plan's intent (§3.1: "the instrument is proven on
  its own") holds; the sequencing in §7 step 4 ("before the list's first PR") was not kept
  literally, and the record says so. Instrument round 1 found **#1347** (the emission-retry
  marker rode every later dispatch; the absent-suite fault re-applied to the correction
  re-takes); fixed in #1348; round 2 pending.
- **#1323's mechanism was wider than §3.1's "one wiring call."** The repair overlay is built
  from the *held* failed result, not from the vault, so authorization at the bank alone would
  not have kept the unauthorized path out of the verifier's tree. Enforced at both points the
  executor admits producer bytes — the held result and the repair before verification — with
  the evidence record naming the stage. §3.1's verification statement was met as written.
- **#999 persisted as an artifact** (`fill_merge_evidence.json` beside `test_report.md`), not
  as a keyed section of `run_verification_summaries.summary`: the summary is references-only
  by contract (SIP-0096 §6.2), and the driver already reads qa artifacts by filename.
- **#1087/#1112 rebuilt by cherry-picking the stale branch's commit onto main** and
  re-verifying, rather than re-authoring: its "ten regression failures" had shrunk to three
  reference pins, all of one kind; contract v12 is classified `reference_defect` with the
  retrospective obligation met by statement.
- **#154 kept the orchestrator's always-inject fallback** and moved the null object into the
  domain (`squadops.telemetry.noop`), which is what makes the import direction legal; the
  issue's "receive it from the composition root, never import it" is satisfied in substance.
- **#225's compose edit merged on the owner's explicit OK**, recorded on the PR as §3.2
  step 10 requires.
- **The set configs use the post-#922 key `development_profile`.** The 1.7.2 configs' loaded
  checks use `dev_capability` and cannot run on a post-#922 deploy; the five 1.7.3 configs
  are written for it, pins blank until the last shakeout.

The scheduling count (§3.3) does not change: every item landed in the plan that scheduled
it for the last time.

## 9. Rev 4 — overnight (2026-09-07), under the delegation extended to the counted set

The owner, going to bed, asked to "proceed all the way to running the cut roll set tonight"
and to report in ET. What follows was decided or found overnight; each is recorded here so
the plan and the tree do not disagree, and each is the owner's to overrule in the morning.

- **#1351 is the fourteenth item, by default decision.** The chain diagnostic on deploy A″
  (`cyc_375bdea6e140`) showed the fill-slot restore putting back the scaffold's router line
  alone: the dev had encoded the resource prefix on the router (`APIRouter(prefix="/runs")`
  + `@router.post("")`), and the restored file — `APIRouter()` + `post("")` — is one FastAPI
  refuses to load. The app could not import, on the first emission and on the repair; the
  restore was silent to the producer. Off the list of thirteen (behavioural, not a
  boundary), but a known defect that produces a non-bootable app in the counted set's own
  stack, one that would cost a §5.1 reset if it bit a counted roll, confined to one pure
  module with tests, and landing before deploy C so the C shakeout pair covers it with no
  extra deploy. The owner was told the default before bed and may veto it; the fix's PR
  names this section. §3.3's count moves to fourteen.
- **Instrument round 2 found two more instrument defects, both fixed before deploy B.**
  #1352: the Python own-frame fault was a `NameError`, which the emission seam's
  `undefined_names` check refused and the handler's self-eval removed before the suite ran
  — L7 on a pytest suite had never been exercised (1.7.2's chain held L7 on its vitest
  task). #1350: `_try_accept_patch` (#1323) enforced a repair's grants with the failed
  task's envelope, so a dev repair of a qa failure was refused as a QA write to a dev slot;
  the grants now follow the producer named on every repair artifact, and an unnamed repair
  artifact is refused loudly. The pre-registration §2 carries both.
- **Deploy B is `4a2cf724` plus #1347, #1350 and #1352 cherry-picked** — the structural
  block with the instrument fixes and nothing behavioural — so the checkpoint still
  isolates the two blocks. The React half of the checkpoint pair: accepted, boot PASS,
  functional, zero correction rounds, no seam finding.
- **The integration job on main was red from #1343's merge (21:22Z on 2026-09-06) and six
  PRs merged past it.** Migration 1150 dropped a column from `agent_status`, a table only
  `init.sql` creates; a database carrying just the migrations (CI) has no such table. Fixed
  with `ALTER TABLE IF EXISTS` and a guard that a migration may only alter a table a
  migration creates. The job is not a required check, and the merge rule read only the
  required three — from here every merge is followed by a read of the whole run. The owner
  noticed first.
- **PR #1353 merged the pre-registration draft and set configs under the #1352 fix's
  title** — opened from the wrong working directory. Retitled to what it merged; #1352
  reopened and closed by its real PR (#1355). Nothing the deploy runs was affected.
