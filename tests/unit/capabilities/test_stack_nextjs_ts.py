"""Stack #2 — the Next.js + TypeScript skeleton (#822, Stage 1c).

The second real stack the Stack Blueprint SIP's acceptance gate requires. What matters here is
not that it expands, but *where it disagrees with stack #1* — those disagreements are S3's
evidence, and a test suite that only proved it works would hide them.

Bug classes guarded:

- **stack #1 moving.** Its contract and manifest hashes are what every bind-mode cycle and the
  1.4 banked evidence key on; a second registration must be inert for it;
- **the API collapsing to one fill slot** (bend 1). Next derives the URL from the directory, so
  five endpoints across four paths are four files. A partition that returned one would put
  every endpoint in a file that cannot serve them;
- **path parameters surviving untranslated** (bend 2) — `{run_id}` reaching disk would create a
  literal `{run_id}` directory that Next never routes;
- **the skeleton passing its own probes.** A stub that returns success would make the
  behavioral gate measure the scaffold instead of the fill (SIP-0098 §7);
- a fill slot that is not expanded, or an expanded file claimed as a slot — the two halves
  disagreeing is how a plan claims a file that does not exist;
- **the pack demanding Python of a stack that has none**, which is what stack #1's
  `tests_pass: CAP_PYTHON` would have done before #818 gave each stack its own pack;
- the five per-stack registries drifting apart.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from squadops.capabilities import scaffold, scaffold_contract
from squadops.capabilities.dev_capabilities import DEV_CAPABILITIES, TEST_FRAMEWORK_VITEST
from squadops.capabilities.handlers import probe_runner as pr
from squadops.capabilities.scaffold import InterfaceManifest, expand, fill_slot_paths
from squadops.capabilities.scaffold_contract import emit_contract_dict, emit_contract_yaml
from squadops.sandbox.environment import get_environment_contract

pytestmark = [pytest.mark.domain_capabilities]

_STACK = "nextjs_ts"
_REFERENCE_SRC = (
    Path(__file__).resolve().parents[3] / "examples" / "03_group_run" / "interface_manifest.yaml"
).read_text(encoding="utf-8")


def _manifest(stack: str = _STACK) -> InterfaceManifest:
    return InterfaceManifest.from_yaml(_REFERENCE_SRC.replace("fullstack_fastapi_react", stack))


def _names(manifest: InterfaceManifest) -> list[str]:
    return [f["name"] for f in expand(manifest)]


# --------------------------------------------------------------------------- #
# Stack #1 is untouched
# --------------------------------------------------------------------------- #


def test_registering_a_second_stack_leaves_the_first_byte_identical():
    """The release's banked evidence is bound to these two hashes."""
    reference = _manifest("fullstack_fastapi_react")

    assert reference.content_hash().startswith("bb472e267e53d5ad")
    assert (
        hashlib.sha256(emit_contract_yaml(reference).encode())
        .hexdigest()
        .startswith("7622f570c949fe95")
    )


# --------------------------------------------------------------------------- #
# Bend 1 — the API is many fill slots
# --------------------------------------------------------------------------- #


def test_five_endpoints_across_four_paths_become_four_route_files():
    """The structural disagreement between the two stacks, and the most valuable thing this
    stack surfaces. Stack #1 holds every endpoint in one `backend/routes.py`."""
    manifest = _manifest()
    routes = [p for p in fill_slot_paths(manifest) if p.startswith("app/api/")]

    assert len(manifest.api.endpoints) == 5
    assert routes == [
        "app/api/runs/route.ts",
        "app/api/runs/[run_id]/route.ts",
        "app/api/runs/[run_id]/join/route.ts",
        "app/api/runs/[run_id]/leave/route.ts",
    ]


def test_the_two_endpoints_sharing_a_path_share_a_file():
    """`GET /runs` and `POST /runs` are one file exporting two handlers — the grouping is by
    path, which is what makes the count four rather than five."""
    content = next(
        f["content"] for f in expand(_manifest()) if f["name"] == "app/api/runs/route.ts"
    )

    assert "export async function GET(" in content
    assert "export async function POST(" in content


def test_the_contract_names_every_route_file_as_a_fill_slot():
    """A slot the contract does not cover ships unverified; a covered path that is not
    expanded is a plan claiming a file that does not exist."""
    manifest = _manifest()
    contract = emit_contract_dict(manifest)

    assert set(contract["fill_files"]) == set(fill_slot_paths(manifest))
    assert set(fill_slot_paths(manifest)) <= set(_names(manifest))


