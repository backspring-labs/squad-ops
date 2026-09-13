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

# sha256 of each narrative. The three legacy profiles still carry their pre-#452 inline
# literal byte-for-byte. The two stack narratives changed DELIBERATELY in #1312: each
# ended with a sentence telling the builder what the QA handoff document must contain
# ("CORS configuration notes", "the build command, the start command, and the port") —
# which is exactly what the notes' exclusion list now names as already supplied, derived
# from the environment contract itself. Leaving them would have instructed the builder to
# restate the one thing it is told not to.
_PINNED_NARRATIVE = {
    "python_cli_builder": "2d7b8b77bcf66751d99eec4baeed9ac044007b4b07dcc7d9fa36b294bee2ad2e",
    "static_web_builder": "c6582150bb6af350f93ac00e7e8ad028bad8d5935e3ce56f0cc999d84ff652eb",
    "web_app_builder": "3e11df5924d41749d00fb6b8a22e281eb4e775af206d560a70d144e6a0ec21fe",
    # changed 2026-09-08 (#1312) — handoff sentence removed
    "fullstack_fastapi_react": "c210a3bb5690d90403efcae6570d373d672e9c396eba1e18186ebb2e2119f6b0",
    # changed 2026-09-08 (#1312) — handoff sentence removed
    "nextjs_ts": "35b96ba8f6b543be4fd315710566fb060d72030b13422bfce120c5abb5d2a96e",
}

# sha256 of each COMPOSED full_system_prompt — the seam the builder handler actually
# consumes (narrative + required/optional/notes blocks), so composition changes cannot
# hide behind a stable narrative.
# EVERY composed prompt changed in #1312: `qa_handoff.md` left the required-files list on
# all five profiles, its NON-NEGOTIABLE section block and skeleton are gone, and the two
# stacks gained the notes block with the exclusion list derived from their own contracts.
# Re-pinned 2026-09-08 so the diff shows the prompt change honestly, which is what this
# gate is for.
_PINNED_COMPOSED = {
    "python_cli_builder": "f2e15c6fcf6f339097ec9c049a9b9456de25c23c30dda5afeacfee8ab5975515",
    "static_web_builder": "52204d16d144f9eb4ecff1fa50a6df685d59b367bc53d754f3d01a748e0e120a",
    "web_app_builder": "835c0d5d5d55e91ad27adb97989f3821b47019cd6597368734be6560efe8d678",
    "fullstack_fastapi_react": "bb278dd81ffd764ce82dd94d39a53698b0e8527bd14866950aba3a23142e35d1",
    # #838: nextjs_ts has NO pre-move inline literal — it was authored for stack #2,
    # after the #452 externalization. Its pin therefore establishes a baseline rather
    # than verifying a move, which is the same guarantee going forward: a change to
    # this prompt shows honestly in the diff instead of arriving as a silent edit.
    "nextjs_ts": "bcfcd88b1f88c71a064ed8301b1befa2f6af2eb072e276b57578453cccbd25bc",
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
