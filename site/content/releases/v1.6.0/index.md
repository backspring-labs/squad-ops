---
title: v1.6.0
---

# v1.6.0

**Released 2026-08-21** · [tag `v1.6.0`](https://github.com/backspring-labs/squad-ops/releases/tag/v1.6.0)

In-flight **1.6 — the Authorship release**. The rung above 1.4: from *filling* a given
interface design to **authoring the design from the PRD**. Lane M is SIP-0103
(Squad-Authored Manifest, accepted 2026-08-07); Lane S is Generalized Build Capability,
whose Stack Blueprint SIP is deliberately held until a second real stack exists.

Landed so far, gates before author: the queue-front fixes (#762 bind-mode preflight,
#766 Langfuse prompt linkage, #770 SIP promotion), then the M-ladder — M0a contract
derivation pinned to the deployed reference pair (#777), M0b derive-at-seed when a cycle
seeds a manifest but no contract (#779), M3 winnability gate (#781), M2 schema gate and
the `decisions[]` judgment record (#783), M6 authoring failure taxonomy (#785), and **M1
the authoring stage itself (#791)** — a dedicated `development.author_manifest` framing
step that revises against the gates, replacing the ungated proposer-side emission it
relocates, and **#796** — the fix V4 roll 1 exposed: an authored manifest now derives and
pins its contract mid-framing, so the plan authors bind to the design their own squad just
wrote instead of inventing paths, and every contract-gated net engages. M4 (the human
manifest gate, narrowed to question-gated review — #807: the gate stops only when the
design declares an unresolved decision, and the question itself is what the operator is
shown; a design that asks nothing records a distinguishable system approval and proceeds) and **M5 authoring provenance (#803)** —
a system-owned block recording mode, cycle, task, attempt count and the *classified* reason
for each revision, excluded from the manifest's canonical projection so recording how a
design was written can never move the hash its contract binds.
**#811** closes the revision loop: a design question the gate asks can now be *answered* —
`RETURNED_FOR_REVISION` re-executes framing with the notes and the prior manifest as
authoring context, bounded by `manifest_max_attempts`, instead of stopping the sequence for a
manual retry run. It **restores the prefix the note does not invalidate** via SIP-0101's
checkpoint translation — enabled by framing task ids becoming deterministic in the same
change — and re-runs from the technical design, so the design answers the note rather than
describing an interface the revised manifest no longer has.
**#812** makes a gate decision say who made it. `decided_by` was a hardcoded `"system"` with
a TODO beside it, so all 140 human approvals in the project's history carried the word that
means *no human was involved* — in the same namespace the machine paths use. It now composes
`{actor}:{principal}` from the request identity, and an agent can declare itself
(`--as-agent`) since a token cannot tell.
**B1 (#809)** closes the one item whose omission would have been permanent: rejections are
now classified at the moment they happen — plan-validation by producing validator, authoring
by M6 class — so the pre-memory recurrence baseline Cross-Cycle Memory will be measured
against is capturable. Read by nothing in 1.6, deliberately.
**Track S opens with S1**: the five per-stack facts — expander, fill slots, QA namespace,
harness boundary, check-stack vocabulary — collapse from four module-level dicts plus one
inline answer into a single `ScaffoldStack` registration. Pure refactor; the reference
manifest and contract hashes are unmoved. It removes a silent-omission trap: `fill_slot_paths`
guarded on whether a stack was *registered* and then returned FastAPI's slot map to whoever
asked, so a second stack would have inherited `backend/routes.py` with nothing objecting.
Plan: `docs/plans/1-6-0-authorship-plan.md`.

Closed out 2026-08-21 at the cut. Later stages beyond the narrative above: Stage 2g
rewrote the Stack Blueprint Contract against main and it was **accepted 2026-08-17 with
its unbuilt parts named (SIP-0105)**; SIP-0104's deterministic verification scaffolding
carried both measurement windows. **Release gate MET**: the pre-registered V7
authored-mode FAY window closed **amended 4/6 functional** (dual record 3/6 pre-registered
instrument / 4/6 corrected, #1004/#1005, both always reported), zero manual interventions;
the V38 model-comparison window (qwen3.8:27b) re-exercised the full authored path at
**4/6, roughly half the wall-clock**, and its §6 synthesis records the failure-class
shift toward framing-rooted contract violations. **Cut basis:** zero code drift between
the window-validated frozen deploy `f7a5e0a2` and main (docs only); full regression 7,615
passed; Guard 1a/1b green. SIP-0103 promoted to implemented at the cut. Post-window
queue deferred to 1.6.1+: #1011, #1012 (byte-verified reproducer banked), #1013, #1014,
#1015, compile-credit bookkeeping.

## Merged pull requests (150)

| PR | Title | Closes |
|---|---|---|
| [#1016](https://github.com/backspring-labs/squad-ops/pull/1016) | chore(release): v1.6.0 — the Authorship release | — |
| [#1010](https://github.com/backspring-labs/squad-ops/pull/1010) | docs: V38 model-comparison window record — closed at 4/6, synthesis vs arm A | — |
| [#1009](https://github.com/backspring-labs/squad-ops/pull/1009) | docs(v7): the V7 FAY window record — closed, amended 4/6, bar met | — |
| [#1008](https://github.com/backspring-labs/squad-ops/pull/1008) | fix(harness): V38 shakedown items — qwen3.8 registry clamp parity + bounded JSON re-ask | — |
| [#1007](https://github.com/backspring-labs/squad-ops/pull/1007) | docs(v38): ruling (a) — stack comparison, both deltas named; preconditions 2.2/2.3 MET | — |
| [#1006](https://github.com/backspring-labs/squad-ops/pull/1006) | feat(profiles): full-38 comparison arm + V38 model-comparison pre-registration | — |
| [#1005](https://github.com/backspring-labs/squad-ops/pull/1005) | fix(audit): reconstruct concatenated UI paths — false PAGE_NOT_API failed the V7 deciding roll (#1004) [OWNER RULING] | [#1004](https://github.com/backspring-labs/squad-ops/issues/1004) |
| [#1003](https://github.com/backspring-labs/squad-ops/pull/1003) | docs(sip): embodiment — bind execution surface to ACP where offered | — |
| [#1001](https://github.com/backspring-labs/squad-ops/pull/1001) | fix(rollup): normalizer reads the authenticity row's own verdict (#1000) [RESET-CLASS / POST-WINDOW] | [#1000](https://github.com/backspring-labs/squad-ops/issues/1000) |
| [#997](https://github.com/backspring-labs/squad-ops/pull/997) | fix(authoring): teach the server-component prerender constraint (#996) [POST-WINDOW] | [#996](https://github.com/backspring-labs/squad-ops/issues/996) |
| [#993](https://github.com/backspring-labs/squad-ops/pull/993) | docs(sip): propose Agent Embodiment Runtime (2.2-era) | — |
| [#992](https://github.com/backspring-labs/squad-ops/pull/992) | docs(v7): freeze the deploy, close the preconditions, open the window | — |
| [#991](https://github.com/backspring-labs/squad-ops/pull/991) | fix(routing): a suite that never invoked the app is the suite's defect (#988) | [#988](https://github.com/backspring-labs/squad-ops/issues/988) |
| [#990](https://github.com/backspring-labs/squad-ops/pull/990) | fix(scaffold): accept the language-prefixed fill fence, and record it (#987) | [#987](https://github.com/backspring-labs/squad-ops/issues/987) |
| [#989](https://github.com/backspring-labs/squad-ops/pull/989) | fix(qa): bank suite-authenticity rows on pass, with what was inspected (#986) | [#986](https://github.com/backspring-labs/squad-ops/issues/986) |
| [#985](https://github.com/backspring-labs/squad-ops/pull/985) | docs(plan): 1e's credit in the window record — the edit that silently did not apply | — |
| [#984](https://github.com/backspring-labs/squad-ops/pull/984) | docs(plan): the four outstanding rulings, closed | — |
| [#983](https://github.com/backspring-labs/squad-ops/pull/983) | docs(2g): rewrite the Stack Blueprint SIP against main — the gate is met | — |
| [#982](https://github.com/backspring-labs/squad-ops/pull/982) | feat(qa): record what the fills assert, not just that slots were filled | [#980](https://github.com/backspring-labs/squad-ops/issues/980) |
| [#981](https://github.com/backspring-labs/squad-ops/pull/981) | docs(plan): declare shakedown #2, and what #1 exposed about a green roll (2.f/2.g) | — |
| [#979](https://github.com/backspring-labs/squad-ops/pull/979) | fix(scaffold): the shell must import TABLES — #936's defect, recurred at #967 | — |
| [#978](https://github.com/backspring-labs/squad-ops/pull/978) | docs(2e): the two disclosures, and the vocabulary reconciliation is three axes | — |
| [#977](https://github.com/backspring-labs/squad-ops/pull/977) | docs(2f): S5's admission rule is enforced by the 2c gate, not just written | — |
| [#976](https://github.com/backspring-labs/squad-ops/pull/976) | docs(plan): declare the pre-window shakedown as non-counting, before it runs | — |
| [#975](https://github.com/backspring-labs/squad-ops/pull/975) | docs(plan): V7 preconditions met; #967 added as blocking (2.7 / 2.d) | — |
| [#974](https://github.com/backspring-labs/squad-ops/pull/974) | test(2c): the blueprint falsification pass, as a standing gate | — |
| [#973](https://github.com/backspring-labs/squad-ops/pull/973) | fix(scaffold): derive and type the store's table names | [#967](https://github.com/backspring-labs/squad-ops/issues/967) |
| [#966](https://github.com/backspring-labs/squad-ops/pull/966) | docs(plan): V7 2.b dispositions built; record the deploy-boundary risk (2.c) | — |
| [#965](https://github.com/backspring-labs/squad-ops/pull/965) | fix(cli): print data as itself, never as Rich markup | [#931](https://github.com/backspring-labs/squad-ops/issues/931) |
| [#964](https://github.com/backspring-labs/squad-ops/pull/964) | fix(verification): name the contract criteria a run did not verify | [#945](https://github.com/backspring-labs/squad-ops/issues/945) |
| [#963](https://github.com/backspring-labs/squad-ops/pull/963) | docs(plan): the SIP-0104 P6 window record | — |
| [#962](https://github.com/backspring-labs/squad-ops/pull/962) | fix(qa): record what the test runner actually did | [#935](https://github.com/backspring-labs/squad-ops/issues/935) |
| [#961](https://github.com/backspring-labs/squad-ops/pull/961) | docs(plan): Guard 1a and 1b are built and green — the plan said otherwise | — |
| [#960](https://github.com/backspring-labs/squad-ops/pull/960) | fix(qa): log which validation check opened the self-eval branch | [#946](https://github.com/backspring-labs/squad-ops/issues/946) |
| [#959](https://github.com/backspring-labs/squad-ops/pull/959) | feat(contract): probe body-discriminated child actions from declared values | [#948](https://github.com/backspring-labs/squad-ops/issues/948) |
| [#957](https://github.com/backspring-labs/squad-ops/pull/957) | fix(qa): reject additive suites that mock the subject instead of invoking it | [#915](https://github.com/backspring-labs/squad-ops/issues/915) |
| [#958](https://github.com/backspring-labs/squad-ops/pull/958) | feat(scaffold): report the delta between declared and verified behaviours | [#951](https://github.com/backspring-labs/squad-ops/issues/951) |
| [#956](https://github.com/backspring-labs/squad-ops/pull/956) | fix(audit): find wrapped UI call sites, and read 405 as proof the route exists | [#952](https://github.com/backspring-labs/squad-ops/issues/952) [#953](https://github.com/backspring-labs/squad-ops/issues/953) |
| [#955](https://github.com/backspring-labs/squad-ops/pull/955) | docs(plan): V7 outcome bands ruled + fixed parameters filled where knowable | — |
| [#954](https://github.com/backspring-labs/squad-ops/pull/954) | docs(plan): V7 FAY window pre-registration (draft, not in force) — closes 4c | — |
| [#943](https://github.com/backspring-labs/squad-ops/pull/943) | fix(verification): build checks judge the deliverable, not pre-repair source | — |
| [#942](https://github.com/backspring-labs/squad-ops/pull/942) | fix(correction): repairs render their own stack's guidance, not stack #1's | — |
| [#941](https://github.com/backspring-labs/squad-ops/pull/941) | docs(sip): propose Test-First Verification (red gate + authoring inversion) | — |
| [#934](https://github.com/backspring-labs/squad-ops/pull/934) | fix(qa): stop ordering the author to produce ONLY the authored file in fill mode | — |
| [#940](https://github.com/backspring-labs/squad-ops/pull/940) | docs(sip): assembly stability and the gate-time preflight gap (§27) | — |
| [#938](https://github.com/backspring-labs/squad-ops/pull/938) | fix(governance): record generations through the shared implementation | — |
| [#937](https://github.com/backspring-labs/squad-ops/pull/937) | fix(scaffold): shell imports the helper the fill vocabulary teaches (GENERATOR_VERSION 2) | — |
| [#932](https://github.com/backspring-labs/squad-ops/pull/932) | fix(observability): classify fences by parsing, not by literal prefix | — |
| [#928](https://github.com/backspring-labs/squad-ops/pull/928) | fix(observability): capture every LLM seam, not the one that had a helper | — |
| [#926](https://github.com/backspring-labs/squad-ops/pull/926) | feat(observability): record what an LLM call actually emitted | — |
| [#923](https://github.com/backspring-labs/squad-ops/pull/923) | docs(roadmap): #922 joins 1.7's vocabulary-leak pool | — |
| [#921](https://github.com/backspring-labs/squad-ops/pull/921) | docs(sip-cba): duty-shaped steward, versioning question, and the pack configuration lifecycle | — |
| [#920](https://github.com/backspring-labs/squad-ops/pull/920) | docs: state the window's final claim by rule, not by roll number (SIP-0104 §13b) | — |
| [#919](https://github.com/backspring-labs/squad-ops/pull/919) | fix(authoring): the sole-author path had a private, drifted copy of the check vocabulary | [#918](https://github.com/backspring-labs/squad-ops/issues/918) |
| [#917](https://github.com/backspring-labs/squad-ops/pull/917) | fix(authoring): the qa example taught the criterion the gate rejects | [#916](https://github.com/backspring-labs/squad-ops/issues/916) |
| [#914](https://github.com/backspring-labs/squad-ops/pull/914) | fix(scaffold): show the qa author the error envelope, and stop the brief contradicting itself | [#875](https://github.com/backspring-labs/squad-ops/issues/875) [#910](https://github.com/backspring-labs/squad-ops/issues/910) [#911](https://github.com/backspring-labs/squad-ops/issues/911) [#912](https://github.com/backspring-labs/squad-ops/issues/912) |
| [#909](https://github.com/backspring-labs/squad-ops/pull/909) | test(guards): Guard 1a and Guard 1b — authored mode is provenance, not a fork | — |
| [#908](https://github.com/backspring-labs/squad-ops/pull/908) | fix(corrections): a suite failure names which tests failed (#878 full) | [#878](https://github.com/backspring-labs/squad-ops/issues/878) |
| [#907](https://github.com/backspring-labs/squad-ops/pull/907) | docs(plan): the roll-3 rebuild carries #902 and nothing else | — |
| [#905](https://github.com/backspring-labs/squad-ops/pull/905) | docs(plan): 1e credits at P6 roll 3; rolls 3-6 serve V6 | — |
| [#904](https://github.com/backspring-labs/squad-ops/pull/904) | docs(sip-0104): §13a — an audit pass gates the window from roll 3 | — |
| [#903](https://github.com/backspring-labs/squad-ops/pull/903) | feat(audit): UI data-path check — does the UI reach its own API? | — |
| [#902](https://github.com/backspring-labs/squad-ops/pull/902) | fix(dev): per-stack fill-only guidance — roll 1's app shipped a dead UI because the author was told stack #1's seam | — |
| [#900](https://github.com/backspring-labs/squad-ops/pull/900) | fix(sip-0102): pin verification before build, not after — plus §11a stack-awareness amendment | — |
| [#899](https://github.com/backspring-labs/squad-ops/pull/899) | fix(sip-0104): four defects measured on window roll 1 (sandbox install, audit stack, silent non-collection, rollup pollution) | — |
| [#898](https://github.com/backspring-labs/squad-ops/pull/898) | feat(sip-0104): Phase 5 — the evidence pipeline (classification, correlation, banked report fields) | — |
| [#897](https://github.com/backspring-labs/squad-ops/pull/897) | feat(sip-0104): Phase 4 — region-level enforcement against adversarial producers (Gate 4) | — |
| [#896](https://github.com/backspring-labs/squad-ops/pull/896) | feat(sip-0104): Phase 3 — the fill protocol and qa.test fill mode (bounded agent surface) | — |
| [#895](https://github.com/backspring-labs/squad-ops/pull/895) | feat(sip-0104): Phase 2 — the execution-readiness gates (static bytes-level + skeleton execution) | — |
| [#894](https://github.com/backspring-labs/squad-ops/pull/894) | feat(sip-0104): Phase 1 — the deterministic test scaffold (contract, generator, seed lifecycle, Gate 1 pins) | — |
| [#893](https://github.com/backspring-labs/squad-ops/pull/893) | docs(sip): Phase 0 — amend §10.4 and accept SIP-0104 (Deterministic Verification Scaffolding) | — |
| [#892](https://github.com/backspring-labs/squad-ops/pull/892) | docs(plan): implementation plan for the verification-scaffolding SIP | — |
| [#885](https://github.com/backspring-labs/squad-ops/pull/885) | docs(sip): propose Deterministic Test Scaffolding (fill-slot qa suites) | — |
| [#891](https://github.com/backspring-labs/squad-ops/pull/891) | fix(authoring): builder example shows the profile's required-files floor (#890) | [#890](https://github.com/backspring-labs/squad-ops/issues/890) |
| [#889](https://github.com/backspring-labs/squad-ops/pull/889) | fix(plan): build-profile required_files are a floor the plan must cover (#888) | [#888](https://github.com/backspring-labs/squad-ops/issues/888) |
| [#887](https://github.com/backspring-labs/squad-ops/pull/887) | fix(correction): suite-health verdict joins the tests_pass signature (#878 minimum) | — |
| [#886](https://github.com/backspring-labs/squad-ops/pull/886) | fix(correction): repair routing honors ownership facts before heuristics (#884) | [#884](https://github.com/backspring-labs/squad-ops/issues/884) |
| [#883](https://github.com/backspring-labs/squad-ops/pull/883) | fix(executor): scaffold-seeded artifacts never shadow produced content (#881) | [#881](https://github.com/backspring-labs/squad-ops/issues/881) |
| [#882](https://github.com/backspring-labs/squad-ops/pull/882) | fix(executor): never re-seed the walking skeleton on resume (#881) | [#881](https://github.com/backspring-labs/squad-ops/issues/881) |
| [#879](https://github.com/backspring-labs/squad-ops/pull/879) | fix(qa): state the suite execution model on both guidance surfaces (#877) | [#877](https://github.com/backspring-labs/squad-ops/issues/877) |
| [#876](https://github.com/backspring-labs/squad-ops/pull/876) | fix(contract): the rejects-blank expectation is the pack's call (#874) | [#874](https://github.com/backspring-labs/squad-ops/issues/874) |
| [#873](https://github.com/backspring-labs/squad-ops/pull/873) | fix(correction): file-owned patch gate + rejected-repair evidence carry (#870) | [#870](https://github.com/backspring-labs/squad-ops/issues/870) |
| [#872](https://github.com/backspring-labs/squad-ops/pull/872) | fix(scaffold): TS frozen surface publishes types, returns, and classes (#871) | [#871](https://github.com/backspring-labs/squad-ops/issues/871) |
| [#869](https://github.com/backspring-labs/squad-ops/pull/869) | fix(crp): validated-fullstack budget 7200 -> 10800s | — |
| [#868](https://github.com/backspring-labs/squad-ops/pull/868) | fix(stack2): the harness can execute the idiom the stack teaches | — |
| [#867](https://github.com/backspring-labs/squad-ops/pull/867) | docs(2b): capability assembly — axes, sandbox seam, trigger (§4c) | — |
| [#866](https://github.com/backspring-labs/squad-ops/pull/866) | fix(context): every judged agent is shown the facts its checks depend on | [#787](https://github.com/backspring-labs/squad-ops/issues/787) |
| [#865](https://github.com/backspring-labs/squad-ops/pull/865) | fix(scaffold): the frozen index publishes call signatures, not just names (#863) | [#863](https://github.com/backspring-labs/squad-ops/issues/863) |
| [#862](https://github.com/backspring-labs/squad-ops/pull/862) | fix(dev): the developer is told what the frozen files declare (#861, #858) | [#861](https://github.com/backspring-labs/squad-ops/issues/861) |
| [#860](https://github.com/backspring-labs/squad-ops/pull/860) | fix(nextjs): the route file is derived from the URL it serves (#859) | [#859](https://github.com/backspring-labs/squad-ops/issues/859) |
| [#857](https://github.com/backspring-labs/squad-ops/pull/857) | fix(plan): the sole author is shown the rules its plan is validated against (#856) | [#856](https://github.com/backspring-labs/squad-ops/issues/856) |
| [#855](https://github.com/backspring-labs/squad-ops/pull/855) | fix(gates): an approved gate promotes, however it was approved (#854) | [#854](https://github.com/backspring-labs/squad-ops/issues/854) |
| [#853](https://github.com/backspring-labs/squad-ops/pull/853) | docs(2b): the blueprint schema itself, not just the field inventory | — |
| [#852](https://github.com/backspring-labs/squad-ops/pull/852) | docs(2b): blueprint schema drafted against both stacks | — |
| [#851](https://github.com/backspring-labs/squad-ops/pull/851) | test(stacks): 2a — the stack inventory as an executable enumeration | — |
| [#850](https://github.com/backspring-labs/squad-ops/pull/850) | fix(contract): criterion ids identify a slot, and a malformed contract is refused (#849) | [#849](https://github.com/backspring-labs/squad-ops/issues/849) |
| [#848](https://github.com/backspring-labs/squad-ops/pull/848) | fix(plan): plan validation knows the stack, and the sole author gets the contract (#846) | — |
| [#847](https://github.com/backspring-labs/squad-ops/pull/847) | fix(checks): one command allowlist, measured against the images (#707) | [#707](https://github.com/backspring-labs/squad-ops/issues/707) |
| [#845](https://github.com/backspring-labs/squad-ops/pull/845) | feat(build): register nextjs_ts, and stop swallowing a missing build profile (#838) | [#838](https://github.com/backspring-labs/squad-ops/issues/838) |
| [#844](https://github.com/backspring-labs/squad-ops/pull/844) | docs(prd): finish the SIP-0098 §6.7 split — group_run PRD v0.5 (#843) | [#843](https://github.com/backspring-labs/squad-ops/issues/843) |
| [#842](https://github.com/backspring-labs/squad-ops/pull/842) | feat(framing): the configured stack outranks whatever the PRD says (#838) | — |
| [#841](https://github.com/backspring-labs/squad-ops/pull/841) | feat(gates): a manifest must be for the stack the cycle is building (#838) | — |
| [#840](https://github.com/backspring-labs/squad-ops/pull/840) | docs(plan): decompose 1e and 4g | — |
| [#839](https://github.com/backspring-labs/squad-ops/pull/839) | docs(plan): decompose Stage 2 into 2a–2g (S3 + S5) | — |
| [#837](https://github.com/backspring-labs/squad-ops/pull/837) | docs(stack-2): the bend register as its own document (#822, Stage 1d) | — |
| [#836](https://github.com/backspring-labs/squad-ops/pull/836) | feat(scaffold): the Next.js + TypeScript stack — stack #2 (#822, Stage 1c) | — |
| [#835](https://github.com/backspring-labs/squad-ops/pull/835) | refactor(task_plan): injection asks the check what it can parse (#833) | [#833](https://github.com/backspring-labs/squad-ops/issues/833) |
| [#834](https://github.com/backspring-labs/squad-ops/pull/834) | feat(cycles): a cycle declares its stack once, not twice (#832) | [#832](https://github.com/backspring-labs/squad-ops/issues/832) |
| [#831](https://github.com/backspring-labs/squad-ops/pull/831) | docs(plan): stage the remaining 1.6.0 sequence | — |
| [#830](https://github.com/backspring-labs/squad-ops/pull/830) | feat(correction): view source for repair targeting comes from the contract (#829) | [#829](https://github.com/backspring-labs/squad-ops/issues/829) |
| [#828](https://github.com/backspring-labs/squad-ops/pull/828) | feat(checks): the buildable project directory is a stack fact, not "frontend/" (#822) | — |
| [#827](https://github.com/backspring-labs/squad-ops/pull/827) | feat(probes): a stack that cannot run from source builds before it boots (#822) | — |
| [#826](https://github.com/backspring-labs/squad-ops/pull/826) | docs(plan): amend S2 — stack #2 is Next.js + TypeScript | — |
| [#825](https://github.com/backspring-labs/squad-ops/pull/825) | feat(diagnostics): build the two SIP-0103 §5c.7 signals M4 spent before they existed | — |
| [#824](https://github.com/backspring-labs/squad-ops/pull/824) | docs(sip-0103): record post-acceptance amendments in the SIP, not only the plan | — |
| [#823](https://github.com/backspring-labs/squad-ops/pull/823) | feat(probes): the probe runner boots the stack the cycle actually builds (#822) | — |
| [#821](https://github.com/backspring-labs/squad-ops/pull/821) | feat(scaffold): the contract emitter refuses a stack it has no criteria for (#818) | [#818](https://github.com/backspring-labs/squad-ops/issues/818) |
| [#819](https://github.com/backspring-labs/squad-ops/pull/819) | docs(plan): correct nine unverified claims found by a source sweep | — |
| [#817](https://github.com/backspring-labs/squad-ops/pull/817) | docs(plan): record what S3's schema will not have validated | — |
| [#816](https://github.com/backspring-labs/squad-ops/pull/816) | refactor(scaffold): one registration per stack, not five scattered facts (S1) | — |
| [#815](https://github.com/backspring-labs/squad-ops/pull/815) | feat(api): a gate decision records who made it (#812) | [#812](https://github.com/backspring-labs/squad-ops/issues/812) |
| [#814](https://github.com/backspring-labs/squad-ops/pull/814) | fix(cycles): an answered design question reaches the author as a revision (#811) | [#811](https://github.com/backspring-labs/squad-ops/issues/811) |
| [#813](https://github.com/backspring-labs/squad-ops/pull/813) | docs(plan): the seeded control becomes conditional; add Track S's missing verification point | — |
| [#810](https://github.com/backspring-labs/squad-ops/pull/810) | feat(cycles): the pre-memory rejection baseline (#809, B1) | [#809](https://github.com/backspring-labs/squad-ops/issues/809) |
| [#808](https://github.com/backspring-labs/squad-ops/pull/808) | feat(cycles): the manifest gate stops only when the design asks a question (#807, M4) | [#807](https://github.com/backspring-labs/squad-ops/issues/807) |
| [#806](https://github.com/backspring-labs/squad-ops/pull/806) | docs(sip): record P6 as built and validated against a real vllm-metal server | — |
| [#805](https://github.com/backspring-labs/squad-ops/pull/805) | feat(llm): VLLMAdapter — second provider, OpenAI-compatible dialect (SIP Atlas P6) | — |
| [#804](https://github.com/backspring-labs/squad-ops/pull/804) | feat(scaffold): authoring provenance on the manifest (#803, M5) | [#803](https://github.com/backspring-labs/squad-ops/issues/803) |
| [#802](https://github.com/backspring-labs/squad-ops/pull/802) | docs(plan): M4 becomes question-gated review, not mandatory manifest review | — |
| [#801](https://github.com/backspring-labs/squad-ops/pull/801) | test(llm): live-tier conformance — the same contract against a real server (SIP Atlas P3) | — |
| [#800](https://github.com/backspring-labs/squad-ops/pull/800) | feat(llm): declare capabilities on the port; model listing speaks ModelInfo (SIP Atlas P0 + P1 listing) | — |
| [#799](https://github.com/backspring-labs/squad-ops/pull/799) | test(llm): LLM port conformance suite — one contract, adapter-parameterized (SIP Atlas P3) | — |
| [#798](https://github.com/backspring-labs/squad-ops/pull/798) | fix(cycles): an authored manifest binds its own run (#796) | [#796](https://github.com/backspring-labs/squad-ops/issues/796) |
| [#797](https://github.com/backspring-labs/squad-ops/pull/797) | fix(telemetry): tokens_per_second reaches LangFuse — replace the hand-copied redaction rebuild | [#793](https://github.com/backspring-labs/squad-ops/issues/793) |
| [#794](https://github.com/backspring-labs/squad-ops/pull/794) | SIP (proposed): Atlas Provider Adapter — config-selected inference providers behind a conformance gate | — |
| [#792](https://github.com/backspring-labs/squad-ops/pull/792) | feat(cycles): the squad authors its own interface manifest (#791, M1) | [#791](https://github.com/backspring-labs/squad-ops/issues/791) |
| [#790](https://github.com/backspring-labs/squad-ops/pull/790) | docs: rotate CHANGELOG for v1.4.0–v1.5.0 and guard the rotation (#789) | [#789](https://github.com/backspring-labs/squad-ops/issues/789) |
| [#786](https://github.com/backspring-labs/squad-ops/pull/786) | feat(cycles): authoring failure taxonomy — one classification, three consumers (#785, M6) | [#785](https://github.com/backspring-labs/squad-ops/issues/785) |
| [#784](https://github.com/backspring-labs/squad-ops/pull/784) | feat(cycles): schema gate — provenance and the decisions[] judgment record (#783, M2) | [#783](https://github.com/backspring-labs/squad-ops/issues/783) |
| [#782](https://github.com/backspring-labs/squad-ops/pull/782) | feat(cycles): winnability gate — prove a manifest can be won before spending on it (#781, M3) | [#781](https://github.com/backspring-labs/squad-ops/issues/781) |
| [#780](https://github.com/backspring-labs/squad-ops/pull/780) | feat(cycles): derive the verification contract when a cycle seeds a manifest but no contract (#779, M0b) | [#779](https://github.com/backspring-labs/squad-ops/issues/779) |
| [#778](https://github.com/backspring-labs/squad-ops/pull/778) | feat(contract): pin the deriver to the deployed reference pair (#777, M0a) | [#777](https://github.com/backspring-labs/squad-ops/issues/777) |
| [#776](https://github.com/backspring-labs/squad-ops/pull/776) | fix(maintainer): derive SIP frontmatter from the body instead of failing (#770) | [#770](https://github.com/backspring-labs/squad-ops/issues/770) |
| [#775](https://github.com/backspring-labs/squad-ops/pull/775) | docs(1.6): verification cadence — V1–V8, and the two corrections it exposed | — |
| [#774](https://github.com/backspring-labs/squad-ops/pull/774) | fix(telemetry): only attempt Langfuse prompt linkage when assets come from Langfuse (#766) | [#766](https://github.com/backspring-labs/squad-ops/issues/766) |
| [#773](https://github.com/backspring-labs/squad-ops/pull/773) | fix(preflight): reject bind mode with no plan_authoring_contributors at create (#762) | [#762](https://github.com/backspring-labs/squad-ops/issues/762) |
| [#771](https://github.com/backspring-labs/squad-ops/pull/771) | docs(1.6): M0 premise correction — the contract deriver already exists, and v9 is its output | — |
| [#769](https://github.com/backspring-labs/squad-ops/pull/769) | docs(1.6): the Authorship plan — author the design, prove it was won | — |
| [#768](https://github.com/backspring-labs/squad-ops/pull/768) | sips: accept Squad-Authored Manifest as SIP-0103 (v1.6 Lane M headline) | — |
| [#767](https://github.com/backspring-labs/squad-ops/pull/767) | docs(roadmap): post-1.5 reconciliation — 1.7's identity, 1.8's co-headliners, memory rails | — |

## Improvement proposals

| Proposal | From | To |
|---|---|---|
| [SIP-0102-Ephemeral-Application-Sandbox](../../design/sips/SIP-0102-Ephemeral-Application-Sandbox.md) | new | accepted |
| [SIP-0103-Squad-Authored-Manifest](../../design/sips/SIP-0103-Squad-Authored-Manifest.md) | new | implemented |
| [SIP-0104-Deterministic-Verification-Scaffolding-with](../../design/sips/SIP-0104-Deterministic-Verification-Scaffolding-with.md) | new | accepted |
| [SIP-0105-Stack-Blueprint-Contract](../../design/sips/SIP-0105-Stack-Blueprint-Contract.md) | new | accepted |
| [SIP-API-Contract-Hardening](../../design/sips/SIP-API-Contract-Hardening.md) | new | proposed |
| [SIP-Agent-Embodiment-Runtime](../../design/sips/SIP-Agent-Embodiment-Runtime.md) | new | proposed |
| [SIP-Atlas-Provider-Adapter](../../design/sips/SIP-Atlas-Provider-Adapter.md) | new | proposed |
| [SIP-Campaign-Orchestration](../../design/sips/SIP-Campaign-Orchestration.md) | new | proposed |
| [SIP-Capability-Backed-Agents](../../design/sips/SIP-Capability-Backed-Agents.md) | new | proposed |
| [SIP-Cross-Cycle-Memory](../../design/sips/SIP-Cross-Cycle-Memory.md) | new | proposed |
| [SIP-Cycle-Evaluation-Scorecard](../../design/sips/SIP-Cycle-Evaluation-Scorecard.md) | new | proposed |
| [SIP-Cycle-Request-Profile-Naming-Taxonomy](../../design/sips/SIP-Cycle-Request-Profile-Naming-Taxonomy.md) | new | proposed |
| [SIP-LLM-Emission-Contracts](../../design/sips/SIP-LLM-Emission-Contracts.md) | new | proposed |
| [SIP-Planning-Sequence-Strategy-First](../../design/sips/SIP-Planning-Sequence-Strategy-First.md) | new | proposed |
| [SIP-Post-Retest-Governance-Acceptance-Review](../../design/sips/SIP-Post-Retest-Governance-Acceptance-Review.md) | new | proposed |
| [SIP-Skill-Layer-For-Capabilities](../../design/sips/SIP-Skill-Layer-For-Capabilities.md) | new | proposed |
| [SIP-Test-First-Verification](../../design/sips/SIP-Test-First-Verification.md) | new | proposed |
| [SIP-Version-Bump-Hardening](../../design/sips/SIP-Version-Bump-Hardening.md) | new | proposed |
| [SIP-intelligent-delegation-protocols](../../design/sips/SIP-intelligent-delegation-protocols.md) | new | proposed |
