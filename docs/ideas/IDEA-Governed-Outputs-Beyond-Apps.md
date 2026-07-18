# IDEA: Governed Outputs Beyond Apps — Operational Flows as a Second Output Family

## Target Release
Vision item for the 1.6+/Campaign arc. Explicitly **not** a 1.4 item: nothing here may
touch the skeleton or contract machinery during the FAY measurement window — the yield
baseline is only meaningful while the golden path is stable.

### Status
Idea draft — distilled from a design conversation, no SIP yet. The cheapest next step is
the dogfood probe (§8), not a spec.

### Owner
Architecture / Vision

### Origin
Distilled 2026-07-18 from a genericization design conversation held mid-SIP-0098
(98.3 orchestration binding just merged, 98.4 probe runner in flight). The conversation
walked outward in steps — second stack → persistence axis → skeleton architecture → and
finally: *could the build output be something other than an app at all?* Specifically:
could an **n8n flow** be a governed output, so SquadOps serves Backspring both as the
engineering squad that produces apps **and** as producer/governor of long-running
operational flows that duty agents execute?

Companion docs: `IDEA-Scaffold-Interface-vs-Implementation.md` (the scaffolding thesis),
`IDEA-Building-Apps-on-Small-Models.md` (the falsifiable small-model thesis),
`SquadOps-Roadmap-Runtime-Loop-Capability-Backed-Agents.md` (the 2.0 capability-pack
arc), `sips/proposed/SIP-Contract-First-Build-Scaffolding.md` (R3, the engine itself).

---

## 1. The claim

> **The golden path is not an app builder. It is a governed-production engine:**
> LLM authors a typed interface → deterministic expander materializes the invariant
> structure → LLM fills narrow slots → deterministic verification holds the result to a
> contract derived from the same interface. Nothing in that loop is web-app-shaped.
> Therefore new output kinds — including operational flows — enter as **packs, not
> forks.**

The corollary that recurred at every rung of the conversation, and is probably the most
load-bearing sentence in this doc:

> **Verification vocabulary, not expansion, is the bottleneck for every new output
> family.** Writing a new expander is a day of template work. A stack (or flow kind) the
> check vocabulary and probe runner cannot hold accountable is not a real output in this
> system — the contract is the product.

## 2. The generalization ladder (nearest → farthest)

Recorded here because each rung was assessed in the same conversation and they gate each
other.

### 2.1 Second stack (99.4 — the forcing function)
The architecture is ~70% ready: `_EXPANDERS` is already a registry keyed by
`manifest.stack`; the executor seam, framing gate (`is_scaffoldable_stack`), fill-only
develop gate, and artifact rail are all stack-neutral. Known leaks to close **when the
second stack lands, not before** (defer-infra-completeness):

- `fill_slot_paths()` hardcodes `backend/routes.py` + view paths — slot maps move
  per-stack alongside their expander.
