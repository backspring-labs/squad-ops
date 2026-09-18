# 1.8.1 — plan

**Revision 4, 2026-09-17.** Rev 1 was written the evening v1.8.0 was tagged; rev 2 the same
evening, on the owner's review of it: the two capability amendments re-placed to 1.8.2 (§8
decision 3), the flip's proof given its positive control and the finding behind it (§3.3), the
window executed as pairs with its void rule, its predicate and its two isolation contracts fixed
here rather than left to the pre-registration (§4.3, §8), the hardening list moved out, the ops
rider bounded, and one miscount corrected (§6: twenty-six open issues, not twenty-seven, and #414
placed); **rev 3 on the owner's ruling that #1448 goes to 1.9**, with the registry's surface
measured and the auth-boundary finding that sharpens it (§3.7, §8 decision 13) — the last open
question rev 2's §9 carried; **rev 4 on the owner's ruling of §8 decision 11 and the word to
merge** — every decision in §8 is now ruled or confirmed, and the plan enters execution.
Written from: the 1.8.0 plan (`docs/plans/1-8-0-plan.md`, rev 11) §3.3 step 7, §3.4 (d),
§4.2, §6, §7 step 14 and §8 decisions 5 and 15; the 1.8.0 pre-registration
(`docs/plans/1-8-0-verification-set-preregistration.md`) §3c, §3f and §10c — the deploy-F set, the
§3c count, the owner's ruling and the evidence gate; SIP-0107 §38 step 7, §39 and §46a; SIP-0108
§4.4, §5 and §10g–§10j; SIP-0086 §12a and SIP-0096 §17a; every 1.8.0 record under
`var/verification_sets/1-8-0-*` (fifty-two record files — every shakeout from deploy B on, the E
set and the F set); and the tracker on the day of writing — twenty-six open issues, every one
placed by name (§6).

**1.8.1 is a patch that carries a measurement window** — the 1.6.3 precedent, which the 1.8.0
plan §3.9 named so the sweep would not read this line as a fix line. It does two things, and
everything in it serves one of the two: **deploy A answers whether the flip was earned; deploy
B proves the contract; deploy B′ produces the first Squad-versus-Solo number.** The flip is
SIP-0107 §38 step 7, ruled 1.8.1's on 2026-09-13; the window is SIP-0108 (d), ruled 1.8.1's on
2026-09-14 with its arms named on 2026-09-17. Beside them, only what those two need: the fixes
the F set filed, the diagnostic the F set was missing, and a reader for the assessment the
evidence gate could only recompute. Its cut promotes both 1.8 headline SIPs to `implemented` if
their own criteria hold on this line's records, and says which did not if not.

Three facts shape it, stated once:

1. **The flip's precondition is not met on 1.8.0's record.** SIP-0107 §39.8 read **N = 5 of 6
   with qa × Next.js empty** (pre-registration §10c.4); the cell's diagnostic supply was never
   registered. The owner closed the *line* on that reading (§10c.5). The flip's precondition is
   the SIP's, and §39.8 is explicit: fewer than N means step 7 does not happen. The five F
   transactions cannot carry into a new count — N is fixed "before any transaction that could
   count toward it is observed" — so 1.8.1 supplies N under its own pre-registration, on its own
   deploy, with the missing diagnostic registered, and the flip lands only after that reading
   (§3.2, §3.3, §4.1). If that N is unmet, 1.8.1 ships without the flip and says so. Deploy A
   decides; no one else does (§8 decision 2).
2. **Zero whole-file repair responses on the whole 1.8.0 record.** Every revision-form row across
   the fifty-two records reads anchored edits, one refused structural edit, prose-only, new
   files only, or fill — never a whole-file response, offered or unoffered (§1). The refusal the
   flip lands is therefore predicted to fire **zero times** on this deploy, this model and these
   prompts; its live effect is a contract, not a change in behaviour, and its proof is the
   historical corpus replayed plus the SIP's fixtures with a positive control, not the window's
   count (§3.3). The plan says this rather than letting the flip read as a measured improvement.
3. **Solo changes role routing and the correction path** (SIP-0108 §10g) — the reason it is here
   and not in 1.8.0 — and the §10i rule binds how: **declarations and one container, never a
   branch on a squad or profile name under `src/` or `adapters/`.** Three of its six items are
   general cleanups the platform owes regardless (the declared role map replacing a silent
   fallback; correction steps declared by the request profile; a process serving the roles its
   profile assigns). They land in the prelude with the squad's behaviour byte-identical, so the
   window's deploy differs from the flip's by one container and two profile files (§3.2, §3.5).

Rules carried from the 1.8.0 line without discount: a measured tranche and a structural tranche
do not share a deploy — **and one kind of change per measured deploy**, which rev 1 bent and rev
2 restores; no fault, no prediction; every field three-state; every diagnostic reaches its seam
on the pinned deploy; §5a amendments in the SIP, in the PR that diverges; **a counted set is a
shakeout round** — the F set's lesson, where the pairs found nothing and the set found seven.

---

## 1. What the 1.8.0 line says this release has to be

