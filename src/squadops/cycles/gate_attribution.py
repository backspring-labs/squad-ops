"""Who decided a gate, in a vocabulary that can tell them apart (#812).

Every API-made gate decision recorded the literal string ``decided_by="system"`` — a
hardcoded value with a ``TODO: extract from auth context`` beside it. So all 140 human
approvals in the project's history carry the same word the machine paths use as their
prefix (``system:plan_validation``, ``system:no_open_questions``). The word that means *no
human was involved* was exactly the word every human decision carried.

That matters beyond tidiness, because two consumers read this as evidence:

- **the authored-mode window** — a banked number describing "squad-authored design with
  human adjudication" means something different from one describing "…with an LLM
  adjudicating its own squad's questions", and the record has to be able to say which;
- **Cross-Cycle Memory (1.8)** — gate and revision history is its seed corpus, and a corpus
  that files agent answers under a human's name teaches the wrong thing about who resolves
  what.

**The honest limit, stated rather than glossed:** an agent acting on a human's token is
undetectable — the token says what it says. This offers a way to *declare* it and records the
declaration faithfully. An undeclared agent decision still records as the token's type. That
is a policy problem, not a mechanism problem; what changes here is that being honest becomes
possible, which it was not.
"""

from __future__ import annotations

from typing import Any

#: An identified person decided it.
ACTOR_HUMAN = "human"
#: An autonomous agent decided it, acting on some principal's credentials. Declared by the
#: caller — never inferred, because it cannot be.
ACTOR_AGENT = "agent"
#: A non-human principal (a service account) decided it.
ACTOR_SERVICE = "service"
#: The machine decided it with no principal involved: plan validation, or M4's
#: no-open-questions pass-through. Pre-existing and unchanged.
ACTOR_SYSTEM = "system"

#: What a caller may declare. ``service`` and ``system`` are not declarable — the first comes
#: from the token, the second only from code paths inside the executor.
DECLARABLE_ACTORS: frozenset[str] = frozenset({ACTOR_HUMAN, ACTOR_AGENT})

#: Recorded when there is no identity at all (auth disabled in a local deployment). Names
#: what is actually known — that something unauthenticated decided it — rather than
#: promoting it to a person.
UNATTRIBUTED = "unattributed"


def compose_decided_by(identity: Any, declared_actor: str | None = None) -> str:
    """``{actor}:{principal}`` for a gate decision, or ``unattributed``.

    ``declared_actor`` wins over the identity's own type, and is the whole point: an agent
    authenticating as a person is invisible to the token, so the only way the record can be
    true is for the caller to say so. It is validated by the caller against
    :data:`DECLARABLE_ACTORS`; anything else falls back to the identity.

    Nothing is inferred from usage patterns or timing — a guess that is usually right would
    make the field unreliable in exactly the cases anyone would want to check it.
    """
    principal = getattr(identity, "user_id", None) or getattr(identity, "display_name", None)
    if not principal:
        return UNATTRIBUTED
    actor = declared_actor if declared_actor in DECLARABLE_ACTORS else None
    if actor is None:
        actor = getattr(identity, "identity_type", None) or ACTOR_HUMAN
    return f"{actor}:{principal}"


def is_machine_decision(decided_by: str) -> bool:
    """True when no principal was involved — the executor decided it.

    Reads the prefix rather than matching whole values, so a new ``system:*`` mechanism is
    covered the day it ships. Deliberately excludes the bare legacy ``"system"``: those are
    the 140 historical rows a human actually made, and calling them machine decisions would
    launder the very confusion this module exists to end.
    """
    return decided_by.startswith(f"{ACTOR_SYSTEM}:")
