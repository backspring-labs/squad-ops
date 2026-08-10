# Stack Blueprint schema — draft against two stacks (Stage 2b)

**What this is.** The 1.6 plan's step 2b: *"draft the blueprint schema against **both** stacks | gate: every field traced to a real declaration in each."* It is the input to 2c (falsification), 2e (disclosures) and 2g (promoting the Stack Blueprint SIP).

**Method: mechanical, not read-and-classify.** Every field below was extracted by reflecting over the six per-stack declarations and comparing values across `fullstack_fastapi_react` and `nextjs_ts`. Nothing here is a reading of the source. That discipline is deliberate — 1a was the read-and-classify version of a sweep and overclaimed three times, and the classifications below are exactly the kind that look obvious and are not.

Regenerate with the extractor in `tests/unit/capabilities/test_stack_inventory.py` (2a), which enumerates from the registries so a third stack enters automatically.

---

## The headline: the falsification surface is nine times larger than the plan estimated

The plan's 2c section records:

> Measured 2026-08-10, **two** `ScaffoldStack` fields are populated by exactly one stack: `harness_entry_modules`, `check_stack`.

That measured one of six declarations. Across all six:

| | count | meaning |
|---|---|---|
| fields total | **47** | across six declarations |
| **differ** across the two stacks | **29** | per-stack-ness demonstrated |
| **identical** on both | **15** | per-stack-ness *unfalsified by this pair* |
| **populated by one stack only** | **3** | optional capability, or a stack-1 assumption wearing a general name |

So 2c's subject is **18 fields**, not two. The plan called 2c *"the step most likely to bite"* while looking at 11% of it.

---

## Class 1 — differ across both stacks (29)

Per-stack-ness demonstrated. These are the blueprint's uncontested core.

`ScaffoldStack`: `name` · `expand` · `fill_slots` · `qa_test_namespace` · `criteria_pack` · `probe_profile` · `dev_capability`
`CriteriaPack`: `name` · `slot_criteria` · `build_criteria` · `suite_criteria`
`ExecutionProfile`: `boot_argv`
`EnvironmentContract`: `stack` · `required_tools` · `operation_commands`
`DevelopmentCapability`: `name` · `system_prompt_supplement` · `file_structure_guidance` · `example_structure` · `expected_extensions` · `test_framework` · `test_prompt_supplement` · `source_filter` · `test_file_patterns` · `build_support_files`
`BuildProfile`: `name` · `system_prompt_template` · `optional_files` · `validation_rules`

**Note what dominates**: 10 of 29 are `DevelopmentCapability`, and 8 of those 10 are *prompt prose*. The largest genuinely-per-stack surface is not structural — it is what the dev and QA agents are told. A blueprint that models only paths and commands would leave the biggest real difference outside the schema.

## Class 2 — identical on both (15)

These are declared per-stack and have never been observed varying. Under 2c's own rule — *"a field whose removal breaks nothing is decorative and is deleted before the schema freezes"* — each needs a disposition.