| what the line showed | evidence | what it says about this release |
|---|---|---|
| **N read 5 of 6, qa × Next.js empty**; the cell's supply — "the same diagnostic in fill mode" — was named in §3c and never registered; the one Next.js roll with a qa fill repair lost its retest to #1602 | pre-registration §10c.4; §3c's supply table | **the ninth diagnostic is registered before anything else** — `own-frame-then-prose-repair` on `nextjs_ts` in fill mode (§3.1); **N is re-fixed on 1.8.1's deploy A** in a fresh pre-registration, the flip after it (§3.2, §4.1) |
| **Next.js counted roll 1 rejected on #1602**: the #970 fill branch aimed at the shells only; the qa's free-authored suite failed the same assertion on every retest and was never a target | `cyc_bb493eb4725b`, §10c.3; PR #1603 | **#1603 is this line's first merge** — held out of the tag so the tag carried zero drift from F; it is exactly the path the ninth diagnostic exercises |
| **zero whole-file responses on any 1.8.0 record** — every repair that was offered the edit form took it (§46l–§46m); the only non-edit forms were prose-only (refunded), new-files-only and fill | the revision-form row on all fifty-two records; §3f named this count as "the count 1.8.1's replay starts from" — it is zero | **the flip's replay proof runs on the historical corpus**, the 1.6.5 and 1.7.5 whole-file repairs the SIP's §1.2 was written from, and on the §30.2 fixtures with a positive control; the checkpoint pair on the flipped deploy predicts zero refusals (§3.3) |
| **no producer of fallback authority exists on main** — the only mention of a whole-file grant region is a docstring on the revision's anchor search (`revision_transaction.py:104`); nothing issues one | a grep of `src/` and `adapters/` on 2026-09-17, not an audit — the flip PR's scoping confirms or corrects it | the flip cannot land a refusal alone: **the flip PR builds the plan-bound authority path §9.4 and §15 describe**, and the positive control is what proves it exists (§3.3, §8 decision 2) |
| **the A1 reader read NO with the mechanism firing** (#1600): a decision that quotes the injected path to refute it counts as inheriting it; the prose refutation #968 logs is never read; the second run of a two-run budget was spent on a reading | `cyc_ad721e796487`, §10c.1 | **#1600 lands before the diagnostics run** — reporting-only, the driver's; a machine join on the task id, a third state `refuted_verbatim` (§3.1) |
| **the seeded conftest provides no isolation** (#1598): roll 6's suite assumed an autouse reset the harness never had, and the plan hint said it might | `cyc_767ad2dc59d2`, E set | **option 1, ruled** (§8 decision 15): the seeded conftest owns isolation through an autouse reset; a committed scaffold golden moves with it, so it lands before deploy A's checkpoint (the #906/#1463 and #1499 lesson) |
| **the evidence gate's word "carries" was read honestly**: the assessment was recomputed read-only over the nine counted cycles (22 indicators each, 0 unresolved refs); the driver's record does not render it and no product reader prints it | §10c.6 | **a reader** — one authenticated route and one CLI command, and the driver's record renders the assessment (§3.6); "carries" becomes "shows" |
| **the compile loop is one pass on a truncated first error** and **a correct dispute is indistinguishable from an empty emission** — the two capability amendments drafted on 2026-09-15 | SIP-0086 §12a, SIP-0096 §17a; #1581 | **re-placed to 1.8.2 by the owner's ruling of 2026-09-17** (§3.4, §6, §8 decision 3): the window measures the substrate 1.8.0 measured, and a substrate that changes the same week beside the flip puts two kinds of change on one measured deploy |
| **the ops rider was skipped**: 1.8.0 §3.7's five items were sequenced "after the counted set, never between" and the box went from the last counted roll to the cut | 1.8.0 §7 step 12; the tracker (#1177, #176, #1176, #1408, #1412 open) | carried, same rule, after the window — **and bounded** so no finding becomes a cut blocker (§3.8) |
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
fail-closed rule landing after the loop already learned to behave: **a guard, proven by replay
with both controls, predicted silent live.** SIP-0107 goes to `implemented` on it — §39.1 through
§39.8 hold on the records — or stays `accepted` with the unmet criterion named.

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
as agent steps. The window compares the squad against Han at N = 6 valid pairs on React, by a
count over pairs declared here (§4.3).

**What the window isolates, so the conclusion matches the independent variable.** Solo removes
several things together — one agent instead of six, no framing roles, no role identities, no
analyzer, no lead, no handoffs, correction reduced to repair, no dispute confirmation, no
unanimity branch. §10i defines it that way on purpose. The result is therefore read as **the
squad's organization against a deliberately de-organized single-generalist execution on the same
deterministic substrate**, and never as "multiple agents are better than one agent". That
narrower causal question belongs to later arms.

What the window does **not** answer, so the cut does not claim it: the **placement thesis**
(§10h — outcome per unit of cost across edge / local / cloud placements) needs the arm axis to
carry provider, model, reasoning and cap per member, and cost as a first-class dimension; the
Solo window runs one provider and one model on both arms, so the axis beyond the model and the
tokens-per-provider accounting are **a successor's criteria** (§10j, its last paragraph), not
this line's. **Free-Solo** (§10j — the same model with a plain agentic loop and no substrate,
every arm judged from the outside by the clean-room audit and a held-out suite) is a later
window, paired with the successor PRD in the group_run line. Both are **2.0 planning inputs, not
1.x completion criteria** (§8 decision 11). The three aims stand together — the placement
thesis, Campaign (2.0), Embodiment — and this window is the first number under the first of them.

### 2.3 The capability amendments — 1.8.2's, by the owner's ruling of 2026-09-17

**SIP-0086 §12a** (the self-evaluation pass becomes the model's compile loop) and **SIP-0096
§17a** (a contested result: the producer's dispute becomes evidence) were drafted on the owner's
question of 2026-09-15, *does the framework constrain the model it runs*, and targeted for 1.8.1
the same day. Rev 1 placed them on deploy B beside the flip. The owner's review of rev 1 asked
that they move to 1.8.2, and the owner ruled it so on 2026-09-17 — a re-placement of the kind
rev 7 of the 1.8.0 plan made for the comparison window, not a reversal of the 09-15 targeting.

The reason, in the reviewer's words: a release whose central contract change is supposed to be
unusually easy to interpret should not gain two behaviour-changing mechanisms at the same point;
and the window answers a cleaner question — *what does the currently measured substrate do with
Squad versus Solo* — than *what does a newly modified substrate do immediately after two
unrelated amendments*. The window does not need either amendment to answer its stated question.

**1.8.2 is the model-capability tranche**: the two amendments, each amended as built in the PR
that builds it, each with the diagnostic that forces its mechanism. The diagnostics' shapes,
settled at this review, are handed to the 1.8.2 plan in §6 so they are not re-derived. #1581
moves with §17a.

---

## 3. The content

### 3.1 Preconditions — before the first code PR, and before the first diagnostic launch

| item | what | why first |
|---|---|---|
| **this plan** | merged on the owner's review, rev 2 carrying the rulings | the criteria do not move after the first diagnostic launch |
| **#1603** | merged as-is — the #970 fill branch targets the failing shells **plus** the failed task's own expected artifacts that a failing case names; wiring test at `run_correction_protocol` | the tag carried zero drift from F by holding it; it is the path the ninth diagnostic exercises, so it must be on deploy A |
| **the ninth diagnostic, registered** | `1-8-1-diagnostic-own-frame-then-prose-repair-nextjs`: the 1.8.0 config with `build_profile` / `development_profile: nextjs_ts`, the same two faults; its `loaded_checks` assert the fill path and #1603's target on the image; **the fault is verified to land where the record can count it** — `_qa_suite_own_frame_failure` swaps a JS import or injects an own-frame call (`fault_injection.py:188`), and on a scaffolded Next.js suite that must reach a shell fill or the free suite, both targets since #1603 | the qa × Next.js cell has no other supply that reached a retest on F; a diagnostic registered after the first launch is a §39.8 violation |
| **#1600** | the driver reads `analyzer_claim_refuted task=… paths=…` into `loop_texture.analyzer_claims_refuted`; `inherited` is a marker **and** no refutation for that task's round; a marker quoted after the refutation fired is `refuted_verbatim`, reported beside, never counted; A1 reads YES when a decision was reached, the refutation fired and no decision inherited | reporting-only, the driver's, not a deploy; the F record spent a diagnostic's second run on this reading |
| **the driver's arm axis** | a set config gains `arm:` — squad profile × request profile × model, per §4.4 — and a pre-registration gains a comparison section; a preflight that asserts both arms' effective grants, per-task-type caps and reasoning levels equal, **the run-state and topology contracts of §4.3**, and refuses to run if any differs; the pairing by registration order; **the interleaved execution order**; the void rule reading pre-run identity only; the Solo preflight's three absences | the window's registration needs it before any roll of either arm is observed; the driver's, not a deploy |
| **the reader** (§3.6) | merged before deploy A | it is how deploy A's records show their assessment |

### 3.2 The prelude — deploy A, behind the nine diagnostics and a counted set

Everything on deploy A is either a fix the F set filed or a cleanup with the squad's behaviour
byte-identical, so that A's count is of the pre-flip contract and a red belongs to a fix.

| step | item | what lands | proof |
|---|---|---|---|
| 1 | **#1603** | as above | its own wiring test; the ninth diagnostic live |
| 2 | **#1598, option 1** | the seeded conftest carries an autouse fixture calling `backend.store.reset()` before each case — isolation is a harness guarantee, not prompt knowledge; the plan-authoring hint's second half dropped in `plan_authoring_rules` and the appendix asset; the scaffold golden moved with every moved line explained | the golden's diff named pin by pin; roll 6's suite as a fixture passes on the seeded conftest |
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

### 3.3 The flip — deploy B, SIP-0107 §38 step 7, and nothing else

**Precondition:** deploy A's N read as met — at least N successful scoped transactions with at
least one in each required cell — in the 1.8.1 pre-registration's own count. Not before. If the
count is unmet the flip PR is not merged, 1.8.1 ships without it, the record states the
shortfall as a budget failure (§39.8's own words), and SIP-0107 stays `accepted` with step 7
open. **No owner discretion enters after the measurement** (§8 decision 2). Nothing else in this
plan waits on it: deploy B is then the prelude's deploy re-pinned, and the line continues to B′.

**The counting rule, explicit.** A transaction counts toward N only if it was produced on the
exact deploy the pre-registration pins. A diagnostic's second run on that deploy counts, as the
false-claim diagnostic's second run did on F. If a diagnostic finds a defect that requires a
deploy change, every transaction from the superseded deploy becomes non-counting evidence and
the pre-registration is replaced before any further eligible transaction is observed.

**What lands**, one PR: §9.4's authority requirement; the §21 row — a whole-file response
without fallback authority is refused with a typed policy outcome; §39.5's sentence; the
all-attempt integrity reading's "whole-file fallback without fallback authority" moves from a
reported count per cell to a violation (§46a item 4); the driver's readout gains the refusal
count per cell beside the forms. **And the authority itself:** no producer of fallback authority
exists on main (§1) — a refusal without a way to grant would make §9.4's last resort
unreachable — so the same PR builds the plan-bound whole-file grant §9.4 and §15 describe, never
automatic, ceilinged as §15 says. The PR's scoping states its size; the plan's estimate of "one
PR" is unverified until then.

**Proof, in four parts, stated before the deploy:**

1. **The historical corpus, replayed.** The whole-file repairs the SIP was written from — the
   1.6.5 roll 6 handler repair (§31), 1.7.5 React roll 3's re-emitted suites (#1501's eight
   stored `test_report.md` versions and their repairs), the 1.7.2 roll 1 unrequested file
   (§32) — replayed through the refusal from the vault, **naming each repair it would have
   turned away and with what reason.** This is a replay of the function on stored emissions,
   and is named as one.
2. **The negative control — the §30.2 fixtures in CI**, each refused with its typed reason on
   the normal path (§39.1).
3. **The positive control — a whole-file replacement with valid fallback authority accepted
   through the same normal path**, so the proof demonstrates that the implementation enforces
   the authority distinction and not merely that it rejects whole-file output. Without it the
   refusal and a blanket rejection are indistinguishable.
4. **One checkpoint pair on deploy B** (§4.2) with the prediction **zero refusals, every repair's
   form unchanged from F's distribution** (anchored edits, prose-only refunded, new files, fill).
   A refusal on the pair is a finding: it names a repair the pre-flip contract would have
   accepted, and the record reads its round.

**What the flip does not claim:** an improvement on this deploy. The window's recorded
unauthorized whole-file count is zero (§1), so the replay §46a item 5 describes — "the pre-flip
window's recorded unauthorized whole-file responses replayed through the refusal" — has an
empty input, and the plan says so instead of running an empty replay and calling it proof.

### 3.4 What deploy B does not carry — §12a and §17a, re-placed to 1.8.2

Rev 1 placed both amendments on deploy B with the flip and argued that their typed records (a
ledger key per pass, a `contested` attribute per row) would let a red be attributed. The
reviewer's point stands: attribution helps diagnosis and does not remove causal complexity, and
the line's own principle is one kind of change per measured deploy. **Ruled by the owner,
2026-09-17: moved to 1.8.2, not an over-ruling of the 09-15 targeting.** Deploy B carries the
flip alone. The two SIP sections' target lines are amended in this plan's PR, dated inside each
section; their status stays *proposed, not built*.

What 1.8.2 inherits, so it is not re-derived (§6): the amendments as drafted; their diagnostics'
shapes — `compile-loop` and `false-criterion` — as the review settled them; #1581.

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

**Teardown is the default** (§8 decision 12). When the window closes, one PR removes the `solo`
squad profile, the solo request profile, the generalist prompt asset and Han's service. Before
it, the record freezes their exact configuration and image identities and keeps the static
assets reproducibility needs; the active runtime surface goes. Retention would require a
separate, affirmative product decision — experimental reproducibility alone does not justify a
permanent mode. Items 1–3 of §3.2 stay: each is a general capability.

### 3.6 The reader — `cycles assess`

The evidence gate at the 1.8.0 cut was read by recomputing the assessment from the registry and
the vault; nothing printed it. One route on the authenticated lane, under the cycles resource
as it is registered today — `GET /api/v1/projects/{project_id}/cycles/{cycle_id}/assessment`,
per `docs/architecture/api-route-lanes.md` — returning the assessment with its projection and
registry versions and its evidence identity, computed by
`adapters/cycles/cycle_evidence.assess_cycle`; and one CLI command,
`squadops cycles assess <project> <cycle-id>`, rendering the four dimensions with each
indicator's state and evidence reference, with `--json`. The driver's per-roll record renders
the same. Read-only; no cycle-path behaviour; no agent in the path; no console page (SIP-0069's,
later); **it does not grow into UI work in this line.** A wiring failure is a 404 or 500 on the
first call after deploy A, which the diagnostics' records read. It is not droppable: the
evidence gate's "carries" is met by a thing a person can look at.

### 3.7 The hardening list — none

Rev 1 carried #1448 and #1039 as a droppable list. Neither adds to the flip or the window, and a
line with two measured windows does not carry optional scope to be dropped once execution is
already expensive.

**#1448 goes to 1.9 — ruled by the owner, 2026-09-17.** The issue reads as a wiring cleanup of
ten route modules and is more than that: the auth middleware resolves the auth port *and* the
authorization port from the same process globals at request time, behind a fallback
(`src/squadops/api/middleware/auth.py:182–187`, `:246`, `:272–274`). So the refactor moves how
every authenticated request resolves its identity port, and the two-apps-in-one-process
isolation half lands on the security boundary rather than on a resource route. Measured on
`main` at 3d9970c8: **eighteen** module-level port globals and **twenty-six** accessors in
`src/squadops/api/runtime/deps.py`, **eighty-five** `get_*()` call sites under the routes,
**thirteen** modules reaching into the registry, **eighteen** test files importing it. Patch
lines are for urgent or small fixes (CLAUDE.md, the cadence); odd minors exist to quarantine
exactly this kind of change so a regression has one owner; and it pairs with #1507 as the same
process's structural cleanup under one verification set. Handed to the 1.9 plan with it: the
`:182` fallback is a **require-don't-default at the auth seam** (the owner's ruling of
2026-09-14), so whatever replaces the registry makes the middleware's port required rather than
preserving the fallback in a new shape. The measurements and the finding are recorded on the
issue; the plan's recommendation differed from the review's 1.8.2, and the owner ruled the
plan's.

**#1039 goes to 1.8.2** — documentation-site design work should not compete with a
pre-registered experiment.

### 3.8 The ops rider — after the window, bounded

Carried from the 1.8.0 plan §3.7, which the cut skipped: **#1177** (the Atlas replay scripts
routed through `arm.sh`), **#176 recipe 2** (one `smoke`-squad launch; the issue closes),
**#1176** (the cheap gate first — whether the served chat template accepts prior-turn
thinking), **#1408** and **#1412** (the Flash-Next plan-authoring replay; the Atlas content-loop
diagnosis — the box to themselves; nothing to the vendor without the owner's go-ahead). Each on
the idle box immediately after the window closes, never between.

