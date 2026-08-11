"""The frozen-surface index the plan author is shown (pf-42).

The bind-mode criteria index names the four fill slots. The other thirteen files the
expander emits are frozen, and nothing put them in front of the proposer — so pf-42's
plan asserted a ``RunEvent`` field called ``meeting_location`` (the manifest declares
``location``) and an ``import_present`` for ``backend.routes`` against a module that
writes ``from .routes``. Both checks targeted files no agent may change, so neither could
pass and neither could be repaired.

These assert the index answers exactly those two questions, and that it is derived from
the expanded skeleton rather than described by hand — so it cannot drift from what the
expander emits.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from squadops.capabilities.scaffold import (
    InterfaceManifest,
    expand,
    fill_slot_paths,
    frozen_surface_index_lines,
)

pytestmark = [pytest.mark.domain_capabilities]

_MANIFEST_PATH = (
    Path(__file__).resolve().parents[3] / "examples" / "03_group_run" / "interface_manifest.yaml"
)


def _manifest() -> InterfaceManifest:
    return InterfaceManifest.from_yaml(_MANIFEST_PATH.read_text(encoding="utf-8"))


def _line_for(path: str) -> str:
    return next(line for line in frozen_surface_index_lines(_manifest()) if f"`{path}`" in line)


# --- the two questions pf-42 got wrong ----------------------------------------- #


def test_model_fields_are_named_exactly_so_none_need_inventing():
    line = _line_for("backend/models.py")

    assert "RunEvent(id, title, datetime, location, distance, pace_target, route_notes" in line
    assert "Participant(id, name)" in line
    # the invented name must be absent — that is the whole point
    assert "meeting_location" not in line


def test_own_imports_render_as_written_and_the_reachable_path_is_stated():
    """Two consumers, two facts, and the line now carries both (#787).

    pf-42's plan author writes ``import_present`` checks against what the file actually
    writes — ``from .routes`` — so the file's own imports render as written. But that
    field was the only import guidance on the line, and V2's qa suite mirrored it:
    ``from .store import reset``, twice, chain terminated as plan_defect. The reachable
    module path is now stated explicitly and the interior imports are labelled as the
    file's own, so neither consumer has to misread the other's fact."""
    line = _line_for("backend/main.py")

    assert "its own imports" in line
    assert "`.routes`" in line
    assert "import as `backend.main`" in line


def test_conftest_gets_no_import_as_line():
    """conftest.py is pytest plumbing loaded by discovery — an ``import as `conftest```
    line would teach exactly the anti-pattern its own header forbids."""
    assert "import as" not in _line_for("conftest.py")


# --- derived from the skeleton, not described by hand -------------------------- #


def test_every_frozen_file_appears_and_no_fill_slot_does():
    manifest = _manifest()
    lines = frozen_surface_index_lines(manifest)
    emitted = {f["name"] for f in expand(manifest)}
    fills = set(fill_slot_paths(manifest))

    listed = {line.split("`")[1] for line in lines}
    assert listed == emitted - fills
    # the slots the author is meant to fill are governed by the criteria index instead
    assert not (listed & fills)


def test_index_tracks_the_expander_rather_than_a_hand_written_description(monkeypatch):
    """Change what the expander emits and the index changes with it."""
    import squadops.capabilities.scaffold as sc

    monkeypatch.setattr(
        sc,
        "expand",
        lambda _m: [{"name": "backend/invented.py", "content": "class Widget:\n    size: int\n"}],
    )
    assert frozen_surface_index_lines(_manifest()) == [
        "- `backend/invented.py` — import as `backend.invented`; defines Widget(size)"
    ]


def test_noise_imports_are_dropped():
    """``__future__`` is on every emitted module and tells the author nothing."""
    assert all("__future__" not in line for line in frozen_surface_index_lines(_manifest()))


# --- edges --------------------------------------------------------------------- #


def test_no_manifest_yields_no_index():
    """Author mode and non-scaffold stacks keep today's prompt byte-identical."""
    assert frozen_surface_index_lines(None) == []


def test_javascript_frozen_files_now_carry_a_surface_too():
    """This test asserted the opposite until 2a, and the assertion was the limitation.

    It read *"the index does not parse JS — it must still name the file"*, which describes
    the renderer accurately and reads as a decision. It was not one: pf-42 built a Python
    reader and nothing was ever written for the other half of stack #1. The consequence
    stayed invisible for the same reason it always does — the checks that would trip on a
    frontend guess are bundler-level, not declaration-level.

    2a's inventory measured it: stack #1 rendered **10 of 15** frozen entries bare, all of
    `frontend/` among them, and stack #2 rendered **every** entry bare — leaving the plan
    appendix's "do not check a frozen file unless the line proves it passes" with no line to
    point at. `api.js` declaring `apiFetch` is exactly the name pf-42 exists to stop an
    author inventing.
    """
    assert _line_for("frontend/vite.config.js") == (
        "- `frontend/vite.config.js` — its own imports `@vitejs/plugin-react`, `vite`"
    )
    assert "functions apiFetch" in _line_for("frontend/src/api.js")


def test_a_file_in_a_language_the_index_cannot_read_is_still_named():
    """The half of the old test that was always right, kept.

    Being unable to describe a file is never a reason to omit it — an author that cannot see
    the file at all will assume the slot is theirs to write. `index.html` has no declarations
    to give and must still appear.
    """
    assert _line_for("frontend/index.html") == "- `frontend/index.html`"


def test_package_json_declares_its_dependency_surface():
    """This test previously asserted the bare form and CALLED it a decision —
    "`package.json` [has] no declarations to give" — and roll 9 falsified it: the
    dependency list is the closed set of packages a suite may import, the qa author was
    never shown it, and the emitted suite opened with `import request from 'supertest'`.
    A dependency name the author cannot see is a dependency it will invent."""
    line = _line_for("frontend/package.json")

    assert "dependencies" in line
    assert line != "- `frontend/package.json`"
    # names, not versions — the index must not churn on template version bumps
    assert "^" not in line and "~" not in line


def test_unparseable_python_degrades_to_a_bare_path(monkeypatch):
    import squadops.capabilities.scaffold as sc

    monkeypatch.setattr(
        sc, "expand", lambda _m: [{"name": "backend/broken.py", "content": "def (:\n"}]
    )
    assert frozen_surface_index_lines(_manifest()) == ["- `backend/broken.py`"]


def test_module_state_is_named_so_a_data_module_does_not_read_as_a_stub():
    """pf-43: store.py is two annotated dicts plus reset(). An index listing only
    functions read as an empty stub, so the plan author wrote a task to build the store
    it already had — five typed checks against a file no agent may change."""
    line = _line_for("backend/store.py")

    assert "participant_store: dict[str, Participant]" in line
    assert "run_event_store: dict[str, RunEvent]" in line
    # the function is still named; state does not displace it
    assert "reset" in line


def test_private_module_state_is_omitted():
    import squadops.capabilities.scaffold as sc

    src = "public: int = 1\n_private: int = 2\n"
    assert sc._python_surface(src) == "module state public: int"
