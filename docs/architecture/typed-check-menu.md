# Typed-Check Menu (generated — do not edit)

Generated from `CHECK_SPECS` / `DECLARED_UNBUILT_CHECKS` in
`src/squadops/cycles/acceptance_check_spec.py` (1.5 A5, #730; design:
`docs/plans/1-5-typed-check-governance-design.md`).
Regenerate: `UPDATE_CHECK_MENU=1 pytest tests/unit/cycles/test_check_governance.py`

## Evaluable checks

| check | origin | ownership | qa | signature | outcome | replayable | blocking default |
|---|---|---|---|---|---|---|---|
| `command_exit_zero` | authored | product | yes | no | yes | no | error |
| `contract_assertions_match` | injected | suite | yes | yes | yes | yes | error |
| `count_at_least` | authored | product | yes | yes | yes | yes | error |
| `endpoint_defined` | authored | product | yes | yes | yes | yes | error |
| `field_present` | authored | product | yes | yes | yes | yes | error |
| `fill_slot_signature` | injected | product | no | yes | yes | yes | error |
| `frontend_compiles` | authored | product | no | no | yes | no | error |
| `function_defined` | authored | product | yes | yes | yes | yes | error |
| `harness_boundary` | authored | suite | yes | yes | yes | yes | error |
| `import_present` | authored | product | yes | yes | yes | yes | error |
| `module_imports` | authored | product | yes | yes | yes | yes | error |
| `regex_match` | authored | product | yes | yes | yes | yes | error |
| `undefined_names` | injected | product | yes | yes | yes | yes | error |
| `unterminated_source` | injected | product | yes | yes | yes | yes | error |

`command_exit_zero` ownership is per-command in truth. The forms it may take
are inventoried below — this replaces the standing caveat that called the
surface untrustworthy pending #707's allowlist inventory.

## Authorable `command_exit_zero` forms

One list, not two (#707): a form is authorable exactly when the tool it needs is
provisioned, and `acceptance_check_spec` refuses to import if that stops being true.
Entries are measured in the agent images, never assumed.

| form | tool needed |
|---|---|
| `python -m py_compile <file>` | `python` |
| `node --check <file>` | `node` |
| `pyflakes <file>` | `pyflakes` |

### Languages no form reaches

Declared, not omitted — a list that simply fails to mention a language reads as
complete. What carries the claim instead is named, because an empty command
surface is only acceptable while something else verifies the code.

| language | why no form | verified instead by |
|---|---|---|
| TypeScript (.ts/.tsx) | no TypeScript checker is provisionable — tsc lives in the app's own node_modules/.bin and never on PATH, and `node --check` refuses both extensions before parsing (ERR_UNKNOWN_FILE_EXTENSION, node v20.19.2, measured 2026-08-10) | frontend_compiles / frontend_build — `next build` runs tsc itself and next.config.mjs declines to ignore type errors, so the bundler check IS the type check (#822 bend register entry 6) |

## Declared-unbuilt (visible, not evaluable, not authorable)

| check | why not yet | trigger |
|---|---|---|
| `package_builds` | 'the emitted container builds and runs' requires docker-in-verification (sandbox territory, SIP-0102 steps 3-7) and blueprint-owned packaging facts (Generalized Build) | Stack Blueprint lands (1.6) |
