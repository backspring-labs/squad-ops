---
sip_uid: '17883224960398652'
status: implemented
title: Cycle Request-Profile Naming Taxonomy
author: SquadOps Architecture (Spark lane)
created_at: '2026-07-01T00:00:00Z'
sip_number: 114
updated_at: '2026-10-23T18:44:13.174273Z'
---
# SIP-0114: Cycle Request-Profile Naming Taxonomy

> **Placement and delivery (2026-10-04: the owner's rulings on the SIP-portfolio audit, `sips/PORTFOLIO.md`).** **Placed: 2.1.0, via #316.** One constraint is ruled: **pinned campaign definitions keep resolving old profile names indefinitely.** The 2.0 set's pinned files name profiles, and the crew re-runs that set. The constraint goes into #316's acceptance, and the inventory here is refreshed in the implementing PR.
>
> **Moved to 2.3.0 (2026-10-05, the owner's ruling on the 2.1 day plan, 2.1 plan §5 ruling 14).** This SIP is still proposed, #316 is large, and nothing in 2.1 depends on it. It joins 2.3's structural batch, and the constraint above stands.
>
> **Moved to 2.4.0 (2026-10-15, the owner's ruling of 2026-10-15, in session: "ok to defer").** The SIP was still proposed when 2.3's last structural rounds ran, and its acceptance is the owner's design review, so 2.3 is cut without it. The 2.4 plan places its review and #316's build. The constraint above stands.


**Status:** Implemented
**Authors:** SquadOps Architecture (Spark lane)
**Created:** 2026-07-01
**Revision:** 4 (2026-10-19; revision 3 was 2026-10-18, revision 2 2026-10-13, revision 1 2026-07-01)
**Tracking:** #316 (holds the deferred #279 fold)

## Delivery ledger (current as of 2026-10-19)

One row per part that ships separately. Statuses as CLAUDE.md defines them. Accepted 2026-10-19, after the MacBook
lane's review (revision 4, PR #2494), by the owner's approval of that day.

| part | status | where |
|---|---|---|
| the operator's request profiles, the stack's request defaults and the campaign profiles apart from them, with every old name still resolving for pinned definitions (revision 4's decisions; Q13) | **shipped** | 2.4.0, PR #2500, issue #316 (§11a) |
| the console's cycle create resolved by the server, with the same builder (§11b) | **shipped** | 2.4.0, PR #2529, issue #2520 |

**What closes this SIP:** #316 shipped, with every pinned definition still resolving the profile it names.

## Revision 4 (2026-10-19): the MacBook lane's review, for acceptance

**Reviewed 2026-10-19, for acceptance under the owner's grant of that day.** The owner's words: "I grant you autonomy
to use good judgement to approve cycles, PRs, issue choices etc." The supervisor wrote this SIP, so the MacBook lane
reviewed revision 3 as the second reader. It approved all five decisions and asked for three additions, (a) to (c)
below. The fourth, (d), was found while checking (c). The decisions below are what acceptance commits to.

- **(a) Three names are in both sets: `build`, `wrapup` and `benchmark`.** Each is an operator name and an old name.
  - **Each keeps its released YAML byte for byte.** It is the old profile, not a new one beside it, and the
    implementing PR's byte-identity test covers all three.
  - **What can change is the stack's defaults (R2.3).** They sit beneath a profile's own keys, and the overrides sit
    above both. A profile that sets a key keeps it. A profile that doesn't, run with a stack set at create time, gains
    the stack's. So `build --set build_profile=fullstack_fastapi_react` asks for the stack's required checks, where it
    asked for none before.
  - **No pinned config names that combination.** On main at dfe993f8, the pinned verification sets and campaign
    definitions name `validated-fullstack` (185 occurrences), `validated-fullstack-solo` (1) and the campaign profiles
    (33). None names `build`, `wrapup` or `benchmark`.
  - **The implementing PR's tests, one added:** every pinned verification-set config and campaign definition resolves
    to the same applied defaults and the same config hash before and after the change.
- **(b) An external Project's cycle names no stack.**
  - **What SIP-0112 E.4.3 does:** a cycle that pins an external Project's source refuses `build_profile` and
    `contract_ref` at create (the preflight finding `source_backed_stack`, PR #2484). A stack would seed its skeleton
    and author a manifest beside the product's own files.
  - **So R2.3's stack defaults never apply to it.** Its verification is its Development Configuration's own checks
    (SIP-0112 FR-20), and it gets its request profile's defaults only.
  - **The boundary with SIP-0112:** this SIP names the request profiles and the defaults a stack carries. SIP-0112
    owns what an external or a greenfield Project's cycle may name. A greenfield Project created from a blueprint
    takes its stack from its Development Configuration (`technical.stack`), and a create-time stack that disagrees is
    refused. SIP-0112 E.4.6 builds that.
- **(c) A campaign's stack is optional (#2443), and it already is.** `CampaignPolicy.stack` is `None` unless declared,
  and then the campaign profiles' own stack stands (`src/squadops/campaigns/models.py:405`). A campaign on an external
  Project declares none.
- **(d) Declaring none isn't enough for a campaign on an external Project. Open, for SIP-0112.**
  - **Why:** every campaign profile pins `fullstack_fastapi_react` in its defaults, and the preflight reads the
    effective config. So a Campaign launched on an external Project is refused by its own profile's stack.
  - **What rules out the easy fixes:** an override can't remove a key (R2.4), and decision 4 with Q13 freezes the
    campaign profiles, so the key can't be deleted from them either.
  - **What's needed:** the campaign launcher needs a path without a stack for an external Project. Where that path
    lives is SIP-0112's (E.4.3, E.4.4), and it doesn't change this SIP's decisions.
  - **When:** it needs deciding before IR-2 and the shared demonstration's Campaign step (the 2.4 plan, §2.7).

**Decision 5, for acceptance:** a campaign carries its stack in its policy (#2443), not in its profiles' names. The stack
is optional, and a campaign on an external Project declares none.

## Revision 3 (2026-10-18): the inventory re-read, `framing` answered, and a campaign's stack

Read against `main` at f821a607, for the owner's design review (the 2.4 plan's D7: in 2.4, landing before the
window's deploy freezes). Revision 2 below still stands. This section changes three facts and adds one decision.

- **21 profiles, one new since revision 2:**
  - **`campaign-increment-asks`** (#2280, 2026-10-13) is a diagnostic: `campaign-increment` verbatim, with one fault
    declared, and a test asserts the parity. It is the campaign's, so it joins R2.4's campaign set, outside the
    operator's listing.
  - **Two keys left every profile:** #2355 and #2358 removed `max_consecutive_failures` and `max_task_seconds`, which
    nothing read. R2.1's columns don't include either.
  - **R2.3 still holds:** `validated-fullstack` differs from `validation` in the same six keys.
- **R2.1's open question, answered: `framing` builds.**
  - **What runs:** with a `workload_sequence`, the `build_tasks` flag isn't read. The implementation phase runs the
    implementation steps (define-done, develop, QA's tests), or the builder's assembly on a squad that has a builder
    (`src/squadops/cycles/task_plan.py:558-563`, and `builder_assembles` at `:488-506`).
  - **So `framing` is** `build` without output validation (`max_self_eval_passes: 0`), plus two planning pulse checks.
    Its name says planning only.
  - **Its mapping:** none. It is frozen under its old name with the rest (R2.4), outside the operator's listing, and
    maps to no new name. Only its own test names it (`tests/unit/contracts/test_planning_profile.py`); the campaign
    tests use the string as an arbitrary value.
  - **`pulse-check` is the same:** `default` plus pulse checks, and only its tests name it. Pulse checks are a
    structured list, so an operator who wants them sets them as an override.
- **A campaign can't set its stack (#2443), and Scheme A depends on that.**
  - **The gap:** R2.4 sets the stack at create time, never in a name. But a campaign has no create time of its own.
    Each launch builds its request from a profile name alone (`src/squadops/campaigns/launch_requests.py`), and every
    campaign profile pins `fullstack_fastapi_react`. So the only way a campaign could run on Next.js today is a
    profile per stack (`campaign-increment-nextjs`, …), the combinatorial trap §2 describes.
  - **The fix (#2443):** the campaign's policy carries the stack, and every launch passes it as an override. The
    campaign set then stays as it is on every stack.
  - **The window needs it too:** it runs two campaigns per stack (the 2.4 plan's D3), and a Next.js campaign has
    never run.

**R2.5's decisions, with one added:**

5. **A campaign carries its stack in its policy (#2443),** not in its profiles' names.

## Revision 2 (2026-10-13): the facts re-read against main, and what they change

Revision 1 framed the decision in July. The profile set has grown since, two of its questions are answered by code that
now exists, and one finding changes the recommendation. **The rest of this document is revision 1, unchanged except
§1's count.** This section is what a reviewer reads first.

### R2.1 The inventory: 20 profiles, read from their YAML

| profile | phases | depth | stack | plan authoring | correction | pulse | budget | required checks |
|---|---|---|---|---|---|---|---|---|
| `selftest` | plan (no sequence) | none | — | sole | analyze, decide, repair | — | — | — |
| `default` | plan (no sequence) | default | — | sole | analyze, decide, repair | — | — | — |
| `benchmark` | plan (no sequence) | default, plus a metrics artifact | — | sole | analyze, decide, repair | — | — | — |
| `pulse-check` | plan (no sequence) | default | — | sole | analyze, decide, repair | yes | — | — |
| `pulse-check-build` | plan + build (no sequence) | default | — | sole | analyze, decide, repair | yes | — | — |
| `builder-assemble` | plan + build (no sequence) | default | `python_cli_builder` | sole | analyze, decide, repair | — | — | — |
| `fullstack-fastapi-react` | plan + build (no sequence) | default | `fullstack_fastapi_react` | sole | analyze, decide, repair | — | — | — |
| `build-only` | build, from a prior cycle's plan | default | — | sole | analyze, decide, repair | — | — | — |
| `framing` | framing, implementation | default | — | sole | analyze, decide, repair | yes | — | — |
| `build` | framing, implementation | output validation | — | sole | analyze, decide, repair | — | — | — |
| `implementation` | implementation | output validation, 2 corrections | — | sole | analyze, decide, repair | yes | 2 h | — |
| `validation` | framing, implementation | output and typed validation, 3 corrections | — | sole | analyze, decide, repair | — | 2 h | — |
| `validation-multirole` | framing, implementation | as `validation` | — | **multi-role** | analyze, decide, repair | — | 2 h | — |
| `validated-fullstack` | framing, implementation | as `validation` | `fullstack_fastapi_react` | sole | analyze, decide, repair | — | **3 h** | **tests_pass, frontend_build, required_files** |
| `validated-fullstack-solo` | framing, implementation | as `validation` | `fullstack_fastapi_react` | sole | **repair only** | — | 3 h | as above |
| `multi-phase` | framing, implementation, wrapup | default | — | sole | analyze, decide, repair | — | — | — |
| `wrapup` | wrapup | default | — | sole | analyze, decide, repair | yes | — | — |
| `campaign-reference` | framing, implementation | as `validation` | `fullstack_fastapi_react` | multi-role | analyze, decide, repair | — | 3 h | as `validated-fullstack` |
| `campaign-proposal` | proposal | default | `fullstack_fastapi_react` | sole | analyze, decide, repair | — | — | — |
| `campaign-increment` | proposal, framing, implementation | as `validation` | `fullstack_fastapi_react` | multi-role | analyze, decide, repair | — | 3 h | as `validated-fullstack` |

**Use, by reference count** (configs and scripts outside the profiles themselves):
- `validated-fullstack` names 120 files, every verification set since 1.7.
- `validated-fullstack-solo` and `selftest` name a handful.
- The three `campaign-*` profiles are named by the campaign code, not by operators (`campaigns/reference.py` `REFERENCE_PROPOSAL_PROFILE`, and the launch requests).
- Most of the rest are named only by their own tests.

**Two axes revision 1 did not have:**
- **The correction path** (SIP-0108 §10i): `validated-fullstack-solo` is `validated-fullstack` with `correction_steps: [repair]`, its one difference, asserted by a test.
- **The proposal workload** (SIP-0109): the campaign profiles.

**One name that misleads, unverified beyond the YAML:** `framing` declares a framing *and* an implementation phase, with no build tasks. Its name says "planning only". The implementing PR reads what its implementation phase does before mapping it.

### R2.2 Questions §9 asked, answered by code that now exists

1. **Is the stack settable at create time, independent of the profile?** **Yes.**
   - `squadops cycles create --set build_profile=<stack> --set development_profile=<stack>` sets it. `--set` writes any key into `execution_overrides`, which merge over the profile's defaults (`merge_config`), `pulse_checks`, `plan_authoring_contributors` and `correction_steps` included.
   - **It is already how every Next.js verification set runs.** They name `validated-fullstack` and override its stack to `nextjs_ts` (for example `2-3-0-g3-regression-tensorfold-nextjs.yaml`). So the profile named for FastAPI and React carries the Next.js counted rolls, which is #316's problem in practice.
   - Scheme A's "main implementation cost" (§8) is already paid. Named flags (`--stack`, `--pulse`, `--multirole`) would be sugar over `--set`.
2. **CLI flags or overrides?** Overrides exist. Flags are optional, and if they are added, they write the same keys.
3. **The deprecation window:** ruled for campaign definitions on 2026-10-04 (old names resolve indefinitely, Q13). This revision recommends the same for every pinned verification-set config, since the records cite them; see R2.4.
4. **`build-only`:** it is already a profile that requires `plan_artifact_refs` in the overrides. It can stay an edge profile, or become `build` plus that override.
5. **Mac-lane sign-off:** moot. Both lanes' work runs on the Spark from one queue.

### R2.3 The finding that changes the recommendation: a stack carries defaults of its own

`validated-fullstack` differs from `validation` in six keys, not one:
- `build_profile` and `development_profile`: the stack;
- `required_checks: [tests_pass, frontend_build, required_files]`;
- `time_budget_seconds: 10800` (against 7200);
- `manifest_max_attempts: 4`;
- `notes`.

So "the stack is a parameter" (P1) is not enough. `validate --set build_profile=fullstack_fastapi_react` would silently drop three requirements, among them `frontend_build`, which only means something on a stack that has a frontend. **Where each one lives decides whether P1 holds:**
- **`required_checks`:** **the stack declares the checks it requires.** A backend-only stack has no frontend build to require. The codebase already keeps stack-shaped literals behind the stack seam (`test_stack_shaped_literals_live_behind_the_seam.py`).
- **`time_budget_seconds` and `manifest_max_attempts`:** **the stack declares them too.** They are what a scaffolded full-stack build costs, not what "validate" means.
- **The request profile names the depth** (`validate`). **The stack says what that depth requires of it.**

The cycle-create resolver adds the stack's defaults to `applied_defaults`, so `validate` with the fullstack stack asks for what `validated-fullstack` asked for. **It does not reproduce its config hash, and need not.** `compute_config_hash` is the SHA-256 of the merged defaults and overrides (`cycles/lifecycle.py`), and those include text like `notes`. Pinned configs keep their hashes because the old profiles stay (R2.4), not because a new name imitates them.

### R2.4 The recommendation, concretely

**Scheme A, with R2.3's stack defaults.**

- **The operator's set is seven names:**

  | name | runs | replaces |
  |---|---|---|
  | `smoke` | minimal | `selftest`, `default` |
  | `build` | framing then implementation, output validation | `build`, `builder-assemble`, `fullstack-fastapi-react`, `pulse-check-build` |
  | `validate` | as `build`, with typed validation and three corrections | `validation`, `validation-multirole`, `validated-fullstack`, `validated-fullstack-solo` |
  | `implement` | implementation alone | `implementation`, `build-only` |
  | `ship` | framing, implementation and wrapup | `multi-phase` |
  | `wrapup` | wrapup alone | `wrapup` |
  | `benchmark` | `smoke`, plus the metrics artifact | `benchmark` |

  `pulse-check` and `framing` are mapped once R2.1's `framing` question is read.
- **Set at create time, never in a name:**
  - the stack (`build_profile`, with the defaults it carries);
  - pulse checks;
  - multi-role authoring;
  - the correction path;
  - a prior cycle's plan.
- **The campaign's three profiles stay the campaign's,** outside the operator's set. The campaign code names them, nobody chooses them, and SIP-0109's pinned definitions resolve them.
- **Old names resolve forever, to exactly what they ran.** Every old profile's YAML is kept, frozen, under its old name, outside the operator's listing. A pinned config, whether a campaign definition or a verification set, resolves to the same defaults and the same config hash, by construction. That extends Q13's ruling from campaign definitions to every pinned verification-set config.
  - **Aliasing an old name to a new name plus overrides is not offered.** An override can add or change a key but never remove one, and the hashed defaults include their `notes`. So an alias could not keep the hash it claimed.
  - **The implementing PR's test:** each frozen profile is byte-identical to its last released YAML, and the operator's listing shows only the new names.

### R2.5 Decisions requested (replaces §10)

1. **Scheme A** (R2.4), or another of §6.
2. **The stack declares its required checks, time budget and manifest attempts** (R2.3). Otherwise the stack stays in the profile name, and P1 is withdrawn.
3. **Old profiles stay, frozen, under their old names,** so every pinned config resolves to what it ran. Q13 already rules this for campaign definitions.
4. **The campaign profiles stay outside the operator's set.**

### Delivery ledger (current as of 2026-10-19)

| part | status | where |
|---|---|---|
| the design (this SIP accepted) | **placed:** 2.4.0, #316 (moved from 2.3.0, 2026-10-15) | revision 4, reviewed by the MacBook lane 2026-10-19 |
| the stack-declared defaults and the resolver (R2.3) | **placed:** 2.4.0, #316 (moved from 2.3.0, 2026-10-15) | the 2.4 plan |
| the new names, with every old profile frozen under its old name | **placed:** 2.4.0, #316 (moved from 2.3.0, 2026-10-15) | the 2.4 plan |
| CLI sugar flags (`--stack`, `--pulse`, `--multirole`) | **unplaced**, deliberately: `--set` covers them | — |

**What closes this SIP:** acceptance, then the resolver and the new names shipped, with every old profile frozen and byte-identical.

## 1. Abstract

The 15 cycle request-profiles (20 at revision 2, R2.1) in `src/squadops/contracts/cycle_request_profiles/profiles/` are individually functional but **incoherent as a set**: each is named after a *different* axis, so a profile name doesn't tell you what it varies or how to choose between near-duplicates. This SIP diagnoses the taxonomy problem, extracts the axes that actually vary, states naming principles, and presents **three candidate schemes** with a migration map for the existing profiles — for the team to react to before any rename lands. It does **not** finalize a scheme; it frames the decision.

## 2. Problem Statement

The names are drawn from at least four different axes with no organizing principle:

| Axis the name is drawn from | Profiles |
|---|---|
| Workload / phase | `framing`, `implementation`, `wrapup`, `multi-phase`, `build`, `build-only` |
| Mechanism | `builder-assemble`, `pulse-check`, `pulse-check-build` |
| Intent / purpose | `validation`, `validation-multirole`, `benchmark`, `selftest`, `default` |
| Stack | `fullstack-fastapi-react` |

Consequences:

- **A name doesn't predict behavior.** You can't tell from `fullstack-fastapi-react` vs a would-be `validated-fullstack` which is "leaner" — because neither name is on the axis (instrumentation depth) that separates them. (This is what triggered #316.)
- **A crowded, overlapping cluster.** `build`, `implementation`, `validation`, `builder-assemble`, and the fullstack profile all mean roughly "instrumented plan→build" with small deltas. Choosing between them requires reading the YAML.
- **Stack is entangled with workflow.** `fullstack-fastapi-react` bakes a `dev_capability` into a workflow identity, so every (workflow × stack) combination would need its own profile — a combinatorial trap.
- **Orthogonal features spawn profiles.** `pulse-check`, `pulse-check-build`, `validation-multirole` are base workflows + one extra toggle, expressed as whole new profiles.

## 3. The axes that actually vary

Every profile is a point in this space:

1. **Phase scope** — framing / implementation / wrapup / which combination.
2. **Instrumentation depth** — plain vs. `output_validation` + `typed_acceptance` + `command_acceptance_checks` + correction budget + self-eval passes.
3. **Builder** — routes through `builder.assemble` or not. *(Note: already squad-driven — `build_tasks: true` auto-routes through the builder when the squad has one. So this is arguably not a profile axis at all.)*
4. **Dev capability / stack** — generic vs. `fullstack_fastapi_react` (etc.).
5. **Plan authoring** — sole-author vs. multi-role (SIP-0093).
6. **Verification** — pulse checks or not.
7. **Intent shortcut** — `default` / `selftest` / `benchmark` presets.

## 4. Goals / Non-goals

**Goals:** a naming convention where (a) a name predicts behavior, (b) orthogonal features don't multiply profile names, (c) stack is decoupled from workflow, (d) the set is small enough to choose from without reading YAML, (e) migration preserves existing references (aliases).

**Non-goals:** changing profile *semantics* (the SIP renames/reorganizes, it doesn't alter what a given config does); designing new workloads or capabilities.

## 5. Design principles (shared by all candidate schemes)

- **P1 — Stack ⊥ workflow.** `dev_capability` is a *parameter*, not a profile identity. `fullstack-fastapi-react` should not be a profile; it should be `<workflow> + dev_capability=fullstack_fastapi_react`. Requires `dev_capability` to be settable at cycle-create (via CLI flag / execution override).
- **P2 — Name by intent, not mechanism.** A name answers "what am I trying to do," not "which internal task types run."
- **P3 — Orthogonal axes → config/flags, not name variants.** Pulse, multi-role authoring, and builder presence are toggles on a base workflow, not separate profiles. (Builder is already squad-driven — P3 collapses `builder-assemble` into "use a builder squad.")
- **P4 — Small curated set beats many near-duplicates.** Prefer ~5–6 well-named workflows over 15 axis-mixed ones.
- **P5 — Backward-compatible migration.** Old names become deprecated aliases that resolve to the new profile (with a warning) for a deprecation window; nothing breaks on rename.
- **P6 — Reuse existing vocabulary where it fits.** The squad ladder is already `smoke / lite / full`; a rigor vocabulary for request-profiles could echo it rather than invent new words.

## 6. Candidate schemes

### Scheme A — Intent presets + orthogonal config *(recommended starting point)*

Profiles name the **goal**; everything orthogonal is a parameter.

| Profile | Intent | Replaces |
|---|---|---|
| `smoke` | Minimal power-on / plumbing check | `selftest` |
| `frame` | Planning only (framing gate), no build | `framing` |
| `build` | Full plan→build, standard instrumentation | `build`, `implementation`, `builder-assemble`, `fullstack-fastapi-react` |
| `validate` | Build at gate-evidence depth (deep instrumentation + correction) | `validation`, `validation-multirole` |
| `ship` | plan→build→wrapup (full lifecycle w/ closeout) | `multi-phase`, `wrapup` |
| `benchmark` | Metrics-collection defaults | `benchmark` |

Orthogonal, set at create-time (flag / override), **not** in the name:
- `--dev-capability fullstack_fastapi_react` (stack) → replaces the fullstack profile
- `--pulse` (verification) → replaces `pulse-check`, `pulse-check-build`
- `--multirole` (plan authoring) → replaces `validation-multirole`
- builder → **squad choice** (`lite`/`full` carry a builder), not a profile toggle
- `build-only` (consume prior plan) → a `--from-cycle` flag on `build`, or a retained edge profile

**Pros:** names = goals (intuitive), stack/pulse/multirole decoupled, 15 → ~6 profiles. **Cons:** requires make orthogonal axes settable outside the profile (new CLI/override surface); loses the "one name pins everything" convenience; a couple of edge cases (`build-only`, `benchmark`) don't fit the intent frame cleanly.

### Scheme B — Composable structured names

`<workflow>[-<modifier>…]`, fully systematic and self-describing.

- Base workflows: `plan`, `build`, `implement`, `ship`
- Modifier suffixes: `-deep` (instrumentation), `-pulse`, `-multirole`, `-fullstack`
- Examples: `build`, `build-deep`, `build-deep-fullstack`, `build-deep-multirole`

**Pros:** completely predictable; no hidden axes; a name fully specifies behavior. **Cons:** combinatorial name explosion and long names; the profile *count* stays high (you materialize the combinations you use); modifier order/precedence needs rules.

### Scheme C — Rigor ladder (mirror the squad ladder)

A workflow × a rigor tier that echoes `smoke / lite / full`.

- Rigor tiers: `smoke` (minimal), `standard` (normal instrumentation), `deep` (full validation + correction + evidence).
- e.g. `build-smoke` · `build` (standard) · `build-deep`; stack + pulse + multirole as parameters (as in Scheme A).

**Pros:** parallels a vocabulary operators already know (squad `smoke/lite/full`); rigor is the axis people most often tune. **Cons:** rigor + phase is two axes to encode; doesn't by itself express pulse/multirole (those still become parameters — so C is really A with a rigor suffix).

## 7. Recommendation (for discussion)

**Scheme A, borrowing C's rigor vocabulary for the depth axis.** i.e. intent-named workflows (`frame` / `build` / `validate` / `ship` / `smoke`), stack + pulse + multi-role as create-time parameters (P1/P3), and where a depth distinction is genuinely needed, a `-deep` / `standard` tier echoing the squad ladder (P6). This collapses 15 axis-mixed profiles to ~6 intent-named ones plus orthogonal config, and — critically — **removes stack from profile identity**, which is the specific trap `fullstack-fastapi-react` / `validated-fullstack` fell into.

## 8. Migration & backward compatibility

- **Aliases:** the loader (`list_profiles` / `load_profile`) maps each old name → its new profile, emitting a deprecation warning. Existing references (docs, scripts, #279 work) keep working through a window (e.g. one minor release).
- **Parameter plumbing:** P1/P3 require `dev_capability` (and `pulse`/`multirole`) to be settable at cycle-create independent of the profile. Verify current override support (`execution_overrides`) and add CLI flags as needed — this is the main implementation cost.
- **Even/odd cadence:** a rename/reorg is structural, not a feature — fits the odd-minor stabilization lane (1.3.0 bucket with the other structural cleanups) rather than a feature release.

## 9. Open questions

1. Is `dev_capability` currently settable at create-time independent of the profile? If not, P1 needs that plumbing first.
2. Should orthogonal toggles (`pulse`, `multirole`) be CLI flags, `execution_overrides` keys, or both?
3. How long a deprecation window for the old names?
4. Does `build-only` (consume a prior cycle's plan) stay a distinct profile or become a `--from-cycle <id>` flag on `build`?
5. **Cross-lane:** profiles drive both lanes' cycles (Mac uses `validation-multirole` for SIP-0093). The final scheme needs Mac-lane sign-off, and the deprecation window must cover Mac's references.

## 10. Decision requested

Pick a direction (A / B / C / hybrid) and confirm the deprecation approach, so a follow-up implementation SIP or PR can carry it out. Until then, `validated-fullstack` stays as-is (functional, badly named) and the #279 fold is held.

## 11a. As built (2026-10-19, #316, PR #2500; the supervisor, under the owner's grant of 2026-10-19)

**What shipped:** R2.3 and R2.4, under decisions 1 to 5 as revision 4 records them.
- **The operator's seven request profiles:** `smoke`, `build`, `validate`, `implement`, `ship`, `wrapup` and `benchmark`
  (`OPERATOR_PROFILES`).
  - `smoke`, `validate`, `implement` and `ship` are new files, each derived from the profile it replaces.
  - `build`, `wrapup` and `benchmark` keep their released YAML byte for byte, as (a) commits.
  - `GET /api/v1/cycle-request-profiles` and the CLI list the seven. Every other name still resolves by name, so every
    pinned definition keeps resolving the profile it names (Q13).
  - The CLI's default is `smoke`.
- **Every v2.3.1 profile is frozen:** a test pins each file's sha256.
- **The stack's request defaults (R2.3):** `squadops.stacks.request_defaults` declares each stack's required checks,
  time budget and manifest attempts, at the values `validated-fullstack` carried. `cycle_request_body`, the one
  builder the CLI and a campaign's launches share, puts them beneath an operator profile's own keys, and the caller's
  overrides above both. `validate` on either stack resolves to `validated-fullstack` apart from `notes`.
- **(a)'s added test:** every pinned verification-set config and campaign definition resolves to the same applied
  defaults and config hash as before (153 sets, and both profiles of every campaign definition).

**Where it narrows revision 4 (a): only an operator profile takes a stack's defaults.**
- **What (a) says:** a profile that doesn't set a key gains the stack's when it runs with a stack set at create time.
- **Why that was too wide:** applied to every profile, the rule changes the campaign profiles. `campaign-proposal` pins
  its own stack and sets none of the three keys, so its launches would gain required checks, a time budget and
  manifest attempts. `fullstack-fastapi-react` is the same. That contradicts decision 4 and Q13, which freeze the
  campaign profiles.
- **So the defaults apply beneath the seven operator profiles only.** Every other profile, released or the campaigns',
  resolves exactly as it did, whatever stack the caller passes. That holds by construction. A test runs every one of
  them on every stack, and a mutant without the rule fails 26 cases.
- **Three released names change, as (a) intends:** `build`, `wrapup` and `benchmark` are operator profiles too, so a
  stack set at create time adds the keys they don't set. No pinned config names any of them.
- **The window's launches are frozen by hash** (the second read of PR #2500). The 2.4 window's and its shakeouts'
  calibration and repair launches resolve to the config hashes main recorded before #316. Those hashes were read on
  main and on this branch, found identical, and pinned in a test. A second reader also rebuilt all 309 pinned
  requests on both trees: 153 verification sets, and every campaign definition's calibration, increment, retry and
  repair launches. Every body and hash was identical.
- **(a)'s own example holds:** `build` is an operator profile, so `build --set build_profile=fullstack_fastapi_react`
  gains the stack's required checks, as (a) says.
- **Evidence:** `test_request_profile_taxonomy.py`; the wiring test `test_a_campaigns_launches_on_a_stack_resolve_as_their_profiles_do`
  enters at a Next.js campaign's `calibration_launch` and `bound_launch`, the path the 2.4 window's campaigns take.


## 11b. The console resolves on the server (2026-10-19, #2520; the supervisor, under the owner's grant of 2026-10-19)

**What was wrong:** §11a's one builder had a copy. The console's cycle-create modal built its own body: the listed
profile's `defaults` as `applied_defaults`, and its own `computeOverrides`.
- **It sent no `request_profile`,** so a console cycle lost its profile provenance (SIP-0096).
- **It put `project_id` and `squad_profile_id` into `applied_defaults`,** so a console cycle's config hash never
  matched the CLI's for the same request.
- **It couldn't take a stack.** Since §11a no operator profile pins one, and the modal had no field for
  `build_profile`. So a console cycle got no stack's request defaults (R2.3), and one whose squad has a builder was
  refused at create (`builder_without_build_profile`, #2437): the console couldn't create a building cycle at all.

The second read of PR #2500 found the copy, and the second read of PR #2529 found the missing stack.

**What changed:**
- **`POST /api/v1/cycle-request-profiles/{name}/resolve`.** It takes the squad, the caller's values, and the notes and
  PRD the body carries. It answers with the cycle-create body that `cycle_request_body` builds from them, and creates
  nothing.
  - An unknown profile is 404.
  - A body the create route would refuse is 422, as the create would answer, and so is a caller setting the resolved
    fields itself.
- **Each profile's listing names the stacks it can run on** (`stacks`): every stack with request defaults for an
  operator profile, and none for any other, which pins its stack or takes none.
- **The modal asks the route:**
  - It offers that stack choice as the CLI's `--set build_profile`, with none by default, as the CLI has.
  - It resolves the request again whenever the profile, the stack, the squad or a value changes, and shows the answer
    as its preview. Nothing is submittable until the latest change has resolved.
  - On submit, it resolves before storing the PRD, then creates the cycle from the request resolved with the PRD and
    notes.
  - It no longer builds a body.

**Evidence:**
- **The wiring test** enters as the console does: it resolves `validate` on `nextjs_ts` through the route, then posts
  the answer to the create route. The cycle created has `request_profile: validate`, the PRD, and the CLI's config
  hash for the same request.
- **The route:** `validate` on each stack resolves to exactly the CLI's body, with the stack's request defaults among
  its applied defaults. The refusals are 404 and 422.
- **The listing** offers the two stacks to every operator profile, and none to `validated-fullstack`.
- **Mutants:** offering no stacks fails the listing test, and a resolve that drops `request_profile` fails three tests.
- **The second reader** resolved all 25 profiles, with three value sets each, through the route. Every one gave the
  CLI's request and config hash.
- **The plugin builds** with no warning from the modal.
