# SIP portfolio: where every live SIP stands, what overlaps, and what needs reconciling

**What this is.** The cross-SIP view that `sips/registry.yaml` (the index of status) does not give. It
holds four things:
- every live SIP's next placement and its open parts;
- the overlaps between documents, and the boundary each one gets;
- the queue of reconciliations waiting on the owner;
- the intake log.

The per-part record of what shipped where lives **in each SIP**, in its `Delivery ledger` (CLAUDE.md,
"SIP System"). This file indexes those ledgers; it does not replace them.

**How it is kept current:**
- **At intake:** every new SIP or idea is checked against this file before it is recorded (CLAUDE.md,
  "SIP System").
- **In the PR that ships or re-places a part:** the SIP's ledger, and its row here.
- **At each release cut:** the SIP sweep (cut step 5) reads the ledgers, promotes what is done, and
  refreshes this file.

**Baseline: 2026-10-04,** `main` at `1b14d592`. 2.0.0 is not tagged; its counted set is running.
- **The audits:** two read-only audits, one of the 11 accepted SIPs in depth (plus the implemented SIPs
  promoted with open items), one of the 29 proposed SIPs and the ideas.
- **The check:** six of their load-bearing claims were spot-checked, and all six held:
  - #1122 closed `not_planned`;
  - no SIP-0107 §15 code;
  - the status script's transitions;
  - the duplicate registry number;
  - the ROADMAP row;
  - SIP-0104's first PR in v1.6.0.
- **Not a full verification:** a row marked *unverified* is one the audit itself could not settle.

---

## 1. Accepted SIPs (10: 9 after the v2.0.0 sweep and SIP-0107's promotion after the tag, then SIP-0110 accepted 2026-10-06)

