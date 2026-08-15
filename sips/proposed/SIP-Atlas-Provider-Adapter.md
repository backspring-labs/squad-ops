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

**Atlas is a third-party open-source LLM inference engine, hand-tuned for NVIDIA DGX
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

> **The one binding constraint (owner ruling, 2026-08-08): do not disturb the 1.6 feature
> work.** Release placement is explicitly *not* load-bearing — this may ship formally dark
> in 1.7 or simply land inert whenever it is ready; strict even/odd compliance is waived
> for this change on the grounds that it is well insulated. **The target is that Atlas is
> selectable and measured in time for 1.8.** Everything in §4.1 exists to serve the 1.6
> guardrail, and that checklist is the real acceptance bar of this document.

**Operational constraint, load-bearing and non-negotiable (§4):** every phase here is
**inert on merge**. No shipped default, compose file, `.env.example` value, agent image,
or profile changes the model runner. The Spark lane is running 1.6 authored-manifest
validation sprints against Ollama; this work must be invisible to them until an explicit,
separate cutover decision (§4.2).

## 1.1 Decision summary — blocked, diagnostic, deferred

The policy in one place, so it does not have to be reconstructed from five sections.

### Owner rulings (2026-08-08) — both previously ⓞ, now settled

**Ruling 1 — release placement is not load-bearing.** Strict even/odd compliance is
**waived** for this change on the grounds that it is well insulated. It may ship formally
dark in 1.7 or simply land inert whenever ready. **The single binding constraint is the
1.6 guardrail (§4.1); the target is Atlas selectable and measured for 1.8.** §4.3's
placement argument is retained only as background — it no longer gates anything.

**Ruling 2 — no formalized cutover framework.** The interest is in **raw observed
performance**, not a threshold gate: *"the story should tell itself once I run a cycle
against the new adapter."* The deliverable is therefore **a working provider switch plus
honest numbers**, and the decision is owner judgment on reading them. Consequences:

- **§C.4's threshold tables are removed.** The benchmark *reports*; it does not adjudicate.
- **§4.2's precondition list is deflated** — no gate stands between a measured Atlas and a
  config change.
- **What survives is measurement hygiene, not governance** (§C.5): cold-vs-warm, arm
  ordering, token-count shift, and quantization mismatch each fake a result convincingly.
  These are kept because they are what make an observed number *real* — not because they
  gate anything.
- **P2 is promoted from plumbing to the headline deliverable.** `LLMConfig.provider` *is*
  the config flexibility the ruling asks for; without it there is no way to point a cycle
  at Atlas without hacking the composition root.

**Blocked — nothing proceeds until answered:**

- *Nothing blocks P0–P3.* The neutrality groundwork stands on its own, closes #313, and is
  worth having even if Atlas never ships.
- **P4** is blocked on §10.2 — Atlas's endpoint shape confirmed, not assumed.
- **P5** is blocked on a live Atlas endpoint on the Spark.
- **Nothing blocks the switch itself** beyond P2 existing and Atlas answering. Per Ruling 2
  the cutover is a config change made on observed results, not a gated event.

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
- **Adopting vLLM as a provider** → a separate decision. P6 runs it as an A/B *control*
  (§3.5a); nothing here commits to shipping it. If the control arm reveals Atlas ≈ vLLM,
  that decision becomes live on its own merits.
- **A durable per-generation throughput record** → surfaced by §10.3a, not solved by it;
  plausibly scorecard/1.8 territory.
- **Per-provider `MODEL_SPECS` restructuring** → deferred until a concrete second use
  (§3.4).

**Settled in this draft, recorded so review can contest rather than rediscover:** P2
references #301 without closing it (§10.1); the headline throughput number is
`wall_clock_ms`, with decode t/s as its diagnostic (§3.6.1); #793 is a real bug worth
fixing but **no longer a precondition of anything** under Ruling 2 — the Prefect log line
carries throughput adequately for an owner reading results.

## 2. Problem Statement

### 2.0 What Atlas is (recorded here because nothing else records it)

**Atlas is a third-party open-source LLM inference engine, hand-tuned for NVIDIA DGX
Spark.** It is a local engine — a direct replacement for Ollama on the Spark box, not a
hosted service. No API key, no egress, no per-token cost, no rate limits.

| | |
|---|---|
| **Publisher** | Avarok Cybersecurity — `github.com/Avarok-Cybersecurity/atlas`, `atlasinference.io` |
| **Built with** | pure Rust + CUDA; ships as a single binary, no Python, no PyTorch |
| **Primary target** | **NVIDIA DGX Spark (GB10, SM121)** — fully verified, not a port. AMD Strix Halo (gfx1151) via SCALE from the same CUDA source; Apple/Intel named as future contributions |
| **License** | **dual: Community Edition AGPLv3, Enterprise commercial** |
| **Models** | tuned recipes across Qwen3/3.5/3.6/3-Next/3-VL, Gemma, Mistral, MiniMax, Nemotron — **including `qwen3.6-27b-fp8`, the model the `full` profile pins** |