- `scaffold_contract.py` (`_ROUTES_PATH`, routes-vs-views criteria dispatch,
  `_behavioral`'s `frontend_build`/`tests_pass`, `CAP_PYTHON`/`CAP_NODE` ordering) —
  criteria *derivation* is stack logic and moves into the pack; the check *vocabulary*
  stays platform-owned.
- `lint()`'s "api.endpoints is empty" is a fullstack rule posing as universal.
- Framing/develop prompt fragments that name `routes.py`/views — prompt content is where
  stack assumptions hide with no compiler to catch them.

Target shape: a `StackPack` = expander + slot map + criteria derivation + prompt
fragments + toolchain capability declaration — the merger of today's `BuildProfile`
proto-pack with the scaffold surfaces. Guardrail when extracted: an architecture test
forbidding stack-name literals outside the pack directory (same pattern as #218).

### 2.2 Persistence axis (postgres vs dynamo — harder than stacks)
Persistence is a **dimension composed into** stacks, not a sibling stack — modeling
combinations as expanders explodes the registry. Three findings:

1. **Composition via a repository seam.** The scaffold emits a frozen repository
   *interface* derived from entities; the provider contributes the frozen adapter +
   bootstrap. Killer property: **fill slots are identical across providers** — same
   develop prompt, same criteria, provider choice invisible to the small model and to
   the yield measurement.
2. **It breaks boots-bare.** A postgres skeleton needs a database; dynamo needs
   creds/emulator. The contract's `capabilities` field grows a *services* category, and
   provisioning lands on the Ephemeral Application Sandbox (Lane S).
3. **Postgres is deterministically derivable from entities; DynamoDB is not.** Good
   dynamo means access-pattern-driven key/single-table design — a design act, not an
   expansion. Either the manifest carries explicit access-pattern declarations (pushing
   design burden back onto framing — exactly what the scaffold exists to remove) or the
   naive per-entity mapping is accepted as the contract. Postgres first; dynamo is its
   own design conversation.

Keep `in_memory` the golden-path default through the entire 1.4 window.

### 2.3 Output families (this doc's headline — §4)

## 3. Skeleton architecture rule (settled in the same conversation)

Question asked: should the emitted skeleton be DDD/hexagonal so components plug in?
Answer: **no — invest the architecture in the projector (expander/pack layer), not the
projection (the skeleton).** The skeleton is regenerable from the manifest; you don't
architect projections. The consumer of the fill slots is a 7–14B model, and every layer
of indirection is a tax on exactly the burden the scaffold exists to remove.

The skeleton already practices hex *discipline* without hex *ceremony* — seams exactly
where invariance matters (`api.js` client port, `errors.py` error contract, `main.py`
bootstrap) and flat idiom everywhere else. The decision rule for any future seam:

> **A seam earns a place in the skeleton only if it narrows the fill slot or makes a
> verification criterion more deterministic.** If it just adds files the dev model must
> understand, it is a tax, not architecture.

`repositories.py` passes this rule (arrives with the persistence axis). Domain-service
layers, DTO/mapper layers, aggregate decomposition fail it. DDD thinking belongs in the
**manifest schema** (entities/shapes/error codes as the ubiquitous-language contract),
not in emitted code.

## 4. n8n flows as governed outputs — the mapping

An n8n workflow is a JSON document: trigger, node graph, connections, credential
*references*, error wiring. It maps onto the golden-path vocabulary almost perfectly —
and in one respect better than apps do:

| Golden-path concept | Flow analog |
|---|---|
| Manifest | `flow_manifest` kind under the same envelope: trigger spec (webhook/cron/event), input/output schemas, declared external services, error policy, human-approval points |
| Expander | Deterministic emission of the workflow JSON: trigger node, topology, credential placeholder refs, error-workflow wiring, retry config, stub Code nodes at the slots |
| Skeleton | A flow that imports into n8n and executes end-to-end with pass-through stub bodies — the walking-skeleton property, verbatim |
| Fill slots | Code-node bodies and expression fields — a **smaller generative surface than an app**: one typed-input→typed-output transform per slot |
| Contract | Frozen topology pinned by hash; slot criteria; behavioral probes = inject test payload at trigger, assert output |

The structural advantage over apps: **the frozen surface is declarative data.** Which
node types, services, and credentials a flow uses is statically provable by reading the
JSON — something never cheaply provable about arbitrary app code. "This flow touches
only Gmail and Sheets, uses only these two credential refs, and has an approval node
before the send step" is a machine-checkable frozen property.

The interface-vs-implementation line holds cleanly: what the flow connects to, when it
fires, and what shapes pass through it = interface (machine-owned); the transform logic
= implementation (LLM-filled). If anything, the small-model thesis gets *easier* here.

## 5. The operate half — what is genuinely new

An app cycle ends at delivery. A flow is a **long-lived operational asset**, and the
new engineering is all on the far side of the verdict:

1. **Cycles produce, duty agents operate.** The engineering squad (cycle mode) builds
   and verifies the flow; duty agents (SIP-0089 duty mode) trigger, monitor, handle
   failures, and escalate. This closes the Backspring loop — the squad that builds tools
   and the squad that runs duty work become one system, with the verification contract
   as the handoff artifact. **SIP-0091 (Duty Durability) is the substrate this needs**,
   which strengthens the case for landing it.
2. **Gates ↔ approval nodes.** n8n wait/approval steps and SquadOps gates are the same
   concept at two layers. The manifest declares "human approval before side-effect X,"
   the expander wires the wait node (frozen), the duty agent surfaces it as a gate
   decision on the existing `squadops gate decide` rail.
3. **Drift detection comes free from the hash discipline.** The classic ops failure is
   hand-editing the deployed flow in the n8n UI until nobody knows what's running.
   Periodically fetch the deployed flow, canonical-hash it, compare against the
   contract: hand-edit = drift = detected — the §10 mechanism applied to a *living*
   artifact, with a duty agent positioned to enforce it continuously. "Amend the
   manifest and re-expand, never edit in the UI" is the `App.jsx` rule applied to
   operations.
4. **Operational-asset registry.** Cycle artifacts are ephemeral; deployed flows need a
   home — flow → contract → deployed version → owning duty agent. A new domain surface,
   cousin to the cycle registry.

## 6. Governance dimensions (why "governed" carries more weight here)

Flows act on real systems with real credentials, so the contract grows teeth apps never
needed — and all three are statically enforceable on the JSON:

- **Service allowlist** — an undeclared node type fails verification.
- **Credential scoping** — refs only, never inline (the existing hard rule,
  machine-checked).
- **Runtime policy as frozen structure** — timeout, retry, approval gates.

The contract stops being just "definition of done" and becomes a standing **license to
operate**.

## 7. Hard parts / risks

- **Behavioral verification needs an execution sandbox.** Probes mean an ephemeral n8n
  instance + mocked/sandboxed external services — the Lane-S sandbox extended one layer
  up. Same shape as the 98.4 probe runner, more moving parts.
- **The JS evaluator gap bites again.** Code-node bodies are JavaScript; the check
  vocabulary currently skips JS (`import_present` skips `.js`, no JS compile check).
  See the §1 corollary — this gap gates flow packs exactly as it gates a JS backend
  stack, so closing it pays twice.
- **Adopt n8n's runtime, not just its format.** Unlike the Claude-Skills posture
  (format-only), here the runtime *is* the value — hundreds of integrations SquadOps
  must never rebuild. SquadOps is producer and governor, not executor. Keeps
  model-independence intact.
- **UI hand-edit culture.** The regenerate-don't-edit discipline is a real operational
  constraint on humans; drift detection makes violations visible but a decided policy
  (block? reconcile? alarm?) is still needed.

## 8. Sequencing and the first probe

- **Timing:** 1.6+/Campaign arc. Wants Campaign's long-running-objective framing and
  SIP-0091 durability; must not perturb the 1.4 FAY window. Enters through the same
  pack seam as the second stack (§2.1) — which is the validation of the whole
  genericization line: because the engine is factored around
  manifest→expand→fill→verify, a flow is a pack, not a fork.
- **First probe (cheap, decisive):** pick **one real Backspring operational flow** that
  is actually needed, hand-write its `flow_manifest` YAML against the v1 envelope, and
  see how much of the schema survives contact. No expander, no runner — just the
  manifest. Costs about a day and teaches more about the flow-manifest schema than any
  design doc. If the manifest can't be written declaratively, the idea dies cheap; if it
  can, it becomes the fixture the eventual expander is built against — exactly how the
  Phase-0.5 spike de-risked the scaffold bet.
