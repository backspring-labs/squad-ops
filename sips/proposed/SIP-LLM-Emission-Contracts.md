---
sip_uid: '17883224960409982'
status: proposed
title: LLM Emission Contracts — Typed Response Handling with Provider-Agnostic Structured
  Output
author: SquadOps Architecture
created_at: '2026-07-25T00:00:00Z'
---
# SIP-0XXX: LLM Emission Contracts — Typed Response Handling with Provider-Agnostic Structured Output

**Status:** Proposed
**Authors:** SquadOps Architecture
**Created:** 2026-07-25
**Revision:** 2

## 1. Abstract

Every LLM-emitting handler in SquadOps hand-rolls the journey from "model produced text"
to "validated work product," and that journey keeps failing in ways we discover one live
roll at a time: five distinct fenced-parser malformation classes patched reactively
(#430, #470, #502, #528, #566), a YAML-escaping bug in plan proposers, think-block
stripping for Qwen-family models, truncated multi-file emissions crashing pytest
collection (pf-31), and — the night this SIP was drafted — two consecutive ten-minute
27b generations discarded because a complete test suite arrived in a filename-less
fence, followed by a correction attempt burned repairing an app that was never tested.

This SIP makes emission handling a **framework concern governed by typed contracts**:

1. **Emission contracts** — each handler declares a typed contract for what it expects
   back; the framework owns obtaining a valid instance. The contract model is an
   extensible type hierarchy, not a set of modes.
2. **Structured Artifact Contracts** — a JSON-Schema surface on the LLM port. Adapters
   that support constrained decoding enforce it natively; adapters that don't get a
   deterministic validate-and-reask emulation. Provider-agnosticism is a consequence
   of the layering, not a feature of any adapter.
3. **Code Artifact Contracts** — code emission stays markdown (evidence in §2.2), with
   extraction re-founded on an explicit recognition → interpretation → validation
   pipeline over a spec-compliant CommonMark engine (absorbs #567).
4. **Evidence-first observability** (absorbs #431) — every generation's raw response,
   finish reason, and extraction outcome persisted and classified, making malformation
   rate a measured per-provider/per-model number.

The port-level abstraction is load-bearing: SquadOps is preparing to move inference off
Ollama (Atlas is the planned next provider), and structured-output support differs per
provider. The contract must live in the port, not in any adapter's dialect.

**The invariant this SIP establishes:**

> **An emission contract either produces a valid artifact of the declared type, or a
> structured failure. Handlers never receive — and never interpret — partially
> extracted output, and never decide retry policy.**

Everything else in this document is machinery in service of that guarantee. It replaces
today's per-handler ad-hoc extraction calls, and it is directly testable: no handler
code path may observe malformed output.

## 2. Problem Statement

### 2.1 The reactive-patch ledger (all live-roll evidence)

| Failure class | Where found | Fix | Cost when it fired |
|---|---|---|---|
| Nested-fence truncation | #430 | depth tracking | whole files lost |
| Path-prefix on first body line | #470 | strategy 5 | whole files lost |
| Bare filename on first line | #502 | strategy 6 | whole files lost |
| `path:` label + unterminated EOF | #528 (replay-diagnosed) | label heal + implicit close | files → `build_warnings.md`, repair burned on formatting miss |
| Filename-less bare fence | #566 (pf-32 live, 2×) | single-expected-artifact fallback + aimed retry | 2 × ~10 min generation discarded, 1 misrouted dev repair |
| Proposer YAML escaping | SIP-0093 B revalidation | hand-patched | blocked multi-role merge |
| Think-block fence pollution | #130 | `_strip_think_blocks` | false fence matches |
| Multi-file truncation mid-emission | pf-31 repair-03 | Fix D syntax gate (drop) | collection crash re-imported by the repair |

Each fix is correct and each was necessary. The pattern is the problem: the extraction
layer only learns a malformation class **after** it has cost a roll. On a
bandwidth-bound box (~10-16 t/s on the full profile), every discarded emission is
minutes of wall-clock, and every misclassified extraction failure burns a bounded
correction attempt on a phantom work-product defect.

### 2.2 The industry answer we are not using

Constrained decoding (grammar-masked sampling against a schema) makes malformed
structured output **impossible by construction** — the sampler cannot emit a token that
violates the schema. Major inference providers now expose this through
provider-specific mechanisms (dialect notes in Appendix A). SquadOps' LLM port predates
the technique: `LLMRequest.format` supports only a legacy `"json"` mode hint, and no
handler can express "this response must satisfy this schema."

The counter-evidence is equally established: **code quality measurably degrades when
models are forced to wrap code in JSON** (aider's code-in-JSON benchmark: every tested
model scored worse; the escaping burden lands hardest on small models — exactly
SquadOps' fleet). So the line is: **structured artifacts get constrained decoding; code
files stay markdown with a hardened extraction pipeline.** This is the same
interface-vs-implementation line the scaffold thesis already draws.

### 2.3 The provider-migration forcing function

The deployment is moving from Ollama to Atlas. Today that migration is risky in a way
nobody can quantify: extraction behavior is tuned against one provider's emission
quirks (think-blocks, fence habits, truncation behavior at the token budget), there is
no per-provider malformation baseline to compare against, and any structured-output
adoption written against Ollama's parameter dialect would have to be redone. The port
must own the contract **before** the second provider arrives.

## 3. Design

### 3.1 The emission contract model (typed, extensible)

An emission contract is a **type implementing a common interface**, not a mode flag —
dispatch is polymorphic, never string-branching (the #559 rule applied to this SIP's
own design):

```
EmissionContract (interface)
├── StructuredContract(schema)                 # JSON-Schema-valid object
├── CodeArtifactContract(expected_artifacts)   # fenced markdown → file records
└── DocumentContract()                         # narrative deliverable (minimal today;
                                               #  extension point for metadata/sections)
```

Each LLM-emitting handler declares exactly one contract per generation. The contract
owns, on the framework side:

- the prompt-side format instructions (selected from managed template assets, #448 —
  so prompt and extractor can never disagree about the expected shape);
- extraction/validation of the response into the declared artifact type;
- **retry policy** — retries on contract violation are framework policy: bounded
  attempts, violation details fed back via template-asset instructions (the aimed-retry
  pattern #566 shipped). A handler never sees malformed output and never decides
  whether a violation deserves another attempt;
- **structured failure** — when the bounded policy is exhausted, the contract yields a
  machine-readable failure record (the #566 `emission_failure` marker is the first
  shipped instance), which downstream consumers (locus classification #568, analyze
  evidence) treat as an infrastructure fact, not a work-product defect.

Adding a future contract kind (tool calls, binary artifacts, streamed emissions) is a
new type, not a change to handler dispatch.

Consumers at adoption: `StructuredContract` — `data.analyze_failure`,
`governance.correction_decision`, plan proposers/merger (today's YAML → schema'd
JSON), future manifest authoring (already the 1.4 plan's designed authoring-parity
remedy). `CodeArtifactContract` — develop/qa.test/builder and all correction repairs.
`DocumentContract` — narrative deliverables (today's default wrap).

### 3.2 Structured Artifact Contracts (the port seam)

**Port surface.** `LLMRequest` gains `response_schema: dict | None` (a JSON Schema).
`LLMPort` gains a capability declaration:

```python
class StructuredOutputSupport:   # constants class, #559
    NATIVE = "native"        # provider enforces the schema during sampling
    EMULATED = "emulated"    # framework validates + re-asks (bounded)
```

**Adapter behavior.**
- *Native*: translate the JSON Schema to the provider's dialect; the response is valid
  by construction.
- *Emulated* (any provider, and the fallback when native support is absent or broken):
  the framework parses and schema-validates the response; on failure the contract's
  retry policy re-asks with the validation errors appended. Same handler code, same
  contract, degraded only in retry cost.

**Normative rules (the provider-agnosticism guarantees):**
1. Handlers and domain code MUST NOT reference a provider name or dialect — capability
   constants on the port only (the strings-boundary rule, #559).
2. JSON Schema is the single contract language; adapters own translation to their
   dialect.
3. **No adapter may be selected by the provider factory unless it passes the shared
   emission-contract conformance suite** (structured output, streaming, usage
   reporting, truncation/finish-reason reporting). An adapter's structured-output tier
   (native vs emulated) is *discovered by the conformance suite*, never assumed —
   including the Atlas adapter's at migration time.

### 3.3 Code Artifact Contracts (markdown, hardened)

Code emission stays fenced markdown (§2.2 evidence). Extraction is re-founded as three
**explicitly separated pipeline stages** — today these are blended inside one strategy
chain, which is why every new malformation class has required surgery in the middle of
it:

1. **Recognition** — "here are the fenced blocks and their info strings." Delegated to
   a spec-compliant CommonMark engine (`markdown-it-py`/`mistune`); the spec itself
   defines unterminated-fence-to-EOF handling, nesting, and indentation cases we have
   been rediscovering by hand (absorbs #567).
2. **Interpretation** — "block #3 appears to be `src/foo.py`." The existing mapping
   strategies (1–6, #528 recoveries, the #566 expected-artifact fallback) plus
   aider-style leniency (filename look-back window, fuzzy match against the contract's
   `expected_artifacts`).
3. **Validation** — "`foo.py` was expected, is path-safe, and parses where required."
   The contract's expected-artifacts check, path-safety guards, and the Fix D syntax
   gate — producing either valid file records or the structured failure of §3.1.

**Acceptance bar for the engine swap:** the accumulated replay corpus passes unchanged
— the refactor may only add recovered files, never lose or remap one.

**Repair emissions.** Whole-file re-emission by correction repairs is the largest
remaining code-emission risk surface (truncation — pf-31 repair-03; frozen-file
temptation — every roll since pf-27; token waste). Diff-based edit emission is a large
design space of its own (edit format, application semantics, frozen-file interaction,
conflict detection, rollback, replay) and is **deliberately out of scope here**: it
will be proposed as a successor SIP ("Deterministic Edit Contracts"), building on this
SIP's contract model as a fourth contract type. This SIP's acceptance does not gate on
it.

### 3.4 Evidence first (absorbs #431)

Every generation records: raw response (persisted artifact), finish reason / token
counts, extraction outcome (`clean` | `recovered:<strategy>` | `failed:<class>`), and
the emission contract in force. Consequences:

- A large raw-vs-stored gap classifies the failure as **infrastructure-locus** — the
  correction loop stops treating extraction losses as work-product defects (#568's
  classifier gains its strongest signal).
- **Malformation rate becomes a dashboardable number per provider × model × handler.**
  This is the migration instrument: run the same workload against the Ollama and Atlas
  adapters and compare extraction health *before* cutting over, then watch it after.

## 4. Phasing (each independently shippable)

| Phase | Content | Size | Lane |
|---|---|---|---|
| P0 | Evidence rule (#431): raw persistence + outcome classification | S | any (hardening) |
| P1 | Contract types + port surface (`response_schema`, capability constants) + Ollama native + emulated fallback + conformance suite (normative) | M | 1.5; pulls into the 1.4 arc iff the authoring-parity remedy fires or the Atlas migration starts |
| P2 | Structured-artifact adoption: analyze/decision → schema'd; proposer/merger plan emission → schema'd | M | 1.5 (same pull-forward trigger) |
| P3 | Code Artifact Contract hardening: recognition/interpretation/validation split on a CommonMark engine (#567) | M | 1.5 |
| P4 | *(successor SIP)* Deterministic Edit Contracts — diff-based repair emission | — | own design review |
| P5 | Atlas adapter + conformance run + A/B malformation baseline | M | at migration |

P0 has no dependencies and should land first — every later phase's verification quality
depends on the corpus it builds. P1/P2 eliminate whole failure classes for structured
artifacts. P3 shrinks (never fully eliminates) the code-emission classes. P5 is the
payoff gate for the provider switch.

## 5. Alternatives Considered

- **Code in constrained JSON** — rejected: measured quality degradation, worst on small
  models (aider benchmark); code emission stays markdown.
- **Per-file emission (one generation per artifact)** — kills filename ambiguity by
  construction but multiplies prompt-refill cost on bandwidth-bound single-GPU
  inference; deferred — revisit after the Deterministic Edit Contracts SIP (edits may
  capture most of the benefit).
- **Mode constants instead of contract types** — rejected: three string modes breed
  exactly the identity-branching #559 bans, and every future emission kind would touch
  handler dispatch. Types make extension additive.
- **Keep patching the parser** — the status quo; five classes in, each discovered by a
  failed roll. Rejected as a strategy, retained as a tactic until P3.
- **Provider-specific structured output (adopt one provider's dialect directly)** —
  rejected; redone at every migration and leaks provider identity past the port (#559).

## 6. Compatibility & Risks

- Additive port change (`response_schema=None` preserves today's behavior); handlers
  migrate per-phase.
- Constrained decoding can degrade generation quality if schemas over-constrain
  free-text fields (e.g., analysis prose inside JSON) — schemas MUST keep prose fields
  unconstrained (`type: string`, no pattern), and P2 adoption is measured per-handler
  via the P0 corpus before/after.
- Emulated fallback adds bounded retry cost on providers without native support — the
  conformance suite makes the tier visible at adapter selection time, never a surprise
  in a roll.
- The recognition-engine swap carries regression risk bounded by the replay-corpus
  acceptance bar (§3.3).

## 7. Relationship to Existing Work

- Shipped groundwork this arc: #566 (fallback + aimed retry + `emission_failure`
  marker — the first instance of this SIP's structured-failure half), #568
  (failure-locus routing), Fix D syntax gate (#564) — all become consumers of the P0
  evidence stream.
- #567 is absorbed as P3. #431 is absorbed as P0. Diff-based repairs are explicitly
  deferred to a successor SIP (§3.3).
- The 1.4 evidence-arc plan already names schema-constrained decoding as the
  authoring-parity remedy for manifest authoring — P1 builds the seam it will use.
- Prompt-side instructions stay in managed template assets (#448); provider identity
  stays out of orchestration strings (#559).

## Appendix A — Provider dialect notes (non-normative, time-bound)

Recorded for implementation convenience; the normative surface is §3.2 only.

- **Ollama** (current provider): native JSON-Schema constrained decoding via the
  `format` parameter (v0.5+, grammar-masked sampling).
- **OpenAI-compatible APIs**: `response_format: {type: "json_schema", ...}` — the
  *expected* Atlas path, to be verified by the conformance suite at adoption, never
  assumed.
- **Anthropic**: schema enforcement via tool-input schemas.
- **vLLM / llama.cpp**: guided decoding / GBNF grammars.
