# SIP-0XXX: LLM Emission Contracts — Provider-Agnostic Structured Output and Hardened Code Extraction

**Status:** Proposed
**Authors:** SquadOps Architecture
**Created:** 2026-07-25
**Revision:** 1

## 1. Abstract

Every LLM-emitting handler in SquadOps hand-rolls the journey from "model produced text"
to "validated work product," and that journey keeps failing in ways we discover one live
roll at a time: five distinct fenced-parser malformation classes patched reactively
(#430, #470, #502, #528, #566), a YAML-escaping bug in plan proposers, think-block
stripping for Qwen-family models, truncated multi-file emissions crashing pytest
collection (pf-31), and — the night this SIP was drafted — two consecutive ten-minute
27b generations discarded because a complete test suite arrived in a filename-less
fence, followed by a correction attempt burned repairing an app that was never tested.

This SIP makes response handling a **framework concern with a declared contract**, in
four parts:

1. **Emission contracts** — each handler declares the shape it expects back
   (`STRUCTURED(schema)` | `CODE_FILES(expected_artifacts)` | `PROSE`); the framework
   owns obtaining a valid instance of that shape.
2. **Provider-agnostic structured output** — a JSON-Schema surface on the LLM port.
   Adapters that support constrained decoding enforce it natively; adapters that don't
   get a deterministic validate-and-reask emulation. Handlers never know or care which.
3. **Code stays markdown, but hardened** — a spec-compliant CommonMark recognition
   engine under the existing mapping strategies (#567), and diff-based edit emissions
   for the correction loop's repairs.
4. **Evidence-first observability** (#431) — every generation's raw response, finish
   reason, and extraction outcome persisted and classified, making malformation rate a
   measured per-provider/per-model number.

Part 2 is the load-bearing abstraction: SquadOps is preparing to move inference off
Ollama (Atlas is the planned next provider), and structured-output support differs per
provider. The contract must live in the port, not in any adapter's dialect.

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

Constrained decoding (grammar-masked sampling against a JSON Schema) makes malformed
structured output **impossible by construction** — the sampler cannot emit a token that
violates the schema. Ollama has supported it natively since v0.5; every serious
provider exposes an equivalent (OpenAI-compatible `response_format: json_schema`,
Anthropic tool-input schemas, vLLM guided decoding, llama.cpp GBNF). SquadOps' LLM port
predates this: `LLMRequest.format` supports only the legacy `"json"` mode hint, and no
handler can express "this response must satisfy this schema."

The counter-evidence is equally established: **code quality measurably degrades when
models are forced to wrap code in JSON** (aider's code-in-JSON benchmark; escaping
burden), and the penalty is worst for small models — exactly SquadOps' fleet. So the
line is: **structured artifacts get constrained decoding; code files stay markdown with
a hardened extraction pipeline.** This is the same interface-vs-implementation line the
scaffold thesis already draws.

### 2.3 The provider-migration forcing function

The deployment is moving from Ollama to Atlas. Today that migration is risky in a way
nobody can quantify: extraction behavior is tuned against one provider's emission
quirks (think-blocks, fence habits, truncation behavior at `num_predict`), there is no
per-provider malformation baseline to compare against, and any structured-output
adoption written against Ollama's `format` parameter dialect would have to be redone.
The port must own the contract **before** the second provider arrives.

## 3. Design

### 3.1 Emission contracts (handler-side declaration)

Each LLM-emitting handler declares its emission contract:

- `STRUCTURED(schema)` — a JSON Schema (portable, provider-neutral). Consumers:
  `data.analyze_failure`, `governance.correction_decision`, plan proposers/merger
  (today's YAML → schema'd JSON), future manifest authoring (already the 1.4 plan's
  designed authoring-parity remedy).
- `CODE_FILES(expected_artifacts)` — fenced markdown emission, extracted by the
  hardened pipeline (§3.3). The expected-artifacts list is part of the contract (the
  #566 fallback and aimed-retry feedback already consume it).
- `PROSE` — narrative deliverables; wrapped as a document artifact (today's default).

The contract replaces per-handler ad-hoc extraction calls; the base handler owns the
dispatch. Prompt-side format instructions remain in managed template assets (#448) and
are selected by the same contract, so prompt and parser can never disagree about the
expected shape.

### 3.2 Provider-agnostic structured output (the port seam)

**Port surface.** `LLMRequest` gains `response_schema: dict | None` (a JSON Schema).
`LLMPort` gains a capability declaration:

```python
class StructuredOutputSupport:   # constants class, #559
    NATIVE = "native"        # provider enforces the schema during sampling
    EMULATED = "emulated"    # framework validates + re-asks (bounded)
```

**Adapter behavior.**
- *Native* (Ollama ≥0.5 via `format: <schema>`; any OpenAI-compatible provider via
  `response_format: {type: "json_schema", ...}` — the expected Atlas path): translate
  the JSON Schema to the provider dialect; the response is valid by construction.
- *Emulated* (any provider, and the fallback when native support is absent or broken):
  the framework parses and schema-validates the response; on failure it re-asks with
  the validation errors appended (bounded attempts, template-asset instruction — the
  same aimed-retry pattern #566 shipped for code emissions). Same handler code, same
  contract, degraded only in retry cost.

**Hard rules (the Atlas-proofing):**
1. Handlers and domain code never reference a provider name or dialect — capability
   flags on the port only (the strings-boundary rule, #559).
2. JSON Schema is the single contract language; adapters own translation.
3. Every adapter must pass a shared **conformance suite** (contract tests exercising
   structured output, streaming, usage reporting, truncation reporting) before it can
   be selected by the factory. The Atlas adapter's structured-output tier
   (native vs emulated) is *discovered by the conformance suite*, not assumed.

### 3.3 Code emission: markdown, hardened (absorbs #567)

- **Recognition layer** → a CommonMark-spec engine (`markdown-it-py`/`mistune`); the
  spec itself defines unterminated-fence-to-EOF handling, nesting, and indentation
  cases we have been rediscovering by hand. The strategy chain (1–6, #528 recoveries,
  #566 fallback) becomes a pure **mapping layer** over recognized blocks, extended with
  aider-style leniency (filename look-back window, fuzzy match against
  `expected_artifacts`).
- **Repair emissions become diffs.** Correction-loop repairs re-emit whole files today
  — the source of truncation risk (pf-31 repair-03), frozen-file temptation (every
  roll since pf-27), and token waste. An aider-style search/replace edit format bounds
  each repair to the lines it names: structurally fill-only, cheap to emit, and
  verifiable by exact application (an edit that doesn't apply is a deterministic
  rejection *before* patch verification). Whole-file emission remains for fresh tasks.
- **Acceptance bar for the engine swap:** the accumulated replay corpus passes
  unchanged — the refactor may only add recovered files, never lose or remap one.

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
| P1 | Port surface (`response_schema`, capability constants) + Ollama native + emulated fallback + conformance suite skeleton | M | 1.5 |
| P2 | Structured-artifact adoption: analyze/decision → schema'd; proposer/merger plan emission → schema'd | M | 1.5 |
| P3 | Code hardening: CommonMark recognition engine (#567) + mapping leniency | M | 1.5 |
| P4 | Diff-based repair emissions | M | 1.5+ (own design review) |
| P5 | Atlas adapter + conformance run + A/B malformation baseline | M | at migration |

P0 has no dependencies and should land first — every later phase's verification quality
depends on the corpus it builds. P1/P2 eliminate whole failure classes for structured
artifacts. P3/P4 shrink (never fully eliminate) the code-emission classes. P5 is the
payoff gate for the provider switch.

## 5. Alternatives Considered

- **Code in constrained JSON** — rejected: measured quality degradation, worst on small
  models (aider benchmark); repairs and fresh emissions stay markdown/diff.
- **Per-file emission (one generation per artifact)** — kills filename ambiguity by
  construction but multiplies prompt-refill cost on bandwidth-bound single-GPU
  inference; deferred, revisit after P4 (diffs may capture most of the benefit).
- **Keep patching the parser** — the status quo; five classes in, each discovered by a
  failed roll. Rejected as a strategy, retained as a tactic until P3.
- **Provider-specific structured output (adopt Ollama's dialect directly)** — rejected;
  it would be redone at the Atlas migration and would leak provider identity past the
  port (#559).

## 6. Compatibility & Risks

- Additive port change (`response_schema=None` preserves today's behavior); handlers
  migrate per-phase.
- Constrained decoding can degrade generation quality if schemas over-constrain
  free-text fields (e.g., analysis prose inside JSON) — schemas must keep prose fields
  unconstrained (`type: string`, no pattern), and P2 adoption is measured per-handler
  via the P0 corpus before/after.
- Emulated fallback adds bounded retry cost on providers without native support — the
  conformance suite makes the tier visible at adapter selection time, never a surprise
  in a roll.
- The recognition-engine swap carries regression risk bounded by the replay-corpus
  acceptance bar (§3.3).

## 7. Relationship to Existing Work

- Shipped groundwork this arc: #566 (fallback + aimed retry + `emission_failure`
  marker), #568 (failure-locus routing), Fix D syntax gate (#564) — all become
  consumers of the P0 evidence stream.
- #567 is absorbed as P3. #431 is absorbed as P0.
- The 1.4 evidence-arc plan already names schema-constrained decoding as the
  authoring-parity remedy for manifest authoring — P1 builds the seam it will use.
- Prompt-side instructions stay in managed template assets (#448); provider identity
  stays out of orchestration strings (#559).
