# Test Execution Report

**Result:** tests failed (exit code 1, 2 test file(s), 17 source file(s))

**Exit code:** 1

**Test files:** 2

**Source files:** 17


## stdout

```
=== Backend (pytest) ===
......F....                                                              [100%]
=================================== FAILURES ===================================
_______________________ test_join_run_duplicate_rejected _______________________
tests/test_runs.py:165: in test_join_run_duplicate_rejected
    assert resp.status_code == 409
E   assert 200 == 409
E    +  where 200 = <Response [200 OK]>.status_code
=========================== short test summary info ============================
FAILED tests/test_runs.py::test_join_run_duplicate_rejected - assert 200 == 409
1 failed, 10 passed in 0.05s

```


## Error

frontend (non-blocking): no test files provided