**Corrected 2026-08-15.** This section previously read "hand-tuned **in-house**," and that
error propagated to seven other sites in this SIP. Its provenance is worth recording,
because the mechanism matters more than the fact: the first draft (`6d7409a3`) correctly
left Atlas undefined and §10.2 read *"What Atlas is. Not recorded anywhere in the repo."*
The next commit (`ac956222`, titled *"correct Atlas premise"*) closed that open question by
**assumption rather than research**, and simultaneously wrote the same claim to session
memory — so every later reading was reinforced by the invention instead of checking it. An
open question was more honest than the answer that replaced it.

*What survives the correction:* local, self-hosted, open-source, DGX Spark-tuned, and the
throughput motive (§2.5) — all confirmed, and the Spark being Atlas's *primary verified
target* is stronger than this SIP previously claimed. *What changes:* §10.2 item 5 is no
longer cheap-at-the-source (see there), the "maintenance burden" framing in §3.5a inverts
into third-party dependency risk (§8), and **the AGPLv3/commercial split is a deployment
decision this SIP previously had no reason to surface** — it is an owner call, recorded
here so it is made deliberately rather than discovered at adoption.

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
as "the *expected* Atlas path." **Confirmed from vendor documentation 2026-08-15** (§10.2
table, Appendix B): Atlas serves `POST /v1/chat/completions` and `GET /v1/models` on port
8888, OpenAI-shaped. It is confined to P4 regardless: if some detail is wrong, the
transport layer of one file changes and nothing else in this SIP moves.

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

### 3.5a vLLM as a control arm (P6 — optional, non-gating)

**The problem a two-provider A/B cannot solve.** Ollama is a convenience wrapper over
llama.cpp; it does not compete on raw throughput. So "Atlas beat Ollama" is consistent with
two very different worlds — Atlas is exceptionally well tuned, or Ollama was simply a low
bar. **A two-point comparison cannot tell those apart, and the difference decides whether
Atlas is worth maintaining.**

vLLM resolves it as a **control**: a serious, externally-maintained performance baseline
that nobody here can tune to flatter the result.

| Outcome | Honest reading |
|---|---|
| Atlas > vLLM > Ollama | the hand-tuning is real and Spark-specific. Adopt Atlas |
| Atlas ≈ vLLM > Ollama | the win was "Ollama is slow," not tuning skill. **Consider deploying vLLM and avoiding the Atlas dependency** |
| vLLM > Atlas | the tuning is behind a commodity engine. Strong signal, cheaply bought |

Any of the three is worth knowing before taking on the dependency. **Amended 2026-08-15:**
this row previously read "retiring the Atlas *maintenance burden*," which assumed we owned
the engine. We do not (§2.0). The cost being weighed is therefore not maintenance effort
but **third-party dependency risk** — upstream release cadence, the AGPLv3/commercial
license split, and no ability to fix the engine ourselves on our own schedule. That is a
different trade, and on the middle row it argues *more* strongly for vLLM, which carries
Apache-2.0 and a far larger contributor base.

**One adapter per provider. No shared dialect base — amended 2026-08-08.**

An earlier revision proposed a shared `OpenAICompatibleAdapter` serving both vLLM and
Atlas, on the theory that a common dialect makes them differ only in capability
declarations. **That is withdrawn**, for two reasons that only became clear once the
dialect was examined rather than assumed:

1. **Atlas is already expected to diverge.** §10.2 asks Atlas to emit duration fields the
   standard OpenAI response shape does not carry (see there for why the A/B needs them).
   A class shared with vLLM would need Atlas-specific handling inside it on day one —
   a conditional keyed on which provider you are, which is exactly the identity-branching
   #559 bans. Separate types *are* the polymorphic answer.
2. **It inverts the no-gold-plating rule.** Extracting a base on the *expectation* that
   Atlas matches vLLM builds shared structure on the same §10.2 assumption this SIP
   otherwise refuses to rely on. Extraction is something done *after* two implementations
   exist and their overlap is demonstrated — not before, from a guess about one of them.

So: `OllamaAdapter`, `VLLMAdapter`, `AtlasAdapter`, each implementing `LLMPort`
independently, each declaring its own capabilities, none aware of the others. If real
overlap appears once two exist, extracting shared helpers then is cheap and evidence-based.

**What makes per-provider adapters affordable is the conformance suite (§3.6).** The usual
objection is duplicated bug surface — fix a streaming defect in one adapter, forget the
other. Every adapter runs the *same* assertions, so a defect in any of them fails the same
test. That is why P3 precedes P4, and why three adapters is a manageable number rather than
three times the risk.

**Naming:** `VLLMAdapter` in code (every adapter class in the tree is CapWords —
`LangFuseAdapter` normalizes a product branded "Langfuse"; PEP 8 N801 agrees), `"vllm"` as
the provider string alongside `"ollama"`, and "vLLM" in prose where the brand belongs.

