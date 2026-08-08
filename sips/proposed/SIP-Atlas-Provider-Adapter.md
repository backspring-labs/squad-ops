---
status: proposed
title: Atlas Provider Adapter — Config-Selected Inference Providers Behind a Conformance
  Gate
author: SquadOps Architecture
created_at: '2026-08-08T00:00:00Z'
---
# SIP-0XXX: Atlas Provider Adapter — Config-Selected Inference Providers Behind a Conformance Gate

**Status:** Proposed
**Authors:** SquadOps Architecture
**Created:** 2026-08-08
**Revision:** 1 (draft — §10 carries the open decisions)

## 1. Abstract

**Atlas is an open-source LLM inference engine, hand-tuned in-house for NVIDIA DGX
Spark** (§2.0 — recorded there because nothing else in the tree defines it). Adopting it
targets the throughput ceiling that bounds every yield window, every shakedown, and the
falsifiability of the small-model thesis itself (§2.5). That is the motive; provider
neutrality is the prerequisite.

SquadOps has one inference provider and no way to select a second. `LLMPort` looks like
a seam and mostly is one, but provider selection is not configurable, the composition
root constructs a vendor adapter directly, and two API route modules branch on
`isinstance(port, OllamaAdapter)`. Adding Atlas today is not "write an adapter" — it is
"write an adapter and discover, one live roll at a time, every place the vendor already
leaked past the port."

This SIP makes the second provider a **configuration decision verified by a gate**, in
four moves:

1. **Provider selection becomes config** — `LLMConfig.provider`, defaulting to `ollama`,
   flowing through the existing `create_llm_provider` factory at every composition root.
   The dormant-posture precedent is `SandboxConfig.provider = "noop"` (SIP-0102).
2. **Capabilities are declared, not inferred** — `LLMPort.capabilities()` replaces every
   `isinstance` check, under the #572 doctrine already written into the queue port: *a
   flag that overstates the implementation is worse than a missing feature.*
3. **Model identity becomes provider-scoped** — `MODEL_SPECS` is keyed on Ollama tag
   syntax (`qwen2.5:7b`). A second provider that names the same weights differently
   silently loses its completion clamp (§2.3). This is the highest-consequence leak in
   the inventory and the least visible.
4. **The Atlas adapter ships dark behind a conformance suite** — no adapter may be
   selected by the factory unless it passes a shared behavioral suite, and the suite
   *discovers* the adapter's capability tier rather than assuming it.

**The invariant this SIP establishes:**

> **A provider is selected by configuration, declares what it can do, and is refused by
> the factory unless it passes the conformance suite. No domain or API code may name a
> provider, branch on an adapter type, or assume a capability the port has not
> declared.**

**Operational constraint, load-bearing and non-negotiable (§4):** every phase here is
**inert on merge**. No shipped default, compose file, `.env.example` value, agent image,
or profile changes the model runner. The Spark lane is running 1.6 authored-manifest
validation sprints against Ollama; this work must be invisible to them until an explicit,
separate cutover decision (§4.2).

## 2. Problem Statement

### 2.0 What Atlas is (recorded here because nothing else records it)

**Atlas is an open-source LLM inference engine, hand-tuned in-house for NVIDIA DGX
Spark.** It is a local engine — a direct replacement for Ollama on the Spark box, not a
hosted service. No API key, no egress, no per-token cost, no rate limits.

This definition is stated here because it exists nowhere else in the tree. Atlas is named
in SIP-0101, SIP-LLM-Emission-Contracts (§2.3, §3.2, Appendix A), and the 1.7 roadmap
entry — always as an assumed shared referent, never defined. Any reader arriving at those
references cold has to ask. This SIP is the canonical record; the others should link here.

**Why that matters for scope:** because Atlas is local and self-hosted, this migration
carries none of the concerns a hosted provider would force into the design — credentials,
network egress of PRDs and source, per-token billing, 429 backoff, multi-tenant latency
variance. The design below is smaller and more honest for it. If Atlas ever grows an auth
surface, it enters through `SecretManager` as a `secret://` ref, which the factory already
resolves for `base_url` — but nothing in this SIP anticipates that, per the standing rule
against building for a second use that does not exist.

### 2.1 Provider selection does not exist

`LLMConfig` (`src/squadops/config/schema.py:531`) declares `url`, `model`, `use_local`,
and `timeout`. **There is no `provider` field.** `create_llm_provider`
(`adapters/llm/factory.py:18`) takes `provider: str = "ollama"` and **no caller in the
tree ever passes it.** The factory's provider branch is unreachable by configuration —
it is decoration on a hardcode.

Setting `SQUADOPS__LLM__PROVIDER=atlas` today does nothing, silently. That is the
`_get_default_instances()` class the repo has a standing rule against: config that
appears to work and does not.

### 2.2 The vendor leaks the port already tolerates

Inventory as of `d4c3f9a2` — every site that must be neutral before a second provider is
selectable. Each was verified by reading the code, not by search-and-assume:

| # | Site | Leak | Consequence at swap |
|---|---|---|---|
| 1 | `api/runtime/main.py:433` | Composition root imports and constructs `OllamaAdapter` directly, bypassing the factory | runtime-api ignores provider config entirely — the swap is *invisible* to the API service. **This is #301.** |
| 2 | `api/routes/cycles/models.py:58` | `isinstance(port, OllamaAdapter)` → 503 "Model management requires Ollama adapter" | all five `/api/v1/models/*` management routes 503 under Atlas |
| 3 | `api/routes/cycles/cycles.py:63` | `isinstance(port, OllamaAdapter)` → returns `None` | model-availability preflight silently degrades to warn-and-allow (SIP-0095 §6.2) — **the correct fallback for an unreachable backend, but here it fires for a *reachable* one**, so cycle creation stops verifying models at exactly the moment verification matters most |
| 4 | `bootstrap/setup/checks.py:439,449,466,595,836,874` | `doctor` shells out to `ollama list` / `ollama ps` | doctor mis-probes on an Atlas box and reports models absent that are present. **This is #313.** |
| 5 | `adapters/llm/ollama.py:499` | `list_pulled_models()` is on the adapter, not the port | every caller that reaches for it (sites 2 and 3) becomes vendor-coupled by construction. **#313's second half.** |
| 6 | `llm/model_registry.py:25` | `MODEL_SPECS` keyed on Ollama tag syntax | §2.3 — silent, and the worst of the six |
| 7 | `agents/entrypoint.py:362` | Uses the factory correctly, but never passes `provider` | the one site already shaped right; it needs one argument, not a refactor |

