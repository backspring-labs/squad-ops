# pf-31 Correction-Convergence Fixes — Fix + Dev Plan

**Status:** proposed (plan-first, #551 precedent). Implements nothing by itself.
**Evidence base:** pf-31 (`cyc_03bc35a21b55`, deploy `e1dcc752`, 2026-07-24) — terminal
`rejected` 4/6 (`endpoint_defined` + `tests_pass`), max-corrections exhausted. All three
deploy mechanisms (#562 fill-only on repairs, 3.4b restore both halves) confirmed live;
the remaining losses are the three defects below. Each has a crisp reproduction in the
pf-31 artifact trail.

---

## Fix A — Authoritative contract expectations in the repair prompt

### Evidence (the `{run_id}` poisoning)

All seven pf-31 repairs emitted `{run_id}` path params where the contract pins `{id}`;
patch verification rejected every one; convergence happened only when a generative
re-roll landed on `{id}` by luck (attempt 3). The final repair's `{run_id}` emission
then superseded the passing version (see Fix E).

### Root cause — delivery ≠ salience

The resolved TypedChecks ARE delivered to the repair today. In bind mode,
`task_plan.py:580-585` extends the plan task's `acceptance` with
`resolve_contract_refs(criteria_refs, contract)` — so the failed envelope's
`acceptance_criteria` carries the concrete `methods_paths` (with `{id}`), and the repair
envelope inherits it (`correction_runner.py` threads `failed_inputs["acceptance_criteria"]`).
But the repair prompt renders that list via `_format_bullets` (`repair_handlers.py`),
which stringifies TypedCheck dicts into repr soup — while the SAME list leads with the
plan's PROSE bullets, which say `{run_id}` in clean English. The model follows the
legible, contradicting prose. This is a rendering/salience defect, not a plumbing defect
— #562 taught us to verify the gate condition; this is the prompt-side equivalent.

### Design

1. **A1 — CONTRACT EXPECTATIONS block (the fix).** In the repair prompt (and the
   correction `failure_summary`), render the failed task's resolved TypedChecks as a
   structured authoritative block, ABOVE prose, using the established
   authoritative-block pattern (`INTERFACE CONFORMANCE` / `FROZEN OWNERSHIP`):

   > CONTRACT EXPECTATIONS (authoritative — apply exactly):
   > - endpoint_defined `backend/routes.py` requires exactly: `POST /runs`, `GET /runs`,
   >   `GET /runs/{id}`, `POST /runs/{id}/join`, `POST /runs/{id}/leave`
   > - import_present `backend/routes.py`: `from .errors import ApiError`

   Renderer: a pure formatter (typed-check dict → one line per check) in the cycles
   layer; block-heading text lives in the request template assets, NOT Python literals
   (#448 rule). Python threads data only.
2. **A2 — demote conflicting prose.** When resolved TypedChecks are present for a file,
   the prose criteria render under a "Narrative (non-authoritative)" subheading in the
   repair prompt. No prose is deleted — it is ranked.
3. **A3 (small, separable) — framing-side conflict lint.** A plan-validation WARNING
   when task description/prose criteria contain path params or methods conflicting with
   the task's resolved refs (pf-31's `{run_id}` prose and pf-30's `DELETE /leave` prose
   were both gate-visible). Surfaces in the gate review payload; warning-only, never a
   rejection (the reverted #552 lesson: no new hard gates on unvalidated surfaces).

### Surfaces

- `src/squadops/cycles/` — new pure formatter (e.g. `contract_expectations.py` or a
  function in `verification_contract.py` beside `criteria_index_lines`).
- `src/squadops/capabilities/handlers/impl/repair_handlers.py` — render variables for
  the block; `_format_bullets` stops receiving raw TypedCheck dicts.
- `src/squadops/prompts/request_templates/request.cycle_repair_task.md` (+ base) — block
  placement.
- A3: `implementation_plan.py` (`validate_criteria_refs` neighborhood) + gate payload.

### Acceptance

- Replay: rebuild repair-01's prompt from pf-31 stored artifacts with A1/A2 applied; the
  rendered prompt contains the exact `{id}` path list above the prose; one-shot 27b
  emission uses `{id}` (replay-verification rule — this exact replay would have caught
  the poisoning pre-deploy).
- Unit: formatter output for endpoint_defined/import_present/command_exit_zero specs;
  conflict-lint fires on the pf-31 plan fixture, silent on a consistent plan.

### Expected unlock

With repairs matching the contract, `_try_accept_patch` (#389) should start accepting —
ending the re-roll lottery (2 of 3 pf-31 dev re-rolls regressed) and shrinking attempt
burn. pf-31 spent 3 of 5 attempts on a one-token mismatch.

---

## Fix D — Emission-integrity gate on the repair path (truncation guard)

### Evidence

pf-31 repair-03 emitted a truncated `backend/tests/test_runs.py` (SyntaxError,
"abruptly truncated function definition") → pytest collection crash → the repair itself
re-imported the failure class it was fixing. The 4-file union emission on qa.test
repairs raises token-budget truncation risk. (Related, not a substitute: PR #528's
fenced-parser EOF-recovery salvages the fence, not the syntax.)

### Design

At the 3.4b enforcement hook (`correction_runner._dispatch_protocol_step`, before
storage): for each repair-emitted `.py` artifact, `ast.parse` the content. On syntax
error: **drop the artifact** (the prior stored version — last known parseable — stays
current for RC3 and the retest), emit a structured event/log (mirror
`scaffold_integrity` shape, e.g. `emission_integrity`), and append a carry instruction
("your emitted `X` was syntactically invalid/truncated — re-emit the complete file"),
reusing the 3.4b restore+signal transport verbatim.

- Python-only in scope (`.py` = the collection-crash class). Frontend/JSON left alone.
- Regular develop-path emissions NOT in scope: their typed checks (`command_exit_zero`
  py_compile) already gate them at task acceptance; the repair path has no such gate.

### Acceptance

- Unit: truncated `.py` repair emission → dropped + carried + evidenced; valid `.py` and
  non-Python artifacts pass through; drop leaves prior stored version current.
- Replay: repair-03's actual truncated artifact from pf-31 → dropped.

---

## Fix E — Rejected-candidate evidence must not supersede standing state

### Evidence

pf-31 final outcome failed `endpoint_defined` even though m001 PASSED it at 18:58 —
because verification aggregates the **RunLedger** with last-evidence-wins per
`(check_id, subject)` (`run_completion._aggregate_verification` → SIP-0096 aggregation),
and the last `endpoint_defined` evidence was repair-04's REJECTED candidate failing
patch verification at 20:22. A discarded candidate's evidence overwrote the accepted
product's state. Same accounting error on the deliverable side: the last stored
`routes.py` in the registry is repair-04's `{run_id}` version (stored for RC3
accumulation), superseding the passing 18:58 version for anything that reads
last-wins-by-filename.

### Design

1. **E1 — ledger:** patch-verification evidence for a candidate that ends REJECTED is
   attempt telemetry, not product state. Tag candidate-verification evidence records
   with a disposition (or record them under a candidate subject); the SIP-0096
   aggregation excludes rejected-candidate records from final supersession. The #379
   failed→passed history for the TASK's own executions is untouched.
2. **E2 — deliverable:** final artifact-state assembly prefers, per filename, the last
   version produced by an ACCEPTED source (completed task or accepted patch) over later
   rejected-candidate emissions. Constraint honored: rejected emissions STAY stored —
   RC3's analyze-side accumulation depends on them — only final-state selection becomes
   acceptance-aware.

### Open question (flagged, decide at implementation)

Where candidate evidence is recorded today (executor patch-verification path vs ledger
recorder) determines whether E1 is a tag-at-write or filter-at-aggregate change; the
investigation step pins this before code. E interacts with Fix A: once acceptance fires
routinely, rejected-candidate volume drops and E becomes a rare-path correctness fix —
still worth building (terminal-on-rejection remains exactly the case where honest
accounting matters most).

---

## Sequencing & verification

1. **A first** (one PR: A1+A2, A3 separable) — highest leverage; plausibly unlocks #389
   acceptance.
2. **D second** (small, independent; reuses 3.4b transport).
3. **E third** (needs the recording-point investigation; benefits from A landing first).

All three land in one deploy window (same baseline-reset discipline). Pre-deploy:
replay verification per fix (A: prompt replay from pf-31 artifacts; D: repair-03's real
truncated artifact; E: pf-31 ledger fixture reproducing the endpoint_defined
supersession). Post-deploy, in-container gate-condition checks per the pf-30 lesson
(rendered block present in a real repair prompt; emission gate drops a seeded truncated
artifact; final aggregation on a replayed ledger). Then pf-32.

## Non-goals

- No authoring-side target binding (#552 territory — stays reverted).
- No changes to accept-outright logic itself (#389): Fix A is expected to make it fire;
  if it still doesn't, that becomes a NEW investigation with pf-32 evidence, not a
  speculative patch here.
- No emission-set narrowing for qa repairs (union targeting stays; D guards its risk).
