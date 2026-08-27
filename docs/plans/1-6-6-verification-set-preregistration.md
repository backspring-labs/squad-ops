# 1.6.6 — Verification Sets: Pre-registration

**In force from roll 1, by the commit hash of this document on its branch, and unchanged
thereafter.** Written 2026-08-27 (afternoon ET), after the rebuild on the merged 1.6.6 pack and
after both shakeouts, before the first counted launch. Merging it is the owner's act and does
not change what it pre-registers; the branch commit is the record.

This is the 1.6.6 plan's §3 (`docs/plans/1-6-6-plan.md`, rev 1) with one change the owner
made on 2026-08-27: **two counting sets of four, not one of six** — the FastAPI+React set that
measures the pack, and a Next.js+TS regression arm that asks only whether anything moved.
Everything not restated here is inherited **verbatim** from the 1.6.5 pre-registration
(`docs/plans/1-6-5-verification-set-preregistration.md`) and, through it, 1.6.4 and 1.6.3:
§5 (scoring), §5.1 (roll validity — void / reset / counted), §6 and §6.1 (the gate constant
and the two approval paths), §7 (prohibited while open).

**The instrument moved with the pack.** The driver (`scripts/dev/verification_set_driver.py`)
gained the readouts the 1.6.6 plan §2.3 promised, so R1, R2, R4 and R5 below are read from the
per-roll record rather than from a log by hand: the React P0 asserts every optional field froze
nullable; the loop texture banks refused and applied patches and `plan_defect_after_zero_applied`;
the static checks bank empty POST bodies and "Found multiple elements" reports. Every fixed
parameter is read from `docs/plans/verification-sets/1-6-6-fastapi-react.yaml` and
`docs/plans/verification-sets/1-6-6-nextjs.yaml` — the pins there and in §1 are the same values,
written once; the driver refuses a counting roll when the deploy's image ids or HEAD differ.

---

## 1. Fixed parameters

