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


def test_imports_render_as_written_so_relative_is_visible():
    """pf-42 asserted ``backend.routes``; the file says ``from .routes``."""
    line = _line_for("backend/main.py")

    assert "`.routes`" in line
    assert "`backend.routes`" not in line


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
        "- `backend/invented.py` — defines Widget(size)"
    ]


def test_noise_imports_are_dropped():
    """``__future__`` is on every emitted module and tells the author nothing."""
    assert all("__future__" not in line for line in frozen_surface_index_lines(_manifest()))


# --- edges --------------------------------------------------------------------- #


def test_no_manifest_yields_no_index():
    """Author mode and non-scaffold stacks keep today's prompt byte-identical."""
    assert frozen_surface_index_lines(None) == []


def test_non_python_frozen_files_are_listed_without_a_surface():
    # vite.config.js is frozen and load-bearing (it strips the /api prefix), but the
    # index does not parse JS — it must still name the file rather than omit it.
    assert _line_for("frontend/vite.config.js") == "- `frontend/vite.config.js`"


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
