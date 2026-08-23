---
title: v1.6.2
---

# v1.6.2

**Released 2026-08-23** · [tag `v1.6.2`](https://github.com/backspring-labs/squad-ops/releases/tag/v1.6.2)

The information-flow patch line. Every fix here is one shape: **a fact the system
already holds, not reaching the agent judged against it** — and the release is the
first in the 1.6 line validated by a green roll with an independent boot audit.

**Cut evidence.** `cyc_79eebcb82205` / `run_9c879ff5458e`: verdict `accepted`, zero
failed checks, 5/5 contract probes verified — and the delivered application
independently **installs, builds, boots, answers every contract probe over real HTTP,
and its UI reaches every path it requests**. The verdict and the oracle agree, which is
the standard SIP-0096 exists to hold and the thing 1.6.2 could not previously show.

**Telling an agent what it is judged against:**
- #1029 — the frozen shell spine pins the success body's declared floor: required fields
  present, declared collection element kinds honoured. A floor, not a schema — every
  exclusion is a false-positive source, and the pin was replayed against banked green
  trees before it gated anything.
- #1042 — the declared success status reaches the developer by derivation. It previously
  survived only as a TODO comment inside the fill body the fill replaces.
- #1060 — the repair receives **every** manifest surface the initial author does. Three
  were missing; two of them (error contract, model surface) had renderers that had been
  producing empty output since they were written.
- #1002 — the detector's inspected-file inventory reaches the record, so a clean verdict
  is distinguishable from a detector that never saw the file.
- #1015 (B/C) — the repair is told to change the minimum, and can see "attempt N of M".

**The success status stops being authored three times** (#1067, #1070 part A). The status
existed in seven places, three of them independently authored — manifest, plan prose,
handler code — while `scaffold_contract` already derives it from endpoint shape. Five
incidents in three weeks took four fixes before anyone counted the recurrence.
- #1067 — a declared status contradicting the derived default must carry a `decisions[]`
  entry naming the endpoint **and** stating the status. Silence becomes the safe default:
  the rule decides, and there is nothing to disagree with.
- #1070 part A — the plan stops restating statuses. The authoring rule had *instructed*
  the copy ("an enforced non-200 status must be STATED"), because prose was once the only
  channel to the implementer; #1042 and #1063 replaced it. `cyc_79eebcb82205` was rejected
  twice, on two differently-named endpoints, for two documents disagreeing about an integer
  neither needed to decide.

**Correction-loop integrity:**
- #1053 — an emission containing nothing is not an attempt. A prior roll spent two of
  three rounds on zero-byte files while holding a correct, stable diagnosis; the refund
  is bounded so a producer that never emits still terminates.
- #761 — the `tests_pass` signature stops collapsing where the runner emits no machine
  report, so A4 can tell REPEAT from SHIFTED on pytest.
- #1030 — `framing_max_rerolls` defaults to 2; #522's free re-roll was dead code.
- #880 — `runs retry` after a failed run, broken by construction.

**Evidence integrity:**
- #1021 — a contract criterion with no result row stops being a silent fourth state;
  `criteria_unevidenced` separates "never ran" from "ran and failed". Reporting from
  production on the cut roll.
- #1022 / #1055 — containment findings for additive suites and for insert-as-update in
  route handlers. **Banked, deliberately not enforced**: #1049 is this line's own
  demonstration of what a rejection gate costs when its premise is never checked
  against real traffic.
- #980 follow-up — the dropped additive suite is recorded, not just the weakened fills.

**Gates and scaffold:**
- #1049 — the framing omission check reads both channels. #1042 made its stated premise
  ("the implementer will default to 200") false, and it was costing one to two re-rolls
  per cycle, dead-ending correct framings.
- #1055 — the frozen store gains `update(table, row)`. Its whole write surface was
  `insert`, which is `push`, so persisting a change had no correct form; two independent
  authorings on two models both stored duplicates instead.
- #972 — the regression gate no longer exits 0 when ruff is absent.
- The blueprint falsification gate stops depending on xdist's work distribution — it
  passed at 4 workers and failed at 20 on the same commit, so its verdict tracked the
  machine.

**Not exercised by the cut evidence, stated plainly.** The green roll ran on `98eb805e`.
Three changes merged after it launched and ride this tag without that roll having tested
them: #1064 (the store `update` seam — additive, a new export, no existing behaviour
altered) and **#1067 / #1070 part A, both authoring-facing behaviour changes**. They are
the right fixes and they are green in CI, but the boot-audit evidence above does not cover
them, and the first roll of 1.6.3 is what will.

**Known and named, not fixed:** #1021's underlying mechanism (why those two compile
criteria produce no row), #1054 (a repair routed to qa while the lead named dev task
types — 3.6 only, never fired on a 3.8 roll), #1070 part B (the manifest's own
`success_status` field remains authorable where the rule decides it — blocked on the
reference-manifest question).

## Merged pull requests (29)

