# One file per issue

A new loaded check goes in a file here, named for its issue: `3268.yaml`, holding the same
top-level `checks:` list as `../loaded_checks.yaml`. Every reader takes that file and these as one
set (`../loaded_check_rows.py`), and an id may appear once across all of them.

Rows are no longer appended to `loaded_checks.yaml`. While they were, any two open pull requests
conflicted at its last line, and each merge put every other one in conflict (#3268).

A YAML anchor reaches only its own file, so rows that share one stay in one file.