| SIP | shipped | remaining, and where it is placed | promote? | ledger |
|---|---|---|---|---|
| **0088** Agent Runtime Modes (umbrella) | child SIP-0089 (v1.1.0) | children SIP-0090 Phases 2–4 and SIP-0091: **unplaced**. The ROADMAP said "target set with the 1.9 and 2.0 plans"; neither did | no: **3.x** (Q7) | added 2026-10-04 |
| **0090** Agent Embodiment Substrate | Phase 1 (v1.2.0), less budget persistence and composition-root wiring | Phases 2–4 and the two Phase-1 deferrals: **deferred to 3.x** (§18a records the deferrals) | no: 3.x | added |
| **0091** Duty Durability via Temporal | nothing | Phases 1–4: **deferred to 3.x**, its engine re-decided at 3.0. SIP-0109 met campaign durability with a Postgres control log, outbox and sweep instead | no: 3.x | added |
| **0092** Implementation Plan Improvement | M1 typed acceptance (v1.1.0); M2 via SIP-0093 (v1.1.0); the M2→M3 gate passed (2026-08-05) | M3 **dropped**; M1's divergences recorded (§14a) | after SIP-0093 closes | added |
| **0093** Multi-Role Plan Authoring | 93.0–93.3 (v1.1.0) | 93.4 → #950; rules 2–5 **dropped**; fan-out amended to sequential (§15a) | **yes**, at the next sweep | added |
| **0101** Cycle Replay Harness | slices 1–3 (v1.5.0); Prefect replay tags (v1.9.0) | slice 4 **dropped**; slice 5 with the next console work; §4.1's test #1974 (2.1.0); 1.9's finding recorded (§11a) | after #1974 | added |
| **0102** Ephemeral Application Sandbox | steps 1, 2 and 4, plus the clean-room audit (v1.4.0); §11a; §11b (v1.8.0) | steps 3, 5, 6, 7 **unplaced, deliberately**; in-agent execution ruled the accepted path (§11c) | no: waits for a clean-room requirement | added |
| **0105** Stack Blueprint Contract | the contract and S5 admission gate (1.6); A1 packaging (v1.8.0); stack #1 extracted (v1.7.1) | fields deleted by #1975 (2.1.0); #1967 (2.1.0); packs to a successor; `check_stack` split unplaced, deliberately (§A2) | after #1975 and #1967 | added |
| **0109** Campaign Orchestration (2.0 headline) | §18 steps 1–8, **v2.0.0**; the set read PASS (§24at); the runbook's second half (#1997) and the digest's renderings (#1998) | **#1710:** closed at the cut: the evolution screenshots ship in the 2.0.0 release package; the squad's first pass is dropped (Q24). **2.1.0:** #1824, #1884, #1934, #1950, #1961, #1962, #1995, #1692, #1940, #1954, #1956, #1959, #1960, #1971, #1972, #1973. **2.2.0:** #1708's remainder. §24b–§24i ratified (§24as) | no: its 2.1 parts are open; §24at is the consolidated status record | added |
| **0110** Cross-Cycle Memory (2.2 headline) | the inert recall port and its call site (2.1.0, #2058) | **the re-read:** 2.1.0, #1964, the evidence to the final deploy in §5b, the cut set's readings added at the cut. **2.2.0:** Phase 1 in four slices (#2105 capture, #2106 replay, #2096 mechanism, #2107 the template and the measurement window), built to §0's normative contract and measured before the cut (shape B). Revision 6 makes the cycle Phase 1's unit: every eligible cycle observed, four consuming seams (plan writing, build authoring, repair, proposal writing), app-build indicators observed beside each exposure, its records stored in Postgres beside the cycle registry (D13), correction rounds sorted by failure shape with a repeat report (D14), lessons drafted by a frontier-model auditor and approved by the owner (D15), the proposal behavior measured first, and no claim about the built application. Phase 1.5 is folded into Phase 1. Phase 2: **unplaced**, until the owner's ruling on the finding (§0.13). **Entry points for chat and task assignment:** proposed 2026-10-09 (`SIP-Memory-Entry-Points`, epic #2173), landing here on acceptance (§5f); placement is Q25 | no: Phase 1 is 2.2's | added 2026-10-04; revisions 4 and 5 2026-10-06; revision 6 2026-10-07 |

**Implemented SIPs promoted with open items.** Each needs a text amendment, not a status change. The
items go to each SIP's next touch, with Q22 for the decisions.

| SIP | open item | tracked by |
|---|---|---|
| 0089 Agent Runtime State | the `queued` FocusLease outcome, in the SIP and not built; deferred only in a plan (D20) | nothing |
| 0103 Squad-Authored Manifest | the §3.3 row is stale (built by PR #1457; #820 closed); §5c.5 operator-edit record and §5c.3 blueprint-owned manifest are unplaced | nothing |
| 0096 Verification Evidence Integrity | §17a says both "built" and "Not built" (l.288) | nothing |
| 0086 Build Convergence Loop | correction-budget allocation | #414 (2.1.0, ruled: the priority reserve) |
| 0108 Cycle Evaluation Scorecard | the topology window; the Free-Solo successor; clean-room indicators wait on SIP-0102 step 5 | partly: #1824 (2.1.0) |
| 0106 Atlas Provider Adapter | provider-aware routing and a per-generation throughput record, to "a successor SIP" (none) | nothing |
| 0097 Executor Decomposition | the post-arc rename of `DispatchedFlowExecutor` | nothing |
| 0070 Pulse Checks | Tiers 2–3 "to a follow-up SIP" (≈ SIP-0109 accumulated acceptance; ≈ #557) | partly |
| 0104 Deterministic Verification Scaffolding | §13d (2026-10-09): a failing slot assertion is routed by demonstrated defect ownership, not by its location; unplaced, after SIP-0110's window | #2153 |
| 0083 Multi-Run Cycles | `returned_for_revision` "deferred", since built (#811, SIP-0109): the text is stale | — |
| 0085, 0077, 0074, 0075, 0048 | console and event v1 deferrals, all low priority | nothing |

---

## 2. Proposed SIPs (30 at the audit; 13 deprecated 2026-10-05 by Q14; 16 live after Cross-Cycle Memory's acceptance as SIP-0110, 2026-10-06)

Class: **live** (wanted, not built), **partly absorbed** (some built or owned elsewhere),
**superseded**, **stale** (names architecture or releases that no longer exist).

| proposal | class | placement it states | action |
|---|---|---|---|
| Outcome Evaluation (PR #1963) | live | instruments 2.3; feature half heads 2.4 | Q1, Q3 |
| Memory Entry Points (epic #2173; drafted 2026-10-09 on the owner's direction) | **accepted 2026-10-09 and absorbed into SIP-0110** (§5g, Appendix A); the proposal file is **deprecated** with a pointer there | 2.3.0 (#2174, #2175, #2176), 2.4.0 (#2177–#2183), 2.5.0 (#2184): SIP-0110's ledger | Q25–Q29, ruled |
| TensorFold Provider Adapter (drafted 2026-10-09 on the owner's direction) | live; extends SIP-0106 (a third candidate engine behind `LLMPort`) | unplaced; recommended: gates G0–G2 on the 2.3 line, dark, after the 2.2 cut; G3–G4 on evidence | its §8 Q1–Q5 |
| Verification Yield | partly absorbed | ledger 2026-10-04: #1960 (2.1), #1965 (crew, 2.1 window), #1966 (after memory) | done 2026-10-04 |
| Test-First Verification | partly absorbed | greenfield gate #1978 (2.6) | ruled |
| Campaign Self-Improvement and Test Bay (`SIP-Campaign-Self-Improvement-and-Test-Bay-Requirements`) | partly absorbed | its own 10-01 note supersedes its targets | Q6 |
| Capability-Backed Agents | **deferred to 3.x**; premise to correct (#400/#401) | 3.x | ruled |
| Agent Embodiment Runtime | **deferred to 3.x** | 3.x | ruled |
| Duty Continuity and Handoff Ledger | **deferred to 3.x** | 3.x | ruled |
| Continuum Runtime Console | partly absorbed; duty view **deferred to 3.x** | 3.x | ruled |
| Edge Deployment Profile | **deferred to 3.x** | 3.x | ruled |
| Post-Retest Governance Acceptance Review | live | #557, after Outcome Evaluation (2.4 or later) | ruled |
| Design Decision Register | live; targets stale | rungs in 1.6.x/1.8; rung 1 is #1031 (2.1) | Q12 |
| Fine-Grained Issue Enumeration | partly absorbed (vision) | none | keep as vision; fix its stale SIP names |
| LLM Emission Contracts | partly absorbed; targets stale | P1–P3 in 1.5 | Q10 |
| Agent Comms Delivery Guarantees | split | #1977 (2.3.0); duty-gated parts 3.x | ruled |
| Cycle Request Profile Naming Taxonomy | live; inventory stale | **2.3.0** via #316 (moved from 2.1.0, 2026-10-05: the 2.1 plan's ruling 14) | Q13 |
| Planning Sequence Strategy-First | live (greenfield only); details stale | none | an outer-loop experiment candidate |
| API Contract Hardening | partly absorbed; residue in #1976 | pre-1.0 | **deprecated** 2026-10-05 (#2023, Q14) |
| Experiment Queue and Cycle Assessment | superseded (by SIP-0108 and SIP-0109) | v1.1/v1.2 | **deprecated** 2026-10-05 (#2023, Q14) |
| QA-First Test Strategy (`IDEA-QA-First-Test-Strategy-1h-Cycles-group_run`) | superseded; contradicts SIP-0109 §8.2 | none | **deprecated** 2026-10-05 (#2023, Q14) |
| Skill Layer for Capabilities | superseded (into Capability-Backed Agents §21, which cites its post-mortem) | none | **deprecated** 2026-10-05 (#2023, Q14) |
| Version Bump Hardening | superseded (#1089, #336, #789, #1061); residue → #1957 | none | **deprecated** 2026-10-05 (#2023, Q14) |
| Intelligent Delegation Protocols | superseded; residue → Capability-Backed Agents §15 | none | **deprecated** 2026-10-05 (#2023, Q14) |
| SIP-0012, 0013, 0016, 0018, 0018-v2, 0023, 0028 (numbered warm-boot drafts in `proposed/`) | stale | 2025 | **deprecated** 2026-10-05 (#2023, Q14); two shared the number 18 |

---

## 3. Where documents overlap, and the boundary each gets

| cluster | members | the point of overlap | boundary |
|---|---|---|---|
| 1. the campaign objective's measurement | SIP-0109 §10 row 3; Outcome Evaluation §4.7; SIP-0108; #1960 | what "the measurement is met" reads | SIP-0109 owns the decision table; Outcome Evaluation extends it **by a SIP-0109 amendment**; SIP-0108 stays per-cycle; #1960 is a projection, never a decision input |
| 2. "outcome" and composite scores | SIP-0108 (an *outcome* dimension: verdict and criteria); Outcome Evaluation (outcome = independent scenarios); Experiment Queue; the Nostromo IDEA | one word, two meanings; whether there is one number | no composite anywhere; **one of the two "outcome"s is renamed before Outcome Evaluation's phase 1** (Q3) |
| 3. curated evaluation corpora | Test Bay fixtures; Outcome Evaluation's held-out scenarios; Verification Yield's fault corpus (#1965); SIP-0108's benchmark registry; replay records; the reference scenario | where versioned evaluation assets live, who writes them, who may read them | one storage and versioning discipline (content-addressed, like verifier bundles); different readers: scenarios held out, faults injected by the crew, benchmarks visible |
| 4. who owns the qa test-value rule | Verification Yield; Test-First Verification; SIP-0109 §8.2; `TEST_QUALITY_STANDARD.md`; the QA-First file; #1884 | what makes a squad-authored test acceptable | already stated in Verification Yield's header: contract requirements govern; Verification Yield measures; Test-First enforces for greenfield. Open: who owns #1884's class |
| 5. independence of verification | Test-First (stub); §8.2 (baseline overlay); Outcome Evaluation (held-out); Post-Retest Review (fail-closed LLM); Verification Yield §36; Design Decision Register | each attacks "the squad's own green proves nothing" from a different side | complementary: deterministic first; LLM judgement only fail-closed; Outcome Evaluation's scenarios are the shared escape detector the others are measured by |
| 6. framework self-improvement | Test Bay (L0–L6); Experiment Queue; the Nostromo IDEA; Outcome Evaluation §5 | who proposes and ratifies framework changes | **ruled:** the squad does not improve the framework; the crew proposes, the owner ratifies. Test Bay's L6 conflicts if kept (Q6) |
| 7. memory | Cross-Cycle Memory; Memory Entry Points; SIP-0085's chat memory; SIP-042's agent store; SIP-0021; Capability-Backed Agents §11; Test Bay §12.7; Design Decision Register §5; Embodiment Runtime; Duty ledger | the memory model's scopes, lifecycle and first payload; and, since 2026-10-09, chat's and task assignment's way in | Cross-Cycle Memory owns them (the ROADMAP already says it is the substrate). The others defer or become candidate payloads (Q4). **Memory Entry Points lands in Cross-Cycle Memory on acceptance,** so there is one memory SIP: it adds record kinds and a context-assembly port, and changes no lesson rule. SIP-0085 keeps chat's transport and persistence; its §10 memory, SIP-042's per-agent store and SIP-0021's patterns are superseded (SIP-0110 §5f) |
| 8. the agent model, runtime and duty | Capability-Backed Agents; Skill Layer; Embodiment Runtime; Duty ledger; Continuum console; Edge; SIP-0088, 0090, 0091 | none of it placed in 2.x; three workflow engines in play (Prefect; Temporal planned; n8n proposed) | one decision on whether duty work enters 2.x, which orders the rest (Q7, Q8) |
| 9. judgement steps in correction and framing | Post-Retest Review (#557); Design Decision Register; #949; #950; #1708's auto tier | all land in 2.2 beside memory | one fail-closed rule, stated once; the sequence inside 2.2 is Q2 |
| 10. emission and revision | LLM Emission Contracts; SIP-0107 §27; #567; #1756 | who types the response vs which tree it may represent | already written in SIP-0107 §27; Emission Contracts records P4 as SIP-0107's and P3 as #567's (Q10) |
| 11. profiles, framing order, the calibration yardstick | the profile taxonomy (#316); Planning Sequence; Test-First; SIP-0109's pinned definitions and calibration | anything that renames a profile or changes greenfield framing moves the outer loop's baseline | pinned definitions keep resolving old names indefinitely; greenfield changes land between campaigns, with calibration before and after (Q13) |
| 12. deployment and transport | SIP-0028; Edge; Comms Delivery Guarantees; SIP-0081 | environment profiles, remote nodes | SIP-0081 owns profiles; Edge owns remote nodes if kept; Comms owns delivery semantics only |
| 13. decision records | SIP-0012; Design Decision Register; #950; #1031 | where design decisions are recorded | the Design Decision Register, or #950, is the home (Q12) |

---

## 4. Reconciliations: ruled 2026-10-04

The owner's words: "yes, move them to 3.x including capability-backed agents. I accept all your other
recommendations to keep SIPs current, reflecting what gets delivered, and where the work is targeted."
Each ruling is recorded in the SIPs it changes, as a ledger row and, where it decides something, a
dated amendment.

| # | decision | ruled | recorded in |
|---|---|---|---|
| Q1 | what 2.4 is | Outcome Evaluation's feature half heads 2.4, with #1966 riding on it. The squad-authored backlog is 2.6, with its own SIP to draft | SIP-0109 §24as; the ROADMAP horizon; Outcome Evaluation's intake note |
| Q2 | 2.2's load | memory is 2.2's only change to squad behaviour, with #1708's auto tier and queue beside it. #557, #949 and #950 follow Outcome Evaluation (2.4 or later) | SIP-0109 §24as; Cross-Cycle Memory and Post-Retest Review notes; issue comments |
| Q3 | Outcome Evaluation's amendment, fit and name | §4.7 lands as a SIP-0109 amendment; phase 1 fits 2.3; it renames its term, and SIP-0108's *outcome* stays | Outcome Evaluation's intake note |
| Q4 | memory ownership | Cross-Cycle Memory owns scopes, lifecycle and payload | Cross-Cycle Memory and Capability-Backed Agents notes |
| Q5 | Capability-Backed Agents | **3.x**, its premise corrected before 3.0's plan | its note |
| Q6 | Test Bay | deprecated after re-homing, once #1968 lands | its note |
| Q7 | the runtime-mode family | **3.x**: SIP-0088, 0090 Phases 2–4 with its Phase-1 deferrals (§18a), and 0091 (engine re-decided at 3.0) | their ledgers; SIP-0090 §18a; the ROADMAP |
| Q8 | duty work | **3.x**: Embodiment Runtime, the Duty ledger, the Continuum console's duty view, Edge | their notes; the ROADMAP |
| Q9 | Comms Delivery Guarantees | split: general hardening #1977 (2.3.0); duty-gated parts 3.x | its note |
| Q10 | LLM Emission Contracts | P3 → #567 (2.1), P4 → SIP-0107, P1/P2 unplaced | its note |
| Q11 | Test-First's greenfield gate | #1978 (2.6) | its note |
| Q12 | Design Decision Register | folds into #950 | its note |
| Q13 | taxonomy aliases | old profile names resolve indefinitely; written into #316 | its note; #316 |
| Q14 | deprecations | **done 2026-10-05 (#2023):** the 13 in §2 (the "12" counted SIP-0018's two drafts as one), after #1968; #1976 holds API Contract Hardening's residue, and Capability-Backed Agents cites the Skill Layer's post-mortem | the notes; §2 |
| Q15 | SIP-0104 | §10.2 read as met; **promoted at the v2.0.0 sweep** | SIP-0104 §13c |
| Q16 | SIP-0107 | §15 dropped; §9.4 declared without a producer; **promoted after the v2.0.0 tag**; #1727 follows as an amendment | SIP-0107 §46t |
| Q17 | SIP-0109 | §24b–§24i ratified as written. Unplaced items: #1971, #1972, #1973 (2.1.0); packaging changes and the GPU check unplaced, deliberately; the builder-tail question dropped. A consolidated status amendment at the cut | SIP-0109 §24as |
| Q18 | SIP-0092 / SIP-0093 | M3 dropped, M1's divergences recorded; 93.4 and its tests fold into #950, merge rules 2–5 dropped, fan-out sequential | SIP-0092 §14a; SIP-0093 §15a |
| Q19 | SIP-0101 | 1.9's finding recorded; slice 4 dropped; slice 5 with the next console work; §4.1's test is #1974 (2.1.0) | SIP-0101 §11a |
| Q20 | SIP-0102 | in-agent execution is the accepted path for campaign evaluation; steps 3, 5, 6 and 7 unplaced until a clean-room requirement returns | SIP-0102 §11c |
| Q21 | SIP-0105 | the table brought current; fields deleted by #1975 (2.1.0); packs to a successor; #1967 | SIP-0105 §A2 |
| Q22 | implemented SIPs' stale text | corrected in SIP-0103, 0096, 0083 and 0089 (the `queued` lease → 3.x) | each SIP's dated amendment |
| Q24 | #1710's "squad's first pass" (who writes a campaign's first reading at its close) | **dropped**: the owner chose it at the v2.0.0 cut; the digest and package carry the close | SIP-0109's ledger and §24at; #1710 |
| Q23 | the `capabilities` package name (the structure audit, ruled the same day: "go ahead, file them and add to the 2.1 plan, plus the 2.3 recommended items") | the package keeps its name; Capability-Backed Agents takes a distinct package, and packs never bind into the task-type registry | Capability-Backed Agents' note; #1993 |

**Two readings the supervisor made, told to the owner when they were recorded:**
- **§24b–§24i are "ratified as written".**
- **SIP-0093's remainder is split:** 93.4 folds into #950, and merge rules 2–5 are dropped.

**Preventing drift** (the owner asked how):
- **#1969:** the guard, extended to stale targets and the deferred state;
- **#1979:** `sip:NNNN` labels, with closure requiring the ledger;
- **#1980:** the cut's sweep script;
- **#1981:** the template and the intake check.

All four are placed early in 2.1.0.


### Ruled 2026-10-09: Memory Entry Points

The owner's words: "accept 2185 with Q25–Q29 as drafted". Each ruling is recorded in SIP-0110 §5g and Appendix A §A.8.

| # | decision | ruled (as drafted) | recorded in |
|---|---|---|---|
| Q25 | where the entry points land | **2.4, beside Outcome Evaluation's feature half** (Q1 gave 2.4's head to it). The relationship is one-way: Outcome Evaluation supports application-quality claims about memory; it is not required to deliver the entry points, and its delivery is not blocked by them. The alternative: 2.6, beside the squad-authored backlog. The legacy store's retirement follows in the next stabilization release either way | SIP-0110 §5g, §A.6; the ROADMAP horizon |
| Q26 | #2171 (no agent can write its legacy store) | **closed as not planned:** the embedding path is not restored; its live defect, the silent failure, is #2174's (2.3) | SIP-0110 §5g, §A.4.5; #2171, closed |
| Q27 | who holds `memory:note` and `memory:instruct` until a membership model exists | admins only | SIP-0110 §5g, §A.3.3 |
| Q28 | chat beyond joi | not required; a config flag | SIP-0110 §5g, §A.8 |
| Q29 | conversation-history retention | set before #2180 ships | SIP-0110 §5g, §A.8 |

---

## 5. Housekeeping found by the audit

- **No tool path to deprecate a proposed SIP.** `update_sip_status.py` allows only `proposed → accepted`
  (#1968).
- **Numbered SIPs sit in `sips/proposed/`**, and two share the number 18 (`registry.yaml:174,183`).
- **The ROADMAP's SIP rows drifted:** Campaign listed as unnumbered, 10 accepted instead of 11, and
  "Embodiment Runtime … still to be drafted". Corrected in the PR that adds this file.
- **The S5 admission gate cannot see a string field empty on one stack** (#1967). SIP-0109's
  `render_profile` and `unset_optional_response` pass it without a recorded reason.
- **A guard for this file and the ledgers** (#1969): every accepted SIP has a `Delivery ledger`, every
  placed row names an open issue, and this file lists every live SIP.

---

## 6. Intake log

| date | item | finding | where recorded |
|---|---|---|---|
| 2026-10-01 | Verification Yield (the owner's draft) | overlaps Test-First Verification (its mechanism for greenfield) and SIP-0109 §8.2 (which governs where they meet) | its placement note |
| 2026-10-04 | Outcome Evaluation (from the owner's idea) | **overlaps** SIP-0109 §10 row 3 (cluster 1), SIP-0108's "outcome" (cluster 2) and the corpora (cluster 3); **complements** Verification Yield (cluster 4) | its §3; Q1, Q3 |
| 2026-10-04 | Verification Yield, re-reviewed | its remaining parts placed: #1960, #1965, #1966 | its ledger |
| 2026-10-04 | the Nostromo crew's enablers (#1959, #1960) | phase 0 of Outcome Evaluation; #1959 generalizes SIP-0109's reference launcher | the 2.1 plan §2.0 |
| 2026-10-04 | Cross-Cycle Memory's 2.1 part (#1964) | placed by the owner's ruling of 2026-09-12, missed in the 2.1 plan's first draft | the 2.1 plan §2.6 |
| 2026-10-04 | the owner's rulings on the whole queue (§4) | runtime modes, duty work and Capability-Backed Agents to 3.x; every other recommendation accepted | §4; each SIP; the ROADMAP horizon |
| 2026-10-04 | the code structure audit (not a SIP) | **one conflict:** Capability-Backed Agents (3.x) reserves the word *capability*, and the 32k-line package still carries it (Q23). **Complements:** #1985's direction guard and #1989's architecture map are the code's version of #1969's ledger guard; #1986's single gate recorder is the seam #1940 and #1708's auto tier decide through | Q23; the 2.1 plan §2.8 |
| 2026-10-06 | SIP-0110's revision 4, the Phase-1 re-read (accepted with it) | **overlaps** the Design Decision Register: the recurring unresolved design questions are decision records, the register's proposed payload (its §5), not Phase 1's. Boundary: memory owns the substrate (Q4), and a decision-record payload arrives with the register's home (#950, Q12). **Overlaps** #1708's auto tier (SIP-0109), which reads the same proposal ledger: an auto-approved proposal is never classified. Sequenced by the 2.2 plan. **Builds on** SIP-0109 §9.2 (the within-cycle rung) and §9.4 (the class vocabulary). No conflict | SIP-0110 §5b; the Design Decision Register's header; the 2.2 plan |
| 2026-10-06 | an external design review of SIP-0110 revision 4 and the 2.2 plan (adopted as revision 5) | no new overlap. It sharpens three existing boundaries: SIP-0109 owns the ruling events, the snapshot's admission point, gate authority and the escalation queue; SIP-042 owns storage; the Design Decision Register owns decision payloads. SIP-0110 §0.14 states them as a table. No conflict | SIP-0110 §0, §5c; the 2.2 plan |
| 2026-10-07 | SIP-0110's revision 6, which restores the cycle as Phase 1's unit (the owner: "this is cross cycle memory; not cross campaign memory") | no new overlap. It touches three existing boundaries. **The cycle registry and the correction loop** (SIP-0064, SIP-0067, SIP-0086) own the records memory now also reads: gate decisions and correction rounds, read as projections, never written. **SIP-0109** keeps the campaign's admission point, and a standalone cycle's creation pins its own snapshot. **#1708's auto tier** decides plan reviews, so an active tier changes the plan-review corpus. That is sequenced by the 2.2 plan's D3: the tier activates after the window. **Build authoring as a seam** meets two existing inputs to the build authors. **SIP-0109's prior-cycle brief** (#1692, §10a) hands a retry's authors the failed cycle it continues: one lineage, as recorded, unreviewed. Memory supplies reviewed, approved lessons from any earlier unit, in a separate slot. **The manifest's surfaces** carry facts about the application, and memory carries none (SIP-0110 §11). **Storage** (the 2.2 plan's D13) changes a boundary the 2026-10-06 row records: Phase 1's four records are stored in Postgres beside the cycle registry, behind their own port, and SIP-042's `MemoryPort` stays each agent's own store, used today by console chat (SIP-0110 §0.8, §0.14). SIP-042 has no document in `sips/`, so the boundary is stated here and in SIP-0110. **The auditor** (D15) follows theme 6's ruling: a frontier model drafts each lesson (the supervisor until the crew is commissioned), the owner approves, and the squad's own model drafts none. It is the outer loop's work, not a squad role, so it is not the Campaign Self-Improvement draft's Memory Librarian (its §12.7), which defers to SIP-0110 (§11). **The failure-shape sorter** (D14) extends the test runner's per-runner message tables (`capabilities/handlers/test_runner.py`, #626, #1130), which SIP-0105 names as a stack declaration (per-runner output signatures). It names target behaviors beneath the attribution registry's classes and never maps to them (SIP-0108 §4.2), so it is not the parallel taxonomy SIP-0109 rules out. It reads the correction loop's records without changing them. **Outcome Evaluation** (instruments 2.3, feature half 2.4) is what a claim about the built application's quality needs; a claim about delivery reliability (repeated build failures, repair effort, delivery cost) waits for no later feature, and #557, #949 and #950 are not memory's dependencies (SIP-0110 §0.13). No conflict | SIP-0110 §0, §5d; the 2.2 plan |
| 2026-10-09 | Memory Entry Points (the owner's direction: one memory architecture for chat and task assignment, execution its driver) | **overlaps** Cross-Cycle Memory entirely, by design: it lands there on acceptance (Q4), extends its store, snapshot, exposure and recall policy, and changes no lesson rule. **Overlaps** SIP-0085 (chat keeps its transport and persistence; its §10 memory is superseded, and its history, never wired, is #2175), SIP-0089 (its `Assignment` is a duty window, so the new record is a *task instruction*), SIP-0109 (gate notes, §24ad answers and proposal notes stay authoritative where they are), SIP-0103 §5c.5 and #950 (a change to the manifest or a decision goes through its owner; memory only references it), and Outcome Evaluation (an application-quality claim needs its scenarios). **Conflicts:** Q1's 2.4 placement (Q25) and #2171 as filed (Q26) | the draft's header; SIP-0110 §5f; SIP-0085's and SIP-0021's notes; §4's open queue |
| 2026-10-09 | Memory Entry Points, revision 2 (the owner's review of revision 1) | **two new overlaps, no conflict.** **SIP-0109's escalation queue** (#1708, §24bj): a task held for an incomplete binding context is escalated through it in a campaign, as a held gate is; SIP-0109 keeps the queue and its authority. **SIP-0073's model context registry** supplies the window a task's total prompt budget is read from. The other changes stay inside the draft and SIP-0110: binding instructions hold dispatch; `lessons: disabled` (today's "memory disabled") keeps instructions identical across arms, and a broader removal is a named experiment; a task instruction's work target is apart from its snapshot owner; emergency withdrawal restarts with corrected bindings; session ownership and provenance links are authorized. 2.2's experiment is unchanged | the draft's header and §3.3–§3.8; SIP-0110 §5f |
| 2026-10-09 | Memory Entry Points, revision 3 (the owner's review of revision 2) | **no new overlap, no conflict.** **SIP-0109's control log** (an existing overlap) gains a record kind: re-binding a running campaign is recorded there and needs `campaigns:supervise`; SIP-0109 keeps the log and the authority. **SIP-0110 §0.8 step 6** (inside the landing SIP) gains one recall input, an effective lesson budget, the smaller of the snapshot's and what binding instructions leave after the lesson slot's framing; it equals the snapshot's whenever they leave room, and always in 2.2. The other changes stay inside the draft: a reference is bound to a concrete revision with its instruction, never at dispatch; a hold on a pinned project instruction is released by an authorized re-binding (forward or restart), never by a revision alone; budgets are applied once, where records are chosen. T8 extended; T10 restated; T16 and T17 added | the draft's revision 3 note; SIP-0110 §5f |
| 2026-10-09 | Memory Entry Points, accepted (the owner: "accept 2185 with Q25–Q29 as drafted") | **both conflicts resolved:** Q25 places the entry points in 2.4 beside Outcome Evaluation's feature half (one-way relationship), and Q26 closes #2171 as not planned. The design is absorbed into SIP-0110 as §5g and Appendix A, with eleven ledger rows placed in 2.3.0, 2.4.0 and 2.5.0, each issue labelled `sip:0110`; the proposal file is deprecated with a pointer there (the absorbed-proposal precedent of §2) | SIP-0110 §5g; §4's ruled table |
| 2026-10-09 | TensorFold Provider Adapter (the owner's direction: plug in TensorFold for its decode rate) | **overlaps** SIP-0106 entirely, by design: one more adapter behind its seam, under its gates, conformance suite, dark-ship rule and A/B protocol; Atlas's and vLLM's negatives are its evidence. **Overlaps** SIP-0110 (the 2.2 window pins the engine, so nothing runs on the Spark until it closes; the capture corpus is the trial's instrument; an engine change is a listed-input change and re-checks the lesson), SIP-0073 (a registry entry with family `qwen3.8`, or the lesson silently stops applying), SIP-0109 §24an (the quiet-box launch rule reads resident models) and #1177/#1178 (one engine resident at a time). **Conflicts:** placement in 2.3, a feature-free stabilization line, needs SIP-0106 §4.3's even/odd waiver (its Q1) | the draft's header |
