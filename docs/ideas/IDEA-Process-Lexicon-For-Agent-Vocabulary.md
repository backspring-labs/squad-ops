# IDEA: A Process Lexicon — One Seeded Vocabulary, Every Domain

## Target Release
Vision item — candidate SIP after the N=5 green baseline (SIP-0098 §98.5) closes.

### Status
Idea / design-thinking draft

### Owner
Build / Architecture

### Origin
Noticed during pf-39 (`cyc_948094e17641`): the same task carries four different names across four surfaces — `task_index: 1` in `implementation_plan.yaml`, `T1` in the lead's prose `planning_artifact.md`, `m001` in the dispatch id, `task_1` in the evaluation artifact. They align numerically, so nothing broke. But this is the benign form of a class that has already been expensive: the `{run_id}` vs `{id}` prose-vs-contract divergence cost pf-31 an entire roll, and pf-33's `harness_boundary` expectation line didn't merely permit a violation — it *instructed* one, and two separate repair agents obeyed it into rejection.

---

## The idea

Agents invent their own labels for shared concepts. Give them a **lexicon they are seeded with** instead — one artifact, authored once, injected into every role on every cycle.

The obvious objection is scale: nobody wants to write a vocabulary for `group_run`, then `app_a`, then `app_p`, ad nauseum — including for apps that do not exist yet. That objection dissolves once you notice **which terms have actually hurt.**

## The terms that hurt are not domain terms

Go through the catalogue: *build* (assembly vs implementation decomposition), *framing* vs *planning*, *manifest*, *fill slot* vs *frozen*, `T0` vs `task_index` vs `m000`, *criterion* / *check* / *evidence*, *workload* / *run* / *cycle* / *gate*. Every one is **SquadOps process vocabulary** — how agents talk about the work. Not one is about running clubs. `RunEvent` and `pace_target` have never been the problem.

There are three lexicons, and only one is missing:

| Lexicon | Scope | Where it lives today |
|---|---|---|
| **Process** — build, framing, fill slot, `task_index`, criterion | framework-wide, domain-blind | **nowhere — this is the gap** |
| **Stack** — `backend/routes.py`, harness boundary, entry modules | per *stack*, not per app | scaffold expander / Stack Blueprint |
| **Domain** — RunEvent, participant, pace | per app | **the PRD** — already a seeded input |

The domain lexicon already exists and is already authored per cycle: it is the PRD. The stack lexicon is keyed to `fullstack_fastapi_react`, so every app on that stack shares it unchanged. **Neither scales per-app, and neither needs a new artifact.** A new app needs its PRD — which you were writing regardless.

## It must be an input, not an output

The tempting shape is to have the lead emit a glossary during framing. That reintroduces the problem one level up: an LLM-authored lexicon drifts per cycle, and now the drift wears authority. Whatever constrains generation cannot be downstream of it.

Which points at a seam that already exists and already has a rule: a **prompt fragment** under `src/squadops/prompts/fragments/`, injected via PromptService. Versioned with the framework, diffable, identical across all six roles, never re-dreamt per cycle. Not a new mechanism — the repo's ownership rule already says this is where prompt content belongs.

## What it can and cannot enforce

Honest accounting, because "enforcement beats instruction" is the standing lesson and a lexicon is instruction.

**Enforcement requires a referent that exists independently of the generator** — machine-readable, authored before generation, compared by identity rather than judgment. Every enforcement that has held here has one: SIP-0100 frozen paths compare against `expand(manifest)`; typed acceptance compares against the contract's typed params; the A3 lint compares prose paths against the contract.

Split the lexicon on that line:

- **Terms that name canonical identifiers** (`task_index`, criterion ids, paths) *are* partially enforceable — prose may reference an identifier, never restate it. Scanning prose for `T\d+` is mechanical, and the A3 lint is the working precedent.
- **Conceptual terms** (*build*, *framing*) are not lintable — both usages are lexically identical and only a reading distinguishes them. For these the durable fix is not policing usage but **collapsing the term**, so the ambiguity stops existing. Renaming one of the two `build`s beats any amount of guidance about which is meant.

So the lexicon reduces casual drift and documents the collapse decisions. It is not a substitute for structure where structure is possible.

## Constraint: keep it small

Every token lands in every prompt, of every role, of every cycle. There is a scar here: pf-33's QA prompt reached ~18k tokens, blew the 8192 cap, truncated mid-file, and crashed test collection. A lexicon that grows into a dictionary will cost more than the drift it prevents. Target the dozen terms that have measurably diverged, one line each — not a glossary of everything.

## Naming

Call it a **process lexicon**, not a "rosetta stone per project." The latter invites exactly the per-app proliferation this idea exists to avoid.