**The bound** (§8 decision 14): each item receives its defined recipe or run, once. A terminal
result closes it. A finding that needs further engineering becomes a new issue or a next-line
item and does not expand 1.8.1. The rider forces the experiment to happen; it does not force
every finding to be solved, and it is never the last thing between a frozen measurement and its
cut.

### 3.9 The count this release owes the record

| item | release plans that scheduled it | times, incl. this plan |
|---|---|---|
| #176 | 1.7.0, 1.7.3, 1.7.4, 1.7.5, 1.8.0, 1.8.1 | **6** — recipe 2 closes on the idle box (§3.8) |
| #1039 | 1.7.0 §3.1, 1.7.3, 1.7.4, 1.7.5, 1.8.0, (1.8.1 rev 1) | **6** — leaves this line by decision, to 1.8.2 (§3.7) |
| #1176, #1408, #1412, #1177 | 1.7.5 (as the idle-box rider), 1.8.0, 1.8.1 | **3** each — sequenced after the window twice and skipped once; bounded here |
| #1448 | 1.7.5, 1.8.0, (1.8.1 rev 1) | **3** — leaves this line by decision, to 1.9 (§3.7) |
| #1469 | 1.8.0, 1.8.1 | **2** — read at the cut, not closed by it |
| #1526, #1539 | 1.8.1 | **1** each |
| #1598, #1600, #1602 | 1.8.1 | **1** each — filed by the line that hands them here |
| #1581 | (1.8.1 rev 1) | leaves with §17a, to 1.8.2 |

