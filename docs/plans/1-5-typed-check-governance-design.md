# Typed-Check Governance — the Curated Menu as a Registry Extension (1.5 A5)

**Established:** 2026-08-05 · Gate-1 deliverable of
`docs/plans/1-5-0-stabilization-plan.md` (Track A5). This doc is the ruled decision
point for **#504** (restore-vs-report), **#629 layer 2** (contract enforcement shape,
A6), **#668** (DOM-testid enforcement), and **#598's check-half** (packaging
criterion). Decisions are presented with recommendations; owner ruling happens at
this doc's PR review.

## Current state — two axes, one already machine-readable

The check vocabulary lives on two deliberately separate axes:

1. **Run-level framework checks** — `src/squadops/cycles/check_registry.py`
   (SIP-0096 §6.3): 4 checks (`tests_pass`, `no_stub_fallback_tests`,
   `required_files`, `frontend_build`), `required_checks`-addressable, load-time
   validated. Complete for its purpose; **not extended by this design.**
2. **Typed acceptance checks** — `src/squadops/cycles/acceptance_check_spec.py`
   (SIP-0092 M1): 11 checks in `CHECK_SPECS: dict[str, CheckSpec]` —
   `undefined_names` · `endpoint_defined` · `import_present` · `field_present` ·
   `function_defined` · `harness_boundary` · `regex_match` · `count_at_least` ·
   `command_exit_zero` · `frontend_compiles` · `module_imports`.

The second axis is the menu's subject — and the good news is **the registry the plan
asks for already exists**: `CheckSpec` is a frozen dataclass carrying
`applicable_extensions`, `required_params`/`param_types`, `supported_stacks`,
`path_params`, and `framework_injected`, validated at plan authoring (unknown names
rejected; #671 module-existence; #686's classification table binds authoring rules to
the validator family with a drift test). The menu is therefore **an extension of
`CheckSpec`, not a new registry** — per the ownership-before-extension rule.

## Design — extend `CheckSpec` with the governance attributes

One PR adds the missing attributes (with a backfill for all 11 checks and a drift
test in the #686 pattern; prose documentation is *generated or validated from* the
registry, never hand-maintained beside it):

| Attribute | Type | Consumer |
|---|---|---|
| `failure_ownership` | `product \| suite \| plan \| contract \| infrastructure` | repair targeting (#688 lineage) and A3's evidence taxonomy — what the check's failure *indicts* |
| `qa_available` | bool | A1 (#670): which checks reach `qa.test` emissions — authored and injected both |
| `signature_participation` | bool | A4.1: whether the check's failures enter the correction failure-signature |
| `outcome_contribution` | bool | SIP-0096 `CycleOutcome` roll-up linkage |
| `replayable` | bool | Track C: whether a stored emission re-evaluates deterministically |
| `blocking_default` | `error \| warning \| info` | authored checks may still set severity; injected checks take this |

`framework_injected` already encodes authored-vs-injected origin; it stays as-is
(an `origin` enum would be a rename with no new information — not worth the churn).

**Backfill notes for the 11:** everything except `command_exit_zero` and
`frontend_compiles` is `replayable=True` (pure static analysis over stored bytes).
`qa_available` starts True for the `.py` static checks + `harness_boundary`
(pending A1's re-exam of its #671 exemption) and False for `frontend_compiles`
(qa emits suites, not views). `failure_ownership`: `undefined_names`/
`endpoint_defined`/`field_present`/`function_defined`/`import_present`/
`module_imports`/`frontend_compiles` → `product`; `harness_boundary`/
`no_stub` family → `suite`; `command_exit_zero` → per-command (see #707 note below).

## The four ruled decisions

### D1 — #504: restore vs report on fill-slot divergences

`fill_slot_integrity` restores `status_code` only; path, method, `response_model`,
function name, and parameter names are reported-but-not-restored (unsafe-restore
reasoning: the producer body may reference renamed params). #689 changed the
calculus — body breakage is now caught at acceptance — but **detection ≠ safe
restore**: a restored signature over a body using the old names produces a *visibly*
broken artifact instead of a silently drifted one.

**Recommendation:** restore nothing further. Instead, **promote the report to a
blocking injected check** — new registry entry `fill_slot_signature` (injected,
`.py` fill slots, `failure_ownership=product`, blocking): any reported divergence on
a scaffold-owned signature element fails acceptance with the divergence list as
evidence, routing repair at the producer instead of silently accepting drift. The
divergence stops being free without the framework ever rewriting producer code.

### D2 — #629 layer 2: two registry entries, split by determinism (= plan A6)

- `contract_assertions_match` — **blocking**, bind-mode only, authored-suite
  assertions diffed against `contract.behavior_expectation_lines()`;
  `failure_ownership=suite` (the pf-54 aim-inversion, made deterministic).
- `plan_prose_contract_divergence` — **advisory**, plan prose vs pinned statuses;
  separate identity so its (lower) evidence quality never launders into the blocking
  check. May only be promoted to blocking by a later registry change with proof of a
  deterministic representation (per the plan's A6 rule).

### D3 — #668: DOM-testid enforcement

The manifest declares `data-testid` anchors (#659 threads them into prompts;
prompts-only today). Two enforceable halves: (a) views carry the declared testids —
a deterministic static presence check on emitted frontend files, buildable now;
(b) qa suites *assert* them — suite-content analysis, weaker evidence, overlaps
1.6's clean-room verification (SIP-0102 step 4).

**Recommendation:** admit `testids_present` (half a) to the registry as a
**capacity-bound 1.5 build** (injected, frontend extensions, blocking_default
`warning` for one window then `error`); half b defers to 1.6 with the named trigger
"SIP-0102 step 4 lands clean-room verdicts."

### D4 — #598's check-half: packaging criterion

"The emitted container builds and runs" requires docker-in-verification — sandbox
territory (SIP-0102 steps 3–7, held to 1.6) and blueprint-owned packaging facts
(Generalized Build, 1.6). **Recommendation:** record `package_builds` in the
registry as *declared-unbuilt* (visible in the menu, not evaluable — the same
honesty pattern as `frontend_acceptance_checks_disabled` marking the unimplemented
JS analyzer) with the named trigger "Stack Blueprint lands." No 1.5 build.

## `command_exit_zero` and #707

`command_exit_zero`'s effective menu is today's two disagreeing allowlists. #707
(capacity-bound, Track D) must produce its command inventory and a precedence ruling
before this check's `failure_ownership` can be trusted (`python -m mypy` passing
both lists while unable to run is an `infrastructure` failure masquerading as
`product`). The registry extension records the dependency; it does not solve #707.

## Implementation shape (after this doc's ruling)

1. **PR 1 — registry extension**: `CheckSpec` attributes + 11-check backfill + drift
   test + generated/validated doc table. No behavior change (attributes are read by
   nothing yet) — pure enablement, safe first.
2. **Consumer PRs read the registry**: A1 reads `qa_available`; A4.1 reads
   `signature_participation`; D1's `fill_slot_signature` and D2's
   `contract_assertions_match` land as new entries behind their own PRs; repair
   targeting reads `failure_ownership` when A3 lands.

The menu issue (filed with this doc) tracks PR 1 + the D1/D2 entries;
D3-half-a is capacity-bound; D4 is declared-unbuilt.