**Secondary value:** it makes the conformance suite honest. Two adapters can silently
encode "whatever these two happen to do." A third that the team does not control tests the
*contract* rather than the house style. And it hedges P4/P5 failure — a second migration
target already proven through the same gate.

**Lineage:** this is #313's original motivating case. Its title reads *"blocks vLLM/alt-
backend swap,"* and its body anticipates exactly this step: *"adding the actual vLLM
adapter + factory branch is a separate, follow-on step when a backend switch is real — the
factory is built for it."*

**Status: P6's adapter is built and validated (2026-08-08).** `VLLMAdapter` ships and
passes the full conformance suite — unit tier plus **live tier against a real
`vllm-metal` server on Apple Silicon** (vLLM 0.26.0, MLX backend, Metal paged
attention), 14/14. That is the value §3.5a claimed and could not previously demonstrate:
the contract now holds against an OpenAI-compatible implementation **nobody on this team
wrote**, rather than against Ollama's own `/v1` surface.

It also earned its keep on contact: registering a second adapter exposed four "shared"
assertions in the conformance suite with Ollama's model name baked in — the suite was
provider-neutral in intent and Ollama-shaped in fact, exactly the trap the 1.5 plan named.

**What the Mac run is NOT.** A local `vllm-metal` server is *adapter* validation, never
the §3.5a control arm. Different chip, different backend (MLX vs CUDA), different memory
architecture — no throughput number from this box informs the Spark comparison. An
indicative side-by-side was collected and is deliberately **not** recorded as a result:
both engines were resident at once (§C.5 trap 1), the quantizations differ (trap 5), and
the two rate figures measure different things (Ollama decode-only from native timings,
vLLM wall-clock-derived including prefill). It demonstrated that the artifact fields
collect end to end; it measured nothing.

**Open risk, stated rather than assumed:** vLLM's maturity on DGX Spark's GB10
Grace Blackwell / ARM64 platform is **unverified here** — the Apple Silicon result above
says nothing about it. Its optimization lineage is
datacenter x86 + CUDA. If it will not run well on the box, the control arm is unavailable
and P6 drops — which costs nothing, because P6 gates nothing. Verify before scheduling it,
not after.

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
  migration decision instrument** and the reason the SIP exists (§2.5). Per Ruling 2 it
  **reports** rather than gates — the numbers go in front of owner judgment (§C.4). It
  carries two:
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

#### 3.6.1 The A/B artifact — the single source of truth

**The cutover decision reads one named artifact and nothing else.** Not a PR description,
not a summary in a comment, not a remembered number from a run. Appendix C's runbook
**must emit this artifact verbatim**, and §4.2's decision is taken against it.

Everything else in this SIP is reasoning about what to measure; this is the record that
survives. A migration reviewed a year later has only this.

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

**Amended by Ruling 2 (§1.1).** The earlier draft gated the cutover behind five
preconditions. That framework is withdrawn: the owner's stated interest is raw observed
performance, decided by judgment on the results, not by a threshold gate.

What remains is a **sequence, not a gate**:

1. **P2 exists**, so a provider is selectable by config rather than by editing the
   composition root. This is the deliverable — everything else is measurement.
2. **Atlas answers on the Spark** and passes the conformance suite (P4/P5) — this stays,
   because an adapter that mistranslates errors or miscounts usage produces numbers that
   are wrong rather than merely unflattering.
3. **A cycle runs against it**, and the results are read.

Then the switch is a config change, made on what was observed.

**What the SIP still asserts, because it is measurement integrity rather than governance:**
the numbers must be *real* before they are read. §C.5's traps — cold-vs-warm engines, arm
ordering, token-count shift, quantization mismatch — each produce a clean-looking result
that is simply false. Those guards are cheap and stay. The thresholds that used to sit on
top of them are gone.

**Not pre-authorized, still:** this SIP changes no default. It delivers the switch and the
instrument; pulling the switch remains a separate, deliberate act.

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
the dark-ship rule, and it is what makes Ruling 1's waiver safe: placement stops mattering
precisely because nothing here can act until someone chooses it.

### 4.3 Release placement — waived, and why that is safe

**Ruled 2026-08-08 (§1.1, Ruling 1): strict even/odd compliance is waived for this change.**
It may ship formally dark in 1.7 or simply land inert whenever ready. **Target: Atlas
selectable and measured for 1.8.**

The waiver is safe for the same reason §4.2a's middle row holds — **nothing here can act
until someone selects it.** The parity convention exists to keep a regression attributable
to one cause; a change that no default reaches cannot be the cause of anything. The
convention is not being bent, it simply has no purchase on inert code.

That is *only* true while §4.1 holds. **The waiver is on release parity, not on the
guardrail** — if a phase stops being inert, it is a feature again and the convention
reapplies with full force.

