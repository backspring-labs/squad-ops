# Continuum: a `--version` option for the CLI

## Problem
An operator running `continuum` has no way to ask which version is installed. `continuum --help`
lists the commands, but nothing prints the version, so a bug report can't say what it ran.

## The change
Add a top-level `--version` option to the `continuum` command line (`src/continuum/cli.py`).
- `continuum --version` prints `continuum <version>` on standard output and exits with status 0,
  where `<version>` is `continuum.__version__` (currently `1.0.2`). It runs no command.
- Every existing command (`run`, `dev`, `inspect`) behaves exactly as before.
- Use argparse's own version action rather than parsing it by hand.

## Tests
Add a test module under `tests/` that runs the CLI's `main()` with `--version` and asserts the
exact output and the exit status 0, and that `continuum` with no arguments still prints help
and exits 1.

## Out of scope
No other command changes, no packaging changes, no dependency changes.
