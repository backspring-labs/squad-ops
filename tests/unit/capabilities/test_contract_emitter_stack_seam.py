"""The contract emitter learns which stack it is emitting for (#818).

S1 consolidated the five per-stack *scaffold* facts. The contract **emitter** was out of
scope and is the larger half: `_ROUTES_PATH = "backend/routes.py"` was hardcoded and the
slot partition was one inline conditional — `_routes_criteria if path == _ROUTES_PATH else
_view_criteria`. A second stack's fill slots are `.ts`, so nothing matched and **every slot,
including the API routes file, derived view criteria**.

That is worse than a coverage gap, which is what the 1.6 plan's S4 section predicted before
anyone read this file. `endpoint_defined` — the check that proves the declared endpoints
exist — was never *emitted*, so the two guards that refuse to credit a check which cannot
run had nothing to catch: `manifest_gates` `PROOF_CHECKS_LIVE` saw no inapplicable check,
and `task_plan`'s dispatch-time strip had nothing to strip. The contract was not incomplete,
it was **wrong, and every gate accepted it**.

Bug classes guarded:

- **a second stack's routes file being checked as a frontend view** — the defect itself,
  and the reason a refusal beats a fallback;
- a stack with no criteria pack silently inheriting another stack's, which is the same
  failure S1 removed from `fill_slot_paths` arriving one layer up;
- the refusal being skipped because a *pack name* was registered that no pack answers to —
  a typo would otherwise resolve to `None` and crash somewhere less informative;
- **the capability list silently dropping a capability it was told about**, in a field whose
  stated claim is that it is derived from the criteria "so the two can't drift";
- the parameterization moving the reference contract, which every bind-mode cycle and the
  golden benchmark key on. (Byte equality itself is pinned by
  `test_contract_derivation_reference.py`; what is asserted here is that a *second* stack
  cannot perturb the first.)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from squadops.capabilities import scaffold, scaffold_contract
from squadops.capabilities.scaffold import InterfaceManifest, ScaffoldStack
from squadops.capabilities.scaffold_contract import CriteriaPack, emit_contract_dict

pytestmark = [pytest.mark.domain_capabilities]

_REFERENCE = (
    Path(__file__).resolve().parents[3] / "examples" / "03_group_run" / "interface_manifest.yaml"
).read_text(encoding="utf-8")


def _manifest(stack: str = "fullstack_fastapi_react") -> InterfaceManifest:
    return InterfaceManifest.from_yaml(_REFERENCE.replace("fullstack_fastapi_react", stack))


def _register_stack(monkeypatch: Any, *, criteria_pack: str) -> None:
    """A Node/TS-shaped second stack: one `.ts` routes slot and one `.tsx` view."""
    monkeypatch.setitem(
        scaffold._STACKS,
        "node_ts",
        ScaffoldStack(
            name="node_ts",
            expand=lambda m: [
                {"name": "src/routes.ts", "content": "// routes"},
                {"name": "src/views/RunsList.tsx", "content": "// view"},
                {"name": "package.json", "content": "{}"},
            ],
            fill_slots=lambda m: ("src/routes.ts", "src/views/RunsList.tsx"),
            check_stack="node",
            criteria_pack=criteria_pack,
        ),
    )


def _checks(contract: dict[str, Any], slot: str) -> set[str]:
    spec = contract["fill_files"][slot]
    return {c["check"] for cls in ("interface", "implementation") for c in spec.get(cls, [])}


# --------------------------------------------------------------------------- #
# The refusal
# --------------------------------------------------------------------------- #


def test_a_stack_with_no_criteria_pack_is_refused_not_given_the_first_stacks_criteria(
    monkeypatch,
):
    """The defect. Before #818 this returned a contract in which `src/routes.ts` carried a
    single `frontend_compiles` bundler check and `endpoint_defined` was absent entirely —
    and nothing objected, because nothing was inapplicable."""
    _register_stack(monkeypatch, criteria_pack="")

    with pytest.raises(ValueError, match="declares no criteria_pack"):
        emit_contract_dict(_manifest("node_ts"))


def test_a_pack_name_nothing_answers_to_is_refused_too(monkeypatch):
    """The typo case. Declaring a pack that is not registered must fail here, naming the
    known packs, rather than resolving to `None` and failing somewhere less informative."""
    _register_stack(monkeypatch, criteria_pack="node_ts_typo")

    with pytest.raises(ValueError, match="not registered"):
        emit_contract_dict(_manifest("node_ts"))


def test_the_refusal_names_what_to_do_about_it(monkeypatch):
    """A refusal that does not say where to register the pack sends the reader into the
    emitter to work it out — and the tempting local fix is a fallback, which is the bug."""
    _register_stack(monkeypatch, criteria_pack="")

    with pytest.raises(ValueError) as exc:
        emit_contract_dict(_manifest("node_ts"))

    assert "_CRITERIA_PACKS" in str(exc.value)
    assert "ScaffoldStack" in str(exc.value)


# --------------------------------------------------------------------------- #
# A second stack with its own pack
# --------------------------------------------------------------------------- #


def _register_node_pack(monkeypatch) -> None:
    monkeypatch.setitem(
        scaffold_contract._CRITERIA_PACKS,
        "node_ts",
        CriteriaPack(
            name="node_ts",
            slot_criteria=lambda m, path: (
                {
                    "interface": [
                        {
                            "check": "endpoint_defined",
                            "id": "vc-routes-endpoints",
                            "methods_paths": [f"{e.method} {e.path}" for e in m.api.endpoints],
                        }
                    ],
                    "implementation": [
                        {
                            "check": "command_exit_zero",
                            "id": "vc-routes-typechecks",
                            "argv": ["npx", "tsc", "--noEmit"],
                            "requires": "node",
                        }
                    ],
                }
                if path.endswith("routes.ts")
                else {
                    "interface": [],
                    "implementation": [
                        {"check": "frontend_compiles", "id": "vc-view", "file": path}
                    ],
                }
            ),
            build_criteria=lambda: [
                {"check": "frontend_build", "id": "vc-frontend-builds", "requires": "node"}
            ],
            suite_criteria=lambda: [
                {"check": "tests_pass", "id": "vc-suite-passes", "requires": "node"}
            ],
        ),
    )


def test_the_second_stacks_routes_file_is_not_checked_as_a_view(monkeypatch):
    """The partition belongs to the pack. Under the hardcoded `path == "backend/routes.py"`
    conditional, `src/routes.ts` took the else-branch and got the frontend bundler."""
    _register_stack(monkeypatch, criteria_pack="node_ts")
    _register_node_pack(monkeypatch)

    contract = emit_contract_dict(_manifest("node_ts"))

    assert _checks(contract, "src/routes.ts") == {"endpoint_defined", "command_exit_zero"}
    assert "frontend_compiles" not in _checks(contract, "src/routes.ts")
    assert _checks(contract, "src/views/RunsList.tsx") == {"frontend_compiles"}


def test_the_second_stack_does_not_inherit_the_first_stacks_toolchain(monkeypatch):
    """`tests_pass` used to be emitted with `requires: CAP_PYTHON` unconditionally, which
    demanded a Python capability of a stack that has none."""
    _register_stack(monkeypatch, criteria_pack="node_ts")
    _register_node_pack(monkeypatch)

    contract = emit_contract_dict(_manifest("node_ts"))

    assert contract["capabilities"] == ["node"]
    assert [c["requires"] for c in contract["behavioral"]["suite"]["checks"]] == ["node"]


def test_registering_a_second_stack_does_not_perturb_the_first(monkeypatch):
    """The reference contract is what every bind-mode cycle and the golden benchmark key
    on; a second registration must be inert for the first."""
    _register_stack(monkeypatch, criteria_pack="node_ts")
    _register_node_pack(monkeypatch)

    reference = emit_contract_dict(_manifest())

    assert reference["skeleton"]["interface_manifest_hash"].startswith("bb472e267e53d5ad")
    assert _checks(reference, "backend/routes.py") == {
        "endpoint_defined",
        "import_present",
        "command_exit_zero",
        "module_imports",
    }
    assert reference["capabilities"] == ["python", "node"]


# --------------------------------------------------------------------------- #
# The capability list
# --------------------------------------------------------------------------- #


def test_a_capability_outside_the_known_two_is_declared_not_dropped(monkeypatch):
    """`_required_capabilities` was `[c for c in (CAP_PYTHON, CAP_NODE) if c in found]` — a
    closed universe that silently discarded a third. The field's own comment claims it is
    "declared from what the criteria actually require, so the two can't drift"; for a Go or
    Rust pack it drifted, in the direction of under-declaring what the sandbox must provide."""
    _register_stack(monkeypatch, criteria_pack="go_pack")
    monkeypatch.setitem(
        scaffold_contract._CRITERIA_PACKS,
        "go_pack",
        CriteriaPack(
            name="go_pack",
            slot_criteria=lambda m, path: {
                "interface": [],
                "implementation": [
                    {"check": "command_exit_zero", "id": "vc-build", "requires": "go"}
                ],
            },
            build_criteria=lambda: [],
            suite_criteria=lambda: [{"check": "tests_pass", "id": "vc-suite", "requires": "go"}],
        ),
    )

    contract = emit_contract_dict(_manifest("node_ts"))

    assert contract["capabilities"] == ["go"]


def test_the_historical_capability_order_is_preserved(monkeypatch):
    """python-before-node is serialized into the pinned reference contract, so a sort that
    reordered them would move a hash that 1.4's banked evidence was measured against."""
    _register_stack(monkeypatch, criteria_pack="mixed")
    monkeypatch.setitem(
        scaffold_contract._CRITERIA_PACKS,
        "mixed",
        CriteriaPack(
            name="mixed",
            slot_criteria=lambda m, path: {
                "interface": [],
                "implementation": [
                    {"check": "command_exit_zero", "id": "vc-a", "requires": "node"}
                ],
            },
            build_criteria=lambda: [{"check": "frontend_build", "id": "vc-b", "requires": "rust"}],
            suite_criteria=lambda: [{"check": "tests_pass", "id": "vc-c", "requires": "python"}],
        ),
    )

    contract = emit_contract_dict(_manifest("node_ts"))

    assert contract["capabilities"] == ["python", "node", "rust"]


