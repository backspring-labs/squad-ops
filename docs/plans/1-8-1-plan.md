# 1.8.1 — plan

**Revision 1, 2026-09-17.** Written the evening v1.8.0 was tagged, from: the 1.8.0 plan
(`docs/plans/1-8-0-plan.md`, rev 11) §3.3 step 7, §3.4 (d), §4.2, §6, §7 step 14 and §8
decisions 5 and 15; the 1.8.0 pre-registration (`docs/plans/1-8-0-verification-set-preregistration.md`)
§3c, §3f and §10c — the deploy-F set, the §3c count, the owner's ruling and the evidence gate;
SIP-0107 §38 step 7, §39 and §46a; SIP-0108 §4.4, §5 and §10g–§10j; SIP-0086 §12a and SIP-0096
§17a, both targeted for 1.8.1 by the owner on 2026-09-15; every 1.8.0 record under
`var/verification_sets/1-8-0-*` (fifty-two record files — every shakeout from deploy B on, the E
set and the F set); and the tracker on the day of writing — twenty-seven open issues, every one placed
by name (§6).

**1.8.1 is a patch that carries a measurement window** — the 1.6.3 precedent, which the 1.8.0
plan §3.9 named so the sweep would not read this line as a fix line. It carries the two halves
the 1.8 headlines declared 1.8.1's *by design*: **the default flip** (SIP-0107 §38 step 7, ruled
2026-09-13) and **the comparison window** (SIP-0108 (d), ruled 2026-09-14, its arms named
2026-09-17). Beside them: the two capability amendments the owner targeted here on 2026-09-15
(SIP-0086 §12a, the model's compile loop; SIP-0096 §17a, the producer's dispute), the fixes the
F set filed, the diagnostic the F set was missing, and a reader for the assessment the evidence
gate could only recompute. Its cut promotes both 1.8 headline SIPs to `implemented` if their
own criteria hold on this line's records, and says which did not if not.

Three facts shape it, stated once:

1. **The flip's precondition is not met on 1.8.0's record.** SIP-0107 §39.8 read **N = 5 of 6
   with qa × Next.js empty** (pre-registration §10c.4); the cell's diagnostic supply was never
   registered. The owner closed the *line* on that reading (§10c.5). The flip's precondition is
   the SIP's, and §39.8 is explicit: fewer than N means step 7 does not happen. The five F
   transactions cannot carry into a new count — N is fixed "before any transaction that could
   count toward it is observed" — so 1.8.1 supplies N under its own pre-registration, on its own
   deploy, with the missing diagnostic registered, and the flip lands only after that reading
   (§3.2, §3.3, §4.1). If that N is unmet, 1.8.1 ships without the flip and says so.
2. **Zero whole-file repair responses on the whole 1.8.0 record.** Every revision-form row across
   the fifty-two records reads anchored edits, one refused structural edit, prose-only, new
   files only, or fill — never a whole-file response, offered or unoffered (§1). The refusal the
   flip lands is therefore predicted to fire **zero times** on this deploy, this model and these
   prompts; its live effect is a contract, not a change in behaviour, and its proof is the
   historical corpus replayed plus the SIP's own fixtures, not the window's count (§3.3). The
   plan says this rather than letting the flip read as a measured improvement.
3. **Solo changes role routing and the correction path** (SIP-0108 §10g) — the reason it is here
   and not in 1.8.0 — and the §10i rule binds how: **declarations and one container, never a
   branch on a squad or profile name under `src/` or `adapters/`.** Three of its six items are
   general cleanups the platform owes regardless (the declared role map replacing a silent
   fallback; correction steps declared by the request profile; a process serving the roles its
   profile assigns). They land in the prelude with the squad's behaviour byte-identical, so the
   window's deploy differs from the flip's by one container and two profile files (§3.2, §3.5).

Rules carried from the 1.8.0 line without discount: a measured tranche and a structural tranche
do not share a deploy; no fault, no prediction; every field three-state; every diagnostic reaches
its seam on the pinned deploy; §5a amendments in the SIP, in the PR that diverges; **a counted set
is a shakeout round** — the F set's lesson, where the pairs found nothing and the set found seven.

---

## 1. What the 1.8.0 line says this release has to be

