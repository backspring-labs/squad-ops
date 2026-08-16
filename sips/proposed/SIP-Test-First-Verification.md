---
status: proposed
title: Test-First Verification
---
# SIP: Test-First Verification

## Status
Draft (proposed)

**Targets:** Phase 1 the release after the SIP-0104 P6 window closes; Phase 2 a later even
minor, gated on contract completeness. See §"Sequencing".
**Builds on:** SIP-0104 (deterministic verification scaffolding — the frozen spine and
fill protocol), SIP-0098 (verification contracts derived from the manifest), SIP-0096
(verification evidence integrity — only executed-and-passed credits).
**Motivating case:** a test that has never been observed to fail has not been shown to
test anything, and today nothing requires one to have failed.

---

## Summary

Require every authored test to **prove it discriminates** before it is allowed to
certify. Phase 1 does this without changing task order: run the authored fills against a
contract-conforming stub and reject any that pass. Phase 2 moves qa authoring ahead of
development so the author provably cannot write against the delivered code.

Phase 1 is the load-bearing half. Phase 2 is a sequencing change that adds independence
and moves spec gaps earlier.

---

## The problem, precisely

**QA is the only layer with no verifier above it.** If dev emits a wrong file the suite
catches it. If qa emits a wrong test, nothing catches it — a failing assertion looks
identical whether the application is broken or the test is wrong, and a *vacuous*
assertion looks identical to a real one that happens to pass.