Recorded because it remains true and may matter to a future reader: the earlier argument
for 1.7 specifically was that 1.7's identity is *"every port is actually a port,"* that
sites 1–6 are exactly that release's thesis, and that a second implementation no default
selects meets the same feature-free test 1.5 applied at its own cut. That argument is now
background rather than a gate.

## 5. Phasing

Each phase is independently shippable, inert per §4.1, and one PR.

**Every phase below is inert on merge and none changes which engine serves a token.**
Release placement is waived (§4.3); phases land when ready, targeting Atlas selectable and
measured for 1.8. The line that *is* hard: a PR from this SIP that changes a shipped
default has left the SIP's scope, regardless of how green its tests are.

**P2 is the headline deliverable, not plumbing** (Ruling 2). `LLMConfig.provider` is the
config flexibility the ruling asks for — without it there is no way to point a cycle at
Atlas short of editing the composition root. It is also the phase touching the hottest 1.6
files, so it is the one to time deliberately against §4.1.5.

| Phase | Content | Size | Depends on | Release |
|---|---|---|---|---|
| **P0** | `capabilities()` on `LLMPort` + Ollama declarations + sites 2/3 stop using `isinstance` + `thinking_tokens` flag declared (§10.3) | S | — | 1.7 |
| **P1** | `list_available_models()` on-port + `ModelInfo` + Ollama impl + doctor provider-aware + #423-style skip cause — **`Closes #313`** | M | P0 | 1.7 |
| **P2** | `LLMConfig.provider` + factory wiring at both composition roots + unknown-provider raises — **references #301, does NOT close it** (§10.1) | S | P0 | 1.7 |
| **P3** | Conformance suite, unit + live tiers, run green against Ollama as the only adapter | M | P0–P2 | 1.7 |
| **P4** | Atlas adapter + conformance run + capability declarations + capture the three discarded duration fields (§3.6) | M | P3, **§10.2 confirmed** | 1.7 |
| **P5** | A/B tier + the artifact contract of §3.6.1 recorded, per Appendix C | S | P4, live Atlas endpoint on Spark | 1.7 |
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

**P0–P3 are Atlas-independent, literally.** They reference no vendor, need no endpoint, and
close #313 on their own merits. If Atlas slips, is descoped, or never ships, P0–P3 still
land as 1.7 debt paydown. Nothing added since — the runbook, the control arm — weakens
this; both attach at P4 or later by construction.

### 5.1 Out of the phase ladder — P6, the optional control arm

**P6 is not part of the migration.** It is deliberately outside the table above so this SIP
does not read as two migrations. **One SIP, one migration target: Atlas.**

| | |
|---|---|
| **What** | a vLLM adapter as a third conformance subject and A/B control arm (§3.5a) |
| **Size / depends on** | S–M · P4 (needs the OpenAI-compatible base to exist first) |
| **Gates** | **nothing.** Not P4, not P5, not the cutover, not this SIP's acceptance |
| **Default position** | **may inform the cutover decision; never blocks it.** If P6 is not run, §C.4's decision proceeds on the two-arm comparison with its interpretive limit (§3.5a) stated in the artifact |
| **Adoption** | out of scope — P6 runs vLLM as a *control*, not a migration target (§1.1, deferred) |

## 6. Verification

### 6.1 Rough-testing on the Mac, without an Atlas instance

**Local Ollama already serves an OpenAI-compatible surface.** Verified on this box
(Ollama 0.12.3):

```
$ curl -s http://localhost:11434/v1/models
{"object":"list","data":[{"id":"qwen2.5:14b","object":"model","created":...,"owned_by":"library"}, ...]}
```

**The live tier exists and this claim is no longer hypothetical** — P3 shipped
`tests/integration/llm/test_llm_port_conformance_live.py`, run green against real
local Ollama (14 checks, ~4s). It names no vendor: the adapter comes from
`create_llm_provider`, so pointing it at Atlas on the Spark is an env change, not
an edit.

```
SQUADOPS_CONFORMANCE_PROVIDER=ollama \
SQUADOPS_CONFORMANCE_BASE_URL=http://localhost:11434 \
SQUADOPS_CONFORMANCE_MODEL=qwen2.5:3b-instruct \
  pytest tests/integration/llm -v
```

Skipped entirely when those are unset, so it never blocks a normal run.
Generations are capped at 16 tokens — this is a contract check, not the §C.2
benchmark, and the two must not be confused.

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

### 6.1a A/B execution protocol — how the comparison is actually run

Provider selection is resolved **once per process, at container boot**
(`agents/entrypoint.py:362`, in `_create_ports()`). Each agent is its own container, so
switching providers is an env change plus a restart of the agent containers — **there is
no per-cycle provider knob, and this SIP deliberately does not add one** (§7 defers
provider-aware routing to a successor SIP).

That constraint sounds limiting and mostly is not, because **the primary measurement does
not run cycles at all.** Three levels, each answering a different question:

