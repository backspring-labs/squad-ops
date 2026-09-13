# Test Execution Report

**Result:** tests failed (exit code 1, 1 test file(s), 18 source file(s))

**Exit code:** 1

**Test files:** 1

**Source files:** 18


## stdout

```
=== Backend (pytest) ===
......FF.                                                                [100%]
=================================== FAILURES ===================================
______________________ test_leave_run_removes_participant ______________________
tests/test_runs.py:136: in test_leave_run_removes_participant
    resp = client.delete(
E   TypeError: TestClient.delete() got an unexpected keyword argument 'content'
_____________________ test_leave_run_unknown_name_rejected _____________________
tests/test_runs.py:155: in test_leave_run_unknown_name_rejected
    resp = client.delete(
E   TypeError: TestClient.delete() got an unexpected keyword argument 'content'
=============================== warnings summary ===============================
../../usr/local/lib/python3.12/site-packages/fastapi/testclient.py:1
  /usr/local/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

../../usr/local/lib/python3.12/site-packages/starlette/testclient.py:53
  /usr/local/lib/python3.12/site-packages/starlette/testclient.py:53: DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.
    _PortalFactoryType = Callable[[], AbstractContextManager[anyio.abc.BlockingPortal]]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/test_runs.py::test_leave_run_removes_participant - TypeError: Te...
FAILED tests/test_runs.py::test_leave_run_unknown_name_rejected - TypeError: ...
2 failed, 7 passed, 2 warnings in 0.05s

```


## Error

frontend (non-blocking): no test files provided
