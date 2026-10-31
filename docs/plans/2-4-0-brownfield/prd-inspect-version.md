# Continuum: the version in `continuum inspect --json`

## Problem
`continuum inspect --json` reports the plugins, slots, commands and registry fingerprint, but not which
Continuum produced it. A saved inspection can't be matched to the version that made it, and `continuum
--version` has to be run separately.

## The change
Add a top-level `"version"` key to the JSON that `continuum inspect --json` prints
(`run_inspect` in `src/continuum/cli.py`).
- Its value is `continuum.__version__` (currently `1.0.2`).
- It is the first key of the object. Every other key and value is exactly as before.
- The human-readable output (`continuum inspect` without `--json`) is unchanged.

## Tests
Add a test module under `tests/` that runs `continuum.cli.main()` with `sys.argv` set to
`continuum inspect --json --plugins-dir <an empty temporary directory>`, parses what it prints, and
asserts that `version` equals `continuum.__version__`, that it is the first key, and that `plugins` is an
empty list and `commands` is 0.

## Out of scope
No other command changes, no packaging changes, no dependency changes.
