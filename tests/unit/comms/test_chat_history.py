"""The bound on a chat turn's history (#2175)."""

from __future__ import annotations

import pytest

from squadops.comms.chat_history import bound_history


def _turns(*contents: str) -> list[dict[str, str]]:
    roles = ("user", "assistant")
    return [{"role": roles[i % 2], "content": c} for i, c in enumerate(contents)]


@pytest.mark.parametrize(
    ("history", "max_turns", "max_tokens", "kept", "dropped"),
    [
        (_turns("a", "b", "c"), 10, 100, ["a", "b", "c"], 0),
        (_turns("a", "b", "c"), 2, 100, ["b", "c"], 1),
        # 8 characters is 2 estimated tokens: the newest two fit in 4, the third would not.
        (_turns("x" * 8, "y" * 8, "z" * 8), 10, 4, ["y" * 8, "z" * 8], 1),
        # The newest turn alone over the token bound: nothing is carried, and all is counted.
        (_turns("a", "z" * 40), 10, 5, [], 2),
        (_turns("a", "b"), 0, 100, [], 2),
        ([], 10, 100, [], 0),
    ],
    ids=["within", "turn-bound", "token-bound", "newest-too-long", "zero-turns", "empty"],
)
def test_the_newest_turns_that_fit_are_kept_in_order(history, max_turns, max_tokens, kept, dropped):
    """Bugs caught: the newest turns dropped instead of the oldest; the kept turns reordered; or
    the drop not counted."""
    bounded = bound_history(history, max_turns=max_turns, max_tokens=max_tokens)

    assert ([t["content"] for t in bounded.turns], bounded.dropped) == (kept, dropped)


def test_a_turn_that_is_not_conversation_is_never_replayed():
    """Bug caught: a system or tool message stored in the session replayed to the agent as a
    turn of the conversation."""
    history = [
        {"role": "system", "content": "s"},
        {"role": "user", "content": "u"},
        {"role": "tool", "content": "t"},
    ]

    bounded = bound_history(history, max_turns=10, max_tokens=100)

    assert (bounded.turns, bounded.dropped) == (({"role": "user", "content": "u"},), 0)