The five idle-box items are on their third plan because the box has gone from the last counted
roll to the cut twice; §7 places them after the window and before the cut, bounded, so the cut
waits for their runs and not for their findings.

### 3.10 The cut criterion — three gates

| gate | criterion |
|---|---|
| **implementation** | §3.1 every row; §3.2 steps 1–8 merged and read on A; the flip merged **iff** A's N read as met, with the authority path and both controls; §3.5 every item merged, Han's service applied by the owner; the driver's arm axis, comparison section and both isolation preflights merged; the teardown PR merged; nothing from §3.4 or §3.7 on any deploy |
| **experimental** | **L1 holds** on every counted roll; **N met on deploy A** in the 1.8.1 pre-registration's count, all-attempt integrity holding on every attempted transaction (with unauthorized whole-file responses a reported count until the flip); **the flip's pair reads zero refusals**, the historical replay names each turned-away repair, and both controls hold in CI; **Han's pair reaches its seams**; **the window closes with six valid pairs, or closes incomplete under the void rule**, its result stated against the registered predicate whichever way it goes, and S / H / tie always rendered; every registered diagnostic reaches its seam on the pinned deploy within its two-run budget; a falsified prediction or an unreached seam stops the set and the plan is revised in the open |
| **evidence** | every counted record of every set carries a `CycleAssessment` **rendered by the reader**, every dimension citing evidence that resolves; the Solo preflight's three absences on every Solo roll; SIP-0108 §5 criterion 6's integrity check and the two isolation contracts asserted on every pair; the record reconstructs every counted / void / shakeout boundary from per-round evidence; deploy-to-tag drift named item by item, expected zero under `src/` and `adapters/` from B′; the package captured with its screenshots — the showcase is **one pair**: a squad roll and its Solo partner, the delivered app of each and the flow-run timeline where the correction variant is legible, chosen and explained per rule 3 |