| Level | Instrument | Answers | Restart? | Cost |
|---|---|---|---|---|
| **1 — Generation** | conformance A/B tier: one process, **both adapters instantiated**, identical stored prompts to each | *Is the engine faster?* | **No** | a test run |
| **2 — Cycle** | two full cycles, same request profile, one per provider | *Does emission quality hold end to end?* | Yes, between | two cycle runs + a redeploy |
| **3 — Shakedown** | one cycle under Atlas on the deployed stack | *Does it work in situ?* | Yes — it **is** the cutover | §4.2 item 4 |

**Level 1 carries the throughput verdict** and produces §3.6.1's artifact rows. Adapters
are ordinary objects: instantiate both, point them at two endpoints, send byte-identical
prompts. Inputs are identical by construction, which no cycle-level comparison can
promise.

**Level 2 measures what Level 1 structurally cannot** — whether work products survive the
engine change (extraction health, malformation classes, correction rates). Use the
SIP-0101 replay harness to control inputs: restore the same boundary checkpoint and run
the remainder under each provider, so the comparison is not confounded by divergent
upstream generations. Note the shipped 1.5 slice does **cycle-prefix restore**, not
prompt-level replay — it constrains the inputs, it does not equalize them.

**Protocol rules — these are the difference between a measurement and a number:**

1. **One engine serving at a time**, even though both are installed. Two engines resident
   on one box contend for GPU memory and thermal headroom, and the contention lands in the
   timing being measured.
2. **Discard warm-up runs; assert `load_ms ≈ 0` on every measured call.** A cold engine's
   first call pays model load. Comparing a warm Ollama against a cold Atlas manufactures a
   throughput win. This is why `load_ms` is a required artifact field (§3.6.1) rather than
   a nice-to-have — it makes the confound *detectable* instead of merely avoidable.
3. **Same model weights, same quantization, both sides.** Model naming differs per provider
   (§2.3), so record the resolved name verbatim on each row and verify they refer to the
   same weights. An unnoticed quantization difference invalidates everything.
4. **Interleave Level 2 cycles** (A, B, A, B) rather than running all of one then all of
   the other, so box-state drift does not alias onto the provider variable.

Rule 4 is where a per-cycle provider knob would genuinely help — it would allow
interleaving without a redeploy between every run. That is a real argument for the
successor routing SIP, and **not** a reason to build it here: for a one-time migration
decision, redeploying between cycles is adequate and vastly cheaper than the machinery.

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
- **Risk: third-party dependency on Atlas — added 2026-08-15, and previously invisible.**
  While this SIP believed Atlas was in-house (§2.0), adoption looked like taking on
  maintenance we controlled. It is an external project: upstream sets the release cadence,
  we cannot fix the engine on our own schedule, and **the Community Edition is AGPLv3 with
  a separate commercial Enterprise tier** — a licensing question this SIP had no reason to
  raise while the premise was wrong, and an owner decision rather than a technical one.
  Partly mitigated by the design already in place: `provider` is config-selected and
  defaults to `ollama` (§3.2/P2), so the dependency is reversible by configuration rather
  than by a code migration. Note this cuts against Atlas on §3.5a's middle row, where vLLM
  carries Apache-2.0 and a much larger contributor base.
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

*The blocked / diagnostic / deferred policy these decisions produce is summarized up
front in §1.1. This section carries the reasoning behind each.*

**10.1 — #301's scope.** #301 covers the composition root bypassing *both* the LLM and
queue factories. This SIP proposes closing the LLM half at P2 and leaving the queue half
in the 1.7 composition-root cluster, which the 1.5 plan flagged as needing a **design gate
before code** because it alters runtime initialization. Splitting an issue across releases
needs an explicit ruling: close #301 here with a scoped title change, or reference it
without `Closes` and file the queue half separately. *Recommendation: the latter — a
partial fix references without closing, per the standing rule.*

**10.2 — Atlas's API surface. Confirmation rule, not an assumption held indefinitely.**
§3.5 assumes OpenAI-compatible (`/v1/chat/completions`, `/v1/models`), matching
SIP-LLM-Emission-Contracts Appendix A. **Amended 2026-08-15: Atlas is third-party (§2.0),
so this is an investigation after all** — against published documentation and then a live
endpoint, not a question to a colleague. **P4 stays blocked until confirmed in writing**,
because an adapter written against a guessed dialect is discovered wrong at integration,
which is the most expensive place to find out.

**This table is the *only* gate on opening P4.** Not "mostly confirmed," not "confirmed in
conversation" — five facts recorded in Appendix B.

Four are now answered **from vendor documentation** (`atlasinference.io`, the repo README
and `QUICKSTART.md`, read 2026-08-15). Doc-derived is not the same standard as measured:
each is marked with what would upgrade it, and **only item 5 remains genuinely open.**