# --------------------------------------------------------------------------- #
# Bend 2 — path parameters translate
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("declared", "placed"),
    [("{run_id}", "[run_id]"), (":id", "[id]")],
)
def test_declared_path_parameters_are_placed_as_bracket_directories(declared, placed):
    """Third convention after `{run_id}` and Express's `:run_id` (#820 trigger 3). An
    untranslated parameter creates a literal directory Next never routes."""
    names = " ".join(_names(_manifest()))

    assert placed in names
    assert declared not in names


# --------------------------------------------------------------------------- #
# The skeleton must fail its own probes
# --------------------------------------------------------------------------- #


def test_every_route_stub_throws_rather_than_returning_success():
    """SIP-0098 §7: if the bare skeleton answered its probes, the behavioral gate would be
    measuring the scaffold instead of the fill."""
    stubs = [
        f["content"]
        for f in expand(_manifest())
        if f["name"].startswith("app/api/") and f["name"].endswith("route.ts")
    ]

    assert stubs
    for content in stubs:
        assert "not_implemented" in content
        assert "TODO" in content


def test_the_declared_testids_reach_the_page_stub_as_required_anchors():
    """The QA suite queries these and nothing else; a stub that omitted them would leave the
    dev agent to rediscover them from the manifest it is not given."""
    page = next(f["content"] for f in expand(_manifest()) if f["name"] == "app/create/page.tsx")

    assert "create-run-form" in page


def test_the_frozen_package_declares_the_scripts_the_contract_runs():
    """`frontend_build` shells `npm run build` and the suite runs vitest; a package.json
    missing either turns both into environment skips rather than evidence."""
    pkg = json.loads(next(f["content"] for f in expand(_manifest()) if f["name"] == "package.json"))

    assert pkg["scripts"]["build"] == "next build"
    assert pkg["scripts"]["start"] == "next start"
    assert "vitest" in pkg["devDependencies"]


# --------------------------------------------------------------------------- #
# The pack
# --------------------------------------------------------------------------- #


def test_the_pack_requires_node_and_never_python():
    """Stack #1's pack emitted `tests_pass: CAP_PYTHON` unconditionally. Before #818 gave each
    stack its own pack, that demanded a Python toolchain of a stack that has none."""
    contract = emit_contract_dict(_manifest())

    assert contract["capabilities"] == ["node"]
    assert all(
        c["requires"] == "node"
        for c in (*contract["behavioral"]["build"], *contract["behavioral"]["suite"]["checks"])
    )


def test_every_fill_slot_carries_the_build_anchored_to_itself():
    """#641/#648: the check is attached to the file under evaluation so a failure repairs
    where the defect lives. Bend 5 records what that costs — seven whole-tree builds."""
    contract = emit_contract_dict(_manifest())

    for path, spec in contract["fill_files"].items():
        checks = [c for c in spec["implementation"] if c["check"] == "frontend_compiles"]
        assert checks, f"{path} has no static check at all"
        assert checks[0]["file"] == path
        assert checks[0]["project_dir"] == ".", "Next builds at the root, not in frontend/"


def test_the_behavioral_probes_transfer_unchanged():
    """S2's HTTP-constant containment paying off: probes are manifest-derived, so both stacks
    get the same five. This is the only tier that proves the endpoints answer."""
    assert len(emit_contract_dict(_manifest())["behavioral"]["probes"]) == len(
        emit_contract_dict(_manifest("fullstack_fastapi_react"))["behavioral"]["probes"]
    )


# --------------------------------------------------------------------------- #
# Five registries, one stack
# --------------------------------------------------------------------------- #


def test_the_stack_is_answered_by_every_registry():
    """Scaffold, criteria pack, probe profile, sandbox environment, dev capability. Forgetting
    one produces a plausible wrong answer rather than an error — the S1 failure, now guarded
    across all five."""
    stack = scaffold._STACKS[_STACK]

    assert stack.criteria_pack in scaffold_contract._CRITERIA_PACKS
    assert stack.probe_profile in pr._PROFILES
    assert stack.dev_capability in DEV_CAPABILITIES
    assert get_environment_contract(_STACK).app_port == 8000
    assert DEV_CAPABILITIES[stack.dev_capability].test_framework == TEST_FRAMEWORK_VITEST


def test_the_probe_profile_builds_before_it_boots():
    """`next start` serves `.next/`, which only `next build` produces. A profile that stopped
    at install would boot into "no production build found" and report it as a boot failure —
    the conflation #827 separated."""
    profile = pr.profile_for_stack(_STACK)

    assert profile is not None
    assert "next build" in " ".join(profile.prepare_argv)
    assert "start" in profile.boot_argv


def test_the_typed_check_vocabulary_is_declared_empty_not_guessed():
    """#503's conservative default. The AST evaluators are Python implementations never
    verified against this stack, so its checks must skip rather than be fed a guess."""
    assert scaffold.check_stack_for(_STACK) is None
    assert scaffold.check_stack_for("fullstack_fastapi_react") == "fastapi"
