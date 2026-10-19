"""Two seams the first Next.js campaign met (the 2.4 shakeout, round 1, ``cmp_a4beedc0bbe7``): a page
criterion's test file the runner never collects (#2511), and a footprint that reads a dynamic route's
bracketed directory as a glob class (#2512). Each refused every increment that met it."""

from __future__ import annotations

import pytest

from squadops.campaigns.change_request import in_footprint
from squadops.stacks.development_profiles import (
    collected_test_patterns_for,
    matches_test_file_patterns,
)
from squadops.stacks.scaffold import criterion_test_path, hosts_campaign_increments

pytestmark = [pytest.mark.domain_orchestration]

CAMPAIGN_STACKS = [
    s for s in ("fullstack_fastapi_react", "nextjs_ts") if hosts_campaign_increments(s)
]


@pytest.mark.parametrize("stack", CAMPAIGN_STACKS)
@pytest.mark.parametrize("kind", ["endpoint", "client_route"])
def test_a_criterions_own_test_file_is_one_its_stacks_runner_collects(stack, kind):
    """#2511. Bug caught: a criterion's file named so its runner never collects it (Next.js named a
    page criterion's ``.test.tsx`` while vitest collects ``.test.ts``), so the plan check refuses
    every increment with that criterion, and were it let through the criterion would never run."""
    path = criterion_test_path(stack, "T2", kind)
    collected = collected_test_patterns_for({"build_profile": stack, "development_profile": stack})

    assert matches_test_file_patterns(path, collected), (path, collected)


def test_the_check_reads_both_campaign_stacks():
    """Bug caught: the test above parametrized over no stack after a rename, and passing."""
    assert CAMPAIGN_STACKS == ["fullstack_fastapi_react", "nextjs_ts"]


@pytest.mark.parametrize(
    ("path", "footprint", "inside"),
    [
        ("app/runs/[run_id]/page.tsx", ("app/runs/[run_id]/page.tsx",), True),
        ("app/runs/r/page.tsx", ("app/runs/[run_id]/page.tsx",), False),
        ("app/api/runs/[run_id]/join/route.ts", ("app/api/runs/[run_id]/**",), True),
        ("__tests__/criteria/T1.test.ts", ("__tests__/**",), True),
        ("lib/store.ts", ("lib/models.ts",), False),
    ],
    ids=["dynamic-route-itself", "a-letter-of-its-name", "under-a-dynamic-route", "glob", "other-file"],
)  # fmt: skip
def test_a_footprint_reads_a_dynamic_routes_brackets_literally(path, footprint, inside):
    """#2512. Bug caught: ``[run_id]`` read as a character class, so the change's own
    ``app/runs/[run_id]/page.tsx`` was 'not touched' while ``app/runs/r/page.tsx`` matched."""
    assert in_footprint(path, footprint) is inside


def test_the_scope_check_reads_brackets_literally_too():
    """#2512, the matcher beside it. Bug caught: an objective scoped to a dynamic route refusing
    the route's own files."""
    from squadops.campaigns.change_request import outside_allowed_scope

    assert outside_allowed_scope(("app/runs/[run_id]/page.tsx",), ("app/runs/[run_id]/**",)) == []
    assert outside_allowed_scope(("app/runs/r/page.tsx",), ("app/runs/[run_id]/**",)) == [
        "app/runs/r/page.tsx"
    ]
