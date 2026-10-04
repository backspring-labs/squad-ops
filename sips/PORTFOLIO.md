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

## 1. Accepted SIPs (11)

| SIP | shipped | remaining, and where it is placed | promote? | ledger |
|---|---|---|---|---|
| **0088** Agent Runtime Modes (umbrella) | child SIP-0089 (v1.1.0) | children SIP-0090 Phases 2–4 and SIP-0091: **unplaced**. The ROADMAP said "target set with the 1.9 and 2.0 plans"; neither did | no: queue Q7 | added 2026-10-04 |
| **0090** Agent Embodiment Substrate | Phase 1 (v1.2.0), less budget persistence and composition-root wiring | Phases 2–4 and the two Phase-1 deferrals: **unplaced** (the deferrals are recorded only in a commit message) | no: Q7 | added |
| **0091** Duty Durability via Temporal | nothing | Phases 1–4: **unplaced**. SIP-0109 met campaign durability with a Postgres control log, outbox and sweep instead | no: Q7 (keep or deprecate) | added |
| **0092** Implementation Plan Improvement | M1 typed acceptance (v1.1.0); M2 via SIP-0093 (v1.1.0); the M2→M3 gate passed (2026-08-05) | M3 plan changes: **unplaced**. M1's divergences from the spec are unamended | no: Q18 | added |
| **0093** Multi-Role Plan Authoring | 93.0–93.3 (v1.1.0) | 93.4 and §5.8 merge rules 2–5: **unplaced**. The sequential fan-out diverges from §5.11, unamended | no: Q18 | added |
| **0101** Cycle Replay Harness | slices 1–3 (v1.5.0); Prefect replay tags (v1.9.0) | slice 4 (compatibility policy) and slice 5 (console, AC 9): **unplaced**. §4.1's replay-exclusion test is possibly unmet. 1.9's restore limit is unrecorded | no: Q19 | added |
| **0102** Ephemeral Application Sandbox | steps 1, 2 and 4, plus the clean-room audit (v1.4.0); §11a; §11b (v1.8.0) | steps 3, 5, 6 and 7, the browser probe and `expose_application`: **unplaced**. SIP-0109 runs evaluation and rendering in the qa agent container instead, and SIP-0102 does not record it | no: Q20 | added |
| **0104** Verification Scaffolding | P0–P5 (v1.6.0); the P6 window ruled complete (2026-08-17) | stack #1 parity **dropped** (#1122, not planned); the §10.3 economics metric is *unverified* | **yes**, with an amendment, after the owner's reading of §10.2: Q15 | added |
| **0105** Stack Blueprint Contract | the contract and S5 admission gate (1.6); A1 packaging (v1.8.0); stack #1 extracted (v1.7.1) | packs, the `check_stack` split (its "1.7" deferral missed) and deleting the four falsified fields: **unplaced**. The S5 gate cannot see a string field empty on one stack (#1967) | no: Q21 | added |
| **0107** Scoped Code Revision | steps 1–6 (v1.8.0); step 7, the flip (#1909, ships in **2.0.0**) | §20 on the re-take path: **2.1.0, #1727**. §15 scope requests and regrant, and §9.4's fallback-authority producer: **unplaced, unamended** | after the 2.0.0 tag, with two amendments: Q16 | added |
| **0109** Campaign Orchestration (2.0 headline) | §18 steps 1–8 on main (**2.0.0**, untagged) | **2.0 cut:** #1710, #1711. **2.1.0:** #1824, #1934, #1950, #1961, #1962, #1692, #1940, #1954, #1956, #1959, #1960. **2.2.0:** #1708's remainder. **Unplaced:** eight items (its ledger). §24b–§24i are "not yet ruled" | no: the set is open, then Q17 | added |

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
| 0083 Multi-Run Cycles | `returned_for_revision` "deferred", since built (#811, SIP-0109): the text is stale | — |
| 0085, 0077, 0074, 0075, 0048 | console and event v1 deferrals, all low priority | nothing |

---

## 2. Proposed SIPs (30, with Outcome Evaluation on PR #1963)

Class: **live** (wanted, not built), **partly absorbed** (some built or owned elsewhere),
**superseded**, **stale** (names architecture or releases that no longer exist).

| proposal | class | placement it states | action |
|---|---|---|---|
| Outcome Evaluation (PR #1963) | live | instruments 2.3; feature half heads 2.4 | Q1, Q3 |
| Verification Yield | partly absorbed | ledger 2026-10-04: #1960 (2.1), #1965 (crew, 2.1 window), #1966 (after memory) | done 2026-10-04 |
| Test-First Verification | partly absorbed; target stale | "after the SIP-0104 P6 window" | Q11 |
| Campaign Self-Improvement and Test Bay | partly absorbed | its own 10-01 note supersedes its targets | Q6 |
| Cross-Cycle Memory | live | **2.2** headline; its 2.1 part is #1964 | Q2, Q4 |
| Capability-Backed Agents | live, unplaced; premise partly stale (the skills layer it extends was deleted, #400/#401) | 2.0, deferred by 2.0 decision 5 | Q4, Q5 |
| Agent Embodiment Runtime | live | "v2.2 era", which collides with memory's 2.2 | Q7 |
| Duty Continuity and Handoff Ledger | live, unplaced; target stale | "v1.2 candidate" | Q8 |
| Continuum Runtime Console | partly absorbed; target stale | "v1.2 candidate" | Q8 |
| Edge Deployment Profile | live in concept; design stale in parts | none | Q8 |
| Post-Retest Governance Acceptance Review | live; target stale | "1.6+"; placed **2.2** via #557 | Q2 |
| Design Decision Register | live; targets stale | rungs in 1.6.x/1.8; rung 1 is #1031 (2.1) | Q12 |
| Fine-Grained Issue Enumeration | partly absorbed (vision) | none | keep as vision; fix its stale SIP names |
| LLM Emission Contracts | partly absorbed; targets stale | P1–P3 in 1.5 | Q10 |
| Agent Comms Delivery Guarantees | partly absorbed; target stale | "gate for Campaign"; 2.0 shipped without it, unrecorded | Q9 |
| Cycle Request Profile Naming Taxonomy | live; inventory stale | **2.1.0** via #316 | Q13 |
| Planning Sequence Strategy-First | live (greenfield only); details stale | none | an outer-loop experiment candidate |
| API Contract Hardening | partly absorbed | pre-1.0 | file the residue as issues, then deprecate (Q14) |
| Experiment Queue and Cycle Assessment | superseded (by SIP-0108 and SIP-0109) | v1.1/v1.2 | deprecate (Q14) |
| QA-First Test Strategy (the `IDEA-` file) | superseded; contradicts SIP-0109 §8.2 | none | deprecate or move to `docs/ideas/` (Q14) |
| Skill Layer for Capabilities | superseded (into Capability-Backed Agents §21) | none | deprecate once that SIP cites its post-mortem (Q14) |
| Version Bump Hardening | superseded (#1089, #336, #789, #1061); residue → #1957 | none | deprecate (Q14) |
| Intelligent Delegation Protocols | superseded; residue → Capability-Backed Agents §15 | none | deprecate (Q14) |
| SIP-0012, 0013, 0016, 0018, 0018-v2, 0023, 0028 (numbered warm-boot drafts in `proposed/`) | stale | 2025 | deprecate (Q14); two share the number 18 |

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
| 7. memory | Cross-Cycle Memory; Capability-Backed Agents §11; Test Bay §12.7; Design Decision Register §5; Embodiment Runtime; Duty ledger | the memory model's scopes, lifecycle and first payload | Cross-Cycle Memory owns them (the ROADMAP already says it is the substrate). The others defer or become candidate payloads (Q4) |
| 8. the agent model, runtime and duty | Capability-Backed Agents; Skill Layer; Embodiment Runtime; Duty ledger; Continuum console; Edge; SIP-0088, 0090, 0091 | none of it placed in 2.x; three workflow engines in play (Prefect; Temporal planned; n8n proposed) | one decision on whether duty work enters 2.x, which orders the rest (Q7, Q8) |
| 9. judgement steps in correction and framing | Post-Retest Review (#557); Design Decision Register; #949; #950; #1708's auto tier | all land in 2.2 beside memory | one fail-closed rule, stated once; the sequence inside 2.2 is Q2 |
| 10. emission and revision | LLM Emission Contracts; SIP-0107 §27; #567; #1756 | who types the response vs which tree it may represent | already written in SIP-0107 §27; Emission Contracts records P4 as SIP-0107's and P3 as #567's (Q10) |
| 11. profiles, framing order, the calibration yardstick | the profile taxonomy (#316); Planning Sequence; Test-First; SIP-0109's pinned definitions and calibration | anything that renames a profile or changes greenfield framing moves the outer loop's baseline | pinned definitions keep resolving old names indefinitely; greenfield changes land between campaigns, with calibration before and after (Q13) |
| 12. deployment and transport | SIP-0028; Edge; Comms Delivery Guarantees; SIP-0081 | environment profiles, remote nodes | SIP-0081 owns profiles; Edge owns remote nodes if kept; Comms owns delivery semantics only |
| 13. decision records | SIP-0012; Design Decision Register; #950; #1031 | where design decisions are recorded | the Design Decision Register, or #950, is the home (Q12) |

---

## 4. The reconciliation queue: owner decisions, most important first

Each has the supervisor's recommendation. The owner's rulings are recorded here and in the SIPs they
change.

| # | decision | recommendation |
|---|---|---|
| **Q1** | **What 2.4 is.** Outcome Evaluation's feature half, Verification Yield's risk-first adoption (#1966) and the squad-authored backlog (no SIP yet) all point at it | Outcome Evaluation's feature half heads 2.4, with #1966 riding on it (measured by its scenarios). The squad-authored backlog moves to 2.6 and gets its own SIP, drafted from Outcome Evaluation's phase-1 data |
| **Q2** | **2.2's load against the one-behaviour-change rule.** 2.2 holds memory, #557 (a new LLM step), #1708's auto tier and queue, and #949/#950. Several change squad behaviour | 2.2 makes **one** squad-behaviour change: memory. #1708's auto tier and queue (control plane, decided from the 2.0 ledger) can ride it. #557, #949 and #950 move after Outcome Evaluation's scenarios exist (2.4 or later), since those are what judge them |
| **Q3** | Outcome Evaluation's amendment, its 2.3 fit, and its name | Record §4.7 as a SIP-0109 amendment at acceptance. Phase 1 (instruments, reporting-only) fits 2.3. Outcome Evaluation renames its term (for example "scenario evidence" and "contribution"); SIP-0108's implemented *outcome* keeps its name |
| **Q4** | Who owns the memory model | Cross-Cycle Memory owns scopes, lifecycle and payload; Capability-Backed Agents §11 defers to it |
| **Q5** | Capability-Backed Agents' placement and stale premise | Correct its premise (the deleted skills layer). It stays unplaced, deliberately, until the duty decision (Q8) |
| **Q6** | The Self-Improvement / Test Bay anchor | Deprecate after re-homing: its campaign parts are SIP-0109's, experiments are the crew's (ruled), corpora are Outcome Evaluation's and Verification Yield's. Its L6 conflicts with the ruling |
| **Q7** | The runtime-mode family (SIP-0088, 0090, 0091) and Embodiment Runtime's placement | **Unplaced, deliberately**, until the duty decision. Fix the stale targets and paths now. Record SIP-0090's Phase-1 deferrals as an amendment. Consider deprecating SIP-0091 (Temporal was not the durability 2.0 needed). Embodiment Runtime drops "v2.2 era" |
| **Q8** | Whether duty work (the duty ledger, the Continuum console's duty view, Edge, the reselling pack) is on the 2.x path | Not before 2.6. Record it as one decision, so the cluster is unplaced together and visibly |
| **Q9** | Comms Delivery Guarantees' gate | Record that 2.0 shipped without it (Postgres outbox and sweep). Restate its trigger as external paid duty work, and place the residue (dedup, dead-letter queue, publisher confirms) as hardening in 2.3 |
| **Q10** | LLM Emission Contracts | Amend: P3 → #567 (2.1), P4 → SIP-0107. P1 and P2 unplaced |
| **Q11** | Test-First's greenfield red gate | It changes verdicts and the calibration cycle's verification, so it needs a feature release with calibration before and after. 2.6 by default, after Outcome Evaluation gives a baseline |
| **Q12** | Design Decision Register | Fold into #950's design, wherever #950 lands (Q2); its rung 1 is #1031 (2.1) |
| **Q13** | The profile taxonomy's aliases | Yes: pinned campaign definitions keep resolving old profile names indefinitely, written into #316's acceptance |
| **Q14** | Deprecations and their mechanics | Add a `proposed → deprecated` transition to `update_sip_status.py` (#1968), then deprecate the 12 candidates in §2, after filing API Contract Hardening's residue as issues |
| **Q15** | SIP-0104's promotion | Read §10.2 as met for the scaffold's mechanics: roll 6 failed on a fill literal and the repair path, outside the scaffold. Promote at the 2.0 cut's sweep, with the amendment its ledger lists |
| **Q16** | SIP-0107: §15 and §9.4 | Drop §15 (scope requests and regrant) by amendment: no live need appeared through 1.8–2.0. Declare §9.4's fallback authority without a producer, with that reason. Promote after the 2.0.0 tag; #1727 follows as a named amendment |
| **Q17** | SIP-0109 before promotion | Rule §24b–§24i (eight amendments marked "implementer's reading") as a batch. Place or drop the eight unplaced items in its ledger. A consolidated status amendment at the 2.0 cut replaces the 2.0 plan's §5a as the permanent record |
| **Q18** | SIP-0092 M3; SIP-0093's remainder | Drop M3 by amendment, citing SIP-0109's cycle-level plan evolution; amend M1's divergences. For SIP-0093, amend the sequential fan-out and fold 93.4 and merge rules 2–5 into #950, or drop them. Then promote both |
| **Q19** | SIP-0101 | Amend 1.9's restore limit. Drop slice 4 and place slice 5 with console work (unplaced). Add §4.1's replay-exclusion test, or record why declared membership discharges it. Then promote |
| **Q20** | SIP-0102 | Rule by amendment that in-agent execution is the accepted path for campaign evaluation, and record SIP-0109 §24n/§24p's divergence. Re-place or drop steps 3, 5, 6 and 7, noting that SIP-0108's clean-room indicators wait on step 5 |
| **Q21** | SIP-0105 | Refresh its "does not assert" table. Delete the four falsified fields (2.1 hardening, small). Move packs to a successor. Close the S5 gate's empty-string blind spot (#1967) |
| **Q22** | The implemented SIPs' stale text (§1's second table) | Amend each at its next touch. SIP-0103, 0096 and 0083 are factual corrections, safe to make without a ruling |

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
