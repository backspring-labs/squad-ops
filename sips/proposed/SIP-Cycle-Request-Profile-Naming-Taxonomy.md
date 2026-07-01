# SIP-0XXX: Cycle Request-Profile Naming Taxonomy

**Status:** Proposed
**Authors:** SquadOps Architecture (Spark lane)
**Created:** 2026-07-01
**Revision:** 1
**Tracking:** #316 (holds the deferred #279 fold)

## 1. Abstract

The 15 cycle request-profiles in `src/squadops/contracts/cycle_request_profiles/profiles/` are individually functional but **incoherent as a set**: each is named after a *different* axis, so a profile name doesn't tell you what it varies or how to choose between near-duplicates. This SIP diagnoses the taxonomy problem, extracts the axes that actually vary, states naming principles, and presents **three candidate schemes** with a migration map for the existing profiles — for the team to react to before any rename lands. It does **not** finalize a scheme; it frames the decision.

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
