# Evidence

Measurement windows run by the maintainers to test framework performance. Each
window is pre-registered: the number of runs, requirement document, deployment
hash, and scoring rule are committed before the first run.

A run scores **functional** when three conditions hold:

1. The cycle verdict is `accepted`.
2. An independent audit confirms the delivered application installs, builds,
   boots, and answers every probe its contract specifies.
3. No human intervened during the run.

## Authored-mode window — closed 20 August 2026

The squad authored its own interface design, then built against it.
Pre-registered N = 6, bar ≥ 4/6.

| Measurement | Result |
|---|---|
| Pre-registered instrument | 3 functional / 6 |
| Corrected instrument | **4 functional / 6** — bar met |

Both numbers are the record. The deciding run first scored as a failure; the
cause was a defect in the auditing tool. The correction was ruled before the
corrected measurement was taken, so the ruling was made independently of its
outcome.

Across the arc, 9 of 9 delivered applications install, build, boot, and answer
their probes. Zero manual interventions across the window. No run was re-run.

## Seeded-mode window — closed 31 July 2026

The squad received a fully specified interface design and built against it.
Pre-registered N = 6.

**6 of 6 functional.**

This window measures implementation against a given design. Authoring the design
was measured separately, in the August window above.

## Scope of these results

Both windows share the same conditions:

| Dimension | Covered |
|---|---|
| Application size | Small-to-moderate greenfield web applications |
| Requirement source | A single requirement document |
| Technology stack | One (a second is in progress) |
| Codebase | New projects only |
| Inference | Local open-weight models, 27B class |

Results outside those conditions — large existing codebases, migrations,
multi-stack work, hosted frontier models — have no measurement here.

## Method notes

**Pre-registration.** The scoring rule and run count are committed in writing
before the window opens, and the window record accumulates per-roll rather than
being edited afterwards.

**Independent audit.** Conditions 2 and 3 above are evaluated outside the
framework, by a separate auditing script and by inspection of the run's gate
decisions.

**Instrument corrections.** When the auditing tool is found defective mid-window,
the disposition is ruled before the corrected measurement is taken, and both
measurements stay on the record. The August window is the worked example.

Window records live in the repository under `docs/plans/`, one file per window.
