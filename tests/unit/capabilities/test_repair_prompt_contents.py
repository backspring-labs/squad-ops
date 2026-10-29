"""What a correction repair's prompt shows of its tree, rendered and counted by one function (#2810).

The repair handlers render the current files, the edit form and a qa repair's failing-case frames
through ``repair_prompt_contents``, and the composer counts a repair's tree
(``acceptance_workspace_files`` with ``failed_task_artifacts`` over it) through it
(``prompt_budget.rendered_input_tokens``), where ``REPAIR_CONTEXT_CONTRACT`` names the rendering.
The handlers' prompts are pinned byte for byte in
``tests/unit/capabilities/handlers/test_repair_prompt_characterization.py``.

What bugs would these catch?
- **The composer counting the whole tree** where the repair shows its named files, so a repair on
  a product larger than half its window is held on an instruction that fits (#2810).
- **The composer counting less than the prompt shows:** the edit form lists each file's entities
  beside the file, which on a small file is longer than the file; the failing frames are a third
  showing. Counted as the file alone, a binding is admitted that the guard then refuses.
- **The base read wrong:** the failed task's own file not laid over the workspace's, a scaffold
  shell or an unsafe path offered, or a file the repair creates shown as if it existed.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from squadops.capabilities.prompt_budget import rendered_input_tokens
from squadops.capabilities.repair_prompt_contents import (
    REPAIR_BASE_INPUTS,
    anchorable_files,
    repair_prompt_contents,
)
from squadops.memory.lessons import _tokens

pytestmark = [pytest.mark.domain_capabilities]

_ROUTES = "def list_moons():\n    return []\n\n\ndef moon_period(name):\n    return 0\n"
_SUITE = "".join(f"def test_moon_{i}():\n    assert moon_period('io') == {i}\n\n\n" for i in (1, 2))
_EVIDENCE = {
    "validation_result": {
        "checks": [
            {
                "check": "tests_pass",
                "failing_cases": [
                    {"file": "tests/test_orbit.py", "title": "test_moon_2", "failing_line": 6}
                ],
            }
        ]
    }
}


def _inputs(**extra) -> dict:
    return {
        "prd": "Orbit lists each moon and its period.",
        "expected_artifacts": ["orbit/routes.py", "tests/test_orbit.py", "orbit/new.py"],
        "acceptance_workspace_files": {"orbit/routes.py": _ROUTES, "orbit/store.py": "ROWS = []\n"},
        "failed_task_artifacts": [{"name": "tests/test_orbit.py", "content": _SUITE}],
        "failure_evidence": _EVIDENCE,
        **extra,
    }


def test_the_prompt_shows_the_named_files_their_edit_form_and_the_failing_frame():
    """The three sections, exactly as the handler renders them: the named files that exist in the
    base (the workspace's, and the failed task's own over it), never the file it creates nor one it
    doesn't name. Bug caught: the base read without the overlay, or a named new file shown."""
    shown = repair_prompt_contents(_inputs())

    assert shown == {
        "current_files": (
            "`orbit/routes.py`:\n```\n" + _ROUTES + "```\n\n"
            "`tests/test_orbit.py`:\n```\n" + _SUITE + "```"
        ),
        "editable_files": (
            "- `orbit/routes.py` — entities: `function:list_moons`, `function:list_moons#body`, "
            "`function:moon_period`, `function:moon_period#body`\n"
            "- `tests/test_orbit.py` — entities: `function:test_moon_1`, "
            "`function:test_moon_1#body`, `function:test_moon_2`, `function:test_moon_2#body`"
        ),
        "case_frames": (
            "`tests/test_orbit.py:6` › test_moon_2\n```\n"
            "     1 | def test_moon_1():\n"
            "     2 |     assert moon_period('io') == 1\n"
            "     3 | \n     4 | \n"
            "     5 | def test_moon_2():\n"
            "→    6 |     assert moon_period('io') == 2\n"
            "     7 | \n     8 | \n```"
        ),
    }