| # | Fact | Sets | Status (2026-08-15) |
|---|---|---|---|
| 1 | chat/generation endpoint path + request shape | the adapter's transport | ✅ **docs** — `POST /v1/chat/completions`, OpenAI request shape, default port **8888** bound to `127.0.0.1` (`--bind 0.0.0.0` to expose). Model identifier is the HuggingFace path (e.g. `Sehyo/Qwen3.5-35B-A3B-NVFP4`), *not* a fixed literal — the marketing example's `"model":"atlas"` appears to be an alias, and which form the adapter must send is a live-verification item |
| 2 | streaming: supported? SSE or NDJSON? | `chat_stream` / `chat_stream_with_usage` | ⚠️ **docs, partial** — `"stream": true` supported and described as OpenAI-compatible, implying SSE `data:` frames terminated by `[DONE]`. The frame shape is *not* documented; verify before relying on `VLLMAdapter`'s parser shape |
| 3 | model-listing endpoint, or none | `model_listing` | ✅ **docs** — `GET /v1/models` is served. Response shape undocumented; if it matches OpenAI's `{"object":"list","data":[{"id":…}]}` then `ModelInfo` carries `None` for size and modified-at, exactly as vLLM does |
| 4 | model load/unload management, or none | `model_management` | ⚠️ **inferred** — no load/unload API appears in the docs; models are launched process-side via `serve <HF-ID>` / recipes. Expect `model_management: False`, but §3.2's capability-honesty rule requires this be *observed*, not assumed |
| 5 | usage fields returned, **and specifically whether prefill / load / total durations are emitted** — see below | `streaming_usage`, and §3.6.1's `prefill_ms` / `load_ms` / `total_ms` | ❌ **OPEN — the one real blocker.** Docs show the standard `usage` object and no timing metadata; benchmark tok/s figures are measurement methodology, not response fields. Neither confirmed nor denied in writing |

**Anything marked ⚠️ or ❌ is settled the same way: one session against a live Atlas on the
Spark.** Atlas is CUDA/GB10 — it cannot run on the Mac, so unlike the vLLM control arm
(§3.5a, validated locally) there is no local shortcut. That session is the whole remaining
cost of opening P4.

**Item 5 is an ask, not just a question — measured, not assumed.** The standard OpenAI
response shape carries **no duration fields at all**. Confirmed against this box's Ollama,
which serves both dialects:

| Field | Ollama native `/api/chat` | the same server's `/v1` shim |
|---|---|---|
| token counts | yes | yes |
| `eval_duration` (decode) | yes | **absent** |
| `prompt_eval_duration` (prefill) | yes | **absent** |
| `load_duration` (model residency) | yes | **absent** |
| `total_duration` | yes | **absent** |

Those four are exactly §3.6.1's `prefill_ms` / `load_ms` / `total_ms`. Two consequences:

1. **Ollama keeps its native adapter.** Moving it onto the OpenAI shape would delete the
   attribution half of the A/B *on the baseline arm*, and drop `model_management` to False.
2. **If Atlas ships the plain OpenAI shape, the A/B is asymmetric** — full attribution on
   the Ollama arm, wall-clock and token counts only on the Atlas arm. `wall_clock_ms`
   survives (the handler measures it client-side), so a decision is still possible, but
   "is the win in decode, prefill, or residency?" becomes answerable for one side only.

**Amended 2026-08-15 — this was the costliest consequence of the in-house error.** The
original read: *"Atlas is in-house, so this is cheap to fix at the source: emit the
durations. Recorded here as an explicit ask on whoever owns the engine."* There is no
in-house owner to ask (§2.0). The ask does not disappear, but it changes shape and price:

1. **Upstream feature request** to Avarok — free to file, no control over whether or when
   it lands, and it cannot be a precondition for our own schedule.
2. **Accept wall-clock derivation**, exactly as `VLLMAdapter` already does — and inherit
   the limitation that adapter documents in its own module docstring: the number is
   *inclusive of prefill and queueing* where Ollama's native figure is decode-only, so
   **the two are not interchangeable.** That is precisely why §3.6.1 makes `wall_clock_ms`
   the decision field and treats rate as a diagnostic.

**Option 2 is the default and requires no one's cooperation**, so item 5's answer coming
back "no durations" does not block P4 — it makes the A/B asymmetric in the way consequence
2 below already anticipates. File the request; do not wait on it.

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

**10.4 — Release placement. RULED 2026-08-08 — waived.** Strict even/odd compliance does
not apply to this change; it is well insulated. Ships dark in 1.7 or lands inert whenever
ready, targeting Atlas selectable and measured for 1.8. **The binding constraint is the 1.6
guardrail (§4.1), not release parity.** Full reasoning and the limits of the waiver: §4.3.

**10.5 — Cutover framework. RULED 2026-08-08 — not wanted.** No threshold gate; the
interest is raw observed performance read by owner judgment, with config flexibility to
choose the provider afterwards. §C.4's threshold tables are removed and §4.2's precondition
list is deflated to a sequence. Measurement *hygiene* survives (§C.5) because it is what
makes an observed number real, not because it governs a decision.

