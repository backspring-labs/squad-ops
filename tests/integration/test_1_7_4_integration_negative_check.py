"""The 1.7.4 plan §3.1 controlled negative check.

This test exists to fail. Its PR is a draft that must show as blocked from merging once
`integration` is a required status check on main; the PR is then closed unmerged. The
test never lands.
"""


def test_integration_is_a_required_check() -> None:
    raise AssertionError(
        "1.7.4 plan §3.1: controlled negative check — a red integration job must block the merge"
    )
