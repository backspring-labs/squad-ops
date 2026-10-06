"""#414, the priority reserve: the run's last correction attempt is held for a required check.

What bug would these catch? The budget was one severity-blind pool drawn down in arrival order,
and completeness checks arrive first (#389: three attempts spent on two markdown headings, and the
unbuildable frontend got none). The rule's edges are where it goes wrong: refusing a round whose
failure names no check, refusing before the last attempt, or refusing where no check is required.
"""

from __future__ import annotations

import pytest

from squadops.cycles.correction_policy import last_attempt_reserved

_REQUIRED = {"required_checks": ["tests_pass", "frontend_build", "required_files"]}


@pytest.mark.parametrize(
    ("failed", "config", "attempt", "refused"),
    [
        (("acceptance:regex_match",), _REQUIRED, 2, True),
        (("acceptance:regex_match", "tests_pass"), _REQUIRED, 2, False),
        (("acceptance:regex_match",), _REQUIRED, 1, False),
        ((), _REQUIRED, 2, False),
        (("acceptance:regex_match",), {}, 2, False),
    ],
    ids=[
        "last-attempt-completeness-only",
        "last-attempt-a-required-check-fails-too",
        "an-earlier-attempt",
        "a-round-naming-no-check",
        "no-required-checks-declared",
    ],
)
def test_only_a_completeness_round_at_the_last_attempt_is_refused(failed, config, attempt, refused):
    assert last_attempt_reserved(failed, config, attempt=attempt, budget=3) is refused
