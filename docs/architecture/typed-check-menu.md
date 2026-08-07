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

Caveat — `command_exit_zero` ownership is per-command in truth and
untrustworthy until #707's allowlist inventory + precedence ruling
(recorded in the registry beside the entry).

## Declared-unbuilt (visible, not evaluable, not authorable)

| check | why not yet | trigger |
|---|---|---|
| `package_builds` | 'the emitted container builds and runs' requires docker-in-verification (sandbox territory, SIP-0102 steps 3-7) and blueprint-owned packaging facts (Generalized Build) | Stack Blueprint lands (1.6) |
