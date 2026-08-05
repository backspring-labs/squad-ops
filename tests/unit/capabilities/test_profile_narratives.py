"""#452 hard acceptance gate — profile narratives externalized BYTE-IDENTICALLY.

The pinned hashes below were computed on main (2026-08-06) from the inline
``system_prompt_template`` literals BEFORE the move to
``src/squadops/prompts/profile_narratives/``. Per the 1.5 plan's rule for
#452, this refactor is only safe byte-identical: any drift between the
externalized files and these hashes is a behavioral change to agent prompts
dressed as a refactor, and this test is what makes that visible.

If a narrative is ever changed DELIBERATELY, update its hashes here in the
same PR — the diff then honestly shows "prompt content changed", which is
the entire point.
"""

from __future__ import annotations

import hashlib

import pytest

from squadops.capabilities.handlers.build_profiles import (
    BUILD_PROFILES,
    _narrative,
)

pytestmark = [pytest.mark.domain_capabilities]

# sha256 of each pre-move inline literal (narrative alone).
_PINNED_NARRATIVE = {
    "python_cli_builder": "2d7b8b77bcf66751d99eec4baeed9ac044007b4b07dcc7d9fa36b294bee2ad2e",
    "static_web_builder": "c6582150bb6af350f93ac00e7e8ad028bad8d5935e3ce56f0cc999d84ff652eb",
    "web_app_builder": "3e11df5924d41749d00fb6b8a22e281eb4e775af206d560a70d144e6a0ec21fe",
    "fullstack_fastapi_react": "2250e64354f268bdc605e05137a3d61bd7de7e9116c5c1b648a5f8a6444b4639",
}

# sha256 of each pre-move COMPOSED full_system_prompt — the seam the builder
# handler actually consumes (narrative + required/optional/qa_handoff blocks),
# so composition changes cannot hide behind a stable narrative.
_PINNED_COMPOSED = {
    "python_cli_builder": "321140533889cb25f8ce0817de680ffce5c2f38412c7464f28c5162ffd0b6cc6",
    "static_web_builder": "10d0efbc5c8c158529b37e5d1da66a49e9fe3a55de9ed75109f471ed55ec3a1f",
    "web_app_builder": "b242252619ccc82c6fc081b6d657a41903174274ca387e576e9171cb878a6e1b",
    "fullstack_fastapi_react": "748c4e740fafe63f39cc94eec91d1e842050dcf5d1e070919e6f0680402b1957",
}


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


@pytest.mark.parametrize("profile_name", sorted(BUILD_PROFILES))
def test_narrative_bytes_match_pre_move_literal(profile_name):
    assert (
        _sha(BUILD_PROFILES[profile_name].system_prompt_template)
        == (_PINNED_NARRATIVE[profile_name])
    ), f"{profile_name} narrative drifted from the pre-#452 inline literal"


@pytest.mark.parametrize("profile_name", sorted(BUILD_PROFILES))
def test_composed_system_prompt_bytes_unchanged(profile_name):
    assert (
        _sha(BUILD_PROFILES[profile_name].full_system_prompt) == (_PINNED_COMPOSED[profile_name])
    ), f"{profile_name} composed system prompt drifted from the pre-#452 bytes"


def test_every_profile_is_pinned():
    # a new profile must join the byte-equivalence regime, not slip past it
    assert set(BUILD_PROFILES) == set(_PINNED_NARRATIVE) == set(_PINNED_COMPOSED)


def test_loader_strips_exactly_one_trailing_newline(tmp_path, monkeypatch):
    # D3: files are stored with one trailing newline; an editor auto-adding
    # it must not change rendered prompt bytes — and real trailing content
    # (a second newline) is preserved, never blanket-stripped
    import squadops.capabilities.handlers.build_profiles as bp

    monkeypatch.setattr(bp, "_NARRATIVES_DIR", tmp_path)
    (tmp_path / "one.md").write_text("narrative text\n")
    (tmp_path / "two.md").write_text("narrative text\n\n")
    assert bp._narrative("one") == "narrative text"
    assert bp._narrative("two") == "narrative text\n"


def test_missing_narrative_raises_loudly():
    with pytest.raises(FileNotFoundError):
        _narrative("no_such_profile")
