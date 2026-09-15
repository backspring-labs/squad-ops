# 1.8.0 — the pre-memory rejection baseline (B1), emitted

**Captured 2026-09-14** by the 1.8.0 plan's second rail (§3.5), from the Spark's artifact vault,
read-only. Data: `docs/plans/1-8-0-rejection-baseline.json` (schema 1,
`squadops.cycles.rejection_baseline.render`). Command:

```
.venv/bin/python scripts/dev/emit_rejection_baseline.py --vault data/artifacts \
    --recorded --benchmark-rolls docs/benchmark/rolls.yaml \
    --out docs/plans/1-8-0-rejection-baseline.json
```

**What it covers: 90 cycles.**
- **The 11 cycles holding the vault's 13 rejection records** (`--recorded`), 2026-08-10 to
  2026-08-23.
- **The 79 counted rolls of 1.6.3 through 1.7.5** (`--benchmark-rolls`, the benchmark
  registry's membership, SIP-0108 §4.3).

**What each row counts, per cycle** (`rejection_baseline.build_baseline`):
- **Rejection classes and their occurrences.** The framing gate's rejection records supply the
  plan-validation classes (`validate_*`). The manifest's authoring provenance, one entry per
  rejected authoring attempt (#803), supplies the authoring revision classes (`authoring_defect`,
  `derivation_defect`, `prd_insufficiency`).
- **Authoring attempts,** from that same provenance: the within-stage time to resolution.
- **Framing re-rolls:** the framing runs that stored a manifest or a rejection record, beyond
  the first.

## Findings

**1. Plan-validation rejection classes: none since 2026-08-23.** The 13 records' `validate_*`
classes occur only on the 11 recorded cycles:

| class | occurrences |
|---|---|
| `validate_manifest_plan_consistency` | 6 |
| `validate_check_applicability` | 2 |
| `validate_command_checks` | 2 |
| `validate_criteria_scope` | 2 |
| `validate_builder_floor` | 1 |

None of the 79 counted rolls carries a `validate_*` class, and none took a framing re-roll.
Framing re-rolls on the recorded cycles: two each on `cyc_181c9572bef2` and `cyc_79eebcb82205`,
none on the other nine. The plan's §2.3 reading holds for the metric it names, the recurrence
of plan-validation rejection classes: on this workload that corpus is empty after 1.6.2.

**2. Authoring revision classes did not stop.** 35 of the 79 counted rolls have at least one
rejected manifest-authoring attempt:
- `authoring_defect` on 35 rolls, 37 occurrences;
- `derivation_defect` on 33 rolls, 35 occurrences;
- `prd_insufficiency` on 10 rolls, 11 occurrences.

Every one resolved inside the authoring stage, in two or three attempts, and never reached the
gate. The recurrence is by stack:

| stack | counted rolls | rolls with a revision class |
|---|---|---|
| Next.js | 38 | 33 |
| FastAPI+React | 41 | 2 (1.7.3 and 1.7.5, one `authoring_defect` each) |

On Next.js the same pair, `authoring_defect` with `derivation_defect`, recurs on 33 of 38 rolls
across nine sets from 1.6.3 to 1.7.5.

The recurrence §2.3 names in the correction loop is one kind. This is a second kind the stores
already label, and a re-read of Phase 1's proving workload at 2.1 (§2.3) has it available: a
labeled class recurring across cycles on one stack. It is recorded here as evidence and changes
no ruling.

**3. Attempts on the counted rolls:** one attempt on 44 rolls, two on 33, three on 2.

## Limits

- **Framing re-rolls are counted from stored artifacts,** not from the registry's runs. A framing
  run that stored neither a manifest nor a rejection record is not counted. The benchmark
  registry's `framing_rerolls` indicator, read from the registry, reads zero on all 79 counted
  rolls too (`docs/benchmark/regrade.json`).
- **A cycle with no authored manifest has no provenance.** Such a cycle (operator-seeded)
  reads zero attempts and no authoring classes. Every counted roll here has attempts of at least 1.
- **The two void launches** (`cyc_e33939eda950`, `cyc_af7dd4ad95b0`) are not counted rolls and
  are not in this capture.
