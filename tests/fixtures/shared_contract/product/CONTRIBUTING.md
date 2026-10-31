# Contributing to Tally

- Build first: `python3 tools/build.py`. It writes `dist/`, which is never committed.
- Run each check file from the repository root, for example:
  `python3 -m unittest discover -s checks -p check_ledger.py`
- `checks/check_notify.py` needs a mail server. Set `TALLY_SMTP_HOST`; without it, the check is skipped.
- One check fails today: `test_strips_spaces_around_the_name` (issue 12). Leave it failing in unrelated
  changes, and fix it only in a change for issue 12.
- Keep each change to one concern, with a check for the behaviour it adds.
