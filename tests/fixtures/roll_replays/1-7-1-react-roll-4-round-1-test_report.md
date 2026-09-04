# Test Execution Report

**Result:** tests failed (exit code 1, 1 test file(s), 17 source file(s))

**Exit code:** 1

**Test files:** 1

**Source files:** 17


**NOT COLLECTED (these ran nothing):** `frontend/src/__tests__/runs.test.jsx`


## stdout

```
=== Frontend (vitest) ===

 RUN  v2.1.9 /tmp/qa_node_1u6fpgar/frontend

 ✓ src/__tests__/runs.test.jsx > RunListView > renders an empty state when the API returns no runs
 ✓ src/__tests__/runs.test.jsx > RunListView > renders run cards with title and participant count when data exists
 × src/__tests__/runs.test.jsx > RunCreateView > shows validation error when required fields are empty on submit
   → default.click is not a function
 × src/__tests__/runs.test.jsx > RunCreateView > submits successfully and navigates to the run detail when all required fields are filled
   → default.type is not a function
 ✓ src/__tests__/runs.test.jsx > RunDetailView > renders run details and the participant list
 × src/__tests__/runs.test.jsx > RunDetailView > shows an error message when joining with a duplicate name is rejected
   → default.type is not a function

 Test Files  1 failed (1)
      Tests  3 failed | 3 passed (6)
   Start at  05:15:35
   Duration  650ms (transform 101ms, setup 73ms, collect 97ms, tests 50ms, environment 198ms, prepare 41ms)

JSON report written to /tmp/qa_node_1u6fpgar/frontend/.vitest_report.json

```


## stderr

```
=== Frontend (vitest) ===
stderr | src/__tests__/runs.test.jsx > RunListView > renders an empty state when the API returns no runs
⚠️ React Router Future Flag Warning: React Router will begin wrapping state updates in `React.startTransition` in v7. You can use the `v7_startTransition` future flag to opt-in early. For more information, see https://reactrouter.com/v6/upgrading/future#v7_starttransition.
⚠️ React Router Future Flag Warning: Relative route resolution within Splat routes is changing in v7. You can use the `v7_relativeSplatPath` future flag to opt-in early. For more information, see https://reactrouter.com/v6/upgrading/future#v7_relativesplatpath.

⎯⎯⎯⎯⎯⎯⎯ Failed Tests 3 ⎯⎯⎯⎯⎯⎯⎯

 FAIL  src/__tests__/runs.test.jsx > RunCreateView > shows validation error when required fields are empty on submit
TypeError: default.click is not a function
 ❯ src/__tests__/runs.test.jsx:108:21
    106| 
    107|     const submitBtn = screen.getByTestId('run-create-submit')
    108|     await userEvent.click(submitBtn)
       |                     ^
    109| 
    110|     const error = screen.getByTestId('run-create-error')

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[1/3]⎯

 FAIL  src/__tests__/runs.test.jsx > RunCreateView > submits successfully and navigates to the run detail when all required fields are filled
TypeError: default.type is not a function
 ❯ src/__tests__/runs.test.jsx:124:21
    122|     )
    123| 
    124|     await userEvent.type(screen.getByTestId('run-create-title'), 'Test…
       |                     ^
    125|     await userEvent.type(screen.getByTestId('run-create-datetime'), '2…
    126|     await userEvent.type(screen.getByTestId('run-create-location'), 'P…

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[2/3]⎯

 FAIL  src/__tests__/runs.test.jsx > RunDetailView > shows an error message when joining with a duplicate name is rejected
TypeError: default.type is not a function
 ❯ src/__tests__/runs.test.jsx:182:21
    180| 
    181|     // Type the duplicate name and submit
    182|     await userEvent.type(screen.getByTestId('join-name-input'), 'Alice…
       |                     ^
    183|     await userEvent.click(screen.getByTestId('join-submit'))
    184| 

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[3/3]⎯


```


## Error

backend: no test files provided