Sites 1–3 are in `src/squadops/` — domain and API code naming a vendor type, which the
#559 strings-boundary rule already forbids in its own domain. The rule was never extended
to adapter identity.

### 2.3 Model identity is provider-scoped, and the failure is silent

`MODEL_SPECS` maps model name → context window + `default_max_completion`. The consumer
is `_resolve_model_budget` (`capabilities/handlers/cycle/base.py:325`):

```python
model_spec = get_model_spec(model_name)
max_tokens = capability_max_tokens
if model_spec is not None:
    max_tokens = min(max_tokens, model_spec.default_max_completion)
    context_window = model_spec.context_window
```

**An unrecognized model name is not an error. It disables the clamp.** The capability's
own `max_tokens` passes through unchecked and `context_window` stays `None`.

The registry's own source comment records what this cost the last time it fired — before
`qwen3.6:27b` had an entry, Spark cycles ran with no clamp, and the `python_cli` fallback
silently capped fullstack work that should have had a higher budget. That was **one
missing key**. A provider migration changes the naming scheme for *every* key at once:
`qwen2.5:7b` (Ollama tag) versus whatever Atlas calls the same weights.

So the swap's first symptom would not be an error. It would be every model running
unclamped, and the diagnosis arriving days later from a token bill or a coherence
collapse. Migration must treat model identity as provider-scoped data, not a global
string.

### 2.4 The 1.5 debt this inherits

Track E of the 1.5 stabilization plan (`docs/plans/1-5-0-stabilization-plan.md:351`) was
titled "Atlas groundwork — provider neutrality, no swap." It was capacity-bound and
shipped nothing; the post-cut sweep re-homed the whole track to the 1.7 pool
(`docs/plans/post-1-5-roadmap-reconciliation.md:49`).

**This SIP absorbs #313 outright** (sites 4 and 5 above) — it is the one Track E item
that is a hard precondition rather than an adjacency, and splitting it from the adapter
would mean touching `checks.py` twice.

**It does not absorb** #410 (thinking-token observability) or #707 (command allowlists).
See §9 for why, and §10.3 for the #410 question that is genuinely open.

### 2.5 Why now, and why on this lane

**The driver is throughput, and throughput is the binding constraint on the entire
measurement program.** Atlas is hand-tuned for the exact hardware the squad runs on, so
it targets the one number that bounds everything else. The repo's own evidence, all of it
recorded before this SIP existed:

- `#410`: *"At the Spark's 11.4 t/s ceiling this is roughly 35 min of a 77-min run."*
- SIP-LLM-Emission-Contracts §2.1: *"On a bandwidth-bound box (~10-16 t/s on the full
  profile), every discarded emission is minutes of wall-clock."*
- `model_registry.py`'s own comment: *"qwen3.6:27b at ~10 t/s on Spark takes ~13 min for
  8K tokens"* — the reason the completion clamp exists at all.
- The post-1.5 reconciliation, on why Campaign is tempting: *"hand-launching them has been
  the human bottleneck through every FAY window and shakedown."*

Every one of those is the same constraint wearing a different hat. Token throughput sets
how long a cycle takes, which sets how many cycles fit in a window, which sets whether a
yield measurement is a statistic or an anecdote. The scorecard's squad-vs-single-model
comparison (1.8) needs *many* cycles to say anything. An engine tuned for this box is the
most direct lever on that, and it is a lever nothing else in the roadmap pulls.

That reframes the migration: it is not provider-neutrality for its own sake, it is an
instrument for the thesis. Which also sets the acceptance bar — **§3.6's A/B tier must
establish quality parity, not just speed.** A faster engine that degrades emission quality
buys nothing, and every prior measurement (the FAY 6/6 window, the 98.5 lineage) was taken
on the Ollama substrate. Changing engines without a parity baseline silently invalidates
the comparison base for everything measured so far. See §8's thesis-discontinuity risk.