@pytest.mark.parametrize(
    ("extra", "anchorable"),
    [
        ({}, ["orbit/routes.py", "tests/test_orbit.py"]),
        # The failed task's own copy wins over the workspace's.
        (
            {"failed_task_artifacts": [{"name": "orbit/routes.py", "content": "X = 1\n"}]},
            ["orbit/routes.py"],
        ),
        # A scaffold shell is filled by slot, never anchored (§9.3).
        (
            {"verification_scaffold": {"files": [{"name": "tests/test_orbit.py"}]}},
            ["orbit/routes.py"],
        ),
        # A path leaving the workspace, an empty one, and a malformed failed artifact.
        (
            {
                "expected_artifacts": ["../orbit/routes.py", "", "./orbit/routes.py"],
                "failed_task_artifacts": [{"content": "no name"}, "not a dict"],
            },
            ["orbit/routes.py"],
        ),
        ({"acceptance_workspace_files": None, "failed_task_artifacts": None}, []),
    ],
    ids=["overlay", "own-copy-wins", "shell", "unsafe-and-malformed", "no-tree"],
)
def test_the_files_offered_are_the_named_ones_in_the_base(extra, anchorable):
    """Edges of the base and the named files, read as the handler reads them. Bug caught: an
    unsafe path or a shell offered for editing, the overlay applied the wrong way round, or a
    missing tree read as an error rather than nothing to show."""
    assert anchorable_files(_inputs(**extra)) == anchorable


def test_the_failed_tasks_own_copy_is_what_the_repair_is_shown():
    """The verifier lays the failed task's files over the workspace (#1264), and the repair edits
    that tree. Bug caught: the workspace's older copy shown, so every anchor copied from it misses."""
    inputs = _inputs(
        expected_artifacts=["orbit/routes.py"],
        failed_task_artifacts=[{"name": "orbit/routes.py", "content": "X = 1\n"}],
    )

    assert repair_prompt_contents(inputs)["current_files"] == "`orbit/routes.py`:\n```\nX = 1\n```"


def _rest(envelope) -> int:
    return rendered_input_tokens(
        SimpleNamespace(
            task_type=envelope.task_type,
            inputs={k: v for k, v in envelope.inputs.items() if k not in REPAIR_BASE_INPUTS},
        )
    )


@pytest.mark.parametrize("task_type", ["development.correction_repair", "qa.test_repair"])
def test_the_composer_counts_a_repairs_tree_as_its_prompt_shows_it(task_type):
    """Entered at ``rendered_input_tokens``, the count ``prompt_budget`` takes. A tree of forty
    modules beside the two named files is counted as what the prompt shows: the named files, their
    edit form and the frame. Bug caught: the whole tree counted (#2810), or the tree and the failed
    task's files each counted again beside the rendering."""
    big = {
        f"orbit/module_{i:02d}.py": "def track(moon):\n    return moon\n" * 60 for i in range(40)
    }
    inputs = _inputs(acceptance_workspace_files={**_inputs()["acceptance_workspace_files"], **big})
    envelope = SimpleNamespace(task_type=task_type, inputs=inputs)
    shown = repair_prompt_contents(inputs)

    assert rendered_input_tokens(envelope) == _rest(envelope) + _tokens(
        json.dumps(shown, sort_keys=True)
    )
    assert _tokens(json.dumps(inputs["acceptance_workspace_files"])) > 10 * _tokens(
        json.dumps(shown)
    )


def test_a_repair_with_no_tree_counts_nothing_for_it():
    """Edge: a repair of a task that carried no workspace (a framing task's) and wrote nothing.
    Bug caught: three empty sections counted for a tree that isn't there, or a crash on the absent
    keys."""
    inputs = {k: v for k, v in _inputs().items() if k not in REPAIR_BASE_INPUTS}
    envelope = SimpleNamespace(task_type="development.correction_repair", inputs=inputs)

    assert repair_prompt_contents(inputs) == {
        "current_files": "",
        "editable_files": "",
        "case_frames": "",
    }
    assert rendered_input_tokens(envelope) == _rest(envelope)


def test_a_task_that_shows_its_inputs_whole_counts_them_whole():
    """The rendering is the repair contract's alone. Bug caught: the repair's scoping reaching a
    task whose prompt shows a workspace-named input whole, under-counting it."""
    inputs = _inputs()
    envelope = SimpleNamespace(task_type="strategy.propose_increment", inputs=inputs)

    assert rendered_input_tokens(envelope) == sum(
        _tokens(v if isinstance(v, str) else json.dumps(v, sort_keys=True)) for v in inputs.values()
    )
