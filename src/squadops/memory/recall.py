"""Cross-cycle failure recall, the domain half (SIP-Cross-Cycle-Memory §5; #1964).

Phase 1's question is narrow: *has this project failed this way before, at this authoring step?*
A recalled pattern is a validated behavioural statement, template-encoded from a validator's
rejection class (§5: no LLM in the encode path, and the memory system invents no pattern). It
reaches a plan-authoring task through the ``plan_rejection_context`` contract, the same one that
threads a framing re-roll's own rejection (#669), never through a handler branch.

2.1 ships the rails inert (the owner's ruling of 2026-09-12, the 1.8.0 plan §8 decision 2): the
port and the call site exist, the composition root injects a recall that answers empty, and so
no prompt, verdict or gate changes. 2.2 swaps in the adapter.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RecallQuery:
    """What an authoring task asks before it authors (SIP-0110 §0.8): its project and task type,
    and the role, stack and model family a lesson's applicability is matched against. Scope comes
    from trusted execution context, never from an agent-supplied value. An empty field matches
    no lesson: an unknown never means "everywhere" (§0.8 step 3)."""

    project_id: str
    task_type: str
    role: str = ""
    stack: str = ""
    model_family: str = ""


@dataclass(frozen=True)
class RecalledPattern:
    """One recalled failure pattern: the rejection class it was encoded from, and its rendered
    statement with the corrective rule (§5's ``ReflectiveFailurePattern``, as recall returns it).
    The 2.2 adapter defines the rest of the record; this is what a task is handed."""

    rejection_class: str
    statement: str
