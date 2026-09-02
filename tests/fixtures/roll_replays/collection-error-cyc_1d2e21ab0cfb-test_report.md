# Test Execution Report

**Result:** tests failed (exit code 2, 3 test file(s), 6 source file(s))

**Exit code:** 2

**Test files:** 3

**Source files:** 6


## stdout

```
=== Backend (pytest) ===

==================================== ERRORS ====================================
__________________ ERROR collecting backend/tests/test_api.py __________________
ImportError while importing test module '/tmp/qa_run_y2elwhe0/backend/tests/test_api.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/usr/local/lib/python3.11/importlib/__init__.py:126: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
backend/tests/test_api.py:3: in <module>
    from main import app
E   ModuleNotFoundError: No module named 'main'
=========================== short test summary info ============================
ERROR backend/tests/test_api.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.07s

```


## Error

frontend (non-blocking): No package.json found in frontend
