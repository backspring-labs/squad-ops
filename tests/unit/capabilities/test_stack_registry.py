"""Everything the scaffold knows about a stack, in one place (S1).

Five facts — the expander, the fill slots, the QA namespace, the harness boundary and the
check-stack vocabulary — were four module-level dicts and one function with the answer
written inline. Spread out, a new stack had to remember to appear in five places, and
forgetting produced a **plausible wrong answer** rather than an error.

Bug classes guarded:

- **a second stack silently inheriting the first's fill slots** — the trap this consolidation
  removes. `fill_slot_paths` guarded on whether a stack was *registered* and then returned
  `backend/routes.py` and `.jsx` view paths to whoever asked, so a Node/TS stack would have
  been handed FastAPI's answer with nothing objecting. The guard it passed asks a different
  question than the one being answered;
- a half-declared stack: registered as expandable while answering some other fact with a
  silent empty default, which reads as "this stack has no QA namespace" rather than "nobody
  filled it in";
- the refusal drifting between accessors, so an unknown stack raises in one place and returns
  `()` in another;
- the consolidation changing what the reference stack answers — this is a pure refactor, and
  the manifest and contract hashes are what every bound cycle and the golden benchmark key on.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from squadops.capabilities import scaffold
from squadops.capabilities.scaffold import (
    InterfaceManifest,
    ScaffoldStack,
    check_stack_for,
    expand,
    fill_slot_paths,
    harness_entry_modules,
    is_qa_test_path_for_stack,
    is_scaffoldable_stack,
    qa_test_namespace,
)

pytestmark = [pytest.mark.domain_capabilities]

_REFERENCE = (
    Path(__file__).resolve().parents[3] / "examples" / "03_group_run" / "interface_manifest.yaml"
).read_text(encoding="utf-8")


def _manifest(stack: str = "fullstack_fastapi_react") -> InterfaceManifest:
    return InterfaceManifest.from_yaml(_REFERENCE.replace("fullstack_fastapi_react", stack))


# --------------------------------------------------------------------------- #
# The trap
# --------------------------------------------------------------------------- #


def test_a_second_stack_does_not_inherit_the_first_stacks_fill_slots(monkeypatch):
    """The bug S1 exists to remove, reproduced against a second registered stack.

    Before this, `fill_slot_paths` checked only that the stack was *registered* and then
    returned FastAPI's slot map unconditionally — so a Node/TS stack would have been told to
    fill `backend/routes.py` and `.jsx` views, and every downstream consumer (the contract's
    covered files, frozen-ownership validation, fill-slot signature checks) would have agreed
    with it.
    """
    other = ScaffoldStack(
        name="node_ts",
        expand=lambda m: [{"name": "src/routes.ts", "content": ""}],
        fill_slots=lambda m: ("src/routes.ts",),
        qa_test_namespace=("src/__tests__/",),
        harness_entry_modules=("src/server",),
        check_stack="node",
    )
    monkeypatch.setitem(scaffold._STACKS, "node_ts", other)

    assert fill_slot_paths(_manifest("node_ts")) == ("src/routes.ts",)
    assert "backend/routes.py" not in fill_slot_paths(_manifest("node_ts"))
    # and the original is untouched
    assert "backend/routes.py" in fill_slot_paths(_manifest())


def test_every_per_stack_fact_answers_from_the_same_registration(monkeypatch):
    """One registration, five answers. Previously a stack could be registered as expandable
    and still answer `()` for its QA namespace — indistinguishable from "declared as empty"."""
    other = ScaffoldStack(
        name="node_ts",
        expand=lambda m: [],
        fill_slots=lambda m: ("src/routes.ts",),
        qa_test_namespace=("src/__tests__/",),
        harness_entry_modules=("src/server",),
        check_stack="node",
    )
    monkeypatch.setitem(scaffold._STACKS, "node_ts", other)

    assert is_scaffoldable_stack("node_ts")
    assert qa_test_namespace(_manifest("node_ts")) == ("src/__tests__/",)
    assert harness_entry_modules("node_ts") == ("src/server",)
    assert check_stack_for("node_ts") == "node"
    assert is_qa_test_path_for_stack("src/__tests__/routes.test.ts", "node_ts")
    assert not is_qa_test_path_for_stack("backend/tests/test_x.py", "node_ts")


# --------------------------------------------------------------------------- #
# The refusal is uniform
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("accessor", [expand, fill_slot_paths, qa_test_namespace])
def test_an_unregistered_stack_is_refused_identically_everywhere(accessor):
    """Divergent refusals are how a caller learns to trust one accessor and not another."""
    with pytest.raises(ValueError, match="no scaffold expander for stack"):
        accessor(_manifest("nothing_registered"))


@pytest.mark.parametrize(
    ("fn", "expected"),
    [(harness_entry_modules, ()), (check_stack_for, None)],
)
def test_the_tolerant_accessors_stay_tolerant(fn, expected):
    """These two are read where no manifest exists (bind-mode dispatch, check-stack
    resolution) and have always degraded rather than raised. #503 chose skip-on-unknown
    deliberately: feeding an evaluator a guessed stack is worse than not running it."""
    assert fn("nothing_registered") == expected


def test_an_unknown_stack_owns_no_qa_namespace():
    assert not is_qa_test_path_for_stack("backend/tests/test_x.py", "nothing_registered")


# --------------------------------------------------------------------------- #
# The refactor changed nothing
# --------------------------------------------------------------------------- #


def test_the_reference_stack_still_answers_exactly_what_it_did():
    manifest = _manifest()

    assert len(expand(manifest)) == 19
    assert fill_slot_paths(manifest) == (
        "backend/routes.py",
        "frontend/src/views/RunsListView.jsx",
        "frontend/src/views/CreateRunView.jsx",
        "frontend/src/views/RunDetailView.jsx",
    )
    assert qa_test_namespace(manifest) == ("backend/tests/", "frontend/src/tests/")
    assert harness_entry_modules("fullstack_fastapi_react") == (
        "backend.main",
        "app.main",
        "main",
    )
    assert check_stack_for("fullstack_fastapi_react") == "fastapi"


def test_the_manifest_hash_every_bound_cycle_keys_on_did_not_move():
    """S1's exact test. The contract binds this value, M0a pins it literally, and the golden
    benchmark is measured against it — a consolidation that moved it would be a silent
    re-basing of every comparison in the project."""
    assert _manifest().content_hash().startswith("bb472e267e53d5ad")


def test_the_registry_is_the_single_answer_to_which_stacks_exist():
    """The point of the consolidation. A second declaration elsewhere is how the five facts
    drifted apart in the first place.

    #822: pinned to a single stack until stack #2 registered. The invariant was never the
    *count* — it is that membership has one source — so it now asserts both known stacks are
    answered from here and that the accessor still refuses everything else."""
    assert set(scaffold._STACKS) == {"fullstack_fastapi_react", "nextjs_ts"}
    assert is_scaffoldable_stack("fullstack_fastapi_react")
    assert is_scaffoldable_stack("nextjs_ts")
    assert not is_scaffoldable_stack("")
    assert not is_scaffoldable_stack("nextjs")
