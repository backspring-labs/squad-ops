# Stack Blueprint schema — draft against two stacks (Stage 2b)

**What this is.** The 1.6 plan's step 2b: *"draft the blueprint schema against **both** stacks | gate: every field traced to a real declaration in each."* Input to 2c (falsification), 2e (disclosures) and 2g (promoting the Stack Blueprint SIP).

**A spec, not code.** The schema is written here rather than as a `StackBlueprint` dataclass on purpose. An unwired dataclass is a declaration nothing reads — the class this release has already deleted once (`CheckSpec.supported_stacks`, 11 declarations and 0 readers, removed at #818 rather than wired, because wiring it would have minted the blueprint vocabulary by accident). Promotion is 2g's job. A schema that becomes load-bearing before it is falsified is exactly the SIP's own warning coming true.

2c can still falsify a spec mechanically: delete a field here, then check whether either stack's real declaration becomes inexpressible. That is a stronger test than corrupting a dataclass nothing consumes.

**Method.** Every value below was extracted by reflecting over the six live per-stack declarations, not read from source. The field inventory it rests on is in [§4](#4-the-inventory-this-rests-on).

---

## 1. The schema

Three tiers. The split is the substance of the draft: a flat field list is what produces *"the FastAPI contract with generic field names"*, and it also produces its mirror image — constants promoted into schema, asserting variability two stacks do not support.

### Tier 1 — declared data (blueprint-owned, falsifiable at 2c)

| field | `fullstack_fastapi_react` | `nextjs_ts` | disposition |
|---|---|---|---|
| `id` | `fullstack_fastapi_react` | `nextjs_ts` | demonstrated |
| `qa_test_namespace` | `backend/tests/`, `frontend/src/tests/` | `__tests__/`, `app/`, `lib/` | demonstrated |
| `source_extensions` | `.py .js .jsx` | `.ts .tsx` | demonstrated |
| `authored_extensions` | `.py .js .jsx .html .css` | `.ts .tsx .json .css` | demonstrated — wider than `source_extensions`; the two are distinct today (`DevelopmentCapability.source_filter` vs `expected_extensions`) and the schema keeps them distinct rather than guessing they are one |
| `test_file_patterns` | `test_*.py`, `*_test.py`, `*.test.js`, … | `*.test.ts`, `*.test.tsx`, `*.spec.ts`, `*.spec.tsx` | demonstrated |
| `test_framework` | `both` | `vitest` | demonstrated |
| `required_tools` | python 3.12, node 20, npm 10 | node 20, npm 10 | demonstrated |
| `operation_commands` | venv + pip + pytest + uvicorn | npm ci + next build + vitest + next start | demonstrated |
| `boot_argv` | `python -m uvicorn backend.main:app …` | `npx next start --port {port}` | demonstrated |
| `packaging.optional_files` | `docker-compose.yaml`, `start.sh`, `.env.example`, `nginx.conf` | `.dockerignore`, `.env.example`, `start.sh` | demonstrated |
| `packaging.validation_rules` | multi-stage build, compose wiring | `next build` then `next start` | demonstrated |
| `criteria_families` | routes + views + build + suite | slots + build + suite | **declared, deliberately un-falsified** — see §3 |

### Tier 2 — pack-supplied callables (required, named, typed)

| field | signature | why not data |
|---|---|---|
| `expand` | `manifest -> [{name, content}]` | Next.js derives file *location* from route path (`POST /runs/{run_id}/join` → `app/api/runs/[run_id]/join/route.ts`). That is a computation over the manifest, not a table. Expressing it as data makes a template language — code with worse tooling and no type checking. |
| `fill_slots` | `manifest -> (path, …)` | same; the slot set is derived, not enumerated. |
| `slot_criteria` | `(manifest, path) -> {interface, implementation}` | the partition of slot *kinds* is a claim about the stack, and #818 already moved it out of the emitter for exactly this reason. |
| `build_criteria` / `suite_criteria` | `() -> [criterion]` | pack-parameterized per the SIP; a server-rendered stack emits no `frontend_build`. |

### Tier 3 — core-owned (hoisted out of the per-stack registries)

Fifteen fields are identical across both stacks. Promoting them into the blueprint would assert per-stack variability the evidence does not support. They become core defaults, overridable only if a future stack demonstrates the need — which is S5's admission rule applied in the subtractive direction.

`ready_path` · `host` · `startup_timeout_s` · `request_timeout_s` · `poll_interval_s` · `prepare_timeout_s` · `image` · `app_port` · `install_network` · `max_completion_tokens` · `test_timeout_seconds` · `packaging.required_files` · `artifact_output_mode` · `qa_handoff_expectations` · `default_task_tags`

Two carry a caveat rather than a clean hoist:

- **`image`** is identical by a deliberate #822 ruling (the sandbox already carries Node 20/npm 10, so no new runtime enters the pipeline). Unfalsified, **not** decorative — a third stack in a different language moves it immediately. Hoist with the reason recorded, do not delete.
- **`ready_path = "/health"`** is identical because *both scaffolds emit a `/health` route*. The probe profile restates a scaffold fact. That is one fact in two declarations — the drift shape this release has paid for three times — and the honest fix is for the probe to read the scaffold's convention rather than re-declare it.

### Optional capabilities (declared, not defaulted)

Populated by one stack. Per S5 these are *"a declared optional capability with its reason"*, never a general field implying every stack has one.

| field | populated | reason, and what an unset value means |
|---|---|---|
| `harness_entry_modules` | S1 | Node module resolution has no test/app import boundary, so there is nothing to forbid. Unset = no boundary check. **Safe default.** |
| `check_stack` | S1 | typed-check evaluators are Python AST implementations never verified against S2. Unset = checks **skip**, which surfaces as unverified under SIP-0096. **Safe default.** |
| `prepare_argv` | **S2** | `next build` must run before `next start`. Unset = no prepare step. **Safe default.** The only field in the inventory introduced by the *second* stack rather than inherited from the first. |

---

## 2. The rule that governs every field

Generalized from #818, which is the only place the repo has yet stated it explicitly:

> **Every blueprint declaration is either required-or-refuse, or optional-with-a-visible-consequence. Never silently defaulted.**

#818's asymmetry is the model: an unset `check_stack` means checks *skip*, and a skip is safe because `CheckOutcome.skipped` is not executed-and-passed under SIP-0096 — it surfaces as unverified. An unset `criteria_pack` means the emitter **refuses**, because the failure it prevents is not a missing check but a *wrong* contract.

Every defect this release found was a silent default: a basename slug (#849), a `.py` suffix (frozen index), a singular routes path (#818), a missing build profile swallowed by `except Exception` (#838). None of them failed; all of them produced a plausible wrong answer.

Applied to the schema: Tier 1 and Tier 2 are **required-or-refuse**. Optional capabilities must state what an unset value *does*, and that consequence must be visible — which is the column above, not a comment.

---

## 3. The two things this schema does not settle

**Prompt prose has no home here, and it is the largest varying surface.** Eight of the 29 demonstrated-varying fields are LLM instruction text (`system_prompt_supplement`, `file_structure_guidance`, `example_structure`, `test_prompt_supplement`, `system_prompt_template`, …). The blueprint above declares *structure* and is silent about them.

The draft's position: **the blueprint declares which asset carries the prose, not the prose itself.** Putting instruction text in the schema collides with the ownership rule that prompt content lives in `prompts/fragments/` via PromptService (#448) — a rule this release already enforced twice. But the consequence must be stated rather than glossed: a blueprint that does not carry prompt content is not sufficient to define a stack, and a pack ships prose alongside it. **Recorded as a boundary, not a gap.**

**`criteria_families` is declared un-falsified, with the reason.** Stack #2 holds HTTP constant *and* has a frontend build, so both stacks agree on precisely the axis the criteria-family question turns on. The field cannot be falsified by this pair. Per the plan, the honest resolution is a declared field with the reason recorded — the `DECLARED_UNBUILT_CHECKS` pattern applied to a schema — rather than deleting it as decorative or implying it was tested.

---

## 4. The inventory this rests on

47 fields across the six live per-stack declarations, extracted mechanically.

| | count | meaning |
|---|---|---|
| **differ** across both stacks | 29 | per-stack-ness demonstrated |
| **identical** on both | 15 | unfalsified by this pair → Tier 3 |
| **populated by one stack** | 3 | optional capability |

The plan's 2c section records **two** single-stack fields (`harness_entry_modules`, `check_stack`) and calls 2c *"the step most likely to bite"* — having measured one of six declarations. The real subject is 18 fields.

Regenerate with the extractor in `tests/unit/capabilities/test_stack_inventory.py` (2a), which enumerates from the registries so a third stack enters the matrix automatically.

---

## 5. Open questions carried to 2g

1. **Does the blueprint own the packaging set?** `required_files` and `qa_handoff_expectations` are identical across both stacks — weak evidence they are universal rather than blueprint-owned. Tier 3 above takes that reading; a third stack could overturn it.
2. **One blueprint per stack, or backend + frontend composition?** Next.js **collapses the split entirely** — one project, one tree, one build. Evidence against composition as the primary shape, and it came from the stack chosen to stress the manifest's api/frontend split.
3. **`expand` as callable or data?** Tier 2 takes the callable side, on the directory-as-identity evidence above.
4. **Two stack vocabularies remain two** — `fullstack_fastapi_react` vs `fastapi`. S1 removed the duplicate declaration, not the drift. Owed at 2e.
5. **Where does a blueprint live?** `stack_nextjs_ts.py` is already a pack shipping its own expander; stack #1 is still inline in `scaffold.py`. The asymmetry resolves by pushing S1 out, not pulling S2 in.
