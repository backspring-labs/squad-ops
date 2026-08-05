# SIP-0096 Promotion Evidence — Acceptance-Criteria Mapping

**Promotion date:** 2026-08-06 (v1.5 line, Gate 2 — per `docs/plans/1-5-0-stabilization-plan.md` §A2:
the promotion PR lands *before* the release candidate, and the Gate-2 exit confirmation shakedown
runs against the promoted state).
**Audit baseline:** `docs/plans/sip-promotion-audit-2026-08-03.md` (verdict then: stays accepted,
four normative items open).

## Closure of the audit's normative set

| Audit item | Closed by |
|---|---|
| #682 gate-waiver slice (§6.5/AC#12) | PR #742 — `GateDecision.waived_checks/waiver_reason`, migration 1030, waiver ⊆ run's unverified disclosure, `CycleOutcome.waived` population, CLI `--waive/--waiver-reason`; verdict stays un-waived |
| #683 wrap-up consumer (§10/§14) | PR #743 — executor injects `verification_evidence` into every wrap-up task; `confidence_ceiling` clamps prose over-claims with frontmatter disclosure; absent outcome fails closed to `inconclusive` |
| #684 §9 inert detection (AC#10 second half) | PR #744 — derived-on-read streak over persisted summaries; execution resets, reports increment, absence pauses; `CycleOutcome.inert` populated |
| §8 pulse SKIP-only→PASS amendment (AC#6) | **This PR** — `PulseDecision.SKIP`; SKIP-only boundaries are zero evidence, disclosed, never a pass credit, dispatch no repair; D18 timeout rule unchanged. *(Premise note: the 1.5 plan's "remaining set is exactly #682/#683/#684" transcription dropped this audit item — caught at promotion build time; the #423 issue closure covered the evidence-gap half only.)* |

## Acceptance criteria — evidence

| AC | Status | Evidence (code → test) |
|----|--------|------------------------|
| 1. Aggregation property: only executed-and-passed credits; 0-of-0 is zero evidence | **Met** | `verification_integrity.classify`/`aggregate_verification` → `test_verification_integrity.py` status×family matrix, `pass_rate` zero-evidence tests |
| 2. Required not-executed → `blocked_unverified`, distinct from `rejected`, no new `RunStatus` | **Met** | `aggregate_verification` verdict rule; `RunVerdict` not a `RunStatus` → blocked/required tests incl. the no-result required check (#291 case) |
| 3. Anti-stub: undisclosed stub pass ≠ executed-passed | **Met** | `classify` §6.6.1 branch; `no_stub_fallback_tests` marks synthesized `tests_pass` as stub (`verification_normalize`) → stub-classification tests; #289 detection records the integrity signal |
| 4. No narrative override: prose cannot alter the structured verdict | **Met** | The verdict derivation has no narrative input by construction; the injection test the AC names is `test_confidence_ceiling.py::TestClamping` — a contradicting prose claim (`verified_complete` over a rejected outcome) is enforced back to the ceiling with disclosure (#683) |
| 5. Requiredness declared, never inferred | **Met** | Required set threaded from explicit declarations only (`run_completion`, via the #724 resolved-config merge) → `test_requiredness_not_inferred_from_name` |
| 6. Pulse SKIP-only no longer PASS | **Met (this PR)** | `determine_boundary_decision` → `PulseDecision.SKIP`; runner dispatches no repair; report counts SKIP separately → `test_skip_only_is_skip_not_pass` and runner/report tests |
| 7. Frontend amendment (#306) | **Met** | `frontend_build`/`frontend_compiles` execute on the fixed image (#648 real-bundler check); `CHECK_FRONTEND_BUILD` requires `TOOL_NODE` — required-with-absent-tooling is a create-time 422 (`required_check_tooling_decision`) and preflight/doctor parity covers it |
| 8. `required_files` enforced through the choke point | **Met** | Builder emits the `required_files` check row (#399, `builder.py`) normalized through the same aggregation; declared-but-missing blocks per requiredness |
| 9. Provenance: reasons on every not-executed; bounded provenance on executed | **Partial — disclosed** | The §7 reason taxonomy is fully implemented (every not-executed row carries a machine-readable reason; unknown reasons disclosed, never dropped; bounded by construction). Optional `CheckProvenance` fields: `exit_code` populated for command-backed checks; `executed_at`/`duration_ms`/`subject_ref`/`executor_ref` remain unpopulated. The audit classified this as **secondary (clean-AC sweep)**, not promotion-gating; the field population is follow-up hardening. |
| 10. Inert/non-executable | **Met** | Doctor `verification` category + preflight parity (non-executable half); #684 streak detection keyed on `check_registry` stable identity, reset only on real execution (inert half) |
| 11. Roll-up constructible only via the aggregation decision | **Met (test added this PR)** | `aggregate_cycle_outcome` is the sole production constructor → `test_cycle_outcome_constructible_only_via_the_aggregation_decision` (architecture scan) |
| 12. Waiver: explicit gate decision only; results never mutated | **Met** | #682 (PR #742): waiver recorded beside the verdict; `validate_waiver_request` (waived ⊆ unverified disclosure); no implicit path → gate-waiver test suite |
| 13. Purity + no third vocabulary | **Met** | `test_module_is_pure_no_io_imports` (AC#13 architecture test); evidence family derived at aggregation only; `ResultStatus` drift test pins producer vocabulary |
| 14. Compatibility honestly stated | **Met** | No shipped profile declares `required_checks` by default — zero default-profile verdict flips (Phase-2 enumeration: none), matching the SIP's expectation; the throttle remains per-profile opt-in |

## Normative sections — disposition

- **§6.1–§6.6** (three layers, aggregation rule, requiredness, choke point, `blocked_unverified` +
  waiver, integrity violations): **implemented** (`verification_integrity`, `run_completion` seam,
  #682 waiver flow).
- **§7** (execution provenance): **implemented** for reasons; provenance fields partial per AC#9 above.
- **§8** (conformance table): pulse row **implemented this PR**; frontend row implemented (#648 +
  tooling preflight); typed-acceptance, generated-test, and `required_files` rows implemented as
  specified (classification + disclosure, no severity-semantics change).
- **§9** (non-executable + inert): **implemented** (doctor/preflight + #684).
- **§10** (`CycleOutcome` roll-up): **implemented**; consumers live: cycle-detail API, wrap-up
  (#683). The Campaign continuation decision remains the designed 1.6+ consumer (non-code here).
- **§11** (phasing): all phases landed across the 1.4 arc + 1.5 Gate 2 — acceptance is all phases,
  per the SIP.
- **§15/§16** (testing, open questions): covered by the suites cited above; no open question
  remains load-bearing (Q resolutions recorded in-text at rev 2).

## Live validation

Core live-proven across the 1.4 arc (shakedowns shk-1…shk-5 consumed the verdict/evidence surfaces;
the 1.4.3 verdict-accepted exhibit). The completion slices' live proofs (waiver E2E, inert on real
history, closeout evidence-in-prompt, SKIP disclosure) ride the **Gate-2 exit confirmation
shakedown**, which runs against this promoted state — per the plan's promotion-before-RC rule.
