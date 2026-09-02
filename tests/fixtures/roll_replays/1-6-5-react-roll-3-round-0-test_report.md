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
backend/tests/test_runs.py:69: in test_join_and_leave_run
    leave_resp = client.delete(f"/runs/{run_id}/participants", json={"name": "Alice"})
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E   TypeError: TestClient.delete() got an unexpected keyword argument 'json'
_____________________ test_empty_participant_name_on_leave _____________________
backend/tests/test_runs.py:149: in test_empty_participant_name_on_leave
    resp = client.delete(f"/runs/{run_id}/participants", json={"name": ""})
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E   TypeError: TestClient.delete() got an unexpected keyword argument 'json'
________________________ test_leave_unknown_participant ________________________
backend/tests/test_runs.py:167: in test_leave_unknown_participant
    resp = client.delete(f"/runs/{run_id}/participants", json={"name": "Nobody"})
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E   TypeError: TestClient.delete() got an unexpected keyword argument 'json'
=========================== short test summary info ============================
FAILED backend/tests/test_runs.py::test_join_and_leave_run - TypeError: TestC...
FAILED backend/tests/test_runs.py::test_empty_participant_name_on_leave - Typ...
FAILED backend/tests/test_runs.py::test_leave_unknown_participant - TypeError...
3 failed, 5 passed in 0.05s

```


## Error

frontend (non-blocking): no test files provided