The two documents that name Atlas both defer it for the same reason and to the same
place: SIP-LLM-Emission-Contracts §2.3 ("the port must own the contract **before** the
second provider arrives") and the 1.7 roadmap entry ("the Atlas migration cannot happen
safely while a vendor's status vocabulary lives in domain objects and the composition
root bypasses the factories").

Both are correct and neither is a reason to wait. The groundwork *is* this work — sites
1–6 are the migration's precondition, and they can be built and proven before any default
moves. Building the adapter alongside them is what proves they are sufficient: a
neutrality refactor with no second implementation is a claim, not a demonstration. The
conformance suite (§3.6) is what converts the claim into evidence, and it cannot exist
without a second adapter to run it against.

The lane argument is separate and equally concrete. This touches the LLM port, adapters,
factory, and doctor — **Spark-lane files** under the 2026-07-14 file-ownership pinning.
Building it from the Mac is a recorded deviation, with the same justification and the same
constraint as SIP-0102's sandbox work: the Spark lane is mid-1.6 and cannot absorb churn
under its validation sprints, and §4's dark-ship rule makes the deviation safe rather than
merely convenient.

## 3. Design

### 3.1 Provider selection becomes configuration

`LLMConfig` gains one field, with the dormant default:

```python
provider: str = Field(
    default="ollama",
    description="LLM provider: 'ollama' or 'atlas'",
)
```

Precedent, deliberately copied rather than invented: `SandboxConfig.provider = "noop"`
(`config/schema.py:256`) — *"Defaults are the dormant posture."* Same shape, same reason.

Rules:

1. **Every composition root routes through `create_llm_provider`.** Site 1 stops
   constructing `OllamaAdapter`; site 7 passes `provider=config.llm.provider`. This is
   #301's LLM half — see §10.1 for the scope ruling this SIP proposes.
2. **An unknown provider name raises.** The factory already does this
   (`ValueError: Unknown LLM provider`). It must keep doing it — no fallback to Ollama,
   ever. A typo in `SQUADOPS__LLM__PROVIDER` fails loudly at startup; it does not
   silently run the old runner (the standing no-masking-fallbacks rule).
3. **`url` stays one field.** It is already provider-agnostic in shape; only its default
   is Ollama-flavored, and defaults are per-provider concerns resolved in the adapter, not
   forked config keys.
4. **Config var:** `SQUADOPS__LLM__PROVIDER`, conforming to the existing `SQUADOPS__*`
   nesting convention. No new prefix, no new lane.

### 3.2 Capabilities are declared, not inferred

`LLMPort` gains `capabilities() -> dict[str, bool]`, modeled directly on the queue port's
(`ports/comms/queue.py:293`) and carrying its doctrine verbatim:

> Every flag is a contract with future callers: it must describe what the provider
> *does*, not what its transport could be configured to do. A flag that overstates the
> implementation is worse than a missing feature — the caller builds on it and loses
> messages silently (#572).

Initial flags, chosen because each has a caller today that currently answers the question
with `isinstance`:

| Flag | Question it answers | Caller |
|---|---|---|
| `model_management` | can this provider pull/delete models? | site 2 |
| `model_listing` | can this provider enumerate available models? | sites 3, 4 |
| `streaming_usage` | does `chat_stream_with_usage` report real token counts, or fall back to `chat()`? | telemetry/LangFuse accounting |
| `thinking_tokens` | does this provider expose reasoning tokens separately from content? | §10.3 (#410) |

Sites 2 and 3 then ask the port a question instead of testing its type:

```python
# site 2, replacing isinstance(port, OllamaAdapter)
if not port.capabilities()["model_management"]:
    raise HTTPException(503, detail="Model management not supported by the configured LLM provider")
```

The 503 remains the honest answer for an Atlas that cannot pull models. What changes is
that the *reason* is a declared capability rather than a vendor identity, so a third
provider that can manage models is not excluded by a check that never heard of it.

**Site 3 is not a mechanical substitution and must not be treated as one.** Its `None`
today means "unverifiable — warn and allow." Under Atlas with `model_listing: True`, it
must return a real list and block on a genuinely missing model; with `model_listing:
False`, it must keep returning `None`. Conflating "provider cannot tell me" with "model is
absent" in either direction is a false verdict, which the 1.4.4 line exists to prevent.

### 3.3 Model availability moves on-port (#313)

`LLMPort` gains:

```python
async def list_available_models(self) -> list[ModelInfo]: ...
```

`ModelInfo` is a frozen dataclass in `squadops/llm/models.py` carrying the fields the
callers actually use — `name`, and optional `size_bytes` / `modified_at` for the console's
pulled-model view. Providers that cannot supply the optional fields leave them `None`;
they do not fabricate them.

- `OllamaAdapter.list_pulled_models()` becomes the Ollama implementation of this method.
  The raw-dict return type dies with it — that dict *is* the leak, since its shape is
  Ollama's `/api/tags` payload and site 2 reads it positionally.
- **Doctor becomes provider-aware** (site 4). `_query_ollama_models()` is selected by
  configured provider rather than assumed. Doctor is a sync pre-flight with no adapter
  pool wired, which is why it shells out today; the honest fix is a provider-selected
  probe, not a fake async context. **`model_availability_decision`
  (`cycles/preflight.py`) is already fully neutral — it takes `Iterable[str]` — and must
  not be touched.**
- Doctor against a provider that cannot enumerate models reports the check as
  **skipped with a stated cause**, never as passed and never as failed. The #423
  skip-cause split is the governing precedent: an unrunnable check is an evidence gap,
  not a green.

### 3.4 Model identity becomes provider-scoped

The minimum change that closes §2.3, and no more:

1. `ModelSpec` gains an optional `aliases: frozenset[str]` so one spec can be reached by
   both providers' names for the same weights.
2. `get_model_spec()` resolves through aliases.
3. **A model name that resolves to no spec is logged at WARNING with the provider name
   and the unclamped budget it is about to use.** This is the only behavior change in
   §3.4 that fires under today's default, and it is deliberate: the silent-unclamped path
   has already cost one incident, and a log line is the cheapest instrument that would
   have caught it.

Explicitly **not** in scope: restructuring `MODEL_SPECS` into a per-provider registry, or
deriving specs from a provider API. Both are plausible and neither is needed for two
providers naming ~6 models. Deferred under the no-gold-plating rule until a concrete
second use exists.

### 3.5 The Atlas adapter

`adapters/llm/atlas.py`, implementing `LLMPort`, structurally a sibling of
`OllamaAdapter`: `httpx.AsyncClient`, the same four exception translations
(`LLMTimeoutError` / `LLMConnectionError` / `LLMModelNotFoundError`), the same
`chat_stream_with_usage` streaming-for-liveness pattern that keeps long generations from
idling out.

**Working assumption: Atlas exposes an OpenAI-compatible HTTP surface**
(`/v1/chat/completions`, `/v1/models`). This is the one assumption in the SIP, and it is
not invented here — SIP-LLM-Emission-Contracts Appendix A already names OpenAI-compatible
as "the *expected* Atlas path." Since Atlas is in-house, this is a fact to confirm rather
than a risk to manage, and it is confined to P4: if wrong, the transport layer of one file
changes and nothing else in this SIP moves.

The dialect is still *verified rather than assumed*, per SIP-LLM-Emission-Contracts
§3.2's rule that an adapter's tier is "discovered by the conformance suite, never assumed
— including the Atlas adapter's at migration time." The assumption sets the starting
implementation; the suite decides what is true.

What the SIP does fix, dialect-independent:

- **Usage accounting is required, not optional.** `prompt_tokens` / `completion_tokens` /
  `tokens_per_second` must be populated or explicitly `None`. Ollama computes t/s from
  `eval_count` / `eval_duration`; a provider reporting only totals declares
  `streaming_usage: False` rather than inventing a rate. Silent zeros would corrupt the
  LangFuse cost accounting the 1.4 arc depends on.
- **Error translation is part of the contract.** A 404 is `LLMModelNotFoundError`, a
  connect failure is `LLMConnectionError`, a timeout is `LLMTimeoutError` — because the
  correction loop's locus classification (#568) reads these to decide whether a failure is
  infrastructure or work-product. An adapter that raises raw `httpx` errors silently
  reclassifies infrastructure failures as work-product defects.
- **No structured-output surface.** `response_schema` belongs to
  SIP-LLM-Emission-Contracts, which is still proposed. This SIP must not foreclose it —
  §9 states the seam — but must not pre-implement an unaccepted design either.

### 3.6 The conformance suite — the gate

A shared, adapter-parameterized behavioral suite that every adapter must pass **before the
factory may return it**. It is the deliverable that makes the swap a verified change
rather than a hopeful one, and it is what the 1.5 plan called for and did not get:

> the suite *characterizes* the current contract; it becomes a conformance suite only when
> a second provider connects

This SIP is that second provider, so the suite ships in its conformance form.

**What it asserts** — for each adapter, the same tests, exact-value assertions on outputs:

| Dimension | Assertion |
|---|---|
| Generation | `generate()` returns non-empty text, echoes the resolved model |
| Chat | multi-turn history preserved; role is `assistant` |
| Streaming | `chat_stream()` yields ≥1 chunk; concatenation equals the non-streamed content for a deterministic prompt (temperature 0) |
| Usage accounting | token counts present and internally consistent (`total == prompt + completion`), or all `None` — never partial, never zero-filled |
| Model listing | `list_available_models()` returns names matching the declared capability |
| **Listing vs. absence** | **three distinct outcomes, asserted separately and never collapsed** — see below |
| Model management | `model_management: True` → pull/delete round-trip; `False` → the method raises, and callers surface an honest 503 rather than a silent no-op |
| Error translation | unknown model → `LLMModelNotFoundError`; unreachable host → `LLMConnectionError`; sub-second timeout → `LLMTimeoutError` |
| Capability honesty | every declared-`True` flag is exercised and observed to work; every declared-`False` flag's method raises rather than degrading silently (#572's rule) |

**Capability honesty is the load-bearing row.** It is what makes §3.2's declarations
trustworthy instead of aspirational, and it is the row that would have caught #572 in the
queue port.

**The listing-vs-absence row exists because these three collapse into one vague check the
moment nobody is watching**, and the collapse is invisible — it looks like a passing test.
The suite asserts each separately, and doctor and the create-time preflight (§3.2 site 3,
§3.3) must agree with it:

| Situation | `list_available_models()` | Preflight decision | Doctor |
|---|---|---|---|
| provider **cannot** enumerate (`model_listing: False`) | raises | `None` → warn and allow | **skipped**, cause stated |
| provider **can** enumerate, model **present** | list contains it | allow | pass |
| provider **can** enumerate, model **absent** | list omits it | **block** | **fail**, names the model |

Row 1 must never be reported as row 3, and row 3 must never be softened into row 1. The
first is a false red that blocks a valid cycle; the second is the false green that lets a
cycle launch against a model that does not exist. The #423 skip-cause split is the
governing precedent: an unrunnable check is an evidence gap, never a verdict.

**Tiering, so the suite is runnable in three places:**

- **Unit tier** — mocked transport, runs in the regression suite, no network. Every
  dimension above.
- **Live tier** — `@pytest.mark.integration`, against a real endpoint from an env var,
  skipped when absent. Same assertions, real wire.
- **A/B tier** — same prompts, same models, same box, through both adapters. **This is the
  migration decision instrument** and the reason the SIP exists (§2.5). It reports two
  numbers, and both gate the cutover:
  - **Throughput, recorded as three numbers rather than one.** Tokens produced against
    the time taken is the right measure and needs no reinterpretation — including
    thinking tokens, which cost real time and are legitimately part of what the engine
    produced. What it needs is *completeness*, because today's single number measures
    less than it appears to:

    | Number | What it is | Status today |
    |---|---|---|
    | **t/s** (`eval_count / eval_duration`) | **decode speed only** | computed; the primary engine-speed metric |
    | **`latency_ms`** | true end-to-end wall-clock for the call | already captured by the handler, already on `GenerationRecord` |
    | **token count** (`eval_count`) | how much was produced | already captured |

    **t/s excludes prefill, model load, and queueing.** `prompt_eval_duration`,
    `total_duration`, and `load_duration` are returned by Ollama in the same response and
    read **zero times** by the adapter. That matters here specifically: prompts are large
    (contract + skeleton + prior outputs), and six agents on different models share one
    box, so model residency is not free. Two engines can post identical t/s and differ
    materially in wall-clock if the tuning win lands in prefill or load rather than
    decode — and t/s is blind to that by construction.

    Recording all three makes the comparison self-interpreting. A token-count change
    (from a different thinking posture, or terser generation) shows up as a token-count
    change; a prefill or residency win shows up as latency moving while t/s holds. No
    inference required, and no separate thinking-token accounting needed to read the
    result. **P4 should capture the three discarded duration fields** — free, same
    response, and the difference between an attributable result and a mystery.
  - **Quality parity** — extraction health (clean / recovered / failed rates per
    SIP-LLM-Emission-Contracts §3.4) and usage-accounting consistency. **A throughput win
    with a quality regression is a loss**, and without this half the FAY and 98.5 lineages
    lose their comparison base (§8).

  It is not a unit-test pass/fail gate; it is a recorded artifact that the cutover decision
  (§4.2) reads. SIP-0101's replay harness should drive it — identical replayed inputs
  through two adapters is precisely the use it already names.

#### 3.6.1 The A/B artifact contract

The comparison is a **named artifact with fixed fields**, not a PR-description summary.
Without this, a later reader re-interprets the numbers to suit whatever question they
arrived with — and a migration decision reviewed a year on is exactly that reader.

One row per (prompt, model, adapter) pair, all fields required, `None` permitted only
where the provider genuinely cannot supply the value (and then declared, never zero-filled
— §3.5's usage-accounting rule):

| Field | Source | Why it is in the contract |
|---|---|---|
| `adapter` | conformance harness | which side of the A/B |
| `model` | resolved model | naming differs per provider (§2.3), so record the resolved value verbatim |
| `prompt_tokens` | `prompt_eval_count` | prompt size — the prefill workload |
| `completion_tokens` | `eval_count` | how much was produced; a thinking-posture change surfaces here (§10.3) |
| `wall_clock_ms` | handler-measured `latency_ms` | **the decision number** — end to end, nothing excluded |
| `decode_tokens_per_second` | `eval_count / eval_duration` | engine decode speed |
| `prefill_ms` | `prompt_eval_duration` | **not captured today** — P4 adds it |
| `load_ms` | `load_duration` | **not captured today** — P4 adds it; model residency across a 6-agent box |
| `total_ms` | `total_duration` | **not captured today** — P4 adds it; reconciles against `wall_clock_ms` |
| `artifact_validated` | the cycle's own verdict | throughput is meaningless without it — §3.6's quality-parity half |

`wall_clock_ms` is the decision field and `decode_tokens_per_second` is the diagnostic. If
the two disagree — decode flat, wall-clock improved — the duration breakdown says why, and
that is the entire reason the three uncaptured fields are in P4 rather than deferred.

**The gate**: `create_llm_provider` returns an adapter only if its conformance run is
green. Enforced as a CI-blocking test over the adapter registry, not a runtime check — a
runtime check would make every process pay for a build-time property.

## 4. The dark-ship rule

This section is a constraint on *how* every phase merges, not a phase itself. It exists
because the Spark lane is running 1.6 authored-manifest validation sprints against Ollama,
and a changed model runner mid-window would invalidate their measurements while looking
like a squad regression.

### 4.1 Inert on merge — the checklist every PR in this SIP satisfies

1. `LLMConfig.provider` defaults to `"ollama"`. **No shipped file sets it to anything
   else** — not `docker-compose.yml`, not `.env.example` (commented reference line only),
   not any squad profile, not any bootstrap profile.
2. **No agent-image dependency changes.** The Atlas adapter uses `httpx`, already a direct
   dependency. If a dialect requires a new package, that is a §10.2 decision and it does
   not ride this SIP silently. (SIP-0102's "no agent-image dep changes before the
   validation phase" constraint, same reasoning.)
3. **Byte-identical default path.** With `provider="ollama"` the resolved adapter,
   requests, and responses are unchanged. Proven by test, not by inspection — the
   golden-first pattern #663 used.
4. **Additive only.** New port methods get concrete defaults on `LLMPort` where a sane one
   exists so no existing adapter breaks; new config fields are optional with dormant
   defaults; no DDL.
5. **No changes to files under active 1.6 edit** without an explicit coordination window.
   The overlap risk is `capabilities/handlers/cycle/base.py` (§3.4's warning line) —
   a two-line addition, and the one place to check before opening the PR.

### 4.2 Cutover is a separate, later, owner decision

Changing any default is **out of scope for this SIP**. The cutover requires, at minimum:

1. the conformance suite green against a live Atlas endpoint on the Spark (P5);
2. **the §3.6.1 A/B artifact recorded, both halves** — a throughput win *and* quality
   parity. Either alone is insufficient: no speed win means no reason to switch, no parity
   means the measurement lineage breaks (§8);
3. **the throughput-telemetry gap fixed and deployed** (**#793**, §10.3a). The cutover is decided on
   throughput evidence, and today `tokens_per_second` never reaches LangFuse while nothing
   persists it at all. Deciding a migration on a log-scraped number is the evidence
   posture SIP-0096 exists to forbid. **This is a hard precondition of the cutover, and it
   gates none of P0–P5** — it has its own issue and lands on its own schedule, it simply
   must be done *before* the decision, not before the adapter;
4. a shakedown cycle on the deployed stack, green, under the new engine;
5. a release window where the Spark lane is not mid-validation.

This SIP delivers the *ability* to switch and the *evidence* to decide. It does not
switch, and it does not pre-authorize switching.

### 4.2a Rollback boundaries — what unwinds, and when

Stated in advance, because the expensive time to discover the blast radius is after a
failed P5. **Each phase is separately revertible, and the surface grows monotonically:**

| Failure point | What reverts | What stays |
|---|---|---|
| **P4 fails** (adapter cannot pass conformance) | `adapters/llm/atlas.py` and its registration — one file plus a factory branch | everything in P0–P3. The port is honest, #313 is closed, doctor is provider-aware. **None of it was Atlas-specific**, which is the point of building the neutrality work first |
| **P4 green, P5 fails** (adapter conforms; engine loses on throughput or parity) | **nothing in the tree.** The adapter stays, dark and unselected | the A/B artifact — a *recorded negative result*, which is the most valuable output of a failed migration and must not be discarded. It says which dimension lost and by how much, and it is the baseline the next attempt is measured against |
| **Cutover made, then regretted** | flip `SQUADOPS__LLM__PROVIDER` back to `ollama` and redeploy | model aliases (§3.4 — additive, harmless), config wiring, persisted A/B artifacts. **No DDL and no data migration**, by §4.1.4's additive-only rule |

The middle row is the one worth internalizing: **a failed P5 costs no revert at all.** The
adapter is inert by construction until a default names it, so "Atlas is not faster" is a
decision not to flip a config value — not a rollback. That property is bought entirely by
the dark-ship rule, and it is the strongest practical argument for §4.3's placement.

### 4.3 Release placement

Proposed: **the groundwork and the adapter land in 1.7, dark; the cutover is 1.8+.**

The even/odd convention makes this the question the review must actually settle, so the
argument is stated rather than assumed. 1.7 is feature-free by rule, and "a new provider
adapter" sounds like a feature. The case that it is not:

- A second implementation of an existing port, which no default selects and no shipped
  config reaches, changes nothing about what the running system does. That is the
  definition 1.5 used at its own feature-free audit (no new contract fields, manifest
  fields, request-profile capabilities, or squad-facing surfaces — this SIP adds none of
  those).
- It is the *rails-before-mechanism* pattern the repo has now applied three times:
  SIP-0101 shipped evidence rails before the harness, SIP-0096 Phase 1 shipped its pure
  core inert, and 1.8's memory recall port ships with a NoOp before any implementation
  exists.
- 1.7's stated identity is **"every port is actually a port."** Sites 1–6 are precisely
  that release's thesis, and the adapter is the proof the thesis holds.

If the review rejects this reading, the fallback is that §5's P0–P2 (the neutrality
groundwork, unambiguously 1.7 debt) land in 1.7 and P3–P4 (adapter + suite) wait for 1.8.
That is a worse outcome — it re-separates the claim from its proof — but it is not a
blocked one, and the phases are ordered so the split is clean.

## 5. Phasing

Each phase is independently shippable, inert per §4.1, and one PR.

**The release boundary runs between P5 and cutover, and it is a hard line.** Everything in
the table below ships dark in **1.7**; nothing in it changes which engine serves a single
token. The switch is a **1.8+** decision governed by §4.2, taken against evidence this SIP
produces but does not act on. A PR from this SIP that changes a default has left the SIP's
scope, regardless of how green its tests are.

| Phase | Content | Size | Depends on | Release |
|---|---|---|---|---|
| **P0** | `capabilities()` on `LLMPort` + Ollama declarations + sites 2/3 stop using `isinstance` + `thinking_tokens` flag declared (§10.3) | S | — | 1.7 |
| **P1** | `list_available_models()` on-port + `ModelInfo` + Ollama impl + doctor provider-aware + #423-style skip cause — **`Closes #313`** | M | P0 | 1.7 |
| **P2** | `LLMConfig.provider` + factory wiring at both composition roots + unknown-provider raises — **references #301, does NOT close it** (§10.1) | S | P0 | 1.7 |
| **P3** | Conformance suite, unit + live tiers, run green against Ollama as the only adapter | M | P0–P2 | 1.7 |
| **P4** | Atlas adapter + conformance run + capability declarations + capture the three discarded duration fields (§3.6) | M | P3, **§10.2 confirmed** | 1.7 |
| **P5** | A/B tier + the artifact contract of §3.6.1 recorded | S | P4, live Atlas endpoint on Spark | 1.7 |
| — | **Cutover — changing the default** | — | **not this SIP** (§4.2) | **1.8+** |

**Issue linkage, stated precisely so a PR cannot overclaim it:** P1 carries
`Closes #313`. **P2 carries a bare `#301` reference and no `Closes`**, because it fixes
only the LLM half of a two-part issue (§10.1) — the queue half stays in the 1.7
composition-root cluster behind its own design gate. P2's PR body must say what remains,
per the standing partial-fix rule.

**P0–P3 have no dependency on knowing what Atlas is.** They are the neutrality work, they
close two 1.7-pool issues, and they are independently valuable if Atlas never arrives.
Only P4 needs the dialect pinned — which is what makes §10.2 a non-blocking open decision
rather than a gate on starting.

P3 before P4 is deliberate: the suite must be written against the *contract*, with Ollama
as its first subject. Writing it after the Atlas adapter exists guarantees it encodes
whatever that adapter happens to do — the exact mistake the 1.5 plan warned about
("**not** enshrine Ollama transport behavior as the contract"), inverted.

## 6. Verification

### 6.1 Rough-testing on the Mac, without an Atlas instance

**Local Ollama already serves an OpenAI-compatible surface.** Verified on this box
(Ollama 0.12.3):

```
$ curl -s http://localhost:11434/v1/models
{"object":"list","data":[{"id":"qwen2.5:14b","object":"model","created":...,"owned_by":"library"}, ...]}
```

**Atlas itself is tuned for DGX Spark and is not expected to run on this Mac** — the same
hardware split that makes the `full` squad profile hard-fail here. So the Mac cannot test
the *engine*. It can fully test the *adapter*, which is what P0–P4 actually deliver.

Under §3.5's OpenAI-compatible assumption, the Atlas adapter points at
`http://localhost:11434/v1` and runs the **entire live-tier conformance suite on this Mac**
against real models: real generation, real streaming, real usage accounting, real error
translation — with no Atlas instance, no Spark contact, and no default changed.

**Be precise about what that proves and what it does not:**

| Proven on the Mac | Requires the Spark |
|---|---|
| the adapter speaks the dialect correctly | Atlas's own conformance (P5) |
| capability declarations are honest | the throughput number (§2.5's entire point) |
| error translation maps to the right exception types | quality-parity A/B on real workloads |
| usage accounting is populated and self-consistent | the cutover decision (§4.2) |

The left column is genuine engineering verification, not a smoke test, and it is the part
that historically breaks. The right column is the Spark lane's, later, on its own
schedule — which is the whole point of §4's dark-ship rule.

If Atlas turns out not to be OpenAI-compatible, the fallback is a recorded-transcript
fixture harness at the unit tier plus a live tier deferred to the Spark — weaker, and the
reason §3.5's assumption is worth confirming early even though it blocks only P4.

### 6.2 Acceptance per phase

- **P0–P2:** regression suite green; the byte-identical-default test (§4.1.3); doctor
  green on this Mac with `provider=ollama`; `SQUADOPS__LLM__PROVIDER=nonsense` fails
  startup loudly with a named error.
- **P3:** the suite passes against `OllamaAdapter` at both tiers on the Mac; every
  capability-honesty row exercised, including a declared-`False` flag proven to raise.
- **P4:** the suite passes against `AtlasAdapter` at the unit tier and — per §6.1 — the
  live tier against local Ollama's compatible surface.
- **P5:** A/B baseline recorded as an artifact, not a claim in a PR description.

Live-cycle validation before merge applies to any phase that touches the runtime path.
P0–P2 do; a smoke or lite cycle on the deployed local stack, with `provider=ollama`,
proving the default path is untouched.

## 7. Alternatives Considered

- **Write the Atlas adapter only, fix the leaks when they bite.** Rejected: sites 1–3
  mean the adapter would be constructed-and-ignored by runtime-api, 503 the model routes,
  and silently disable model preflight. The leaks are not adjacent work; they are the
  reason the swap does not currently function.
- **Do the neutrality groundwork now, adapter later** (the strict 1.7-pool reading).
  Rejected as the *plan*, retained as the §4.3 fallback: a neutrality refactor with no
  second implementation cannot be verified, and the conformance suite — the thing that
  makes neutrality checkable — needs two subjects to be a conformance suite at all.
- **Keep `isinstance` and add `isinstance(port, AtlasAdapter)` beside it.** Rejected:
  N providers × M call sites, and each new provider edits code that has no business
  knowing it exists. This is the `task_type ==` identity-branching class (#559) in adapter
  clothing.
- **A per-provider config section (`SQUADOPS__ATLAS__*`).** Rejected: forks the config
  surface per vendor and re-litigates every knob. One `llm` section with a `provider`
  discriminator matches `secrets`, `auth`, `sandbox`, and `cycles` — the established
  shape.
- **Make `LLMRouter` provider-aware (route per task type to different providers).**
  Deferred, not rejected — it is the router's documented 0.8.8 future and a real
  capability (small model for verdicts, large for authoring). It needs two *working*
  providers first, and folding it in here would couple a migration to a routing-policy
  design. Successor SIP.

## 8. Compatibility & Risks

- **Additive throughout.** `provider` defaults to `ollama`; `capabilities()` gets a
  concrete default; `list_available_models()` is the one method needing an Ollama impl at
  P1. No DDL, no wire-format change, no contract or manifest change.
- **Risk: `capabilities()` becomes aspirational.** Mitigated by the capability-honesty
  conformance row (§3.6) — a declared-`True` flag that is not exercised fails the suite.
  Unmitigated, this reproduces #572 in a new port.
- **Risk: site 3's semantics get flattened** — the highest-consequence subtle change here.
  "Provider cannot enumerate" and "model is absent" must stay distinct in both directions
  (§3.2). A false green here would let a cycle launch against a model that does not exist.
- **Risk: the model-alias table silently rots** as models are added per provider.
  Mitigated by §3.4's WARNING on unresolved names — the instrument that was missing when
  `qwen3.6:27b` ran unclamped.
- **Risk: doctor's provider-aware probe degrades the Ollama path.** Mitigated by P1's
  acceptance running doctor green on this Mac before merge.
- **Risk: this SIP and 1.6 collide on `capabilities/handlers/cycle/base.py`.** One
  two-line addition; §4.1.5 makes checking it a pre-PR step.
- **Risk: thesis-measurement discontinuity — the one that outlives this SIP.** Every
  measurement the project has banked (the FAY 6/6 window, the 98.5 lineage, shakedown
  greens, correction-rate baselines) was taken on the Ollama substrate. Switching engines
  changes the substrate under all of them at once. If the cutover happens without §3.6's
  quality-parity baseline, a later regression cannot be attributed — engine, or squad? —
  and the comparison base for the 1.8 scorecard is silently gone. This is the same class
  of reasoning the odd-minor convention already encodes (quarantine risky refactors so a
  regression is unambiguously the refactor). Mitigated by making parity a recorded,
  gating artifact of the cutover decision, never a post-hoc rationalization.
- **Risk: the throughput win does not materialize.** The SIP's justification (§2.5) is
  throughput; if Atlas is not meaningfully faster on real workloads, P0–P3 are still worth
  having (they close #313 and #301's LLM half and make the port honest) but the cutover
  should not happen. The A/B tier is what makes that a decidable question rather than a
  sunk-cost argument.
- **Risk to the Spark lane: none by construction, if §4.1 holds.** §4.1 is the mitigation
  and it is checkable per PR. That is the whole design of the dark-ship rule.

## 9. Relationship to Existing Work

- **#313** — absorbed as P1 (§2.4). **#301** — its LLM half closed by P2; the queue half
  stays in the 1.7 composition-root cluster (§10.1).
- **SIP-LLM-Emission-Contracts (proposed)** — complementary and deliberately
  non-overlapping. That SIP owns *what comes back* (typed emission contracts, structured
  output, extraction); this one owns *who is asked*. Its P5 is "Atlas adapter +
  conformance run + A/B baseline" — **this SIP delivers that, so if both are accepted, its
  P5 folds into this SIP's P4/P5 and its structured-output dimension is added to §3.6's
  suite as a new row.** Neither blocks the other: `response_schema` is additive to
  `LLMRequest`, and the conformance suite is designed to gain dimensions.
- **SIP-0101 (accepted)** — names provider A/B over identical replayed inputs
  ("identical inputs through Ollama and Atlas, as migration conformance") as a use case
  the replay harness enables. The replay harness is the natural driver for §3.6's A/B tier;
  P5 should use it rather than build a second comparison path.
- **#572 / queue capabilities** — the pattern §3.2 copies, doctrine included.
- **#423 / #427 skip-cause discipline** — governs §3.3's doctor behavior: an unrunnable
  check is an evidence gap, never a pass.
- **#559 strings-boundary** — extended here from `task_type` identity to *adapter*
  identity; sites 2 and 3 are the same defect class.
- **#410** — not absorbed; see §10.3.
- **#707** — listed under Track E in the 1.5 plan but concerns check-command allowlists,
  not the LLM port. It belongs with the typed-check-menu work (#504's lineage). Named here
  only to record that the omission is deliberate.

## 10. Open decisions (draft — resolve before acceptance)

### 10.0 Decision summary

The policy in one place, so it does not have to be reconstructed from five sections.
Design-review positions below are adopted into this draft; **items marked ⓞ still need
Jason's explicit word**, per the standing rule that a SIP's position is not a ruling.

**Blocked — nothing proceeds until answered:**

- *Nothing blocks P0–P3.* The neutrality groundwork stands on its own, closes #313, and is
  worth having even if Atlas never ships.
- **P4** is blocked on §10.2 — Atlas's endpoint shape confirmed, not assumed.
- **P5** is blocked on a live Atlas endpoint on the Spark.
- **The cutover** is blocked on all five §4.2 preconditions, including the §10.3a
  telemetry fix. ⓞ

**Diagnostic — informs, never gates:**

- **#410 thinking tokens** (§10.3). Explains *why* a throughput number moved; does not
  decide *whether* to switch. Capability flag declared at P0; the observability half keeps
  its own issue and schedule, depending on nothing here.
- **`decode_tokens_per_second`** (§3.6.1). The diagnostic beneath `wall_clock_ms`, which is
  the decision field.

**Deferred — named home, deliberately not here:**

- **Structured output / `response_schema`** → SIP-LLM-Emission-Contracts (§9).
- **#301's queue half** → the 1.7 composition-root cluster, behind its own design gate
  (§10.1).
- **#707 command allowlists** → the typed-check-menu lineage; on the 1.5 Track E list by
  filing accident, not by subject (§9).
- **Provider-aware routing** (small model for verdicts, large for authoring) → successor
  SIP; needs two working providers first (§7).
- **A durable per-generation throughput record** → surfaced by §10.3a, not solved by it;
  plausibly scorecard/1.8 territory.
- **Per-provider `MODEL_SPECS` restructuring** → deferred until a concrete second use
  (§3.4).

**Settled in this draft, recorded so review can contest rather than rediscover:** the
release boundary is 1.7-dark / 1.8+-cutover ⓞ (§4.3); P2 references #301 without closing
it (§10.1); the A/B decision field is `wall_clock_ms`, not t/s (§3.6.1).

**10.1 — #301's scope.** #301 covers the composition root bypassing *both* the LLM and
queue factories. This SIP proposes closing the LLM half at P2 and leaving the queue half
in the 1.7 composition-root cluster, which the 1.5 plan flagged as needing a **design gate
before code** because it alters runtime initialization. Splitting an issue across releases
needs an explicit ruling: close #301 here with a scoped title change, or reference it
without `Closes` and file the queue half separately. *Recommendation: the latter — a
partial fix references without closing, per the standing rule.*

**10.2 — Atlas's API surface. Confirmation rule, not an assumption held indefinitely.**
§3.5 assumes OpenAI-compatible (`/v1/chat/completions`, `/v1/models`), matching
SIP-LLM-Emission-Contracts Appendix A. Since Atlas is in-house this is a confirmation, not
an investigation — but **P4 stays blocked until it is confirmed in writing**, because an
adapter written against a guessed dialect is discovered wrong at integration, which is the
most expensive place to find out.

*Confirmed* means these five recorded in this SIP (Appendix B) before P4 opens:

| # | Fact | Sets |
|---|---|---|
| 1 | chat/generation endpoint path + request shape | the adapter's transport |
| 2 | streaming: supported? SSE or NDJSON? | `chat_stream` / `chat_stream_with_usage` |
| 3 | model-listing endpoint, or none | `model_listing` |
| 4 | model load/unload management, or none | `model_management` |
| 5 | usage fields returned, incl. any timing/duration fields | `streaming_usage`, and §3.6.1's `prefill_ms` / `load_ms` / `total_ms` |

**Failure mode if it is not OpenAI-compatible** — bounded, and worth stating so the
assumption is not load-bearing beyond its blast radius: the transport layer of
`adapters/llm/atlas.py` changes, one file. Nothing in P0–P3 moves, the port surface does
not move, and the conformance suite does not move — it is written against the *contract*,
which is why P3 precedes P4 (§5). The one real casualty is §6.1's Mac live tier, which
depends on Ollama's `/v1` compatibility surface as a stand-in; that would fall back to a
recorded-transcript fixture harness at the unit tier, with the live tier deferred to the
Spark. Strictly weaker, and the reason to confirm early even though it blocks only P4.

**10.3 — #410 (thinking tokens): diagnostic, not gating.** Recorded position, after this
was argued in both directions during drafting.

An intermediate revision made #410 a precondition for the cutover, reasoning that
`eval_count` conflates thinking with content so a wall-clock difference could not be
attributed. **That was an overcorrection.** Thinking tokens cost real time and are
legitimately part of throughput; and once token count is recorded alongside latency
(§3.6), a different thinking posture simply *appears* as a different token count. The A/B
is interpretable without splitting them.

The split remains genuinely useful — knowing that 60% of a 7.6-minute generation bought
unread reasoning is actionable, and it is why #410 exists — but it diagnoses *why* a
number moved, and does not gate deciding *whether* to switch.

*Recommendation: declare the `thinking_tokens` capability flag at P0 (§3.2, cheap — the
port surface is being touched anyway) so the port can express the concept when a provider
supports it. Leave #410's observability half in its own issue, on its own schedule,
depending on nothing here.*

**10.3a — the throughput telemetry gap (#793), found while drafting.** Separately from #410:
`tokens_per_second` is computed by the Ollama adapter, threaded onto `GenerationRecord`
by the handlers — and then **dropped** by `LangFuseAdapter.record_generation`
(`adapters/telemetry/langfuse/adapter.py:188`), which rebuilds the record field-by-field
for redaction and copies ten of eleven fields, omitting that one. It silently defaults to
`None`, so LangFuse metadata has carried a null throughput for every generation since
SIP-0061. `parent.generation()` also passes no `start_time`/`end_time`, so LangFuse cannot
derive it either, and the emission runs on a buffered daemon thread well after the call.

Consequence: **the only working throughput surface is the Prefect log line**, and t/s is
persisted nowhere (zero hits in `adapters/persistence/`, `cycles/`, `infra/`).

**Disposition — non-gating for the adapter, hard-gating for the cutover.** Deciding a
migration on a log-scraped number is precisely the evidence posture SIP-0096 forbids, so
this cannot stay a footnote:

- **Own issue, own owner, own schedule — filed as #793** (2026-08-08), independent of
  #410: that one is thinking tokens missing from LangFuse; this is *throughput* reading
  null for every generation since SIP-0061. The repair is `dataclasses.replace()` in the
  redaction copy rather than adding the missing keyword, so a future field addition cannot
  regress it the same way, plus a round-trip completeness test on both records.
- **Blocks nothing in P0–P5.** The adapter, suite, and A/B harness all proceed regardless.
- **Precondition of the cutover** — §4.2 item 3. Fixed and deployed before the decision
  reads throughput evidence, not before the adapter is written.

The larger question — a *durable, queryable* per-generation throughput record rather than
a restored metadata field — is surfaced here and deliberately not solved. It plausibly
belongs with the 1.8 scorecard, which needs to grade over exactly this kind of series.

**10.4 — Release placement. ⓞ Needs Jason's explicit word.** §4.3's argument for 1.7-dark
is a reading of the feature-free rule, and readings of a release convention are the owner's
to make, not an implementer's.

Design review's recommendation: **keep the 1.7-groundwork / 1.8+-cutover split unless the
review explicitly overrides it.** Adopted into this draft — §5's phasing table carries the
release column, and §4.2a shows the split is what makes a failed P5 cost nothing.

§4.3's fallback (P0–P2 in 1.7, adapter and suite deferred) stays available as a **clean
fallback, not a competing interpretation.** If the split is overridden, P0–P2 still land as
1.7 debt-paydown on their own merits — they close #313 and make the port honest with no
reference to Atlas at all. That is a smaller plan, not a different one, and nothing in
P0–P2 changes if it is taken.

## Appendix A — Coupling inventory verification

Reproduce the §2.1 inventory against any revision:

```bash
# Sites 1, 2, 3 — vendor type named in src/
grep -rn "OllamaAdapter" --include="*.py" src/

# Site 4 — doctor's shell-outs
grep -rn "\"ollama\"" --include="*.py" src/squadops/bootstrap/

# Site 7 — factory callers, and whether any passes `provider`
grep -rn "create_llm_provider" --include="*.py" src/ adapters/
```

At `d4c3f9a2`: **7 code hits** naming `OllamaAdapter` across 3 files (`main.py` ×2,
`routes/cycles/models.py` ×3, `routes/cycles/cycles.py` ×2), plus **1 docstring
reference** in `cycles/preflight.py:226`. The docstring is not a coupling — `preflight.py`
is genuinely neutral (§3.3) — but it names the vendor method as the expected source and
should be repointed at `list_available_models()` in P1, or it will teach the next reader
the wrong seam.

Also at `d4c3f9a2`: 2 shell-outs in `bootstrap/setup/checks.py` (`ollama list` at :449,
`ollama ps` at :595) across 4 wrapper/call sites; and **exactly 1 factory call site**
(`agents/entrypoint.py:362`), passing no `provider`.

## Appendix B — Provider dialect notes (non-normative, time-bound)

Recorded for implementation convenience only; the normative surface is §3.2, §3.3, and
§3.6.

- **Ollama** (current): `/api/generate`, `/api/chat` (NDJSON streaming), `/api/tags`,
  `/api/pull`, `/api/delete`. Usage via `prompt_eval_count` / `eval_count` /
  `eval_duration` (ns). Native JSON-Schema constrained decoding via `format` (v0.5+).
  **Also serves an OpenAI-compatible surface at `/v1`** — the §6.1 rough-test path.
- **Atlas** (in-house engine, DGX Spark-tuned; §2.0): assumed OpenAI-compatible per §3.5 —
  `/v1/chat/completions` with SSE streaming, `/v1/models`,
  `usage.{prompt,completion,total}_tokens`. Note that the OpenAI shape carries **no native
  tokens/sec field**, unlike Ollama's `eval_count`/`eval_duration`. Since throughput is
  this SIP's entire justification (§2.5), the adapter must either compute t/s client-side
  from wall-clock and completion tokens — the honest option, and adequate for A/B
  comparison — or Atlas exposes a native timing field, which is the better answer if it is
  cheap to add on the engine side. **Worth deciding before P4**: an in-house engine can
  simply report it, and a native number beats one inferred across an HTTP boundary.
- **vLLM / llama.cpp**: OpenAI-compatible plus guided decoding (`guided_json`, GBNF).
  Listed only as dialect precedent for the structured-output work that
  SIP-LLM-Emission-Contracts owns, not as candidate providers.