| declaration | fields | reading |
|---|---|---|
| `ExecutionProfile` | `ready_path`, `host`, `startup_timeout_s`, `request_timeout_s`, `poll_interval_s`, `prepare_timeout_s` | **6 of its 8 fields.** Only `boot_argv`/`prepare_argv` vary. This is a defaults object with two stack-specific fields, not a per-stack object. |
| `EnvironmentContract` | `image`, `app_port`, `install_network` | `image` is identical **by deliberate decision** (#822: the sandbox already carries Node 20/npm 10, so no new runtime enters the pipeline) — unfalsified, not decorative. |
| `DevelopmentCapability` | `max_completion_tokens`, `test_timeout_seconds` | tuning constants that happen to live per-stack. |
| `BuildProfile` | `required_files`, `artifact_output_mode`, `qa_handoff_expectations`, `default_task_tags` | `required_files` and `qa_handoff_expectations` are the packaging *contract*, plausibly universal rather than per-stack. |

**`ready_path = "/health"` deserves separate mention.** Both stacks declare it because both scaffolds emit a `/health` route — it is a scaffold convention that the probe profile restates. Two declarations of one fact, in the drift-prone shape this release has already paid for three times.

## Class 3 — populated by one stack only (3)

| field | populated by | disposition |
|---|---|---|
| `ScaffoldStack.harness_entry_modules` | S1 | Node module resolution has no test/app import boundary, so there is nothing to forbid. **Declared empty as a fact**, already argued in the registry. |
| `ScaffoldStack.check_stack` | S1 | The typed-check evaluators are Python AST implementations never verified against S2. Empty means *skip*, which is safe under SIP-0096 (a skip surfaces as unverified). |
| `ExecutionProfile.prepare_argv` | **S2** | The one field where **stack #2 is the populated side**: `next build` must run before `next start`. S1 needs no prepare step. |

`prepare_argv` is the most useful entry here: it is the only evidence in the whole inventory that a field can be introduced by the *second* stack rather than inherited from the first. Every other single-stack field is stack #1's.

---

## Schema implications

**1. The blueprint should not carry all 47.** Fifteen are constants with a stack-shaped home. Promoting them into a blueprint schema would assert per-stack variability that two stacks' worth of evidence does not support — the *"FastAPI contract with generic field names"* the SIP declines acceptance over, arrived at from the opposite direction.

**2. Three tiers, not one flat field list.**

- **Declared data** — schema-governed, falsifiable per 2c. Paths, suffixes, conventions, tool names, test patterns, criteria families.
- **Pack-supplied callables** — `expand`, `fill_slots`, `slot_criteria`. Named, typed, required. Generation stays code: expressing it as data makes a template language, which is code with worse tooling.
- **Core-owned** — everything else, with an architecture test that nothing in core branches on stack identity.

**3. Every declaration is required-or-refuse, or optional-with-a-visible-consequence. Never silently defaulted.** #818 set the precedent (unset `check_stack` = skip, which is safe; unset `criteria_pack` = refuse, because silently-wrong has no safe default). Every defect this release found was a silent default — a basename slug, a `.py` suffix, a singular routes path.

**4. Prompt prose is the largest per-stack surface and needs a home.** Eight of the 29 demonstrated-varying fields are LLM instructions. The blueprint either owns them, or declares which asset carries them, or the schema is silent about the majority of what actually differs between two stacks.

---

## What 2c must falsify

For each of the 15 identical fields, one of:

- **remove it** and confirm something breaks on at least one stack → genuinely per-stack, keep;
- **hoist it** to a core default → not per-stack, and the blueprint is smaller;
- **declare it un-falsified with the reason recorded** → the `DECLARED_UNBUILT_CHECKS` pattern applied to a schema, which the plan already prescribes for the criteria-family field.

The third is legitimate but must be *rare and reasoned*. Applied to all 15 it would mean the schema was written from the code rather than from evidence.

## Carried open questions

Recorded rather than answered here; 2g's promotion needs them settled.

1. **Does the blueprint own the packaging set?** `BuildProfile.required_files` and `qa_handoff_expectations` are identical across both stacks, which is weak evidence they are universal rather than blueprint-owned.
2. **One blueprint per stack, or backend + frontend composition?** Next.js **collapses the split entirely** — one project, one tree, one build. That is real evidence against composition as the primary shape, and it arrived from the stack that was chosen to stress the manifest's api/frontend split.
3. **`expand` as callable or data?** Evidence favors callable: Next.js's file placement is a *computation* over the manifest (directory-as-identity routing), not a table.
4. **Two stack vocabularies remain two** — `fullstack_fastapi_react` vs `fastapi`. S1 removed the duplicate declaration, not the drift. Still owed at 2e.
5. **Criteria-family variation stays untested by construction** — both stacks hold HTTP constant and both have a frontend build, so they cannot disagree on the axis the question turns on. Already recorded in the plan as a disclosure obligation.