**The SIP sweep at the cut, stated now so the sweep does not read silence as shipped.**
**SIP-0107** → `implemented` if the flip landed and §39.1–§39.8 hold on this line's records
(§39.1 on the replay and the fixtures with both controls; §39.2–§39.7 on A's and B's
transactions; §39.8 on A's count); if A's N was unmet, `accepted` with step 7 named open and the
shortfall stated — the SIP's own rule, not a plan's. **SIP-0108** → `implemented` if §5's seven
criteria hold — 1–5 on 1.8.0's record, 6–7 on this window with the Solo arm; the window's
*result* does not gate it, its closure does — and a window closed incomplete under the void
rule leaves criterion 7 open and named; §10h's placement axis, its cost accounting and §10j's
Free-Solo window are a successor's criteria and are named as such, not as open children; §4.4's
"runs after" sentence is amended by §10k (the interleaved order). **SIP-0086** and **SIP-0096**
stay `implemented`, §12a and §17a re-targeted to 1.8.2 in their own sections and not built here.
**SIP-0102** step 5 stays open and named: `verified_executable` and `verified_functional` read
unaskable on every cycle until it lands. Nothing else moves; §6 names what stays.

### 3.11 Merge discipline

**One independently reviewable causal change per PR** — implementation, its characterization
proof and its required SIP amendment travel together when their evidence only makes sense
together; a PR never mixes two mechanisms. `gh pr view` before every push; every job of main's
run read after every merge; the seam table in every PR that binds, removes or re-weights a check
(the flip's refusal row; the role map's refusal at creation); the mirror rule on every removal
(the role fallback, the correction step table); the characterization tests in the same PR as
the seam they characterise; **§5a amendments in the SIP, in the PR that diverges**; **no merge to
main while any of the three windows is open** (A's set, B's pair, B′'s pair and window); a
committed golden moves only when every moved line is explained in the PR (the owner's ruling of
2026-09-13; #1598 moves one); **`docker-compose.yml` is the owner's edit** — Han's service block
travels in a PR body; drivers launch detached from their own worktree; the main checkout is not
touched while a driver runs.

---

## 4. The verification sets — three, on two deploys

Same driver, the 1.8.0 set configs re-registered under a `1-8-1-` prefix in
`docs/plans/verification-sets/`, one pre-registration per window committed before that window's
first launch, the pins from the deploy it runs on; if the deploy moves after a pre-registration
is committed, that commit is void and re-made, and no transaction or roll from the superseded
deploy counts (§3.3's counting rule). The gate constant inherited verbatim.

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
and does not count; every transaction read against its round's revision-form row), plus §3.3's
rule on deploys and reruns. The expected range's low end misses N, and the plan says what that
means (§3.3): no flip in 1.8.1.

**Bar and texture:** L1; all-attempt integrity; the #598 prediction re-read (unaskable on every F
roll — the pre-registration says whether any counted roll here can evaluate `container_packaging`
and, if none can, drops the prediction with the reason); the assessment rendered on every record;
every field three-state.

### 4.2 Deploy B — the flip alone

**The checkpoint pair** (one React, one Next.js) with the flip's prediction — zero refusals, the
form distribution F's. The shakeout loop's exit rule applies: a pair with no new seam finding;
budget **three rounds**, the record reporting how many it took. The flip's historical replay and
both control fixtures run before B is built and are committed with B's pre-registration as the
flip's first proof. If the flip did not land (§3.3), deploy B is the prelude's deploy re-pinned,
the pair still runs as B′'s entry condition, and the record says which of the two B was.

### 4.3 Deploy B′ — Han's pair, then the window

**Han's shakeout pair** — two Solo React rolls — reading: every task type dispatched to `han`
and consumed; the role map resolved with no fallback; correction on a failure taking the
`repair` step alone with the deterministic `patch`; the Solo preflight's three absences; the
assessment rendered. A seam not reached within two runs stops the window.

**The window**, registered in the pre-registration **before any roll of either arm is
observed**, per SIP-0108 §4.4 and the 1.8.0 plan §4.2, with these fixed here:

| | fixed |
|---|---|
| **arms** | squad = `full-38` × `validated-fullstack`; Solo = `solo` × `validated-fullstack-solo`; both `qwen3.8:27b` on the same Ollama configuration and box |
| **pairs** | **six valid pairs**, React only (§4.4); pair *k* = the squad arm's *k*-th registered roll and Solo's *k*-th; a **fresh** squad arm — no 1.8.0 roll is reused (§10g) |
| **execution order** | **interleaved by pair, pre-registered and alternating**: pair 1 Squad → Solo, pair 2 Solo → Squad, pair 3 Squad → Solo, and so on — never six of one arm then six of the other. Pairs are matched trials, not replicas; running them as pairs removes the temporal confounds a serial order carries (model and cache warming, host thermal state, accumulated infrastructure state) at no cost, since on one GPU the arms serialize anyway. This amends SIP-0108 §4.4's "the single-model arm runs after the loop set closes", which was written for a squad arm reused from the loop set, as **§10k** |
| **the void rule** | a pair is void only for pre-run identity or infrastructure invalidity named by the rule, never for outcome; **a void removes its pair in full** — the mate may finish for diagnostic evidence, and neither member contributes; a void pair is **replaced by the next sequential pair**, up to a **maximum of eight attempted pairs**; if fewer than six valid pairs exist after eight, the window **closes incomplete** and the predicate is not changed to fit |
| **substrate held equal, asserted by the driver's preflight** | the PRD, the request-profile constants, the framework deploy; per-task-type caps and reasoning levels equal; each task's effective write grant equal — the comparison refuses to run if any differs |
| **run-state isolation, asserted per arm** | a fresh workspace and project state for every cycle; no artifact, framing document, evidence or repair inherited from the paired predecessor or any prior cycle; no agent-side memory consulted (true by construction until the 2.1 recall port, and asserted rather than assumed); equivalent service and filesystem starting state — so the record can show that an arm could not learn anything from the arm that ran before it |
| **runtime topology held equal** | **all seven agent containers stay up for both arms; only the designated arm's agent receives work.** Neither arm runs against a different container set or a different memory envelope; the same model is resident for both, so no model swap separates them |
| **the predicate — outcome** | per pair, binary on `accepted-functional`: a **Squad win** when Squad is accepted-functional and Solo is not; a **Solo win** when Solo is and Squad is not; otherwise a **tie**. **The directional criterion is at least four wins of six valid pairs, for either arm.** The record always renders **Squad wins / Solo wins / ties** (for example 4 / 1 / 1), never only "criterion met". The claim is stated as measured — *Squad produced the better outcome in X of six pre-registered pairs; the pre-registered directional criterion was / was not met* — and never generalized to "the squad improves outcome" |
| **the verification-quality proxy and efficiency — reported, never tie-breakers** | quality is labelled a **verification-quality proxy** (the retest, the boot audit, correction rounds and termination reasons): the clean-room indicators stay unaskable until SIP-0102 step 5, so the stronger product-quality reading is not available yet and the label says so; efficiency is tokens and wall clock per pair, rendered per arm; a cost delta is a result on its own line |
| **the asymmetries, named** | in Solo the #1054 dispute and #1582 unanimity branches do not run (no analyzer, no lead); the repair brief carries the failing cases, the failed rows, the contract expectations and the files, with no analysis summary — each is part of what the arm measures |

**Early stop, one direction, for every window:** a falsified prediction or an unreached seam
stops the set; a good result never stops it early; a stop in one arm does not stop the other.
**The result is stated whichever way it goes**, in the words above.

**Drift the record must declare:** intended zero under `src/` and `adapters/` between B and B′
and between B′ and the tag — the tag is the measured deploy plus the pre-registrations, the
records, the teardown and the package.

---

## 5. Capacity — what drops first, and what cannot

**Cycles:** deploy A, nine diagnostics plus six counted, with the two-run budgets, fifteen to
twenty-two; deploy B, the pair plus up to two more shakeout rounds, two to six; deploy B′, Han's
pair, twelve for six pairs, and up to four more under the void rule, fourteen to twenty.
**Thirty-one to forty-eight cycles**, against the 1.8.0 line's forty across E and F — three to
four nights on the box if no shakeout round finds a seam, and the F set says one will.
**PRs:** the preconditions five, the prelude seven, the flip one or two, Solo four plus the
owner's compose edit, the pre-registrations three, the teardown one — **about twenty-two** before
the cut's own, against the seventy-eight the 1.8.0 line merged between its plan and its package,
and against rev 1's thirty-two.

**If capacity forces a drop**, in this order, each to **1.8.2** by a plan revision in the open:
the ops rider, item by item (their runs, never their findings — §3.8) → #1526 → #1539.
**Non-droppable:** #1603, the ninth diagnostic and deploy A's pre-registration (the flip's
precondition), the reader (the evidence gate), Solo's six items and the window (SIP-0108's
criteria 6–7 and the line's reason), the teardown. **The flip is not droppable by capacity; it
is conditional on N**, and only the count decides it. There is no longer optional scope to be
dropped once execution is expensive: everything on the line contributes to one of the two
sentences in the preamble.

---

## 6. Re-placements by name — nothing silently carried

Twenty-six open issues (rev 1 said twenty-seven and left #414 unplaced). **Eleven are in this
release:** #1602 (by #1603), #1600, #1598, #1539, #1526, #1177, #176, #1176, #1408, #1412, and
#1469 — which stays open by design and is read at the cut against the `frontend_build` corpus,
as 1.8.0 read it. Of the eleven, **seven close by the cut** by code or on the box; #1176, #1408
and #1412 close with an answer if the answer is terminal; #1469 stays. The fifteen that are not
in the release:

**§12a, §17a and #1581 — 1.8.2, the model-capability tranche, by the owner's ruling of
2026-09-17** (§2.3, §8 decision 3). Handed with them, settled at this review so the 1.8.2 plan
does not re-derive them:

- **`compile-loop`** — two independent, non-cascading TypeScript type errors in one existing
  file on `nextjs_ts`, each with a unique marker and each reported by `tsc` (a string assigned
  to a numeric declaration, a number to a string one); no missing imports, no syntax errors, no
  error produced by another, one build system. Reads: both faults present before the task; the
  verifier's evidence exposes both; self-evaluation receives it; both repaired before the task
  completes; the final compile clean; zero correction rounds; every self-evaluation invocation in
  the usage ledger. **Success is both errors fixed inside the task, however many passes it
  took** — the mechanism under test is that the task can compile until clean and is no longer
  constrained by truncated first-error evidence, not that the model must take several attempts.
- **`false-criterion`** — the historically grounded shape, not a synthetic semantic
  disagreement: a valid `@/lib` alias import (the repository's own configuration proves it
  resolves) against a **planted** verification row that rejects it. The original false positive
  was fixed on main, so the row is planted by the fault, not produced by a live check. Reads: the
  producer leaves the correct implementation unchanged and emits a typed dispute naming the
  check; the row reads `contested`; the analyzer confirms the contradiction from repository
  evidence; the round refunds through the `blocked_unverified` path; the terminal record names
  the disputed check. Falsified by a refunded round with no dispute (the #1053 coincidence) or a
  dispute the framework never read.

**#1039 — 1.8.2** (§3.7). **#1448 — 1.9, ruled** (§3.7, §8 decision 13).

**#1507, #567, #353, #1031 — 1.9, unchanged** from the 1.8.0 plan §6 and the ROADMAP's 1.9 row.

**#1522 — 1.9 by decision.** Banking a repair whose retest reduces failures but does not pass
changes what an accepted patch *means*; that is verdict semantics, and the 2026-08-15 ruling
keeps verdict-semantics changes out of a measured window. Legitimate, adjacent to §17a, not this
line's.

**#414 — 1.9 by decision.** The 1.8.0 plan left the reserve's adoption to the Lane M PR that
implemented SIP-0107 §22, and it was not adopted there; a correction-budget policy change beside
a measured window is the same class as #1522, and the 1.9 plan names it or closes it with the
reason.

**#316 — 2.0, with Campaign.** **#949, #950, #194, #557 — at design review, unchanged.**
**#1122 — not scheduled**, as in 1.8.0.

**The SIP re-read**, so the sweep at the cut does not read silence as shipped:

| SIP | state on main | this release |
|---|---|---|
| SIP-0107 | `accepted`; steps 1–6 shipped, §46a–§46p; step 7 open | **step 7 lands on N** (§3.3), with the authority path; `implemented` if §39 holds, else `accepted` with the shortfall |
| SIP-0108 | `accepted`; (a)–(c) shipped, §10a–§10j; (d) and §5 criteria 6–7 open | **(d) lands** (§3.5, §4.3); §10k amends §4.4's order; `implemented` if §5 holds; the successor's criteria named |
| SIP-0086 | `implemented`; §12a proposed, not built | **§12a re-targeted to 1.8.2** in its own section; not built here |
| SIP-0096 | `implemented`; §17a proposed, not built | **§17a re-targeted to 1.8.2** in its own section; not built here |
| SIP-0102 | steps 3–7 open; step 5 named absent by SIP-0108 | stays `accepted`; step 5 named again at the cut |
| SIP-0104, SIP-0105 | as at 1.8.0 | unchanged |
| SIP-0088, SIP-0090, SIP-0091 | as at 1.8.0; the Embodiment Runtime SIP is a proposed draft (`sips/proposed/SIP-Agent-Embodiment-Runtime.md`, since 2026-08-19; its stated dependency on §12a is re-targeted with it) | unchanged here; **Embodiment is the third aim** (§10h): the draft's **design review and acceptance come with the 1.9 plan** — a design commitment, which a feature-free minor may carry — and it is **built in 2.0**, never as part of the 1.x closure (§8 decision 11) |
| SIP-0092, SIP-0093, SIP-0101 | as at 1.8.0 | unchanged |

**Held, by name:** the group_run successor PRD and the Free-Solo window (§2.2) — **2.0 planning
inputs, not 1.x completion criteria**; lifted at 2.0 planning, where they are placed beside
Campaign and the broader placement work (§8 decision 11).

**Not this line's, by name:** any analysis of the line's own test economics (the verification
yield work discussed for 2.0). This line will produce the source material for it — diagnostics,
the historical replay, prediction outcomes, shakeout-versus-counted findings, the tests and
fixtures added to protect seams, cost and cycle records — and the driver's records capture it;
1.8.1 does not analyze it.

---

## 7. Sequencing

1. **This plan**, on its own PR, with the 1.8.0 plan §10 amendment pointing here and the two SIP
   sections' target lines amended. Merges on the owner's review.
2. **#1603** merged — the line's first merge. **The ninth diagnostic registered**, its fault
   verified to land where the record can count it.
3. **The driver** — #1600, the arm axis and the comparison section, the interleaved order, the
   void rule, the isolation and topology preflights, the Solo preflight — and **the reader**
   (§3.6). The driver's changes are not a deploy; the reader is.
4. **The prelude** (§3.2), one PR each in order — #1598 and #1539 first, the three Solo cleanups
   (steps 4–6) with their byte-identical proofs, #1526, the reader last.
5. **Deploy A. The 1.8.1 pre-registration** — N re-fixed with its supply tabled, the pins from
   the deploy, every field's producer and unaskable state — committed **before the first
   diagnostic launch.** Then the nine diagnostics, then the counted set of four and two. A seam
   not reached stops the line here. **N read.**
6. **The flip PR** — merged iff N was met — with the authority path, the historical replay and
   both control fixtures committed with it. Nothing else.
7. **Deploy B; B's pre-registration; the checkpoint pair**, the shakeout loop to its exit rule,
   budget three rounds.
8. **Solo's declarations and Han** (§3.5): the prompt asset, the two profiles, the image; the
   compose block to the owner. **Deploy B′**, zero drift from B under `src/` and `adapters/`.
9. **The window's pre-registration** — the arms, the six pairs and the attempt budget, the
   alternating order, the substrate and isolation assertions, the predicate — committed before
   any roll; **Han's shakeout pair**; then **the six pairs, interleaved**, with void
   replacements under the rule. No merge to main while it is open.
10. **Close the window; the result stated against the predicate, S / H / tie rendered.** **The
    ops rider** on the idle box, bounded (§3.8) — after, never between.
11. **The teardown PR** — identities frozen in the record first.
12. **The preliminary measurement conclusion**: §3.10's three gates read against the frozen
    deploy before anything else moves; the SIP sweep decided on that reading.
13. **Final record; cut 1.8.1 by the seven steps** — re-authenticate immediately before the
    capture, the preview read before `--write`, the screenshots of one pair, zero drift named.
    **Then the 1.8.2 plan** — the model-capability tranche, §12a and §17a with their diagnostics,
    #1581, #1039 — **and the 1.9 plan** — the executor's completion boundary (#1507), the debts
    re-placed by name (#567, #353, #1031, #1448, #1522, #414), the Embodiment Runtime SIP
    reviewed and accepted, the close of the 1.x line — so that 2.0 can open on Campaign with the
    number this window produced and the Free-Solo question placed.

The key property of this order: N is re-fixed before any transaction that could count toward
it is observed, and the flip lands only after that reading; nothing changes the substrate
between the flip's deploy and the window's; the window is registered before either arm is
observed and executed as the pairs it is analysed as; and the three deploys each carry one kind
of change, with B′ differing from B by nothing under `src/` or `adapters/`.

---

## 8. Decisions — ruled, and recommended for the owner to overrule, not fill in

1. **The flip's N is re-supplied on deploy A under a fresh pre-registration; F's five
   transactions do not carry; N stays 6; a rerun on the same pinned deploy counts and a
   superseded deploy's transactions never do** (§3.3). §39.8's rule, applied as written — and
   lowering N after a miss would choose it with the evidence in hand. **Confirmed at review.**
2. **Deploy A's count alone decides whether the flip lands; no owner discretion enters after
   the measurement.** The proof is the historical replay, the negative fixtures, **the positive
   control** (an authorized whole-file replacement accepted through the normal path), and a
   silent pair — and, because no producer of fallback authority exists on main, the flip PR
   builds the plan-bound authority path before it can refuse (§3.3). **Confirmed at review; the
   positive control and the authority finding added in rev 2.**
3. **SIP-0086 §12a and SIP-0096 §17a are re-placed to 1.8.2, the model-capability tranche, with
   their diagnostics and #1581. Ruled by the owner, 2026-09-17**, on the review of rev 1: "fine,
   and not an over-ruling" of the 09-15 targeting. Deploy B carries the flip alone (§3.4).
4. **Solo's three general items land in the prelude with byte-identical squad behaviour; the
   arm's declarations and Han land on B′ with zero code drift from B.** The §10i rule is the stop
   condition. The `resolve_agent_config` fallback is deleted, not deprecated (the 2026-09-14
   ruling). **Confirmed at review.**
5. **The window is executed as pairs, in a pre-registered alternating order** (§4.3), never six
   of one arm then six of the other; SIP-0108 §4.4's "runs after" is amended as §10k.
   **Recommended at review; adopted.**
6. **Six valid pairs, at most eight attempted; a void removes its pair in full for pre-run or
   infrastructure invalidity only; the mate may finish for diagnostic evidence; fewer than six
   after eight closes the window incomplete with the predicate unchanged** (§4.3). **Recommended
   at review; adopted.**
7. **The outcome predicate is binary per pair on accepted-functional; the directional criterion
   is at least four of six for either arm; Squad / Solo / tie is always rendered; the
   verification-quality proxy and efficiency are reported separately and are never
   tie-breakers; the claim is stated as measured, never generalized** (§4.3). **Recommended at
   review; adopted.** The Solo-direction criterion is added so the answer reads either way, as
   the SIP requires.
8. **Run-state isolation and runtime-topology equality are asserted substrate properties**, not
   implicit Docker conditions: fresh state per cycle, nothing inherited across arms, no memory
   consulted; all seven agent containers up for both arms, only the designated arm receiving
   work (§4.3). **Recommended at review; adopted.**
9. **The window's conclusion matches its independent variable** — the squad's organization
   against a deliberately de-organized single-generalist execution on the same substrate — and
   is never read as "many agents beat one" (§2.2). In Solo the #1054 and #1582 branches do not
   run, and that is part of what the arm measures. **Recommended at review; adopted.**
10. **The reader is one route on the `/api/v1` lane and one CLI command, read-only, in the
    prelude, and does not grow into UI work here** (§3.6). **Confirmed at review.**
11. **Free-Solo and the successor PRD are 2.0 planning inputs, not 1.x completion criteria; the
    Embodiment Runtime SIP, a proposed draft since 2026-08-19, is reviewed and accepted with
    the 1.9 plan and built in 2.0; tokens per provider and the placement axis beyond the model
    are a successor's** (§2.2, §6). **Ruled by the owner, 2026-09-17**, on this plan's review,
    consistent with the roadmap rulings of 2026-09-12 and 2026-09-17. The 1.9 plan inherits the
    SIP's review; the 2.0 plan inherits Free-Solo and the successor PRD as inputs, and the hold
    on both is lifted there rather than here.
12. **Teardown is the default.** Han, the solo profiles and the active compose service are
    experimental apparatus; their identities are frozen in the record and the runtime surface is
    removed; retention requires a separate, affirmative product decision (§3.5). **Ruled at
    review, 2026-09-17.**
13. **#1448 goes to 1.9. Ruled by the owner, 2026-09-17**, on the measured surface and on the
    finding that the auth middleware resolves both its ports from the same process globals at
    request time behind a fallback (§3.7): a refactor that moves the auth boundary's resolution
    wants the stabilization minor's quarantine and #1507's company, not a patch line beside
    behaviour changes. This was the one point where the plan differed from the review's 1.8.2,
    and the owner ruled the plan's. Its require-don't-default half is handed to the 1.9 plan.
    **#1039 to 1.8.2. #1522 and #414 to 1.9 by decision. #1507, #567, #353, #1031 stay 1.9's;
    #316 2.0's; the design-review items unchanged** (§6).
14. **The ops rider is bounded** — each item its recipe, a terminal result closes it, a finding
    needing engineering becomes an issue, never a cut blocker — and runs immediately after the
    window (§3.8). **Recommended at review; adopted.**
15. **#1598 — option 1.** The seeded conftest owns isolation through an autouse reset fixture;
    the plan-authoring hint no longer implies an isolation the scaffold does not guarantee;
    isolation is an executable harness property, not model instruction (§3.2). **Ruled at
    review, 2026-09-17.**
16. **Han's compose service is the owner's edit.** The PR carries the block; the plan does not
    touch `docker-compose.yml`. **Standing rule.**
17. **One independently reviewable causal change per PR** replaces "one PR per row" (§3.11).
    **Recommended at review; adopted.**

---

## 9. What this plan does not decide

- **The window's exact pre-registration text** — the pins, the field producers, the eight pair
  slots and their order as registered; the predicate and every rule are fixed here (§4.3).
- **Whether the flip lands** — deploy A's count decides it, not this plan and not the owner
  after the measurement (§3.3, §8 decision 2).
- **The flip PR's size** — the authority path's scope is read on main when the PR is scoped;
  the plan's "one PR" is unverified (§3.3).
- **The 1.8.2 plan's own shape** — beyond what §6 hands it.

---

## 10. Revision history

- **Rev 4 (2026-09-17)** — the owner's ruling on §8 decision 11 (Free-Solo and the successor
  PRD as 2.0 planning inputs; the Embodiment Runtime SIP reviewed and accepted with the 1.9
  plan, built in 2.0; the placement axis and per-provider tokens a successor's) and the word to
  merge. **No decision in §8 is left recommended**; §9's four items are each decided by a later
  commit, not by the owner. Merged at this revision; superseded at the cut.
- **Rev 3 (2026-09-17)** — the owner's ruling on rev 2's one open question: **#1448 goes to
  1.9** (§3.7, §8 decision 13, now ruled; §9's bullet retired). Behind it, read on `main` at
  3d9970c8 and recorded on the issue: the auth middleware resolves the auth and authorization
  ports from the same process globals at request time behind a fallback, so the refactor moves
  the auth boundary's resolution and not only ten resource routes; eighteen globals,
  twenty-six accessors, eighty-five call sites, thirteen modules, eighteen test files. The
  fallback's require-don't-default half is handed to the 1.9 plan.
- **Rev 2 (2026-09-17)** — on the owner's review of rev 1. §12a and §17a re-placed to 1.8.2
  by the owner's ruling (their diagnostics' shapes handed over in §6); the flip's proof given a
  positive control, with the finding that no fallback-authority producer exists on main and the
  flip PR builds it; the explicit counting rule on deploys and reruns; the window executed as
  interleaved pairs with the void rule (six valid of at most eight), the 4-of-6 directional
  predicate for either arm, S / H / tie always rendered, quality labelled a verification-quality
  proxy, and the run-state and topology contracts asserted; the conclusion sentence matched to
  the independent variable; teardown the default; the hardening list moved out (#1448 → 1.9,
  #1039 → 1.8.2); the ops rider bounded; PRs by causal unit; Free-Solo and the successor PRD as
  2.0 planning inputs, the Embodiment SIP's acceptance placed in 1.9; #1598 option 1 ruled; the miscount
  corrected (26 open issues; #414 placed). Cycles 31–48, PRs about twenty-two.
- **Rev 1 (2026-09-17)** — written the evening v1.8.0 was tagged, on the owner's ask, from the
  1.8.0 plan (rev 11), the 1.8.0 pre-registration §10c, SIP-0107 §38/§39/§46a, SIP-0108
  §4.4/§5/§10g–§10j, SIP-0086 §12a, SIP-0096 §17a, all fifty-two 1.8.0 records and the tracker.
  Structure: the flip's precondition re-supplied on deploy A behind nine diagnostics and a 4 + 2
  counted set; the flip and the two capability amendments on deploy B behind a pair and two new
  diagnostics; Solo as declarations and one container on B′ behind Han's pair, then the window
  at N = 6 pairs. Three facts stated up front: N unmet on 1.8.0's record, zero whole-file
  responses on the whole line, Solo's §10i rule. Thirteen decisions by recommendation.
