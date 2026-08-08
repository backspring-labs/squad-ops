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

**The wire dialect is deliberately not fixed by this SIP** (§10.2). The port surface,
capability declaration, and conformance suite are the normative content; the dialect is an
implementation detail resolved when Atlas's API is pinned, and *verified* by the
conformance suite rather than assumed. This follows SIP-LLM-Emission-Contracts §3.2's
existing rule that an adapter's tier is "discovered by the conformance suite, never
assumed — including the Atlas adapter's at migration time."

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
| Error translation | unknown model → `LLMModelNotFoundError`; unreachable host → `LLMConnectionError`; sub-second timeout → `LLMTimeoutError` |
| Capability honesty | every declared-`True` flag is exercised and observed to work; every declared-`False` flag's method raises rather than degrading silently (#572's rule) |

**Capability honesty is the load-bearing row.** It is what makes §3.2's declarations
trustworthy instead of aspirational, and it is the row that would have caught #572 in the
queue port.

**Tiering, so the suite is runnable in three places:**

- **Unit tier** — mocked transport, runs in the regression suite, no network. Every
  dimension above.
- **Live tier** — `@pytest.mark.integration`, against a real endpoint from an env var,
  skipped when absent. Same assertions, real wire.
- **A/B tier** — same prompts through both adapters, comparing usage accounting and
  extraction health. This is the migration instrument, not a pass/fail gate; it produces
  the before/after baseline that SIP-LLM-Emission-Contracts §3.4 asks for.

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
the conformance suite green on a live Atlas endpoint, the A/B baseline recorded, and a
shakedown cycle on the deployed stack — and it lands no earlier than a release where the
Spark lane is not mid-validation. This SIP delivers the *ability* to switch and the
*evidence* to decide; it does not switch.

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

| Phase | Content | Size | Depends on |
|---|---|---|---|
| **P0** | `capabilities()` on `LLMPort` + Ollama declarations + sites 2/3 stop using `isinstance` | S | — |
| **P1** | `list_available_models()` on-port + `ModelInfo` + Ollama impl + doctor provider-aware + #423-style skip cause (**closes #313**) | M | P0 |
| **P2** | `LLMConfig.provider` + factory wiring at both composition roots + unknown-provider raises (**closes #301's LLM half**) | S | P0 |
| **P3** | Conformance suite, unit + live tiers, run green against Ollama as the only adapter | M | P0–P2 |
| **P4** | Atlas adapter + conformance run + capability declarations | M | P3, §10.2 resolved |
| **P5** | A/B tier + malformation/usage baseline recorded | S | P4, live endpoint |
| — | **Cutover** | — | **not this SIP** (§4.2) |

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

If Atlas is OpenAI-compatible (§10.2's leading candidate), the Atlas adapter can be
pointed at `http://localhost:11434/v1` and run the **full live-tier conformance suite on
the Mac** against real models — real generation, real streaming, real usage accounting,
real error translation — with no Atlas instance, no Spark contact, and no default changed.
The A/B tier becomes genuinely meaningful too: the same weights through two adapters
isolates *adapter* differences from *model* differences, which a cross-machine comparison
never could.

This is a rough test and the SIP says so plainly: it proves the adapter speaks the
dialect correctly, not that Atlas behaves like Ollama. Real Atlas conformance is P5 and
needs a real endpoint.

If Atlas is *not* OpenAI-compatible, the fallback is a recorded-transcript fixture harness
at the unit tier plus a deferred live tier — weaker, and a reason to prefer resolving
§10.2 early.

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

**10.1 — #301's scope.** #301 covers the composition root bypassing *both* the LLM and
queue factories. This SIP proposes closing the LLM half at P2 and leaving the queue half
in the 1.7 composition-root cluster, which the 1.5 plan flagged as needing a **design gate
before code** because it alters runtime initialization. Splitting an issue across releases
needs an explicit ruling: close #301 here with a scoped title change, or reference it
without `Closes` and file the queue half separately. *Recommendation: the latter — a
partial fix references without closing, per the standing rule.*

**10.2 — What Atlas is.** Not recorded anywhere in the repo; every reference defers the
question. SIP-LLM-Emission-Contracts Appendix A calls OpenAI-compatible
(`response_format: {type: "json_schema"}`) "the *expected* Atlas path, to be verified by
the conformance suite at adoption, never assumed." **This blocks P4 only** — P0–P3 proceed
regardless — and it is what decides whether §6.1's Mac rough-test path works as described.
Needed at P4: base URL shape, auth (bearer? none?), model-listing endpoint, and whether
model management (pull/delete) exists at all, since that sets `model_management`.

**10.3 — #410 (thinking tokens), in or out.** Currently out. The case for pulling it in:
it is provider-shaped, the port has no way to express "return reasoning separately," and
it will recur verbatim at Atlas — §3.2 already reserves a `thinking_tokens` flag for it.
The case for leaving it out: its *ruling* was that thinking stays ON and only the
observability half ships, which is a LangFuse-emission change with its own redaction
questions, and it never gates a cut. *Recommendation: declare the `thinking_tokens`
capability flag here (cheap, and the port surface is being touched anyway), implement the
observability half in its own PR against #410.*

**10.4 — Release placement.** §4.3's argument for 1.7-dark needs an owner ruling against
the feature-free rule, since it is the kind of reading that should be decided explicitly
rather than assumed by an implementer.

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
- **OpenAI-compatible** (§10.2's leading candidate): `/v1/chat/completions` with SSE
  streaming, `/v1/models`, `usage.{prompt,completion,total}_tokens` (no native rate — t/s
  is computed client-side or declared unsupported), `response_format:
  {type: "json_schema"}`. No pull/delete equivalent, so `model_management: False`.
- **vLLM / llama.cpp**: OpenAI-compatible plus guided decoding (`guided_json`, GBNF).