Underneath that sits a structural asymmetry: **dev is asked to choose, qa is asked to
guess what dev chose.** Where the contract is silent dev simply picks — picking is always
legal — and qa must predict the same pick from documents. Every under-specification
therefore surfaces as a qa failure rather than a dev failure. The fixes that have actually
worked all have this shape: showing the author the error envelope it had been inventing
(#911), pinning endpoint statuses after five authored suites asserted 200 where the probe
pinned 201 (#629). Neither taught qa to write better tests; both removed a guess.

The obvious repair — show qa what dev built — is worse than the disease. It produces
suites that assert the code does what the code does: green, meaningless, and
indistinguishable from verification. The correct move is that the interface is settled
**upstream by neither party**, completely enough to write a test from, and then
independently proven to discriminate.

### What is currently undetected

- A suite may mock `global.fetch` and assert its own mock. It goes green and nothing
  detects it (#915, open).
- A fill may assert nothing meaningful. `void body` satisfies the compiler; an assertion
  that restates the declared status satisfies the runner.
- Roll 1 of the P6 window passed 36/36 checks, all five probes, `tests_pass`,
  `frontend_build` and the boot audit **with a completely dead UI**. A human found it; no
  layer did.

Each is the same hole: nothing establishes that a passing test *could have failed*.

---

## Phase 1 — the red gate

**Rule: a fill that passes against a contract-conforming stub is not a test, and is
rejected at authoring time.**

Reuse the SIP-0104 P3 disposition for a rejected fill — it renders as a failing state
exactly like a missing slot, so the correction loop already knows what to do with it.

### The stub is the whole design problem

The naive form of this gate is vacuous. Running a merged shell against a *bare* skeleton
fails regardless of the fill, because the frozen spine's own status assertion
(`expect(res.status).toBe(201)`) fails first. That proves nothing about the fill.

The gate must therefore isolate the fill's contribution, which means running against a
stub that **satisfies the contract and violates everything else**:

- returns each behavior's **declared status** — so the spine passes and the fill is the
  only thing under test;
- returns a structurally empty or deliberately wrong **body**;
- produces deliberately wrong **store effects**.

Against that stub, a fill asserting real response values or real state effects fails — as
it must. A fill that merely restates the status, or asserts nothing, passes — and is
rejected.

The stub is derivable from the same contract the shells are, and should be emitted by the
same generator under the same byte pins.

### It must fail *as an assertion*

A fill that dies on an import error proves nothing. Phase 2 of SIP-0104 already measured
this surface and built the classifier: vitest delivers both chai mismatches and thrown
errors as bare messages, so the allowlist of assertion shapes is what separates "this test
discriminates" from "this test is broken". The red gate consumes that classifier
directly — mechanical failure against the stub is a *defect in the fill*, not a pass.

### What Phase 1 buys

- **Tautological fills are rejected**, by construction rather than by review.
- **The mocked-`fetch` loophole closes structurally.** A suite that mocks the network and
  asserts its own mock passes against the stub — and is therefore rejected. Nothing has to
  detect mocking.
- **`tests_pass` starts meaning something stronger**: not merely "executed and passed", but
  "executed, passed, and demonstrated it could have failed."

### What Phase 1 costs

One additional workspace materialization and dependency install per qa task. The
skeleton-execution gate already pays this cost, so the machinery exists; the honest
accounting is that qa tasks get measurably slower.

### What Phase 1 does *not* require

No change to plan ordering, `depends_on`, the manifest schema, or the framing sequence.
It is additive to the existing qa task.

---

## Phase 2 — authoring before implementation

Move `qa.test` ahead of `development.develop` in the plan, inverting `depends_on`:

```
manifest + contract  →  qa authors from the contract alone
                     →  red gate (Phase 1)
                     →  dev implements against the contract
                     →  green run
```

### What Phase 2 adds beyond Phase 1

- **Independence becomes structural, not behavioural.** The author cannot write against
  the delivered code because the delivered code does not exist. Phase 1 proves a test
  discriminates; Phase 2 removes the opportunity to overfit in the first place.
- **Spec incompleteness surfaces at framing.** "Can a discriminating test be written from
  this contract alone?" is a completeness check on the contract, answered in minutes
  rather than after a three-and-a-half-hour build. QA becomes the consumer that proves the
  specification is sufficient — a considerably better use of the role than post-hoc
  prediction.

### What Phase 2 requires

**The contract must pin the observable interface, not just its edges.** Today it pins
method, path and declared status; it does **not** pin response bodies — the uncovered
surface this window already named (#913, itself blocked on #795). Without body pinning,
test-first merely moves the guessing earlier: the author writes honest tests against an
incomplete specification and guesses the shapes anyway.

Phase 1 has no such dependency: discrimination is checkable against whatever the contract
currently says.

---

## Sequencing

1. **Draft and accept freely.** Docs only; no effect on any measurement in flight.
2. **Neither phase may land inside a measurement window.** Rolls are attributable only
   because a deploy boundary carries exactly one named change. A new enforcement surface
   is not one named change, and Phase 2 alters framing's output.
3. **Phase 1 after the P6 window closes.** Small, independent of contract completeness,
   and it carries most of the honesty benefit.
4. **Phase 2 after response bodies are pinned**, as a headline for an even minor — it adds
   verification capability rather than hardening it.

---

## Non-goals

- **Not TDD for dev.** Dev continues to implement against the contract and never sees the
  suite. Coding to a specification is correct; coding to assertions is overfitting.
- **Not a replacement for the scaffold.** This extends SIP-0104 — the scaffold removes
  mechanical error, the red gate removes dishonest assertions. Neither substitutes.
- **Not a claim that failing tests are good tests.** A test that fails against the stub
  has demonstrated discrimination, not correctness. It can still assert the wrong thing.
- **Not behavioural coverage.** Neither phase catches "does the wrong thing" — roll 6's
  leave endpoint returning 404 where the contract pins 200 would satisfy every rule here.
  That belongs to the probes.

---

## Open questions for review

1. **How hostile should the stub be?** A stub that returns the declared status with an
   empty body is easy to derive and rejects the weakest fills. One that actively returns
   wrong values and wrong store effects rejects far more — and risks rejecting legitimate
   fills. Where is the line, and is it per-stack?
2. **Negative assertions may be vacuously true.** "Nothing was created" holds trivially
   against a stub that creates nothing — so a legitimate negative fill could be rejected,
   or a lazy one accepted, depending on the stub's behaviour. This is the sharpest known
   weakness and it drives question 1.
3. **Where does the red run execute** — inside the qa handler, or as a separate gate task
   with its own evidence row? The latter is more visible and more expensive.
4. **Can the stub run be cached** per (manifest hash, generator version)? The stub is
   deterministic, so in principle yes; the fills are not, so only the workspace is
   reusable.
5. **Do additive suites face the same gate?** They are whole files rather than fills, and
   they are where the mocking loophole actually lives — which argues yes.
6. **Does `not_applicable` remain a legal disposition** for a slot under this rule? It
   asserts nothing by design, so it cannot discriminate; it is presumably exempt, but the
   exemption should be explicit and counted.
7. **Phase 2 only:** does qa author from the contract alone, or also from the skeleton?
   The skeleton is dev-independent and supplies the import surface, so it is probably
   legitimate context — but it is one step closer to writing against an implementation.

---

## Evidence

To be completed from the diagnostic run of 2026-08-16 (`cyc_831dfe6ac551`), which
exercises the corrected scaffold and fill protocol end to end. That run tests whether the
two known implementation defects are fixed; it does not test this SIP's thesis, but a
clean result is the strongest available demonstration that the scaffold bet works when
correctly implemented — which is what the red gate extends.
