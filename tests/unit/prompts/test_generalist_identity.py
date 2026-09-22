"""The generalist role's identity layer (SIP-0108 §10i item 4, 1.8.1 plan §3.5).

Bug this catches: the fragment on disk but unregistered, or registered under the wrong path,
so ``get_system_prompt("generalist")`` falls through to the shared identity and Han is
briefed as "an AI agent operating within the framework" — a system prompt that names no
role at all, which the record could not tell from a specialist's.
"""

from __future__ import annotations

from pathlib import Path

from adapters.prompts.filesystem import FileSystemPromptRepository
from squadops.prompts.assembler import PromptAssembler

FRAGMENTS = Path(__file__).resolve().parents[3] / "src" / "squadops" / "prompts" / "fragments"


def test_the_generalist_identity_resolves_to_its_own_fragment():
    assembled = PromptAssembler(FileSystemPromptRepository(FRAGMENTS)).get_system_prompt(
        "generalist"
    )
    head = assembled.content.split("\n", 1)[0]
    assert head.startswith("You are the Generalist Agent"), head
    # The identity says what the arm removes — no lead, no analyst, no decision step — so a
    # reader of the rendered prompt sees the independent variable, not a specialist's brief.
    assert "no lead reviewing your plan" in assembled.content
    for specialist in ("QA Agent", "Developer Agent", "Lead Agent"):
        assert specialist not in assembled.content