Consequence worth recording: **#793 stops being a precondition of anything.** It remains a
real bug worth fixing — throughput reads null in LangFuse for every generation — but under
this ruling the Prefect log line carries throughput adequately for an owner reading
results, so nothing waits on it.

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
- **Atlas** (third-party engine by Avarok Cybersecurity, DGX Spark-tuned; §2.0) — **updated
  2026-08-15 from vendor documentation; see §10.2's table for per-item confidence.**
  OpenAI-compatible: `POST /v1/chat/completions`, `GET /v1/models`, default port **8888**
  bound to `127.0.0.1`. Also serves **Anthropic (`/v1/messages`) and Responses dialects on
  the same port** — irrelevant to `LLMPort`, recorded so a future reader does not mistake
  the OpenAI surface for the only one. A `/tokenize` endpoint exists. No auth is
  documented; if one appears it enters via `SecretManager` as a `secret://` ref, which the
  factory already supports. No documented health endpoint — `health()` will likely probe
  `/v1/models`, as the vLLM adapter does. Models are launched process-side
  (`serve <HF-ID>`, recipes), so expect `model_management: False`. Usage is the standard
  `usage.{prompt,completion,total}_tokens` with **no native tokens/sec or duration
  fields** — so, exactly as with vLLM, the adapter computes t/s client-side from
  wall-clock, inclusive of prefill (§10.2 item 5).
- **vLLM**: OpenAI-compatible (`/v1/chat/completions`, `/v1/models`) plus guided decoding
  (`guided_json`). **A candidate third arm, not merely dialect precedent** — see §3.5a
  (P6) for the control-arm rationale. `usage` carries token counts; like all
  OpenAI-shaped responses it has no native tokens/sec field. No pull/delete equivalent, so
  `model_management: False`. **Platform maturity on GB10 Grace Blackwell / ARM64 is
  unverified here** — its optimization lineage is datacenter x86 + CUDA (§3.5a).
- **llama.cpp**: OpenAI-compatible plus GBNF grammars. Dialect precedent only; Ollama
  already wraps it, so it is not an independent arm.


## Appendix C — A/B runbook (operational; §6.1a is the design)

§6.1a says *what* is measured and why. This is *how to run it*. Normative only in that the
cutover decision (§4.2) reads an artifact produced by this procedure.

**Two claims, two instruments. Run the cheap one first — it is a kill gate.**

| Claim | Instrument | Cost |
|---|---|---|
| **A — the engine is faster** | paired generation benchmark, no cycles | hours |
| **B — quality holds** | interleaved cycle pairs | days |

A negative Phase A ends the migration for the price of an afternoon. Never run B first.

### C.1 Preconditions — all four, or the numbers lie

1. Engines installed on the Spark with **the same weights at the same quantization** —
   verified, not assumed. Model naming differs per provider (§2.3), so identical-looking
   names prove nothing.
2. **#793 fixed and deployed** — otherwise throughput never reaches telemetry (§10.3a).
3. **P4 capturing** `prefill_ms` / `load_ms` / `total_ms` (§3.6.1).
4. **Frozen prompt corpus** — 6–8 real prompts from stored runs, stratified short/medium/
   long, spanning the handler mix (framing, dev, qa, governance). Frozen means
   content-hashed and reused verbatim across every arm.

### C.2 Phase A — throughput benchmark

