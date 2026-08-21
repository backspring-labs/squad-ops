---
title: Design Decision Register
status: proposed
author: jladd
created_at: '2026-08-21T00:00:00Z'
---
# SIP: Design Decision Register

**Status:** Proposed (2026-08-21)
**Builds on:** SIP-0103 (Squad-Authored Manifest — the M2 `decisions[]` judgment record,
#783, is this SIP's foundation), SIP-0104 (deterministic scaffolding — the contract
derivation this SIP's linkage walks), #811 (framing revision loop — this SIP's actuator).
**Siblings:** #557 (post-retest governance review — the fail-closed judgment precedent this
SIP inherits), #950 (plan-gate review packet — the human-gate surface of the same data;
convergence proposed in §6).
**Forward hooks:** SIP-Campaign-Orchestration, SIP-Cross-Cycle-Memory (§5).

## 1. Summary

Make the squad's key design decisions a first-class, enumerated, challengeable register at
cycle scope — and give it three consumers: a **judgment-oriented review step** (an LLM can
challenge taste where deterministic gates can only check coherence), a **deterministic
failure→decision linkage** (when a build goes bad, the record points at the decision that
bit it), and — forward — a **campaign-level ledger** a continuation policy can act on
without inventing judgments from raw checks.

## 2. Motivation — two samples, one of each polarity

Both from the 48 hours before this draft:

- **Unenumerated and fatal.** V38 slot 6 (`cyc_cac1e479a462`): the manifest declared join
  `success_status: 201` — the first framing of either measurement arm to do so — as a bare
  endpoint field, not a decision entry. Nothing existed to challenge; no reviewer, human or
  agent, ever saw a *choice*. The dev built the 200 default, the contract enforced 201, and
  the roll died on it (dual attribution in `docs/plans/1-6-0-v38-window-record.md`).
- **Enumerated but unreviewed.** The 1.6.1 shakedown (`cyc_6b2de19a868e`): the manifest
  *did* record `leave-missing-participant → 400 validation_error` with a PRD warrant — and
  the owner's review of that entry ruled it a clear misuse (404 is the resource-lookup
  semantics; the error code itself is named as a lookup failure). Every deterministic gate
  passed it, correctly: it is coherent, winnable, warranted. It is merely wrong. The
  recorded decision axis ("400 vs *silent no-op*") also shows the authoring failure mode
  precisely: the conventional option never entered the author's frame.

The register concept is half-built: M2's `decisions[]` already carries id / choice /
warrant / unresolved-question entries. What is missing is (a) a rule for what MUST be
enumerated, (b) any reviewer of resolved entries, (c) any pointer back from failures, and
(d) any cross-cycle aggregation. The V38 window's per-roll attributions — framing-rooted
vs squad-side, done by hand for every red — are the manual labor this SIP industrializes.

## 3. Design

### 3.1 The register (hardened `decisions[]`)

The manifest's `decisions[]` becomes the canonical Key Design Decision register for the
cycle. Schema additions to each entry:

- `alternatives_considered` — the options actually weighed. The 400 sample's recorded axis
  ("vs silent no-op") demonstrates why: frame-narrowing is invisible unless alternatives
  are recorded, and a reviewer's cheapest question is "why not the convention?"
- `scope` — the endpoints/routes/files the decision governs (machine-readable; the
  linkage in §3.3 walks it).
- Existing fields unchanged: `id`, `choice`, `warrant`, `unresolved`/`question`.