| PR | Title | Closes |
|---|---|---|
| [#1075](https://github.com/backspring-labs/squad-ops/pull/1075) | chore(release): 1.6.2 — the information-flow patch line | — |
| [#1073](https://github.com/backspring-labs/squad-ops/pull/1073) | fix(plan): the plan stops restating success statuses — part A of #1070 | — |
| [#1068](https://github.com/backspring-labs/squad-ops/pull/1068) | fix(gates): a status that overrides the derived default must say why | [#1067](https://github.com/backspring-labs/squad-ops/issues/1067) |
| [#1072](https://github.com/backspring-labs/squad-ops/pull/1072) | fix(site): transparent favicon — Safari plates opaque icons | — |
| [#1069](https://github.com/backspring-labs/squad-ops/pull/1069) | test(site): indigo favicon tile to clear Safari's contrast plate | — |
| [#1066](https://github.com/backspring-labs/squad-ops/pull/1066) | docs(site): record the accepted Safari favicon tradeoff | — |
| [#1064](https://github.com/backspring-labs/squad-ops/pull/1064) | feat(scaffold): the frozen store gains an update seam — the write it never had | [#1055](https://github.com/backspring-labs/squad-ops/issues/1055) |
| [#1063](https://github.com/backspring-labs/squad-ops/pull/1063) | fix(correction): the repair sees every fact the initial author is judged against | [#1060](https://github.com/backspring-labs/squad-ops/issues/1060) |
| [#1062](https://github.com/backspring-labs/squad-ops/pull/1062) | feat(release): publish the GitHub Release from the tag, not from memory | [#1061](https://github.com/backspring-labs/squad-ops/issues/1061) |
| [#1059](https://github.com/backspring-labs/squad-ops/pull/1059) | feat(scaffold): insert-as-update findings on emitted route handlers — banked, not enforced | — |
| [#1058](https://github.com/backspring-labs/squad-ops/pull/1058) | docs(site): factual tone, the framing task sequence, and brand assets | — |
| [#1057](https://github.com/backspring-labs/squad-ops/pull/1057) | fix(qa): the containment findings actually reach the record — #1052 dropped them | — |
| [#1056](https://github.com/backspring-labs/squad-ops/pull/1056) | fix(correction): an emission containing nothing is not an attempt at the fix | [#1053](https://github.com/backspring-labs/squad-ops/issues/1053) |
| [#1052](https://github.com/backspring-labs/squad-ops/pull/1052) | feat(qa): additive-suite containment findings — banked, deliberately not enforced | — |
| [#1051](https://github.com/backspring-labs/squad-ops/pull/1051) | fix(verification): a contract criterion with no evidence stops being a silent fourth state | — |
| [#1050](https://github.com/backspring-labs/squad-ops/pull/1050) | fix(gates): the framing omission check reads BOTH channels — #1042 made its premise false | [#1049](https://github.com/backspring-labs/squad-ops/issues/1049) |
| [#1048](https://github.com/backspring-labs/squad-ops/pull/1048) | fix(correction): the repair is told to change the minimum, and can see the loop it is in | — |
| [#1047](https://github.com/backspring-labs/squad-ops/pull/1047) | fix(correction): the tests_pass signature stops collapsing when the runner emits no machine report | [#761](https://github.com/backspring-labs/squad-ops/issues/761) |
| [#1046](https://github.com/backspring-labs/squad-ops/pull/1046) | docs(site): separate the framework's verification from the project's measurement | — |
| [#1045](https://github.com/backspring-labs/squad-ops/pull/1045) | feat(qa): the retreat had two halves — record the dropped additive suite too | — |
| [#1044](https://github.com/backspring-labs/squad-ops/pull/1044) | docs(site): restructure on Diátaxis — evidence, roadmap, observability, dependencies, diagrams | — |
| [#1043](https://github.com/backspring-labs/squad-ops/pull/1043) | fix(prompts): the developer is told the declared success status, not left to plan prose | [#1042](https://github.com/backspring-labs/squad-ops/issues/1042) |
| [#1040](https://github.com/backspring-labs/squad-ops/pull/1040) | feat(scaffold): pin the success body's declared floor in the frozen shell spine | [#1029](https://github.com/backspring-labs/squad-ops/issues/1029) |
| [#1038](https://github.com/backspring-labs/squad-ops/pull/1038) | docs(site): Squad Ops documentation site — MkDocs Material, colocated with the code | — |
| [#1037](https://github.com/backspring-labs/squad-ops/pull/1037) | test(2c): the blueprint falsification gate stops depending on xdist's work distribution | — |
| [#1036](https://github.com/backspring-labs/squad-ops/pull/1036) | fix(cycles): carry the inspected-set reference to the record — a clean detector verdict is no longer indistinguishable from one that never looked | [#1002](https://github.com/backspring-labs/squad-ops/issues/1002) |
| [#1035](https://github.com/backspring-labs/squad-ops/pull/1035) | fix(cycles): retry after a failed run — typed workload-position resolution (#880) | [#880](https://github.com/backspring-labs/squad-ops/issues/880) |
| [#1034](https://github.com/backspring-labs/squad-ops/pull/1034) | fix(scripts): regression-gate preflight + positive completion evidence (#972) | [#972](https://github.com/backspring-labs/squad-ops/issues/972) |
| [#1033](https://github.com/backspring-labs/squad-ops/pull/1033) | fix(cycles): framing_max_rerolls defaults to 2 (#1030) | [#1030](https://github.com/backspring-labs/squad-ops/issues/1030) |

## Cycle evidence

### `cyc_79eebcb82205`

**Verdict:** `accepted` · **Runs:** 4

| | Checks |
|---|---|
| Verified | acceptance:frontend_compiles, acceptance:regex_match, acceptance_criteria_prose, expected_artifacts, frontend_build, no_self_mocking_tests, no_stub_fallback_tests, non_stub_files, required_files, tests_pass, vc-probe-api-runs, vc-probe-api-runs-join, vc-probe-api-runs-join-duplicate, vc-probe-api-runs-leave, vc-probe-api-runs-rejects-blank |
| Failed | — |
| Required unmet | — |
| Never executed | — |
