"""The conversation history a chat turn carries to its agent (SIP-0085 §4, §7, §9; #2175).

The proxy loads a session's earlier messages and sends them with the turn. They are bounded by
count and by an estimate of their tokens, the oldest dropped first, and the drop is counted so
the request says what it left out.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

#: The keys of a chat turn's A2A message metadata, which the proxy writes and the agent reads.
HISTORY_KEY = "history"
HISTORY_DROPPED_KEY = "history_dropped"
HISTORY_UNAVAILABLE_KEY = "history_unavailable"
#: The turn's memory context (SIP-0110 Appendix A §3.5, #2180), assembled by the runtime API and
#: rendered by the agent, which owns no memory: ``squadops.memory.chat.chat_context``'s second part.
MEMORY_CONTEXT_KEY = "memory_context"

#: The roles a history turn may carry. Anything else is not conversation and is not replayed.
HISTORY_ROLES = frozenset({"user", "assistant"})

#: About four characters a token: the runtime API has no tokenizer for the agent's model, so the
#: bound is an estimate, and it errs short (a token is rarely more than four characters).
CHARS_PER_TOKEN = 4


@dataclass(frozen=True)
class BoundedHistory:
    """The turns a request carries, oldest first, and how many earlier turns it dropped."""

    turns: tuple[dict[str, str], ...]
    dropped: int


def estimated_tokens(text: str) -> int:
    return -(-len(text) // CHARS_PER_TOKEN)


def bound_history(
    history: Sequence[dict[str, str]], *, max_turns: int, max_tokens: int
) -> BoundedHistory:
    """The newest turns of ``history`` that fit both bounds, in order; the rest are dropped."""
    turns = [
        {"role": t["role"], "content": t["content"]} for t in history if t["role"] in HISTORY_ROLES
    ]
    kept: list[dict[str, str]] = []
    used = 0
    for turn in reversed(turns):
        cost = estimated_tokens(turn["content"])
        if len(kept) == max_turns or used + cost > max_tokens:
            break
        kept.append(turn)
        used += cost
    return BoundedHistory(turns=tuple(reversed(kept)), dropped=len(turns) - len(kept))


def turn_metadata(history: BoundedHistory, *, unavailable: bool) -> dict[str, object]:
    """What a chat turn's request says of its history: the turns, how many were dropped, and
    whether the history could be read at all."""
    return {
        HISTORY_KEY: [dict(t) for t in history.turns],
        HISTORY_DROPPED_KEY: history.dropped,
        HISTORY_UNAVAILABLE_KEY: unavailable,
    }
