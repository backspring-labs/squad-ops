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

    assert (
        outside_allowed_scope(
            ("app/runs/[run_id]/page.tsx",), ("app/runs/[run_id]/**",), stack="nextjs_ts"
        )
        == []
    )
    assert outside_allowed_scope(
        ("app/runs/r/page.tsx",), ("app/runs/[run_id]/**",), stack="nextjs_ts"
    ) == ["app/runs/r/page.tsx"]


_NEXTJS_MANIFEST = """\
version: 1
kind: interface_manifest
project_id: group_run
source_prd: group_run
stack: {stack}
scope: runs
entities:
  - name: Run
    fields:
      - {{ name: id, type: string, required: true, generated: true }}
      - {{ name: title, type: string, required: true }}
      - {{ name: participants, type: "list[string]", required: true, default: [] }}
api:
  base_path: ""
  request_shapes:
    RunCreate:
      required: [title]
      optional: [{optional}]
    JoinInput:
      required: [name]
  endpoints:
    - {{ method: POST, path: /api/runs, request: RunCreate, response: Run, success_status: 201, errors: [validation_error] }}
    - {{ method: GET, path: "/api/runs/{{run_id}}", response: Run, errors: [run_not_found] }}
    - {{ method: POST, path: "/api/runs/{{run_id}}/join", request: JoinInput, response: Run, errors: [{join_errors}] }}
  error_contract:
    shape: '{{"error": {{"code": "...", "message": "..."}}}}'
    codes:
      validation_error: {{ http: 400 }}
      run_not_found: {{ http: 404 }}
{extra_codes}
frontend:
  framework: {framework}
  routes:
    - {{ path: "/runs/{{run_id}}", view: RunDetailView, purpose: detail, testids: [run-detail-view] }}
persistence: in_memory
"""


def _manifest(stack: str, *, capacity: bool) -> str:
    return _NEXTJS_MANIFEST.format(
        stack=stack,
        framework="nextjs_app_router" if stack == "nextjs_ts" else "react_vite",
        optional="capacity" if capacity else "",
        join_errors="validation_error, run_not_found, capacity_reached"
        if capacity
        else "validation_error, run_not_found",
        extra_codes="      capacity_reached: { http: 409 }" if capacity else "",
    )


def test_a_change_to_an_endpoints_request_or_errors_puts_its_route_file_in_the_footprint():
    """Next.js shakeout round 2 (cyc_0df8d7215ef2). Bug caught: a capacity increment, which adds a
    field to ``RunCreate`` and ``capacity_reached`` to the join endpoint's errors, derived a
    footprint without ``app/api/runs/route.ts`` and ``app/api/runs/[run_id]/join/route.ts``. A
    Next.js route file is one endpoint's, and its skeleton named neither, so it was unchanged;
    every dev and repair edit to it was then dropped as another producer's slot."""
    from squadops.campaigns.change_request import derive_footprint, footprint_product_files

    footprint = footprint_product_files(
        derive_footprint(
            _manifest("nextjs_ts", capacity=False), _manifest("nextjs_ts", capacity=True)
        )
    )

    assert "app/api/runs/route.ts" in footprint
    assert "app/api/runs/[run_id]/join/route.ts" in footprint
    assert "app/api/runs/[run_id]/route.ts" not in footprint  # unchanged: GET, no new error


def test_a_field_added_to_an_entity_puts_every_route_that_returns_it_in_the_footprint():
    """Next.js shakeout round 5 (``cyc_311e2117c21d``). Bug caught: a capacity increment that adds
    ``capacity`` to ``Run`` left the detail route, which returns a ``Run`` and listed its fields,
    outside the footprint. No repair could add the field there, so the page's capacity criterion
    could never pass, though the page itself rendered it."""
    from squadops.campaigns.change_request import derive_footprint, footprint_product_files

    participants = (
        '      - { name: participants, type: "list[string]", required: true, default: [] }'
    )
    base = _manifest("nextjs_ts", capacity=False)
    with_field = base.replace(
        participants, participants + "\n      - { name: capacity, type: number, required: false }"
    )
    assert with_field != base

    footprint = footprint_product_files(derive_footprint(base, with_field))

    assert {
        "app/api/runs/route.ts",
        "app/api/runs/[run_id]/route.ts",
        "app/api/runs/[run_id]/join/route.ts",
    } <= set(footprint)


def test_fastapis_footprint_for_the_same_delta_is_unchanged_by_the_route_contract():
    """Bug caught: the Next.js fix reaching FastAPI's scaffold, whose one routes.py already changed
    with any endpoint."""
    from squadops.campaigns.change_request import derive_footprint, footprint_product_files

    footprint = footprint_product_files(
        derive_footprint(
            _manifest("fullstack_fastapi_react", capacity=False),
            _manifest("fullstack_fastapi_react", capacity=True),
        )
    )

    assert "backend/routes.py" in footprint


def _expanded_nextjs():
    from squadops.stacks.scaffold import expand
    from tests.unit.capabilities._stack_fixtures import manifest_for_stack

    return {f["name"]: f["content"] for f in expand(manifest_for_stack("nextjs_ts"))}


def test_every_page_suite_the_runner_collects_runs_in_a_dom_with_testing_library():
    """#2534, the 2.4 shakeout's round 3 (``run_a5756a5606ef``). Bug caught: a page suite
    collected but run in node with no DOM, so a page that loads its data in the browser shows only
    its loading state and its criterion can never pass; or the DOM named in the config with its
    packages, its setup file or its proof missing from the tree, so every page suite fails to load."""
    import json
    import re

    from squadops.stacks.development_profiles import (
        matches_test_file_patterns,
        test_file_patterns_from_glob,
    )

    tree = _expanded_nextjs()
    config = tree["vitest.config.ts"]
    (jsdom_glob,) = re.findall(r"environmentMatchGlobs: \[\['([^']+)', 'jsdom'\]\]", config)
    (setup,) = re.findall(r"setupFiles: \['([^']+)'\]", config)
    dom = test_file_patterns_from_glob(jsdom_glob)
    dev = json.loads(tree["package.json"])["devDependencies"]

    from squadops.stacks.scaffold import test_config_files_for_stack

    for page_suite in (
        criterion_test_path("nextjs_ts", "T3", "client_route"),
        "__tests__/run-detail.test.tsx",
        "__tests__/harness-dom.test.tsx",
    ):
        assert matches_test_file_patterns(page_suite, dom), page_suite
    assert not matches_test_file_patterns("__tests__/runs-api.test.ts", dom)
    # Each package a page suite imports is declared, and pinned as the stack pins all of them.
    needed = (
        "jsdom",
        "@testing-library/react",
        "@testing-library/dom",
        "@testing-library/jest-dom",
    )
    assert all(dev.get(p, "")[:1].isdigit() for p in needed), {p: dev.get(p) for p in needed}
    # The setup file the config names is in the tree, and is one of the test-config files a
    # frozen evaluation tree carries, or vitest fails to start there.
    assert setup in tree and setup in test_config_files_for_stack("nextjs_ts")
    assert "__tests__/harness-dom.test.tsx" in tree