# --------------------------------------------------------------------------- #
# The registries cannot drift apart
# --------------------------------------------------------------------------- #


def test_every_registered_stack_declares_a_pack_that_exists():
    """Two registries means two places to forget. This is the binding that makes forgetting
    an error rather than the plausible wrong answer S1 was written to eliminate."""
    for name, stack in scaffold._STACKS.items():
        assert stack.criteria_pack, f"stack {name!r} declares no criteria_pack"
        assert stack.criteria_pack in scaffold_contract._CRITERIA_PACKS, (
            f"stack {name!r} names pack {stack.criteria_pack!r}, which is not registered"
        )


# --------------------------------------------------------------------------- #
# #849 — criterion ids must identify a slot, not a filename
# --------------------------------------------------------------------------- #


def _contract_for(stack: str):
    """The reference manifest's contract, re-stacked. One manifest, two emitters."""
    import pathlib

    import yaml

    from squadops.capabilities.scaffold import InterfaceManifest
    from squadops.cycles.verification_contract import VerificationContract

    raw = yaml.safe_load(pathlib.Path("examples/03_group_run/interface_manifest.yaml").read_text())
    raw["stack"] = stack
    manifest = InterfaceManifest.from_yaml(yaml.safe_dump(raw, sort_keys=False))
    return VerificationContract.from_dict(scaffold_contract.emit_contract_dict(manifest))


