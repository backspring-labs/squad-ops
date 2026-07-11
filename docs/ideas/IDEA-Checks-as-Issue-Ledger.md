# IDEA: Checks as an Issue Ledger — Fine-Grained QA→Dev Remediation

## Target Release
Vision item — successor direction to the SIP-0086 convergence loop. Seed for `sips/proposed/SIP-Fine-Grained-Issue-Enumeration.md`.

### Status
Idea / vision draft

### Owner
QA / Build / Architecture

### Origin
Emerged 2026-07-10 from the #374 / #379 verification-integrity work, when the question came up: *"once we scale this out, QA may file issues on the app that dev fixes one by one — is a `check` an early incarnation of that?"* Answer: yes, in embryo — this note records the distinction and the direction.

---

## Check ≠ Issue

A **check** is a *measurement*: a named verification assertion — *"did criterion X hold?"* — that resolves to pass / fail / not-run (`CheckResult` in `verification_integrity.py`). It carries evidence (status, reason, provenance), **not** a description of a defect or a unit of work.

An **issue** is a *remediation unit*: a characterized problem with a repro, a fix, an owner, and a lifecycle (open → fixed → verified → closed).

A failed check is the **trigger and the evidence**; an issue is the **actionable, trackable ticket**. The connective tissue: **a check is an issue's definition-of-done** — the acceptance test that closes it.

## Today: coarse. The vision: fine-grained.

Today's convergence loop (SIP-0086) is **task-granular and binary**: a whole task fails → one `plan_delta` / `failure_analysis` → repair the whole task → re-run. The "issue count" is ~1 (the entire task).

The scaled model mirrors how human teams work:

1. Scaffolding makes the app **build and boot** (see `IDEA-Scaffold-Interface-vs-Implementation.md`), so QA can reach *behavioral* issues (endpoint returns 500) instead of drowning in structural ones (won't compile).
2. QA runs the app in an isolated sandbox (see `SIP-Externalized-Build-Sandbox`) and emits **many fine-grained checks** — one per endpoint / behavior / acceptance criterion.
3. **The set of FAILED checks *is* the enumerated issue list.**
4. Dev **resolves them one by one** — each fix flips one check from failed → passed.
5. The run's verdict is `accepted` only when every required check is executed-and-passed.

"Fixing issues one by one" is literally "flipping each failed check to passed" — N subjects converging independently, instead of one coarse task retried.

## The primitive already exists

`(check_id, subject_ref)` — the identity discussed for #379 — is a discrete, trackable unit with an **open (FAILED) → resolved (PASSED)** transition. That *is* an issue's state machine in miniature. #374 (re-run the real check) produces the resolved state; #379 (supersede to final state per `(check_id, subject_ref)`) teaches aggregation to honor it. So the verification layer is the **substrate** an issue ledger sits on — not the ledger itself.

## The missing surface

There is no single doc today that shows a check's **failed → passed lifecycle**:

- `run_report.md`'s `## Verification Integrity` section enumerates **failed** and **not-executed** checks by name, but shows **passed** only as a count, and only the **final** post-correction state.
- The failed→repair→passed trail is scattered across `failure_analysis.md`, `plan_delta_N.json`, `repair_validation.md`.
- The append-only `RunLedger` holds **both** states in memory but is never persisted as an enumerated, lifecycle view.

A first-class **issue ledger** — every check/issue listed with its subject, severity, and open/resolved lifecycle across the run — is the surface this vision adds. It is the natural extension of SIP-0096's `CycleOutcome` roll-up (§10) from an evidence summary into a per-issue tracker.

## Relationship to the arc

- **SIP-0096 (Verification Evidence Integrity):** provides the honest per-check evidence (executed-passed / executed-failed / not-executed) this ledger enumerates.
- **SIP-0086 (Build Convergence Loop):** the coarse predecessor; this is its fine-grained successor.
- **Scaffolding SIP (Contract-First Build Scaffolding):** gets the app to *build and boot* so QA reaches behavioral issues.
- **Externalized-Build-Sandbox:** the isolated place QA runs the app to *find* the issues.

The endgame reads like a real dev team: **scaffold → build/boot in a sandbox → QA enumerates fine-grained issues (failed checks per behavior) → dev resolves each → each check flips to passed → verdict `accepted`.**