| Parameter | Value |
|---|---|
| N (rolls) | **4 counted** on FastAPI+React (the measurement, §3) and **4 counted** on Next.js+TS (the regression arm, §4). See §1.3 for what N=4 can and cannot say. |
| Bar | **none** on either rate; each prediction is pass/fail on its own terms |
| Project / PRD / squad / request profile | `group_run`, `full-38`, `validated-fullstack` — identical to 1.6.5 |
| Overrides | FastAPI+React: none (`validated-fullstack`'s defaults are stack #1). Next.js+TS: `build_profile=nextjs_ts`, `dev_capability=nextjs_ts` |
| `resolved_config_hash` | FastAPI+React `c4d6a2165acf`, Next.js+TS `d4d4f66217d8` — **unchanged** from 1.6.5: the pack changed code, not configuration; a roll on any other hash is void |
| `squad_profile_snapshot_ref` | `575707c58536cf3b…` — unchanged from 1.6.5 (E's eve budget still in force); a roll on any other snapshot is void |
| Deploy — commit | `e14a6ad4` (main at the #1141 merge: A #1136, B #1137, F #1138, C #1139, D #1140, E #1141) |
| Deploy — 7 image ids | runtime-api `5d6c78df37f4` · max `0b996c984c2a` · neo `577f8271178f` · nat `c4faec0cb1c6` · bob `90e0539eb041` · eve `248da1560551` · data `37e27803b5ed` — asserted at every counting launch by the driver |
| Loaded, not built | verified in-container by the driver's `loaded_checks` before both shakeouts and recorded with the deploy identity: runtime-api carries `REPAIR_REFUSED_MARKER` / `repair_refused_in_round` (D), `supersede_evidence_artifacts` (F), `InterfaceManifest.request_body_fields` / `request_model_name` (E) and `app_invocation_for` (C); eve carries `AppInvocation` and both stacks' declarations (C). A and B are frozen-output changes read by P0 (R1) and the shakeout's stored harness. |
| Gate policy | 1.6.3 §6 constant, verbatim in each set config's `gate_notes`; `--as-agent`; both §6.1 paths satisfy zero-intervention and the decider is recorded per roll |
| Audit instrument | `scripts/dev/audit_delivered_app.py` at the frozen deploy commit |
| Driver | `verification_set_driver.py roll --set docs/plans/verification-sets/1-6-6-fastapi-react.yaml --roll N`, then `…/1-6-6-nextjs.yaml` — one roll per invocation |
| Order | FastAPI+React rolls 1–4 first (the measurement), then Next.js+TS rolls 1–4 |

### 1.3 The honest limits of N=4

Four rolls per arm is the owner's sizing, and this section says what it buys and what it
does not. **It buys the mechanism questions**: every prediction in §3 and §4 is pass/fail per
roll, and one falsification is a finding at N=1 — that is what stopped the previous sets early
and it works at any N. **It does not buy a rate**: 4 of 4 is 95% CI [51%, 100%] (Wilson); 2 of
4 is [9.5%, 90.5%]. Against the 1.6.5 FastAPI+React baseline of 2 of 6 ([9.7%, 70.0%]) no
outcome of four rolls can claim a significant change, and this document does not. Against
the Next.js 6 of 6, four greens say "nothing moved" and one red is one red — a finding to
attribute, not a rate. The verdict counts are reported with their intervals and no bar.

---

## 2. Preconditions

- **Both shakeouts on THIS deploy read, before roll 1** — `__SHAKEOUT_FASTAPI__` (FastAPI+React)
  and `__SHAKEOUT_NEXTJS__` (Next.js+TS). A shakeout is non-counting by declaration before
  launch; what it must show is that the pack is *loaded and exercised where the manifest
  gives it the chance*: on FastAPI+React the frozen `models.py` optional fields nullable (R1's
  P0 row) and no "Found multiple elements" in any report (R2); on Next.js+TS byte-identical
  behaviour to 1.6.5 (Q0/Q5/P0 as recorded there). If either shakeout falsifies one of its
  arm's predictions, the set does not open and the failure is the first finding.
- Leases 0, nothing in flight, HEAD pinned at the deploy commit, working tree clean, at
  every launch (driver preflight).
- **No merges to main while either set is open** (§7 of 1.6.3). The instrumentation PR that
  carries this document and the set configs is merged **before** roll 1; the driver pins HEAD
  at roll 1.

---

## 3. FastAPI+React (`fullstack_fastapi_react`) — the measurement, four rolls

The set the 1.6.6 pack was built for. Every prediction is one item of the pack, read only from
the evidence named, and each has a 1.6.5 roll that falsified it before the fix:

| # | prediction | falsified by | read from | 1.6.5 evidence |
|---|---|---|---|---|
| **R1** | (A #1125) no frozen entity field is emitted non-nullable with a `None` default | the driver's P0 `models_nullable_mismatches` non-empty, or one `string_type … input_value=None` on a frozen field in any per-round `test_report.md` | driver `static_checks.p0` (asserted per roll); per-round reports | rolls 1, 2, 4, 5, 6 |
| **R2** | (B #1127) no stored frontend report fails "Found multiple elements" | `static_checks.multiple_elements_reports` non-empty | driver record | roll 1 |
| **R3** | (C #1126) no suite that imports `App` or a view component is failed by `no_self_mocking_tests` | one `handler_failed` on a `qa.test` whose own report passed, with `no_self_mocking_tests` offenders naming a suite that imports `App`/`views/` | eve log + the stored suite (by hand — the one prediction the record cannot read alone) | roll 1 |
| **R4** | (D #1129) no run terminates `plan_defect` with zero applied patches | `loop_texture.plan_defect_after_zero_applied` true | driver record | rolls 5, 6 |
| **R5** | (E #1128) no POST probe on an endpoint that declares a `request:` carries `json: {}` | `static_checks.empty_body_probes` non-empty | driver record | roll 3 |
| **R6** | (F #1111) after a passing retest, the qa task's stored `test_report.md` is the passing one | a failed `test_report.md` stored under the task id later than a passing retest report for the same task | artifact vault timestamps (by hand); `loop_texture.evidence_superseded` is the positive trace | roll 1 |
| **S0–S3, Q3** | carried from 1.6.5 §4 unchanged | as there | as there | held 6/6 |

**Texture, no prediction attached:** the verdict rate against 2 of 6 (Wilson interval, no
bar, no significance claim at N=4 — §1.3); correction rounds against 3/1/2/1/2/2; **greens by
repair versus by re-dispatch**, counted separately; refused versus applied patches per roll
(new); `stores_beyond_roots`; qa primary completion tokens against 1.6.5's twelve.

**What this arm cannot read:** anything about a repair that is never attempted. A roll whose
manifest omits `default: null` never exercises A (three of nine 1.6.5-era manifests did), and a
roll with zero correction rounds exercises none of D or F. Unexercised is not passed; each
roll's record says which predictions it exercised.

**Early stop, one direction.** A falsified R1–R6 (or S0–S3/Q3) stops this set: the fix did
not work and the remaining rolls teach nothing about it. A good result is never grounds to
stop early. A stop in one set does not stop the other.

---

## 4. Next.js+TS (`nextjs_ts`) — the regression arm, four rolls

Nothing in the pack should reach this stack: A is the Python model emitter, B the React
harness, E a manifest shape no Next.js manifest has used (and its output is byte-identical
on the pinned reference), and C/D/F are loop code the 1.6.5 Next.js set never executed (zero
correction rounds). The arm exists because "should not" is the claim under test — the 1.6.5
finding F1 was exactly a check written for one stack reaching the other.

| # | prediction | falsified by | read from |
|---|---|---|---|
| **Q0** | every `qa.test` primary emission places all fill fences before any additive file | one emission with an additive file ahead of a fill | LangFuse generation output (first fill fence index < first path fence) |
| **Q5** | no `qa.test` primary emission reaches the 12,288 cap | one primary at 12,288 | eve `emission shape … completion_tokens=` |
| **P0** | the seeded frozen tree agrees with the floor | the driver's P0 `FALSIFIED` | driver `static_checks.p0` |
| **Coverage** | an accepted roll credits every criterion | `criteria_verified < criteria_total` on an accepted roll | `run_verification_summaries` |
| **C on Next.js** | a suite that imports an `app/api/` route module with `fetch` stubbed is still not flagged, and a suite that stubs `fetch` without one still is | either direction reversed on any roll that emits an additive suite | `no_self_mocking_tests` rows in `validation_result` + the stored suite |

**Texture:** correction rounds against 0/0/0/0/0/0; if any roll enters the loop, D and F are
read on it exactly as in §3 (R4, R6) and reported — as an observation on this arm, not as a
prediction it registered.

**Early stop, one direction, per set** — as §3.

---

## 5. Delegation

Executed by the assistant under the owner's standing delegation for both sets — FastAPI+React
rolls 1–4, then Next.js+TS rolls 1–4: launch, gate approval with the §6 constant, collection,
and the per-roll record; **the counted/void/reset reading and the prediction check are made at
each roll boundary before the next launch**; a reset or a falsified prediction stops that set
for the owner. No merges to main while either set is open (§7).

## 6. Gate constant

Inherited verbatim (1.6.3 §6, §6.1); the text is in each set config's `gate_notes`.

## 7. Prohibited while open

Inherited verbatim (1.6.3 §7): no merges to main, no rebuilds, no config edits, no manual
intervention on any roll; a rebuild voids every roll after it.
