# 1.8.1 comparison window — pre-registration (plan §7 step 9, §4.3)

**Status: rev 2 (2026-09-23) — the pins, read from deploy B′ after the squad's shakeout pair met
its exit rule (§3a).** B′ was rebuilt from `36f2af6e` (both arms and runtime-api, one rebuild);
every value below was read from that deploy, none carried. §1's four *rev 2* rows now carry them,
and both set configs' pin blocks hold the same values. Nothing else in §1–§9 moved. The §3a
readings are in §10.

**How the config hashes were read.** The rule is "by attempting a roll, never carried" (deploy A
rev 5). Before the shakeout, one cycle per arm was launched with the driver's own `launch()`
command and cancelled 0.2 s later: `cyc_4ec8974a3bc1` (squad) and `cyc_cf40784e4389` (solo).
Nothing counts. **But not "nothing ran"**: each run's first task had already been dispatched, and
the agent ran it to completion after the cancel (#1648, §10a). **Stability without a second launch:**
the CLI computes the hash locally and warns on any server mismatch, and printed none. The server
adds to the hash only a derived `contract_ref` (`api/routes/cycles/cycles.py`, #779), so the value
is a pure function of the request profile. The squad shakeout pair then launched at the pinned
squad hash, which confirms it.

*Rev 1's status block, kept for the record:*

**Status: rev 1 (2026-09-22) — the rules, the arms, the pairs and the readouts, committed before
deploy B′ exists.** The pins — both arms' resolved config hashes, both squad snapshots, the eight
image ids — are read from deploy B′ after the rebuild and land as **rev 2**, before any roll of
either arm is observed (SIP-0108 §4.4: registration precedes observation). Nothing in this
document moves after rev 2 except §10, which is appended as readings land. Written from: the
1.8.1 plan (`docs/plans/1-8-1-plan.md`) §3.5, §4.3 and §8 decisions 5–9, 12 and 16; SIP-0108
§4.4, §10g–§10m; the deploy-A pre-registration (`1-8-1-verification-set-preregistration.md`) for
the shape and the §7 constants; the driver's `window` command (#1638) and its gates (#1620).

**What this window measures.** One thing, in the SIP's words: *under the same deterministic
substrate and execution envelope, does the squad improve outcome and quality over one generalist
agent, and at what additional or reduced token and wall-clock cost?* The independent variable is
**the squad's reasoning organization** — role decomposition, the role-specific identities, the
framing roles, the handoffs, the analyzer and the lead's decision — against one generalist
process on the same substrate. It does not isolate agent count or handoffs alone (that is the
Free-Solo window, a 2.0 planning input, plan §8 decision 11). **The answer is stated whichever
way it goes** and is never generalized beyond this PRD, this model, this deploy.

**What deploy A's reading does not change.** N was unmet (4 of 6, qa × Next.js empty) and the
flip does not land; deploy B is deploy A re-pinned. The window does not need the flip and never
did: it measures the substrate as it is. Deploy A's set also found that the loop answers a qa
own-frame failure by re-authoring the suite rather than by scoped repair (deploy-A
pre-registration §10e). That is a property of the substrate both arms share, and the record
reads it as texture on both, never as an arm effect.

---

## 1. Fixed parameters

| Parameter | Value |
|---|---|
| Arms | **squad** = `full-38` × `validated-fullstack`; **solo** = `solo` × `validated-fullstack-solo`. Both `qwen3.8:27b` on the same Ollama configuration and box; both `group_run`, `fullstack_fastapi_react`, no overrides |
| Pairs | **six valid, at most eight attempted**, React only. Pair *k* = the squad arm's *k*-th registered roll and the solo arm's *k*-th; a **fresh** squad arm — no deploy-A roll is reused (§10g) |
| Order | **interleaved, alternating, fixed here**: pair 1 Squad → Solo, pair 2 Solo → Squad, pair 3 Squad → Solo, pair 4 Solo → Squad, pair 5 Squad → Solo, pair 6 Solo → Squad; replacement pairs 7 and 8 continue the alternation. `pair_order(k)` in the driver is this sentence as code |
| The predicate | per pair, binary on **accepted-functional** (verdict `accepted` AND the boot audit passed): a Squad win when Squad is and Solo is not, a Solo win when Solo is and Squad is not, otherwise a tie. **The directional criterion is at least four wins of six valid pairs, for either arm.** The record always renders Squad wins / Solo wins / ties |
| The void rule | a pair is void **only** for pre-run identity or infrastructure invalidity named here: preflight refused the launch; the roll's config hash or squad snapshot did not match the arm's pins; P0 refused (the seeded tree did not match the manifest); a solo roll stored an artifact the arm is defined by not producing (§10i item 6). **Never for outcome**: a red framing, a rejected verdict, a failed boot audit are outcomes and count. A void removes its pair in full; a mate not yet launched is not launched; the next sequential pair replaces it, up to eight attempted; fewer than six valid after eight **closes the window incomplete**, the criterion not read |
| Reported, never tie-breakers | quality as a **verification-quality proxy** (the retest, the boot audit, correction rounds, termination reasons — the clean-room indicators stay unaskable until SIP-0102 step 5, and the label says so); efficiency as wall clock and completion tokens per roll, rendered per pair |
| Gate policy | the 1.6.3 §6 constant, verbatim in both set configs' `gate_notes`; `--as-agent`; the decider recorded per roll |
| Driver | `verification_set_driver.py window --squad-set docs/plans/verification-sets/1-8-1-window-squad.yaml --solo-set docs/plans/verification-sets/1-8-1-window-solo.yaml`; shakeouts via `shakeout --set …`. **The sample and the budget are the configs' registered data** (`window_pairs: 6`, `window_max_attempts: 8`, declared on both arms and required equal), never flags; a resume whose arms, sample or budget differ from the recorded state is refused. **No arm is observed until the exact pair has passed the comparison gate**: the runner proves the two supplied configs name each other, then reads both arms from the deploy before pair 1's first roll; the per-launch preflight stays, for drift |
| Deploy — commit | **`36f2af6e`** (a label, not an assertion, #1296): main after #1647; runtime-api reports `framework_git_sha` `36f2af6e` |
| Deploy — image ids | runtime-api **`75d866b9883c`**, max **`fcb71587b260`**, neo **`3ac94b110a13`**, nat **`5b947a1d469b`**, bob **`801c18a1c886`**, eve **`c508e66ee55f`**, data **`d7349139a4bc`**, han **`3c63b8422147`**. All eight differ from deploy A's. **Both configs pin all eight**: the committed guard requires the two arms' image maps to be equal. Pinning `han` names it in the squad arm's identity, so every squad record carries Han's image id beside its own and the topology gate asserts all eight containers up for either arm |
| `resolved_config_hash` | squad (`validated-fullstack`) **`58eed2c52e1f`**; solo (`validated-fullstack-solo`) **`5c164909188d`**. Read from B′ by attempting a roll (status block). The squad value equals deploy A's React pin, as it should: the request profile did not move between A and B′ |
| `squad_profile_snapshot_ref` | `full-38` **`2d8d4feb3519a7ec`** (version 2, six × 12288; equals A's pin, because the profile did not move); `solo` **`ef6111328d35570d`** (version 1, seeded at B′'s runtime-api start). Each is the live read (`live_squad_snapshot`) and also the value stamped on that arm's hash-read cycle |
| Records | `var/verification_sets/1-8-1-window-squad/`, `…/1-8-1-window-solo/`; the window's own state and reading in the squad arm's directory (`window-state.json`, `window-<UTC>.{md,json}`) |

---

## 2. Deploy B′ — what it is, and the one code change from B

**B′ is a rebuilt deploy for both arms, not "B plus one container".** The plan's §3.5 wrote
"zero drift under `src/` and `adapters/` from B" and its §8 decision 4 the same; the build showed
one change was necessary and general (SIP-0108 §10m, PR #1641): the identity layer of every
system prompt reads **what the process is** (`context.role_id`, resolved by the entrypoint and now
required at every seam) rather than the handler's step role. On a squad container the two
coincide for every registered handler — the invariant is pinned by a test — so the squad's
prompts are byte-identical to B's; on Han they differ, which is the whole point. **Because it is a
`src/` change, the squad's images are rebuilt from the same tree as Han's**, and the squad arm on
B′ is proven equal to B by that invariant rather than equal by construction. The plan is amended
to say so (plan rev 5, §3.5 and §8 decision 4).

**Every other item is a declaration.** The generalist identity fragment (#1640); the `solo` squad
profile and the `validated-fullstack-solo` request profile (#1642); Han's roster entry and image
inputs (#1643); the repair brief's decision section, optional (#1644); the window runner in the
driver (#1638). The compose service block is the owner's edit (plan §8 decision 16), carried in
#1643's body and applied at the rebuild.

**How `solo` reaches the deploy.** A new profile id seeds itself at runtime-api startup
(`seed_profiles` inserts any id absent from `squad_profiles_seed_log`, `is_active` false), unlike
`full-38`, which needed a PUT because the seeder skips an already-seeded id. Its snapshot is read
from the deploy at rev 2, as `full-38`'s was on A.

**The driver's identity surface grows by one service.** `DEPLOY_SERVICES` is the squad's seven; B′
has eight. The driver reads and pins `han` for a set that names it (`SOLO_SERVICES`,
`named_services`, landed with this registration — `scripts/dev/`, no deploy move), so the
comparison's topology check asserts **all eight containers up for both arms**, not seven, and
the solo arm's records carry Han's image id beside the squad's.

---

## 3. The exercise plan — stated before the first launch

### 3a. The squad's shakeout pair on B′ — two non-counting React rolls, exit rule stated

Because the squad's images move (§2), B′ gets what the plan gives every moved deploy: a shakeout
pair before anything is read as proven. Two React rolls on the squad arm's config, non-counting.
**Exit rule: no new seam finding**, plus one prediction that must hold on both:

| id | prediction | read from |
|---|---|---|
| **I1** (#1641, §10m) | **byte-identical squad prompts.** The system prompt each specialist assembles on B′ hashes to the value the same fragments produced on A's tree — `lead 95ecaf9cb6b79fe1`, `dev 13e209e6caa5dc9f`, `strat dc64a93d9dcda0c4`, `builder 11ed180485de17f9`, `qa 1f1f5c65a90641a7`, `data c74e0e6d4bdd9635` (sha256 prefixes of `get_system_prompt(role).content`) — read live in **each of the six squad containers** (`max`, `neo`, `nat`, `bob`, `eve`, `data`) by the squad config's loaded checks, each with `generalist ccb18ec10f99b448` as the control that a different identity hashes differently; a driver test requires the six probes to be present in the config | `loaded_checks` per container; the stored prompts of the pair's tasks |
| **I2** (#1644) | **the squad's repair brief carries the lead's decision as before**: every repair prompt on the pair contains "The lead reviewed the failure and chose to patch" and never "patch by rule" | the stored repair prompts of any correction round; unaskable on a pair with no correction round, and said so |

A shakeout pair that reaches its exit rule pins rev 2. A finding voids this registration and it is
re-made on the deploy that fixes it, as deploy A's was, and no roll from the superseded deploy
counts toward any pair.

### 3b. Han's shakeout pair — two non-counting Solo React rolls (plan §3.5, §4.3)

Read for seams, never for outcome. **A seam not reached within two runs stops the window for a
plan revision.**

| id | seam | reached when |
|---|---|---|
| **H1** | every task type dispatched to `han` and consumed | every task envelope of the run names `han`; no queue named after a role exists; zero `HandlerNotFoundError` / `UndeclaredRolesError` in any container's log |
| **H2** | the role map resolved with no fallback | the served-roles log line at Han's boot lists six roles; the "serving its own role only" warning is absent |
| **H3** | correction on a failure takes the `repair` step alone with the deterministic patch | on a run that corrects: no `data.analyze_failure` and no `governance.correction_decision` task dispatched; the round's repair brief carries the rule section ("patch by rule", #1644); the plan delta names the deterministic facts (#1614). **Unaskable** on a run that never enters correction, and said so |
| **H4** | the Solo preflight's three absences | `solo_absences` empty on the record: no framing document, no failure analysis, no correction decision stored (#1620, §10i item 6) |
| **H5** | the assessment rendered | the record carries `cycle_assessment` with its attribution id |
| **H6** (#1640, §10m) | Han is briefed as the generalist | the stored system prompt of any Han task hashes to `ccb18ec10f99b448`; the loaded check on `han` reads the same live |

### 3c. The window — six pairs, interleaved, under the runner

Launched only after §3a and §3b exit. The driver's `window` command executes §1's order and void
rule, writes its state after every roll, and renders the reading (#1638). **The comparison gate
runs before either arm is observed** (#1620): the substrate table below is asserted from the
deploy, and any difference refuses the launch.

**Substrate held equal, asserted by the driver from the deploy** (SIP-0108 §4.4, plan §4.3): the
PRD, the request-profile constants (budgets, required checks, time budget, self-eval depth, the
task plan and its gate — `validated-fullstack-solo` differs from `validated-fullstack` in
`correction_steps` alone, asserted by `test_solo_profiles`), the framework deploy, the model, the
effective per-task-type completion cap (12288 on every role of both arms, §10l) and reasoning
level, each task's effective write grant, **run-state isolation** per roll (no run in flight, no
lease held), and **runtime topology** (every agent container up for both arms; only the
designated arm's agent receives work).

**The asymmetries, named as part of what the arm measures** (§10i): in Solo the #1054 dispute and
#1581 unanimity branches do not run — no analyzer, no lead — and the repair brief carries the
failing cases, the failed rows, the contract expectations and the files with no analysis summary;
the Correction Decision section states the rule (#1644). Han's completion cap is the squad's flat
cap; the qa lane's re-authoring behaviour (deploy A §10e) is the substrate's and shows on both.

**Early stop, one direction:** a falsified prediction or an unreached seam stops the window; a good
result never stops it early; a stop in one arm does not stop the other.

### 3d. Predictions per fix, read on the window (one mechanism each, no rates)

| fix | mechanism predicted | read from |
|---|---|---|
| #1641 (§10m) | I1 holds on every squad roll of the window; every Han roll's system prompt hashes to the generalist's | the stored prompts; the loaded checks at each launch |
| #1644 | I2 on the squad; the rule section on every Han repair; **`{}` appears in no repair prompt on either arm** | the stored repair prompts |
| #1642 | `solo` served from Postgres with the flat cap and six served roles; `arm_substrate_problems` reads both arms equal — **predicted silent**: a refusal here is a finding, not a void | the arm preflight at every launch |
| #1643 | Han's image carries node, tsc and pytest: no `missing_tooling` skip on any Han roll that the squad's roll does not also carry | the non-execution-by-skip-reason field per roll |
| #1638 | the runner's state file names every roll in the registered order; a void, if any, is replaced by the next sequential pair and its mate is not launched | `window-state.json` |

---

## 4. What the record renders at close

The runner's reading, verbatim: Squad wins / Solo wins / ties over the valid pairs; the criterion
(`squad`, `solo`, `neither`, or "not read — the window closed incomplete"); attempted, valid and
void pairs with each void's reason; per pair, both cycles, both functional readings, wall clock
and completion tokens. Beside it, per arm: the verification-quality proxy (retest, boot audit,
rounds, termination reasons). The conclusion sentence names the independent variable — *the
squad's organization against one generalist process on this substrate* — and nothing broader
(plan §8 decision 9).

## 5. Drift the record must declare

The one code change from B (§2) and the rebuilt image ids; both arms' config hashes against
deploy A's `58eed2c52e1f` (the squad's should equal it: the request profile did not move) and the
solo arm's against it (it differs by `correction_steps` and the profile name); both snapshots;
the eighth service.

## 6. Prohibited while this window is open

**Nothing merges to main** (plan §3.11). No change under `src/`, `adapters/`, `config/` or
`src/squadops/prompts/`; no deploy move; no profile PUT. Docs and driver-only changes are free
only where they cannot alter a reading, and a change that could is a deploy move, which voids
this registration.

## 7. Teardown, after the reading

One PR removes the `solo` squad profile, the solo request profile, the generalist identity
fragment and Han's compose service (plan §8 decision 12), after the record freezes their exact
configuration and image identities. Items that are general capabilities stay: the declared role
map, correction steps by request profile, a process serving its declared roles, the identity
layer reading the process (§10m), the optional decision section (#1644), the window runner.

---

## 10. Readings — appended as they land

*(§3a's pair, §3b's pair, then the window; rev 2 adds the pins above this line before any roll
of either arm.)*

### 10a. §3a — the squad's shakeout pair on B′ (2026-09-23, non-counting)

Both rolls ran on `36f2af6e`. Each record's identity block carries the seven squad image ids,
matching §1. `han` was not yet named in the squad config when the pair ran, so the pair's
records don't carry Han's id; it was up throughout, idle. Each record stamps config `58eed2c52e1f` and
snapshot `2d8d4feb3519`, the rev 2 squad pins. Records:
`var/verification_sets/1-8-1-window-squad/shakeout-20260923T{035939,045147}Z.{md,json}`.

| roll | cycle | verdict | boot audit | functional | criteria | correction rounds | wall clock |
|---|---|---|---|---|---|---|---|
| 1 | `cyc_4fd319b021bc` | accepted | PASS (5 probes) | yes | 21 / 21 | none (asked) | 52 min |
| 2 | `cyc_a1909a39b8a1` | accepted | PASS (7 probes) | yes | 23 / 23 | none (asked) | 51 min |

**I1 — holds, on the live source.** In both rolls' identity blocks, every one of the six squad
containers hashes its identity prompt to the value §3a registered (`lead 95ecaf9cb6b79fe1`,
`dev 13e209e6caa5dc9f`, `strat dc64a93d9dcda0c4`, `builder 11ed180485de17f9`,
`qa 1f1f5c65a90641a7`, `data c74e0e6d4bdd9635`), each against the generalist control
`ccb18ec10f99b448`. **The stored-prompt half is unaskable, and the registration named a source that
does not hold it:** LangFuse records each generation's `prompt_layers` ids with `hash: null`, and
its `input` is the user prompt (10,000-character cap), not the system prompt. What the stored
generations do show is each task on the right agent with its own role's system layer
(`data-planning-system` on data … `qa-build-system` on eve), 16 generations on roll 1.

**I2 — unaskable on this pair.** Neither roll entered correction, so no repair prompt was
rendered. §3a allowed for this ("unaskable on a pair with no correction round, and said so"). The
lead-decision section is the window's to exercise.

**Seam findings from the pack: none.** Across both rolls (03:06–04:52Z), no B′ container logged an
ERROR or a traceback that belongs to either roll.

**One finding from outside the pack: #1648.** The two hash-read cycles (status block) were cancelled
0.2 s after their first dispatch. Cancel marked the runs cancelled, stopped their Prefect flows and
released their leases. **The agents that had already consumed the envelopes ran them to completion
anyway:** han until 03:06:47Z, data until 03:11:24Z. Roll 1 passed run-state isolation at 03:06:52
(runs and leases both clean) and dispatched its first task to data while data was still working
the cancelled squad run's task. Roll 1's framing therefore started about 4.5 min late, behind a
ghost generation. Roll 1 is non-counting, and its verdict, audit and criteria don't depend on
timing. **Its wall clock is inflated by about that much and is not a baseline.** The four
runtime-api tracebacks in the window all belong to the two cancelled runs (the executor waited on
the ghost replies, then logged a harmless `cancelled → cancelled`).

**Exit rule, and the question it leaves.** The pack found nothing new, and I1 holds. #1648 is new,
but the pack didn't produce it: the rev 2 hash-read procedure did. It does bear on §1's void rule
and §3c's run-state isolation, though: a cancel near a launch puts the next arm's first task behind
a ghost the gate cannot see. **Whether #1648 voids this registration, is fixed first (driver-side
gate or agent-side drop), or is carried with a procedural guard is the owner's ruling.** Until
then, §3a's exit is stated as "met for the pack, open on #1648".

### 10b. §3b — Han's shakeout pair on B′ (2026-09-23, non-counting)

Both rolls ran on `36f2af6e`, config `5c164909188d`, snapshot `ef6111328d35`. Records:
`var/verification_sets/1-8-1-window-solo/shakeout-20260923T{054958,070323}Z.{md,json}`.

| roll | cycle / impl run | verdict | boot audit | criteria | what correction did | wall clock |
|---|---|---|---|---|---|---|
| 1 | `cyc_8c6d36b89b6d` / `run_a3241715d118` | rejected (`tests_pass`) | PASS | 20 / 21 | round 00: dev repair offered no qa-owned file (#884 veto), emitted nothing, refunded; `qa.test` re-authored (1 → 3 failing); `plan_defect` at round 0 | 57 min |
| 2 | `cyc_30ee4777d182` / `run_aea9baa75e73` | rejected (`tests_pass`) | PASS | 20 / 21 | round 00: patch applied, verification passed (10 checks), retest FAILED; `qa.test` re-authored; round 01: repair hit the completion cap, refunded; `qa.test` re-authored (1 → 4 failing); `plan_defect` at round 1 | 72 min |

Han's own log (read directly, since the driver couldn't; see H-row notes): roll 1, 17 emissions and
86,806 completion tokens; roll 2, 21 emissions and 106,088 tokens, one of them zero-character.

| seam | reading |
|---|---|
| **H1** | **Reached.** Every framing task (8 on roll 1) and every implementation, repair and retest task went to `han_comms`; no role-named queue exists; zero `HandlerNotFoundError` / `UndeclaredRolesError` in any container |
| **H2** | **Reached.** Han's boot line: `serves roles: lead, dev, strat, builder, qa, data`; the fallback warning is absent |
| **H3** | **Reached in its core.** Both rolls corrected with the `repair` step alone; no `data.analyze_failure` and no `governance.correction_decision` was dispatched. **The brief's rule section is unaskable from the stored generation**: LangFuse caps `input` at 10,000 characters and the section falls past the cap. Han's loaded check proves the template (`1644 True True`). **Texture, not a finding:** the deterministic classifier gave a non-own locus to a failure in a qa-owned suite, so the dev repair was offered the views, not the suite (#884). In the squad arm, the lead's decision can name the owner. This is §10i's named asymmetry at work |
| **H4** | **FAILS on both rolls, and the rule is wrong, not the arm: #1650.** The absence check forbids any `governance.*` artifact, and the solo task plan this registration holds equal (§3c) opens every implementation run with `governance.define_done`. **As coded, every Solo pair voids.** Needs an owner ruling (options in #1650) |
| **H5** | **Unaskable, driver defect #1654**: `cycle_assessment` ran on an expired CLI token. It reads as unaskable on 8 of the 10 1.8.1 records, including both of §3a's rolls. The driver's exact command after a login returns a full assessment. Fix: #1655 |
| **H6** | **Holds on the live source** (Han's loaded check: `10m generalist ccb18ec10f99b448`). The stored half is unaskable, as for I1. The generation's `prompt_layers` label reads `dev-system` on Han, but that label is built from the *step's* role (`handlers/cycle/base.py:1055`), not from the prompt it sent, so it's a telemetry label, not evidence either way |

**Driver defects this pair surfaced, beyond H4 and H5:**
- **#1651:** emission facts were read from the squad's six containers only, so every Solo emission fact read unaskable, including the per-roll completion tokens §1 reports. Fix: #1652.
- **#1653:** correction rounds are counted by stored correction decisions, so every Solo roll reads 0 rounds, including roll 2, which applied, verified and retested a patch. Needs a definition (does a refunded round count?) before a fix.

**A gap in this registration:** SIP-0108 §10i item 3 says the Solo termination rule is "stated in the
window's pre-registration". It is not. Both rolls terminated `plan_defect` on the first conjunct
alone (carried without progress, "candidate=none"), once after a round that had been refunded.

**§3b's exit is not met.** Five findings (#1650, #1651, #1653, #1654 and the termination-rule gap)
are all in the driver or the registration, none in the deploy. The rule is "a seam not reached within
two runs stops the window for a plan revision": H4 and H5 were not reached. The window does not
launch on this registration.