**Budget trap, addressed first.** Real generations run ~7.6 min (§3.6's worked example). A
naive corpus × reps × arms is 28+ hours. Separate the two things being measured:

- **Prompt size stays realistic** — that is the prefill workload, and where a tuned engine
  may win.
- **Cap completion at ~500–1000 tokens** for the rate measurement. Decode rate is being
  sampled; the full 5,000 tokens are not needed to measure it.
- **Add 2–3 uncapped full-length runs per arm** to confirm the rate holds as the KV cache
  grows.

~28 hours becomes ~4.

**Isolation — the distinction that makes or breaks this.** §6.1a says the benchmark runs
"both adapters in one process." That is about **client objects**, not servers, and the two
must not be confused:

| Layer | State during a measured arm | Why |
|---|---|---|
| **Adapter** (client object, `httpx`) | **all arms' adapters instantiated in the one benchmark process** | they are ordinary objects holding a connection pool. Zero GPU, zero contention. This is what makes the benchmark a test run rather than a deploy |
| **Engine** (the server process holding weights) | **exactly one running and holding weights** | GPU memory and thermal headroom are the shared resource. Two resident engines contend, and the contention lands inside the interval being measured |

So: one benchmark process, N adapters, **one live engine at a time** — every other engine
stopped (not merely idle; a stopped engine cannot hold weights). Idle-but-running is *not*
sufficient: an engine that has previously served still holds its model resident.

**Per arm** (`ollama`, `atlas`, and `vllm` only if P6 is run):

```
1. stop every other engine process      # not "idle" — stopped. Weights must be released
2. verify: only this engine holds GPU memory
3. start it; load the model; run 3 discard generations     # warm-up
4. assert load_ms ~ 0 on the next call  # the cold/warm guard — the warm-up landed
5. corpus x 3 reps, fixed order, temperature 0
6. record one §3.6.1 artifact row per generation — including the discarded warm-ups,
   flagged `warmup: true`, so the discard is auditable rather than assumed
```

Step 6 matters more than it looks: **warm-ups are recorded and flagged, never silently
dropped.** A reviewer must be able to see that the discard happened and that `load_ms`
fell where claimed. Deleting them makes the guard unverifiable.

**Then reverse the arm order and run the whole thing again.** Whichever engine goes second
inherits a warmer, more thermally loaded box. Running both orderings makes that effect
visible instead of silently crediting one side.

**Reading the result:**

- **Pair by prompt.** Same prompt, both arms, paired difference on `wall_clock_ms`.
- **Medians and spread, never means** — thermal and GC outliers skew a mean.
- **Check `completion_tokens` before interpreting anything.** Materially fewer tokens is a
  thinking-posture difference (§10.3), not raw speed; normalize per token before claiming
  a win.
- **Reconcile** `prefill_ms + decode + load_ms ≈ total_ms ≈ wall_clock_ms`. If they do not
  reconcile, the instrument is wrong and the result is void.

### C.3 Phase B — cycle parity

Only if Phase A shows a real win. Same PRD, same request profile, same squad profile.

**Interleave A, B, A, B** — never all of one then all of the other; box-state drift would
alias onto the provider variable. Restart the agent containers between each (§6.1a).
Minimum 3 pairs; at 1–2.5 h per cycle this is the real budget line.

Compare: verdict (accepted/rejected) · checks executed vs passed · **correction attempts
consumed** · extraction health (clean / recovered / failed) · wall-clock per cycle.

> **`correction attempts consumed` is the sleeper metric.** An engine emitting slightly
> worse-formed output burns correction budget, and a burned correction costs far more
> wall-clock than decode speed saves. **A Phase A throughput win can be entirely erased
> here, and it is invisible until Phase B.**

Where feasible, use SIP-0101 replay from a common boundary to constrain inputs — noting
(§6.1a) that the shipped slice is cycle-prefix restore, so it constrains inputs without
equalizing them.

### C.4 Reading the result

**Amended by Ruling 2 (§1.1): the threshold tables that stood here are removed.** The
benchmark *reports*; it does not adjudicate. No margin is defined in advance, because the
decision is owner judgment on observed results — *"the story should tell itself once I run
a cycle against the new adapter."*

**What to put in front of that judgment**, in the order it should be read:

| # | Number | Why it is read in this position |
|---|---|---|
| 1 | **`completion_tokens`, both arms** | read *first*, before any speed claim. If the arms produced materially different token counts, every downstream comparison needs normalizing per token — a thinking-posture difference otherwise reads as speed (§10.3) |
| 2 | **median paired `wall_clock_ms`** | the headline. Same prompt, both arms, paired |
| 3 | **`decode_tokens_per_second`** | the diagnostic: is a wall-clock difference decode speed, or something else? |
| 4 | **`prefill_ms` / `load_ms` / `total_ms`** | *where* the difference lives — decode, prompt processing, or model residency. Answers "why" when 2 and 3 disagree |
| 5 | **Phase B: corrections consumed, extraction health, verdict** | the half a generation benchmark cannot see |

**The one asymmetry worth stating plainly, since no threshold now enforces it:** a
throughput win and a quality regression are not comparable quantities. Extra wall-clock
costs minutes; a degraded verdict costs the comparison base for every measurement banked on
the Ollama substrate (FAY 6/6, the 98.5 lineage — §8). Speed is recoverable, an
invalidated baseline is not. Worth weighing asymmetrically even in a judgment call.

**If P6 ran**, apply §3.5a's three-outcome reading before attributing a win to Atlas's
tuning rather than to Ollama's baseline.

### C.5 The traps, ranked by how easily they fake a result

| # | Trap | Guard |
|---|---|---|
| 1 | **Cold vs warm** — a warm Ollama against a cold Atlas manufactures a win | `load_ms ≈ 0` asserted on every measured call |
| 2 | **Ordering effects** — the second arm inherits a hotter box | run both orderings |
| 3 | **Token-count shift** — fewer tokens reads as speed | check `completion_tokens` before interpreting |
| 4 | **Correction burn** — inverts the whole result | only visible in Phase B; never skip B |
| 5 | **Quantization mismatch** — invalidates everything silently | C.1 precondition 1, verified |

Trap 1 is first because it produces a clean-looking number that survives review: nothing
in the artifact reveals which engine had weights resident unless `load_ms` is recorded.
That is why it is a **required** field in §3.6.1 rather than a diagnostic — it converts an
avoidable mistake into a detectable one.
