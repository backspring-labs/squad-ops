# Test Execution Report

**Result:** tests failed (exit code 1, 1 test file(s), 17 source file(s))

**Exit code:** 1

**Test files:** 1

**Source files:** 17


## stdout

```
=== Frontend (vitest) ===

 RUN  v2.1.9 /tmp/qa_node_bi4csuk_/frontend

 ✓ src/__tests__/runs.test.jsx > RunListView > renders run titles, locations, and participant counts
 ✓ src/__tests__/runs.test.jsx > RunListView > shows empty state when no runs exist
 × src/__tests__/runs.test.jsx > RunDetailView > renders participant names and submits join with expected payload
   → expected undefined to be defined
 ✓ src/__tests__/runs.test.jsx > RunDetailView > shows not-found state when the run does not exist

 Test Files  1 failed (1)
      Tests  1 failed | 3 passed (4)
   Start at  01:09:49
   Duration  625ms (transform 62ms, setup 71ms, collect 60ms, tests 67ms, environment 203ms, prepare 37ms)

JSON report written to /tmp/qa_node_bi4csuk_/frontend/.vitest_report.json

```


## stderr

```
=== Frontend (vitest) ===
stderr | src/__tests__/runs.test.jsx > RunListView > renders run titles, locations, and participant counts
⚠️ React Router Future Flag Warning: React Router will begin wrapping state updates in `React.startTransition` in v7. You can use the `v7_startTransition` future flag to opt-in early. For more information, see https://reactrouter.com/v6/upgrading/future#v7_starttransition.
⚠️ React Router Future Flag Warning: Relative route resolution within Splat routes is changing in v7. You can use the `v7_relativeSplatPath` future flag to opt-in early. For more information, see https://reactrouter.com/v6/upgrading/future#v7_relativesplatpath.

⎯⎯⎯⎯⎯⎯⎯ Failed Tests 1 ⎯⎯⎯⎯⎯⎯⎯

 FAIL  src/__tests__/runs.test.jsx > RunDetailView > renders participant names and submits join with expected payload
AssertionError: expected undefined to be defined
 ❯ src/__tests__/runs.test.jsx:145:22
    143|       (call) => call[0] === '/runs/run-123/join' && call[1] && call[1]…
    144|     )
    145|     expect(joinCall).toBeDefined()
       |                      ^
    146|     const parsedBody = JSON.parse(joinCall[1].body)
    147|     expect(parsedBody).toEqual({ name: 'Charlie' })

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[1/1]⎯


```


## Error

backend: no test files provided