| what the line showed | evidence | what it says about this release |
|---|---|---|
| **N read 5 of 6, qa × Next.js empty**; the cell's supply — "the same diagnostic in fill mode" — was named in §3c and never registered; the one Next.js roll with a qa fill repair lost its retest to #1602 | pre-registration §10c.4; §3c's supply table | **the ninth diagnostic is registered before anything else** — `own-frame-then-prose-repair` on `nextjs_ts` in fill mode (§3.1); **N is re-fixed on 1.8.1's deploy A** in a fresh pre-registration, the flip after it (§3.2, §4.1) |
| **Next.js counted roll 1 rejected on #1602**: the #970 fill branch aimed at the shells only; the qa's free-authored suite failed the same assertion on every retest and was never a target | `cyc_bb493eb4725b`, §10c.3; PR #1603 | **#1603 is this line's first merge** — held out of the tag so the tag carried zero drift from F; it is exactly the path the ninth diagnostic exercises |
| **zero whole-file responses on any 1.8.0 record** — every repair that was offered the edit form took it (§46l–§46m); the only non-edit forms were prose-only (refunded), new-files-only and fill | the revision-form row on all fifty-two records; §3f named this count as "the count 1.8.1's replay starts from" — it is zero | **the flip's replay proof runs on the historical corpus**, the 1.6.5 and 1.7.5 whole-file repairs the SIP's §1.2 was written from, and on the §30.2 fixtures; the checkpoint pair on the flipped deploy predicts zero refusals (§3.3) |
| **the A1 reader read NO with the mechanism firing** (#1600): a decision that quotes the injected path to refute it counts as inheriting it; the prose refutation #968 logs is never read; the second run of a two-run budget was spent on a reading | `cyc_ad721e796487`, §10c.1 | **#1600 lands before the diagnostics run** — reporting-only, the driver's; a machine join on the task id, a third state `refuted_verbatim` (§3.1) |
| **the seeded conftest provides no isolation** (#1598): roll 6's suite assumed an autouse reset the harness never had, and the plan hint said it might | `cyc_767ad2dc59d2`, E set | **the owner's ruling, then the prelude** — option 1 moves the seeded conftest, a committed scaffold golden moves with it, so it lands before deploy A's checkpoint (the #906/#1463 and #1499 lesson) |
| **the evidence gate's word "carries" was read honestly**: the assessment was recomputed read-only over the nine counted cycles (22 indicators each, 0 unresolved refs); the driver's record does not render it and no product reader prints it | §10c.6 | **a reader** — one authenticated route and one CLI command, and the driver's record renders the assessment (§3.6); "carries" becomes "shows" |
| **the compile loop is one pass on a truncated first error**: the readiness probe fixed the named error in six of six trials and every build stopped at a second error the evidence had never shown | SIP-0086 §12a; `var/probes/2026-09-15-scoped-repair-readiness-v2` | **§12a lands** on the repair path's deploy, with a diagnostic that plants two errors (§3.4) |
| **a correct dispute is indistinguishable from an empty emission** (#1581, deploy C pair 2): the dev refused to edit a file every party agreed was correct, and the framework read it as "no content" | #1581; the repair template's unread "say why in one line" | **§17a lands** beside §12a, with a diagnostic that forces a false criterion (§3.4); #1581 closes with it |
| **the ops rider was skipped**: 1.8.0 §3.7's five items were sequenced "after the counted set, never between" and the box went from the last counted roll to the cut | 1.8.0 §7 step 12; the tracker (#1177, #176, #1176, #1408, #1412 open) | carried verbatim, same rule, after the window (§3.8) |
| **the shakeout pairs found nothing and the counted set found seven** | 1.8.0 §10 rev 10 | every deploy here is shaken out by the diagnostics *and* a counted set before anything is read as proven; the budget assumes one counted-set round per deploy (§4) |

---

## 2. Why this release, on the roadmap

### 2.1 The flip — the contract closes, and the plan says what that is worth

SIP-0107's pre-flip contract (§46a) has one code path: a repair of a supported existing artifact
requests a scoped revision, and a whole-file response without the fallback authority of §9.4 is
accepted, recorded as an unauthorized whole-file fallback, and never counted toward N. Step 7
lands what waits: §9.4's authority requirement, the §21 row refusing whole-file replacement
without authority, and the matching sentence of §39.5. Nothing else in the SIP changes at the
flip; every other rule has applied since the step that introduced it.

What the record says the flip will do on this deploy: **nothing observable.** Across every
record of the 1.8.0 line — thirty-three from deploy B's first shakeout through E's set, nineteen
from F — the revision-form row never once reads a whole-file response, offered or unoffered. §46l
asked for edits and §46m showed the files, and the model took the edit form every time it was
offered one; where it did not, it emitted prose (refunded by #1591), new files only (a repair
that supplies a missing suite), or a fill. The refusal's predicted count on the flipped deploy's
checkpoint pair is zero, and a non-zero count is a finding about the pair, not a success of the
flip.

Why ship it anyway, and why this release: because the contract is the point. A repair path
whose smallest-revision property depends on the model's current compliance is a property of the
model; a path that refuses the whole-file shape is a property of the framework, and it holds
when the model, the prompt or the stack changes. The owner ruled the flip its own release on
2026-09-13 so that it could land on a measurement rather than inside one (§46a's evidence); the
measurement exists, and it says the guard will be silent. That is the honest shape of a
fail-closed rule landing after the loop already learned to behave: **a guard, proven by replay,
predicted silent live.** SIP-0107 goes to `implemented` on it — §39.1 through §39.8 hold on the
records — or stays `accepted` with the unmet criterion named.

### 2.2 The window — the thesis gets its first number

SIP-0108 §4.4's question, in the record's words: *under the same deterministic substrate and
execution envelope, does the squad improve outcome and quality over one generalist agent, and at
what additional or reduced token and wall-clock cost?* Total cost is measured, not equalized; a
negative is a result and is 2.0's problem, not this cut's. §10h names the arm as **Solo** — one
agent, display name Han, role `generalist` in source, the squad's reasoning organization removed
(no framing roles, no role prompts, no handoffs, correction without the analyzer and the lead)
on the same substrate (manifest, plan, typed checks, patch acceptance, retests, budgets, gates).
§10g is why it is 1.8.1's: steps bind roles, an unmatched role resolves to a queue nobody
consumes, a process serves one role, and the correction protocol runs the independent variable
as agent steps. The window compares the squad against Han at N = 6 pairs on React, by a count
over pairs declared before either arm is observed (§4.3).

What the window does **not** answer, so the cut does not claim it: the **placement thesis**
(§10h — outcome per unit of cost across edge / local / cloud placements) needs the arm axis to
carry provider, model, reasoning and cap per member, and cost as a first-class dimension; the
Solo window runs one provider and one model on both arms, so the axis beyond the model and the
tokens-per-provider accounting are **a successor's criteria** (§10j, its last paragraph), not
this line's. **Free-Solo** (§10j — the same model with a plain agentic loop and no substrate,
every arm judged from the outside by the clean-room audit and a held-out suite) is a later
window, paired with the successor PRD in the group_run line, **held** by the owner's ruling of
2026-09-17. Both are on the record so their absence at the cut names a gap in the successor,
not an open child here. The three aims stand together — the placement thesis, Campaign (2.0),
Embodiment — and this window is the first number under the first of them.

### 2.3 The capability amendments — the framework stops constraining the model it runs

Both were drafted on the owner's question of 2026-09-15, *does the framework constrain the
model it runs*, and targeted for 1.8.1 the same day. Neither is built; each SIP section says so
and says nothing below it describes main until the PR that builds it amends it with what
shipped.

**SIP-0086 §12a — the self-evaluation pass becomes the model's compile loop.** Four changes on
the seam that already exists: depth is the request profile's, required (`max_self_eval_passes`
on every profile, the 1-hour build profiles at 3, the selftest profiles at 0), each pass in the
run's usage ledger under its own key; every error, not the first (`tsc --noEmit --pretty false`
beside the build on the TypeScript stacks, every failing row on Python, the evidence limit
raised); the pass sees what it edits (the files shown, the edit-fence form when the file
exists, a whole-file re-emission recorded on the revision form); one evaluation per pass, on
the verifier's tree. The correction protocol and its budget are untouched. The evidence is the
probe: the named error fixed six of six, the build stopped at a second error six of six, and a
pass costs 20 to 60 seconds where a round costs five to ten minutes.

**SIP-0096 §17a — a contested result: the producer's dispute becomes evidence.** A typed
`disputed_checks` block through the prompt-asset system; `contested` as an attribute on a row
at the verification choke point — never a fourth family, never a credit; the failure evidence
carries contested rows in their own block and the analyzer answers one typed question per row;
a confirmed dispute routes the round to the harness path `blocked_unverified` already uses (the
round refunded, the check named in the terminal decision, an issue opened by the driver's
readout); an unconfirmed one proceeds as an uncontested failure with the dispute recorded; the
readout counts contested rows per cell. No agent gains waiver authority. The evidence is the
list of correct work the framework refused: the `@/lib` alias import, #1259's dev fix refused
twice, the dead Python-AST checks on `.jsx`, #1532/#1533, #1255, and #1581.

Why both are here rather than after the window: they are substrate. Both arms of §4.3 share the
self-evaluation seam and the verification rows, so a substrate that changes after the window is
registered is the next window's, not this one's. Why they are not in the prelude: each changes
what a repair emits and how a failed row is read, and deploy A's count must be of the pre-flip
contract with the squad byte-identical. So they land with the flip, on deploy B, each with a
diagnostic that forces its mechanism (§3.4, §4.2).

---

## 3. The content

### 3.1 Preconditions — before the first code PR, and before the first diagnostic launch

| item | what | why first |
|---|---|---|
| **this plan** | merged on the owner's review, with §8's rulings recorded in rev 2 | the criteria do not move after the first diagnostic launch |
| **#1603** | merged as-is — the #970 fill branch targets the failing shells **plus** the failed task's own expected artifacts that a failing case names; wiring test at `run_correction_protocol` | the tag carried zero drift from F by holding it; it is the path the ninth diagnostic exercises, so it must be on deploy A |
| **the #1598 ruling** | option 1 (the seeded conftest carries an autouse fixture calling `reset()`) or option 2 (the qa proposal template states the fact); the plan hint's second half dropped either way | it moves a committed scaffold golden, which lands before the checkpoint or not at all |
| **the ninth diagnostic, registered** | `1-8-1-diagnostic-own-frame-then-prose-repair-nextjs`: the 1.8.0 config with `build_profile` / `development_profile: nextjs_ts`, the same two faults; its `loaded_checks` assert the fill path and #1603's target on the image; **the fault is verified to land where the record can count it** — `_qa_suite_own_frame_failure` swaps a JS import or injects an own-frame call (`fault_injection.py:188`), and on a scaffolded Next.js suite that must reach a shell fill or the free suite, both targets since #1603 | the qa × Next.js cell has no other supply that reached a retest on F; a diagnostic registered after the first launch is a §39.8 violation |
| **#1600** | the driver reads `analyzer_claim_refuted task=… paths=…` into `loop_texture.analyzer_claims_refuted`; `inherited` is a marker **and** no refutation for that task's round; a marker quoted after the refutation fired is `refuted_verbatim`, reported beside, never counted; A1 reads YES when a decision was reached, the refutation fired and no decision inherited | reporting-only, the driver's, not a deploy; the F record spent a diagnostic's second run on this reading |
| **the driver's arm axis** | a set config gains `arm:` — squad profile × request profile × model, per §4.4 — and a pre-registration gains a comparison section; a preflight that asserts both arms' effective grants, per-task-type caps and reasoning levels equal and refuses to run if they differ; the pairing by registration order; the void rule reading pre-run identity only | the window's registration needs it before any roll of either arm is observed; the driver's, not a deploy |
| **the reader** (§3.6) | merged before deploy A | it is how deploy A's records show their assessment |

### 3.2 The prelude — deploy A, behind the nine diagnostics and a counted set

Everything on deploy A is either a fix the F set filed or a cleanup with the squad's behaviour
byte-identical, so that A's count is of the pre-flip contract and a red belongs to a fix.

| step | item | what lands | proof |
|---|---|---|---|
| 1 | **#1603** | as above | its own wiring test; the ninth diagnostic live |
| 2 | **#1598** | the ruling's option; the plan-authoring hint corrected in `plan_authoring_rules` and the appendix asset; the scaffold golden moved with every moved line explained | the golden's diff named pin by pin; roll 6's suite as a fixture passes on the seeded conftest |
| 3 | **#1539** | `_is_test_file` matches a root-level `__tests__/` directory on Next.js — the stack's own rule, not a shared-file special case | the two paths in the issue as the test; the qa source set of a stored Next.js emission unchanged except the helper |
| 4 | **the declared role map** (SIP-0108 §10i item 1) | every squad profile declares role → agent; the schema requires it; `resolve_agent_config`'s fallback to `ResolvedAgentConfig(role, None, {})` is **deleted** — an unmatched role is a configuration error at load, not a queue at dispatch (the owner's 2026-09-14 ruling: require, don't default) | every profile in `config/squad-profiles.yaml` declares the identity map it has today; a profile missing a role the request profile's plan names is refused at cycle creation with the role named; a wiring test enters at the executor's dispatch |
| 5 | **correction steps declared by the request profile** (§10i item 3) | `validated-fullstack` and every profile that runs correction declares `correction_steps: [analyze, decide, repair]`; the runner reads the declaration; the step table in code goes; the no-decide rule — deterministic `patch`, termination by budget, the deadlock rule (#1221), and #1521's repeated-signature rule with its second conjunct dropped where no decision exists — exists as a rule but is exercised by no profile on deploy A | the 1.8.0 records' correction goldens byte-identical; a profile declaring no steps and running a failure is refused at creation, not at the first round |
| 6 | **a process serves the roles its profile assigns** (§10i item 2) | `_resolve_role` (`entrypoint.py:917`) accepts the roster's list of roles for the agent id; the handler registry already holds several roles' handlers | every deployed agent still serves one role; a wiring test proves a two-role registration dispatches both |
| 7 | **#1526** | inert detection reads the perspective cycle's own series window, not the project's newest 50 | the benchmark's re-grade of 1.6.3 rows gains an `inert` reading where it was empty; the 1.7.5 rows unchanged |
| 8 | **the reader** (§3.6) | | |

**Deploy A's readings** (§4.1): the nine diagnostics as the shakeout, then the counted set, with
N re-fixed in 1.8.1's pre-registration before the first diagnostic launch. A red on A is a
fix's or a cleanup's; the cleanups' proofs are byte-identical goldens, so a red there is a
wiring defect the goldens did not reach, and the plan says so rather than blaming a fix.

### 3.3 The flip — deploy B, SIP-0107 §38 step 7

**Precondition:** deploy A's N read as met — at least N successful scoped transactions with at
least one in each required cell — in the 1.8.1 pre-registration's own count. Not before. If the
count is unmet the flip PR is not merged, 1.8.1 ships without it, the record states the
shortfall as a budget failure (§39.8's own words), and SIP-0107 stays `accepted` with step 7
open. Nothing else in this plan waits on it.

**What lands**, one PR: §9.4's authority requirement; the §21 row — a whole-file response
without fallback authority is refused with a typed policy outcome; §39.5's sentence; the
all-attempt integrity reading's "whole-file fallback without fallback authority" moves from a
reported count per cell to a violation (§46a item 4); the driver's readout gains the refusal
count per cell beside the forms. The fallback authority itself is unchanged from §9.4: a
plan-bound grant, never automatic.

**Proof, in three parts, stated before the deploy:**

1. **The historical corpus, replayed.** The whole-file repairs the SIP was written from — the
   1.6.5 roll 6 handler repair (§31), 1.7.5 React roll 3's re-emitted suites (#1501's eight
   stored `test_report.md` versions and their repairs), the 1.7.2 roll 1 unrequested file
   (§32) — replayed through the refusal from the vault, **naming each repair it would have
   turned away and with what reason.** This is a replay of the function on stored emissions
   (`feedback: replay verification`), and is named as one.
2. **The §30.2 fixtures in CI** — each refused with its typed reason on the normal path (§39.1).
3. **One checkpoint pair on deploy B** (§4.2) with the prediction **zero refusals, every repair's
   form unchanged from F's distribution** (anchored edits, prose-only refunded, new files, fill).
   A refusal on the pair is a finding: it names a repair the pre-flip contract would have
   accepted, and the record reads its round.

**What the flip does not claim:** an improvement on this deploy. The window's recorded
unauthorized whole-file count is zero (§1), so the replay §46a item 5 describes — "the pre-flip
window's recorded unauthorized whole-file responses replayed through the refusal" — has an
empty input, and the plan says so instead of running an empty replay and calling it proof.

### 3.4 The capability tranche — deploy B, with the flip

One PR per numbered item of each amendment where an item stands alone; the SIP section amended
"as built" in the PR that builds it, not after.

| amendment | PRs | diagnostic (§4.2) | prediction |
|---|---|---|---|
| **SIP-0086 §12a** | (1) `max_self_eval_passes` required on every request profile, each pass in the ledger under its own key; (2) every error — `tsc --noEmit --pretty false` beside `frontend_compiles` on the TypeScript stacks, every failing row on Python, the evidence limit raised, the failure evidence carrying the same list; (3) the pass sees what it edits, edit-fence form, revision form recorded; (4) one evaluation per pass on the verifier's tree, `_attach_typed_checks` folded in | **`compile-loop`** — a dev emission on `nextjs_ts` with **two** planted type errors in one file, the probe's shape, `FIRST_ATTEMPT` scope | both errors fixed **inside the task** by the passes, zero correction rounds, each pass's cost in the ledger under its key; falsified by a correction round opened on the second error |
| **SIP-0096 §17a** | (1) the typed `disputed_checks` output through the prompt-asset system and the extractor; (2) `contested` on the row at the choke point, `unmatched_dispute` recorded; (3) the contested block in the failure evidence and the analyzer's `dispute_confirmed`; (4) the harness route — refund, the check named in the terminal decision, the driver's readout opens the issue; (5) the readout's counts per cell | **`false-criterion`** — a typed criterion planted on the plan's qa row that the manifest contradicts (the #1581 shape: the app is right, the check is wrong), so the dev's correct refusal is a dispute | the dev emits a dispute naming the check; the row reads `contested`; the analyzer confirms; the round is **refunded** and the check named in the terminal decision; falsified by a refunded round with no dispute (the #1053 coincidence) or a dispute the framework never read |

**The Solo asymmetry, for §17a.** Solo has no analyzer to confirm a dispute (§10i item 3). In
the Solo arm a dispute is recorded, unconfirmed, and read as nothing — the round proceeds as an
uncontested failure — and the readout counts it. That is the same treatment §10i gives the
#1054 and #1582 branches: part of what the arm measures, stated in the window's
pre-registration. Han does not confirm his own dispute; no agent gains waiver authority (§8
decision 5).

**Why the three share a deploy.** The flip is predicted silent (§2.1); §12a's passes and §17a's
disputes each carry a typed record (a ledger key, a row attribute); so a red on B is attributed
from its records, not inferred — the standard every 1.8.0 finding met. If a red on B cannot be
attributed to one of the three from its record, the deploy is split and the plan revised in the
open.

### 3.5 Solo — declarations and one container, on deploy B′

Deploy B′ is deploy B plus Han's container and two profile files. **Zero drift under `src/` and
`adapters/` from B**, named in the window's pre-registration; the squad's images are B's, so the
squad arm on B′ is the squad on B by construction. The §10i rule is the stop condition: if
building any item below needs a branch on a squad or profile name under `src/` or `adapters/`,
the design is wrong and the work stops for a plan revision.

| item (§10i) | what lands | where |
|---|---|---|
| 4 — the generalist prompt asset | one system prompt for the `generalist` role through PromptService and `docs/PROMPT_AUTHORING_STANDARD.md`; the task-type fragments the squad's roles share are Han's too, because they are the substrate's, not a role's | `src/squadops/prompts/` |
| 4 — Han's image and compose service | the agent image built by `build_agent.py generalist`; **the compose service block is the owner's edit** by the docker rule — the PR carries the block in its body, the owner applies it | `docker-compose.yml` (owner) |
| the `solo` squad profile | one member, `agent_id: han`, role `generalist`, model `qwen3.8:27b`, the qa cap override (`max_completion_tokens: 12288`) reproduced as the generalist's, the role map every role → `han` | `config/squad-profiles.yaml` |
| the `validated-fullstack-solo` request profile | `validated-fullstack`'s constants verbatim (budgets, required checks, time budget, self-eval depth), `correction_steps: [repair]`, the task plan unchanged — steps still bind roles, and the role map routes every role to Han | `src/squadops/contracts/cycle_request_profiles/profiles/` |
| 5 — the decision section optional | `request.cycle_repair_task` renders the deterministic fact — the rule chose `patch` — where the decision would be | a prompt-asset change |
| 6 — the per-roll preflight | the driver asserts, per Solo roll, that no framing document, no failure analysis and no correction decision was stored for the run — "Han never saw it" as a fact the record proves | the driver |

**Han's shakeout pair** — two Solo React rolls on B′ — proves the multi-role process, the role
map and the correction variant on the deploy (§10h: the topology window's one use). A seam not
reached stops the window for a plan revision. Then the window (§4.3).

**Teardown.** When the window closes, one PR removes the `solo` squad profile, the solo request
profile, the generalist prompt asset and Han's service **unless the owner decides a solo mode
stays as a product capability** — a decision asked at the window's close, not assumed either
way. Items 1–3 of §3.2 stay: each is a general capability.

### 3.6 The reader — `cycles assess`

The evidence gate at the 1.8.0 cut was read by recomputing the assessment from the registry and
the vault; nothing printed it. One route on the authenticated lane, under the cycles resource
as it is registered today — `GET /api/v1/projects/{project_id}/cycles/{cycle_id}/assessment`,
per `docs/architecture/api-route-lanes.md` — returning
the assessment with its projection and registry versions and its evidence identity, computed
by `adapters/cycles/cycle_evidence.assess_cycle` — and one CLI command,
`squadops cycles assess <project> <cycle-id>`, rendering the four dimensions with each
indicator's state and evidence reference, with `--json`. The driver's per-roll record renders
the same. Read-only; no cycle-path behaviour; a wiring failure is a 404 or 500 on the first call
after deploy A, which the diagnostics' records read. It is not droppable: the evidence gate's
"carries" is met by a thing a person can look at.

### 3.7 The hardening list — CI-verified, in neither deploy's cycle path

| step | item | what lands | in the image? |
|---|---|---|---|
| 1 | **#1448** (third plan) | the routes read their ports through `Depends` from `request.app.state`; the module-level globals and their setters retired under the mirror rule | runtime-api's request path, not the cycle path; a wiring failure is a 500 on the first `cycles create`, which the pair reads |
| 2 | **#1039** (sixth plan) | the docs site's design pass — diagrams and the screenshots the packages now ship | no — docs only |

Two items; the windows take the capacity the 1.7 lines gave to their lists.

### 3.8 The ops rider — after the window, never between

Carried verbatim from the 1.8.0 plan §3.7, which the cut skipped: **#1177** (the Atlas replay
scripts routed through `arm.sh`), **#176 recipe 2** (one `smoke`-squad launch; the issue
closes), **#1176** (the cheap gate first — whether the served chat template accepts prior-turn
thinking), **#1408** and **#1412** (the Flash-Next plan-authoring replay; the Atlas content-loop
diagnosis — the box to themselves; nothing to the vendor without the owner's go-ahead). Each on
the idle box after the window closes; nothing lands in the framework from them in this release.

### 3.9 The count this release owes the record

| item | release plans that scheduled it | times, incl. this plan |
|---|---|---|
| #176 | 1.7.0, 1.7.3, 1.7.4, 1.7.5, 1.8.0, 1.8.1 | **6** — recipe 2 closes on the idle box (§3.8) |
| #1039 | 1.7.0 §3.1, 1.7.3, 1.7.4, 1.7.5, 1.8.0, 1.8.1 | **6** — docs only; last in the drop order |
| #1176, #1408, #1412, #1177 | 1.7.5 (as the idle-box rider), 1.8.0, 1.8.1 | **3** each — sequenced after the window twice and skipped once |
| #1448 | 1.7.5, 1.8.0, 1.8.1 | **3** |
| #1469 | 1.8.0, 1.8.1 | **2** — read at the cut, not closed by it |
| #1526, #1539, #1581 | 1.8.1 | **1** each |
| #1598, #1600, #1602 | 1.8.1 | **1** each — filed by the line that hands them here |

The five idle-box items are on their third plan because the box has gone from the last counted
roll to the cut twice; §7 places them after the window and before the cut this time, so the
cut waits for them or the plan says why it did not.

### 3.10 The cut criterion — three gates

| gate | criterion |
|---|---|
| **implementation** | §3.1 every row; §3.2 steps 1–8 merged and read on A; the flip merged **iff** A's N read as met; §3.4 both amendments merged with their SIP sections amended as built; §3.5 every item merged, Han's service applied by the owner; the driver's arm axis and comparison section merged; the teardown PR merged or the owner's decision to keep a solo mode recorded; §3.7 merged or dropped by a plan revision naming the destination |
| **experimental** | **L1 holds** on every counted roll; **N met on deploy A** in the 1.8.1 pre-registration's count, all-attempt integrity holding on every attempted transaction (with unauthorized whole-file responses a reported count until the flip); **the flip's pair reads zero refusals** and the historical replay names each turned-away repair; **the compile-loop and false-criterion predictions hold**; **Han's pair reaches its seams**; **the window closes with its result stated against the registered decision rule**, whichever way it goes; every registered diagnostic reaches its seam on the pinned deploy within its two-run budget; a falsified prediction or an unreached seam stops the set and the plan is revised in the open |
| **evidence** | every counted record of every set carries a `CycleAssessment` **rendered by the reader**, every dimension citing evidence that resolves; the Solo preflight's three absences on every Solo roll; SIP-0108 §5 criterion 6's integrity check on every pair; the record reconstructs every counted / void / shakeout boundary from per-round evidence; deploy-to-tag drift named item by item, expected zero under `src/` and `adapters/` from B′; the package captured with its screenshots — the showcase is **one pair**: a squad roll and its Solo partner, the delivered app of each and the flow-run timeline where the correction variant is legible, chosen and explained per rule 3 |

**The SIP sweep at the cut, stated now so the sweep does not read silence as shipped.**
**SIP-0107** → `implemented` if the flip landed and §39.1–§39.8 hold on this line's records
(§39.1 on the replay and the fixtures; §39.2–§39.7 on A's and B's transactions; §39.8 on A's
count); if A's N was unmet, `accepted` with step 7 named open and the shortfall stated — the
SIP's own rule, not a plan's. **SIP-0108** → `implemented` if §5's seven criteria hold — 1–5 on
1.8.0's record, 6–7 on this window with the Solo arm; the window's *result* does not gate it,
its closure does; §10h's placement axis, its cost accounting and §10j's Free-Solo window are a
successor's criteria and are named as such, not as open children. **SIP-0086** and **SIP-0096**
stay `implemented`, §12a and §17a amended as built in their PRs. **SIP-0102** step 5 stays open
and named: `verified_executable` and `verified_functional` read unaskable on every cycle until it
lands. Nothing else moves; §6 names what stays.

### 3.11 Merge discipline

One PR per row; `gh pr view` before every push; every job of main's run read after every merge;
the seam table in every PR that binds, removes or re-weights a check (§17a's `contested`
attribute, §12a's `tsc` row); the mirror rule on every removal (the role fallback, the
correction step table, #1448's globals); the characterization tests in the same PR as the seam
they characterise; **§5a amendments in the SIP, in the PR that diverges**; **no merge to main
while any of the three windows is open** (A's set, B's pair and diagnostics, B′'s pair and
window); a committed golden moves only when every moved line is explained in the PR (the
owner's ruling of 2026-09-13; #1598 moves one); **`docker-compose.yml` is the owner's edit** —
Han's service block travels in a PR body; drivers launch detached from their own worktree; the
main checkout is not touched while a driver runs.

---

## 4. The verification sets — three, on two deploys

Same driver, the 1.8.0 set configs re-registered under a `1-8-1-` prefix in
`docs/plans/verification-sets/`, one pre-registration per window committed before that window's
first launch, the pins from the deploy it runs on; if the deploy moves after a pre-registration
is committed, that commit is void and re-made, and no transaction or roll from the superseded
deploy counts. The gate constant inherited verbatim.

### 4.1 Deploy A — the flip's precondition

**The nine diagnostics** — the eight of 1.8.0 §3d plus `own-frame-then-prose-repair-nextjs` —
as the deploy's shakeout, two-run budget each, recorded with the entry point each used; then
**the counted set: four React, two Next.js.** Four React rather than three because on F the
qa × React cell was supplied by counted rolls alone (rolls 3 and 5) — the own-frame diagnostic's
expected qa transaction did not materialize, both of its repairs reading prose-only — and two of
six rolls carried a qa round.

**N, re-fixed in 1.8.1's pre-registration before the first diagnostic launch, with the supply
tabled per cell and F's readings as the calibration:**

| cell | supply | F read | expected here |
|---|---|---|---|
| dev × React | `dev-lane-fastapi-react`; a counted round | 2 (one from the dev-lane diagnostic, one from the false-claim diagnostic's second run) | 1–2 |
| dev × Next.js | `dev-lane-nextjs` | 1 | 1–2 |
| qa × React | `own-frame-then-prose-repair`; the counted rolls | 2, both from counted rolls | 1–3 |
| qa × Next.js | **`own-frame-then-prose-repair-nextjs`** in fill mode, counted under §3c's rule 1 (the fill-merge evidence); a counted Next.js qa round, now that #1603 targets the free suite too | **0** — no supply reached a retest | 1–2 |
| builder × React | `contentless-builder-all-attempts` | 0 — the one builder edit read exceeded the 50 % ceiling | 0–1, declared, not required |
| builder × Next.js | — | unaskable | unaskable, as before |

Expected 4–9 against **N = 6 with at least one per required cell** — the number 1.8.0 fixed,
kept deliberately: lowering N after a miss would be choosing it with the evidence in hand,
which the 1.8.0 plan §8 decision 11 forbade. The three counting rules of 1.8.0 §3c carry
verbatim (fill counts on its merge evidence; more than half the file replaced is a scoped rewrite
and does not count; every transaction read against its round's revision-form row). The expected
range's low end misses N, and the plan says what that means (§3.3): no flip in 1.8.1.

**Bar and texture:** L1; all-attempt integrity; the #598 prediction re-read (unaskable on every F
roll — the pre-registration says whether any counted roll here can evaluate `container_packaging`
and, if none can, drops the prediction with the reason); the assessment rendered on every record;
every field three-state.

### 4.2 Deploy B — the flip and the capability tranche

**The checkpoint pair** (one React, one Next.js) with the flip's prediction — zero refusals, the
form distribution F's — and **two new diagnostics**, `compile-loop` and `false-criterion`
(§3.4), two-run budget each. The shakeout loop's exit rule applies: a pair and the two
diagnostics with no new seam finding; budget **three rounds**, the record reporting how many it
took. The flip's historical replay runs offline before B is built and is committed with B's
pre-registration as the flip's first proof.

### 4.3 Deploy B′ — Han's pair, then the window

**Han's shakeout pair** — two Solo React rolls — reading: every task type dispatched to `han`
and consumed; the role map resolved with no fallback; correction on a failure taking the
`repair` step alone with the deterministic `patch`; the Solo preflight's three absences; the
assessment rendered. A seam not reached within two runs stops the window.

**The window**, registered in the pre-registration **before any roll of either arm is
observed**, per SIP-0108 §4.4 and the 1.8.0 plan §4.2 (kept as the design 1.8.1 registers
from):

| | fixed at registration |
|---|---|
| **arms** | squad = `full-38` × `validated-fullstack`; Solo = `solo` × `validated-fullstack-solo`; both `qwen3.8:27b` on the same Ollama configuration and box |
| **pairs** | N = 6, React only (§4.4); pair *k* = the squad arm's *k*-th registered roll and Solo's *k*-th; a **fresh** squad arm — no 1.8.0 roll is reused (§10g) |
| **substrate held equal, asserted by the driver's preflight** | the PRD, the request-profile constants, the framework deploy; per-task-type caps and reasoning levels equal; each task's effective write grant equal — the comparison refuses to run if any differs |
| **inclusion** | pre-run identity and infrastructure validity only; a void removes its pair; nothing leaves on outcome |
| **the decision rule** | **a count over pairs**, declared here and not read afterwards, on three dimensions of the assessment: **outcome** (accepted-functional per arm, per pair), **quality** (the retest and the boot audit — the clean-room indicators stay unaskable until SIP-0102 step 5), **efficiency** (tokens and wall clock per pair; a cost delta is a result, not a tie-breaker); the exact predicate — how many of six pairs the squad must win on outcome for the answer to read "the squad improves outcome" — is fixed in the pre-registration, and the plan does not pre-empt it beyond: no rate at N = 6, no composite, no grade band (SIP-0108 §3.2) |
| **the asymmetries, named** | in Solo the #1054 dispute and #1582 unanimity branches do not run (no analyzer, no lead); a §17a dispute is unconfirmed and read as nothing; the repair brief carries the failing cases, the failed rows, the contract expectations and the files, with no analysis summary — each is part of what the arm measures |
| **order** | the squad arm first, then Solo, on the same frozen deploy; the record names drift if any |

**Early stop, one direction, for every window:** a falsified prediction or an unreached seam
stops the set; a good result never stops it early; a stop in one arm does not stop the other.
**The result is stated whichever way it goes.** A squad that does not improve outcome over Han
at measured cost is a result; it is 2.0's problem and the thesis's, not this cut's.

**Drift the record must declare:** intended zero under `src/` and `adapters/` between B and B′
and between B′ and the tag — the tag is the measured deploy plus the pre-registrations, the
records, the teardown and the package.

---

## 5. Capacity — what drops first, and what cannot

**Cycles:** deploy A, nine diagnostics plus six counted, with the two-run budgets, fifteen to
twenty-two; deploy B, two plus two, with budgets, four to eight, plus up to two more shakeout
rounds; deploy B′, Han's pair plus twelve, fourteen to sixteen. **Thirty-three to forty-six
cycles**, against the 1.8.0 line's forty across E and F — three to four nights on the box if no
shakeout round finds a seam, and the F set says one will. **PRs:** the preconditions five, the
prelude eight, the flip one, §12a four, §17a five, Solo five plus the owner's compose edit, the
reader one, the hardening two, the teardown one — **thirty-two**, against the seventy-eight the 1.8.0
line merged between its plan and its package.

**If capacity forces a drop**, in this order, each to **1.8.2** by a plan revision in the open
— and for anything that touches a window's substrate, **before that window's pre-registration is
committed**: the hardening list in reverse (#1039, #1448) → the ops rider, item by item → **§17a**
→ **§12a** (both to 1.8.2 as its content, because a substrate change after the window is the next
window's) → #1526 → #1539. **Non-droppable:** #1603, the ninth diagnostic and deploy A's
pre-registration (the flip's precondition), the reader (the evidence gate), Solo's six items and
the window (SIP-0108's criteria 6–7 and the line's reason), the teardown decision. **The flip is
not droppable by capacity; it is conditional on N**, and only the count decides it.

---

## 6. Re-placements by name — nothing silently carried

Twenty-seven open issues. **Fourteen are in this release:** #1602 (by #1603), #1600, #1598,
#1539, #1526, #1581 (closes with §17a — its routing half was #1582), #1448, #1039, #1177, #176,
#1176, #1408, #1412, and #1469 — which stays open by design and is read at the cut against the
`frontend_build` corpus, as 1.8.0 read it. Of the fourteen, **nine close by the cut** by code or
on the box; #1176, #1408 and #1412 close with an answer if the answer is terminal; #1469 stays.
The thirteen that are not in the release:

**#1507, #567, #353, #1031 — 1.9, unchanged** from the 1.8.0 plan §6 and the ROADMAP's 1.9 row.
The completion boundary is 2.0's entry condition; the parser, the stamped hash and the primer
move behaviour beside a measured window here as they did beside a headline there.

**#1522 — 1.9 by decision.** Banking a repair whose retest reduces failures but does not pass
changes what an accepted patch *means*; that is verdict semantics, and the 2026-08-15 ruling
keeps verdict-semantics changes out of a measured window. It is legitimate, it is adjacent to
§17a, and it is not this line's. Re-placed with the reason so the 1.9 plan names it.

**#316 — 2.0, with Campaign.** **#949, #950, #194, #557 — at design review, unchanged.**
**#1122 — not scheduled**, as in 1.8.0. **#1469 — open by design**, above.

**The SIP re-read**, so the sweep at the cut does not read silence as shipped:

| SIP | state on main | this release |
|---|---|---|
| SIP-0107 | `accepted`; steps 1–6 shipped, §46a–§46p; step 7 open | **step 7 lands on N** (§3.3); `implemented` if §39 holds, else `accepted` with the shortfall |
| SIP-0108 | `accepted`; (a)–(c) shipped, §10a–§10j; (d) and §5 criteria 6–7 open | **(d) lands** (§3.5, §4.3); `implemented` if §5 holds; the successor's criteria named |
| SIP-0086 | `implemented`; §12a proposed, not built | **§12a built** (§3.4), amended as built |
| SIP-0096 | `implemented`; §17a proposed, not built | **§17a built** (§3.4), amended as built |
| SIP-0102 | steps 3–7 open; step 5 named absent by SIP-0108 | stays `accepted`; step 5 named again at the cut |
| SIP-0104, SIP-0105 | as at 1.8.0 | unchanged |
| SIP-0088, SIP-0090, SIP-0091 | as at 1.8.0; the Embodiment Runtime SIP still to be drafted | unchanged here; **Embodiment is the third aim** (§10h) and its SIP is drafted with the 1.9 and 2.0 plans, not this one |
| SIP-0092, SIP-0093, SIP-0101 | as at 1.8.0 | unchanged |

**Held, by name:** the group_run successor PRD and the Free-Solo window (§2.2) — the owner's
ruling of 2026-09-17; lifted together when the owner says so.

---

## 7. Sequencing

1. **This plan**, on its own PR, with the 1.8.0 plan §10 amendment pointing here. Merges on the
   owner's review, with §8's rulings recorded in rev 2.
2. **#1603** merged — the line's first merge. **The #1598 ruling.** **The ninth diagnostic
   registered**, its fault verified to land where the record can count it.
3. **The driver** — #1600, the arm axis and the comparison section, the Solo preflight — and
   **the reader** (§3.6). The driver's changes are not a deploy; the reader is.
4. **The prelude** (§3.2), one PR each in order — #1598 and #1539 first, the three Solo cleanups
   (steps 4–6) with their byte-identical proofs, #1526, the reader last.
5. **Deploy A. The 1.8.1 pre-registration** — N re-fixed with its supply tabled, the pins from
   the deploy, every field's producer and unaskable state — committed **before the first
   diagnostic launch.** Then the nine diagnostics, then the counted set of four and two. A seam
   not reached stops the line here. **N read.**
6. **The flip PR** — merged iff N was met — **and the capability tranche** (§3.4), one PR per
   item, each SIP section amended as built. The flip's historical replay committed before B.
7. **Deploy B; B's pre-registration; the checkpoint pair and the two diagnostics**, the shakeout
   loop to its exit rule, budget three rounds. A red is attributed from the flip's refusal
   record, the ledger's pass keys or the row's `contested` attribute — or the deploy is split.
8. **Solo's declarations and Han** (§3.5): the prompt asset, the two profiles, the image; the
   compose block to the owner. **Deploy B′**, zero drift from B under `src/` and `adapters/`.
9. **The window's pre-registration** — the arms, the pairs, the substrate assertions, the
   decision rule — committed before any roll; **Han's shakeout pair**; then **the squad arm,
   six React rolls; then Solo, six.** No merge to main while it is open.
10. **Close the window; the result stated against the rule.** **The ops rider** on the idle box
    (§3.8) — after, never between.
11. **The teardown PR**, or the owner's decision that a solo mode stays, recorded.
12. **The preliminary measurement conclusion**: §3.10's three gates read against the frozen
    deploy before anything else moves; the SIP sweep decided on that reading.
13. **Final record; cut 1.8.1 by the seven steps** — re-authenticate immediately before the
    capture, the preview read before `--write`, the screenshots of one pair, zero drift named.
    **Then the 1.9 plan** — the executor's completion boundary (#1507), the debts re-placed by
    name (#567, #353, #1031, #1522), the close of the 1.x line — so that 2.0 can open on
    Campaign with the number this window produced.

The key property of this order: N is re-fixed before any transaction that could count toward
it is observed, and the flip lands only after that reading; the substrate both arms share is
fixed before the window is registered, and the window is registered before either arm is
observed; the three deploys each carry one kind of change, and B′ differs from B by nothing
under `src/` or `adapters/`.

---

## 8. Decisions made by recommendation — the owner overrules, not fills in

1. **The flip's N is re-supplied on deploy A under a fresh pre-registration; F's five
   transactions do not carry; N stays 6.** §39.8's rule, applied as written — and lowering N
   after a miss would choose it with the evidence in hand. If A's count is unmet, 1.8.1 ships
   without the flip, SIP-0107 stays `accepted` with step 7 open, and nothing else waits.
2. **The flip's proof is the historical replay, the fixtures and a silent pair — not the
   window's count, which is zero.** Stated in §2.1 and §3.3 so the flip never reads as a
   measured improvement.
3. **§12a and §17a land on deploy B with the flip, each with a diagnostic, and are the first
   substantive items to move to 1.8.2 if capacity forces it** — before the window's
   pre-registration, never after it.
4. **Solo's three general items land in the prelude with byte-identical squad behaviour; the
   arm's declarations and Han land on B′ with zero code drift from B.** The §10i rule is the stop
   condition. The `resolve_agent_config` fallback is deleted, not deprecated (the 2026-09-14
   ruling).
5. **In Solo a §17a dispute is recorded, unconfirmed, and read as nothing.** Han does not
   confirm his own dispute; no agent gains waiver authority. Named in the window's
   pre-registration as an asymmetry the arm measures.
6. **The window is React only at N = 6 pairs, a fresh squad arm, the decision rule a count over
   pairs on outcome, quality and efficiency** — SIP-0108 §4.4 and the 1.8.0 plan §4.2 as
   written; the exact predicate is the pre-registration's, and no rate, composite or grade band
   is read at N = 6.
7. **The reader is one route on the `/api/v1` lane and one CLI command, read-only, in the
   prelude** — not a console page (SIP-0069's, later), not a recommendation, no agent in the
   path (the 1.8.0 plan §8 decision 4, unchanged).
8. **Tokens per provider on the run summary, the placement axis beyond the model, and
   Free-Solo are not built here.** The Solo window runs one provider and one model on both arms
   and needs none of them; §10j names them a successor's. Building them beside this window
   would be capacity spent on a question this window does not ask.
9. **The teardown is asked, not assumed.** At the window's close the owner decides whether a
   solo mode stays as a product capability; the plan carries both outcomes (§3.5).
10. **#1522 goes to 1.9 by decision** — a verdict-semantics change beside a measured window
    (§6). **#1507, #567, #353, #1031 stay 1.9's**; #316 2.0's; the design-review items
    unchanged.
11. **The ops rider is sequenced before the cut, not after it** (§7 step 10) — its five items
    are on their third plan because the cut has come first twice.
12. **#1598 — option 1 recommended** (the seeded conftest carries the autouse reset; isolation
    becomes a harness guarantee), the plan hint's second half dropped either way. The owner
    rules; the prelude waits on it.
13. **Han's compose service is the owner's edit.** The PR carries the block; the plan does not
    touch `docker-compose.yml`.

---

## 9. What this plan does not decide

- **The #1598 ruling** — option 1 or 2; §8 decision 12 recommends 1.
- **The window's exact decision predicate** — the pre-registration's, committed before any roll
  (§4.3); the plan fixes only its shape.
- **Whether a solo mode stays** — the owner's, at the window's close (§3.5, §8 decision 9).
- **The `compile-loop` and `false-criterion` faults' exact shapes** — B's pre-registration's,
  with the mechanism each must force stated here (§3.4).
- **Whether the flip lands** — deploy A's count decides it, not this plan (§3.3).
- **The Free-Solo window's timing and the successor PRD** — held by the owner (§2.2, §6).
- **The Embodiment Runtime SIP** — drafted with the 1.9 and 2.0 plans; the third aim is named
  here and built nowhere in this line.

---

## 10. Revision history

- **Rev 1 (2026-09-17)** — written the evening v1.8.0 was tagged, on the owner's ask, from the
  1.8.0 plan (rev 11), the 1.8.0 pre-registration §10c, SIP-0107 §38/§39/§46a, SIP-0108
  §4.4/§5/§10g–§10j, SIP-0086 §12a, SIP-0096 §17a, all fifty-two 1.8.0 records and the tracker
  (27 open issues, every one placed). Structure: the flip's precondition re-supplied on deploy A
  behind nine diagnostics and a 4 + 2 counted set; the flip and the two capability amendments on
  deploy B behind a pair and two new diagnostics; Solo as declarations and one container on B′
  behind Han's pair, then the window at N = 6 pairs. Three facts stated up front: N unmet on
  1.8.0's record, zero whole-file responses on the whole line, Solo's §10i rule. Thirteen
  decisions by recommendation.