**Mandatory-enumeration rule (the completeness half):** any deviation from the stack's
declared conventions (the conventions rubric shipped by the primer issue, this SIP's rung
1) MUST exist as a warranted register entry — an unwarranted deviation is a schema-gate
finding that returns the manifest for revision (#811). Conventional defaults need no
entry; the register stays short and every entry is, by construction, a real choice.

### 3.2 The review step (judgment, fail-closed)

A framing task after manifest authoring **and after the deterministic expansion** — the
reviewer sees the derived probes, shells, and briefs, the same view implementers get,
where design sins are concrete.

- **Role: strategy (nat)** — not the author. Self-review has a measured poor record
  (dev self-eval repeated an identical error three rounds; qa self-eval was 68% waste);
  a different role persona is the cheapest same-model-blind-spot mitigation. nat is idle
  in nearly every cycle today (0 completion tokens in most implementation runs).
- **Unit of review: the register entry**, judged against the same conventions rubric that
  taught the author (one asset, two consumers). Bounded scope by construction.
- **Authority: one-way, fail-closed — the #557 rule verbatim.** The reviewer may return
  the manifest for revision (the #811 loop: notes in, bounded re-author, unaffected prefix
  restored) or annotate findings onto the human gate. It may never approve past a
  deterministic red, never loosen a gate, never block beyond the attempts cap.
- **Findings are a typed artifact**: entry id, category (convention / coherence /
  completeness / risk), severity, warrant-assessment. Recorded, not buried — the 1.8
  scorecard's design-quality input.

**Introduction protocol — reporting-only first.** The step ships with no gate authority:
findings recorded, nothing returned, for a pre-registered observation window. Arming the
revision loop is a separate deliberate promotion, decided on the measured correlation
between findings and (a) downstream reds, (b) owner taste rulings (the 400 sample is
labeled datum #1). If it rubber-stamps, we learn that for a few thousand tokens per
framing. This is the house pattern (reporting-only through a window; promotion separate).

### 3.3 Failure→decision linkage (deterministic first, judgment second)

- **Deterministic:** a failing check maps to its surface (probe → endpoint; compile
  criterion → file), and surfaces map to register entries via `scope`. Failure analysis
  and the verification summary gain `implicated_decisions: [...]` — derived, not opined.
- **Judgment (existing seams, new question):** the analyzer's classification extends with
  the distinction the V38 window drew by hand on every red: *decision-was-the-defect* vs
  *implementation-missed-a-sound-decision*. This is the "actually, that design decision
  bit us" record, written at failure time with the evidence attached.

### 3.4 Boundaries

- Deterministic gates keep everything determinism can check (#1013's consistency and
  completeness stay deterministic; judgment is spent only on taste/coherence residue).
- Works identically for authored and seeded manifests (a seeded manifest's decisions are
  reviewable the same way; provenance differs, the register does not).
- No verdict surface changes: `implicated_decisions` is additive evidence, never a
  verdict input.

## 4. What this SIP deliberately does not do

No decision quality *score* (that is the 1.8 scorecard's job, consuming this SIP's typed
findings); no automatic decision reversal (a challenged entry returns to the author or
the human gate — judgment tightens, humans decide); no free-form design commentary (the
reviewer's output is findings against enumerated entries, or nothing).

## 5. Campaign integration (forward hooks, non-binding on this SIP)

- **Ledger:** campaigns aggregate per-cycle registers with their outcome links — the
  enumerated history of what was decided and what it cost.
- **Continuation policy:** the 1.8 ordering rule (grade definitions before continuation
  policy) is respected — the register is *grading input*: "cycle N's decision D was
  implicated in its red" is a typed fact a continuation policy may act on (constrain D,
  carry the corrected choice forward) without inventing a stopping rule from raw checks.
- **Cross-Cycle Memory Phase-1 payload candidate:** of everything a campaign could
  remember, decision-outcome records are the safest first cargo — typed at write time,
  warranted by construction, outcome-linked at read time, nothing free-form. This SIP
  proposes them as the answer to the memory SIP's "what do the rails carry first."

## 6. Relationship to #950

#950's review packet is the *human-gate surface* of the same data this SIP's reviewer
produces. Proposed convergence: the packet's design-decisions section IS the register plus
the reviewer's findings; #950 then owes only synthesis and coverage-derivation. To be
settled at #950's design time, not here.

## 7. Rungs and sequencing

| Rung | Content | Lane |
|---|---|---|
| 1 | Conventions primer + schema-gate findings (separate issue, filed alongside this draft) | 1.6.x patch lane (prompt assets + existing gate) |
| 2 | Register hardening (§3.1) + deterministic linkage (§3.3) | this SIP, first implementation phase |
| 3 | Review step, reporting-only (§3.2) | this SIP, second phase, pre-registered window |
| 4 | Revision-loop arming | separate promotion on measured evidence |
| 5 | Campaign ledger + memory payload (§5) | Campaign / Cross-Cycle Memory SIPs, 1.8 |

## 8. What acceptance asserts (and does not)

Acceptance commits the register schema, the mandatory-enumeration rule, the linkage, and
the review step's fail-closed contract + reporting-only introduction. It does NOT assert
the review step catches real defects — that is precisely what the observation window
measures, and the promotion decision owns it.
