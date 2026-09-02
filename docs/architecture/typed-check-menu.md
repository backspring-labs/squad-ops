# Typed-Check Menu (generated — do not edit)

Generated from `CHECK_SPECS` / `DECLARED_UNBUILT_CHECKS` in
`src/squadops/cycles/acceptance_check_spec.py` (1.5 A5, #730; design:
`docs/plans/1-5-typed-check-governance-design.md`).
Regenerate: `UPDATE_CHECK_MENU=1 pytest tests/unit/cycles/test_check_governance.py`

## Evaluable checks

| check | origin | ownership | qa | signature | outcome | replayable | blocking default |
|---|---|---|---|---|---|---|---|
| `assertion_kinds_match` | injected | suite | yes | yes | yes | yes | error |
| `command_exit_zero` | authored | product | yes | no | yes | no | error |
| `container_packaging` | injected | product | no | no | no | yes | warning |
| `contract_assertions_match` | injected | suite | yes | yes | yes | yes | error |
| `count_at_least` | authored | product | yes | yes | yes | yes | error |
| `declared_imports` | injected | product | yes | yes | yes | yes | error |
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

## Declared coverage gaps

Framework-injected checks that do not cover a language the framework emits,
with the reason (#1216). A gap here is disclosure, not suppression: an emission
in that language is checked less than an identical one elsewhere, and this is
where a reader finds out. An undeclared gap fails
`test_every_coverage_gap_is_declared`.

| check | language | reason |
|---|---|---|
| `declared_imports` | `.py` | Python declares dependencies in requirements files, not a manifest beside the source, and resolution is environment-wide rather than per-directory. The equivalent check is a different check, not this one with another extension — no Python emission is silently less checked as a result, since undefined_names and the syntax gate both cover .py. |

## Tooling each check needs, and where it is declared absent

A typed check executes in the producing role's agent container (#1229, rule B),
so a role whose handlers evaluate typed checks provisions each tool below as data
(`agents/instances/<role>/system-packages.txt`, `npm-global-packages.txt`) or
declares the gap with its reason. Both sides are held by
`test_typed_check_tooling_is_provisioned_where_checks_run`. A check whose tool is
absent where it runs skips as `missing_tooling` and says so; it never fails the
emission, and it never reads as a pass.

| check | tools |
|---|---|
| `frontend_compiles` | `npm` |
| `undefined_names` | `tsc` |

| role | tool | why absent |
|---|---|---|
| `builder` | `npm` | The builder assembles packaging (Dockerfile, nginx, requirements) and emits no frontend source, so frontend_compiles never applies to its artifacts; its image declares no Node.js. Verified absent 2026-09-01 after the rebuild. The day an assemble emits a .js/.ts file this entry must go and the role must provision it. |
| `builder` | `tsc` | Same as npm: no frontend emission from the builder, so undefined_names' tsc half never runs there. Declared rather than provisioned so the image stays what the role needs. |

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
| TypeScript (.ts/.tsx) | the command safelist carries no TypeScript checker. `tsc` is provisioned globally in the dev and qa images since #939 (npm-global-packages.txt) for the undefined_names check, but a safelist entry is a separate decision: runtime-api has no node, so an authored `tsc` criterion would be #707's passes-the-allowlist-but-cannot-run class there until #1229. `node --check` refuses both extensions before parsing (ERR_UNKNOWN_FILE_EXTENSION, node v20.19.2, measured 2026-08-10) | frontend_compiles / frontend_build — `next build` runs tsc itself and next.config.mjs declines to ignore type errors, so the bundler check IS the type check (#822 bend register entry 6) |

## Declared-unbuilt (visible, not evaluable, not authorable)

| check | why not yet | trigger |
|---|---|---|
| `package_builds` | 'the emitted container builds and runs' requires docker-in-verification (sandbox territory, SIP-0102 steps 3-7) and blueprint-owned packaging facts (Generalized Build). The static half — pf-38's three recipe defects as findings — is `container_packaging`, reporting-only (#598, 1.7.1) | Stack Blueprint lands (1.6) |
