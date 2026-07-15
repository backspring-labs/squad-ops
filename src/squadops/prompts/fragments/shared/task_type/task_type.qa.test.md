# Task: Generate and Execute Tests (qa.test)

You are generating test files that will be executed immediately, as-is, in the
workspace they are written for. Your tests are themselves a deliverable that
can fail the build — a test suite that cannot load is a failed check, not a
neutral outcome.

## Dependency Constraint (hard rule)

Generated tests may ONLY import packages that appear in the workspace's
dependency manifests shown in the source files (`requirements.txt`,
`package.json`). Never introduce a new dependency in a test file — a suite
that fails to import fails the whole `tests_pass` check. If a test would need
an unavailable library, cover that behavior from the other side of the stack
(e.g. backend API tests) or omit it.

## Scope Discipline

- Test the deliverable that exists, against the interfaces it actually
  exposes — do not test aspirational behavior the PRD excludes.
- If the frontend dependency manifest declares no test runner, generate no
  frontend test files; the frontend build check covers compile-level
  integrity.
- Prefer fewer tests that exercise real code paths over many shallow ones.
