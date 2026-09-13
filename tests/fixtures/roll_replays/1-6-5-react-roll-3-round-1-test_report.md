# Test Execution Report

**Result:** tests failed (exit code 1, 1 test file(s), 17 source file(s))

**Exit code:** 1

**Test files:** 1

**Source files:** 17


## stdout

```
=== Backend (pytest) ===
..F...FF                                                                 [100%]
=================================== FAILURES ===================================
___________________________ test_join_and_leave_run ____________________________
backend/tests/test_runs.py:89: in test_join_and_leave_run
    resp = client.delete(f"/runs/{run_id}/participants", json={"name": "Alice"})
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E   TypeError: TestClient.delete() got an unexpected keyword argument 'json'
_____________________ test_empty_participant_name_on_leave _____________________
backend/tests/test_runs.py:171: in test_empty_participant_name_on_leave
    resp = client.delete(f"/runs/{run_id}/participants", json={"name": ""})
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E   TypeError: TestClient.delete() got an unexpected keyword argument 'json'
___________________________ test_leave_unknown_name ____________________________
backend/tests/test_runs.py:186: in test_leave_unknown_name
    resp = client.delete(f"/runs/{run_id}/participants", json={"name": "Ghost"})
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E   TypeError: TestClient.delete() got an unexpected keyword argument 'json'
=========================== short test summary info ============================
FAILED backend/tests/test_runs.py::test_join_and_leave_run - TypeError: TestC...
FAILED backend/tests/test_runs.py::test_empty_participant_name_on_leave - Typ...
FAILED backend/tests/test_runs.py::test_leave_unknown_name - TypeError: TestC...
3 failed, 5 passed in 0.05s

```


## Error

frontend (non-blocking): no test files provided