@pytest.mark.parametrize("stack", sorted(scaffold._STACKS))
def test_every_stack_emits_unique_criterion_ids(stack):
    """The defect that shipped a malformed contract into `cyc_7899ed1feae5`.

    `nextjs_ts` slugged the BASENAME, and App Router fixes the filename — every route file
    is `route.ts`, every page `page.tsx` — so four route criteria and three page criteria
    collapsed onto two ids. `criterion_index()` is keyed on id and is last-writer-wins, so
    five of seven fill slots resolved to no criterion at all while a plan binding all seven
    refs read as fully covered.

    Parameterized over the registry rather than written against one stack: the assumption
    "a filename identifies a file" is FastAPI-shaped, and the next stack gets to break it
    too. Stack #1 passes by construction (its views share one flat directory), which is
    exactly why a stack-specific test would have proved nothing.
    """
    ids = [i for i in _contract_for(stack).criterion_ids() if i]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    assert not dupes, (
        f"stack {stack!r} emits duplicate criterion id(s) {dupes} — criterion_index() is "
        f"keyed on id and last-writer-wins, so every slot but one silently loses its criteria"
    )


@pytest.mark.parametrize("stack", sorted(scaffold._STACKS))
def test_every_stack_emits_a_contract_that_passes_its_own_linter(stack):
    """The generalization of the test above, and the one that would have caught it first.

    `lint()` already checked id uniqueness; nothing outside CI and unit tests ever ran it,
    and CI runs it only against the reference FastAPI manifest, which cannot collide. This
    puts every registered stack through the linter, so a new stack's structural defects are
    a test failure rather than a live-run discovery.
    """
    assert _contract_for(stack).lint() == []


def test_next_js_ids_name_the_directory_that_distinguishes_the_slot():
    """Uniqueness alone is satisfiable by a counter (`vc-compiles-1`), which would be stable
    only until a slot is added in the middle. The id has to carry the path that makes the
    slot distinct, so a diff of two contracts stays readable and a criterion id in evidence
    still says which file it judged."""
    ids = {i for i in _contract_for("nextjs_ts").criterion_ids() if i.startswith("vc-compiles-")}
    assert "vc-compiles-app-api-runs-route" in ids
    assert "vc-compiles-app-api-runs-run-id-join-route" in ids
    assert "vc-compiles-app-api-runs-run-id-leave-route" in ids
    assert len({i for i in ids if i.endswith("-route")}) == 4
