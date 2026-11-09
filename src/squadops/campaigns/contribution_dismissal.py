"""The owner's "this work won't land": a closed, unmerged Campaign contribution, dismissed
(SIP-0109 §24dg; #2926; the owner's choice of 2026-11-05).

A contribution closed unmerged keeps blocking the operator's integration gate, because the work isn't in
(``campaigns.unintegrated``), and nothing else clears it. The dismissal says it never will be:

- It is an **applied ``contribution_dismissed`` row of the Campaign's control log,** with who and why,
  and the commit and review request it dismisses. The contribution's own record stays as it was,
  ``closed``: nothing is deleted or rewritten, and the work stays on the Campaign's branch.
- **It takes only a closed, unmerged contribution of the Campaign's own.** One pending or integrated
  may still land or has landed, and a Campaign with none has nothing to dismiss.
- It moves no state, and a completed Campaign takes it: a contribution exists only after the close.
- **There is no undoing it.** Re-opening is not built (§24dg).

Pure: the route reads the stores and writes the transition, and ``unintegrated`` reads the log.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from squadops.campaigns.models import (
    CampaignTransition,
    ControlLogEntry,
    ControlOperation,
    ControlOutcome,
)

#: The binding's key for where the owner's decision came from: a link, when a conversation.
SOURCE_REF_KEY = "source_ref"


def contribution_dismissal(log: Iterable[ControlLogEntry]) -> ControlLogEntry | None:
    """The applied dismissal in the Campaign's control log, or ``None``. A refused row is none."""
    return next(
        (
            e
            for e in log
            if e.operation is ControlOperation.CONTRIBUTION_DISMISSED
            and e.outcome is ControlOutcome.APPLIED
        ),
        None,
    )


def dismissal_refusal(
    campaign_id: str, contribution: Any | None, log: Iterable[ControlLogEntry]
) -> str | None:
    """Why the Campaign's ``contribution`` can't be dismissed, or ``None``."""
    # deferred (pair): squadops.projects imports this package at load
    from squadops.projects.contribution import CLOSED

    if contribution is None:
        return f"campaign {campaign_id} has no contribution to dismiss"
    if contribution.state != CLOSED or contribution.integrated_commit is not None:
        return (
            f"campaign {campaign_id}'s contribution is {contribution.state}: only one closed "
            "unmerged can be dismissed"
        )
    dismissed = contribution_dismissal(log)
    if dismissed is not None:
        return f"campaign {campaign_id}'s contribution was dismissed by {dismissed.actor}"
    return None


def dismissal_transition(
    contribution: Any,
    *,
    actor: str,
    actor_role: str,
    reason: str,
    idempotency_key: str,
    source_ref: str | None = None,
) -> CampaignTransition:
    """The dismissal's row, naming what it dismisses. Who may write it is the route's:
    ``campaigns:control``, the owner's alone.

    Raises ``ValueError`` when the reason is blank."""
    return CampaignTransition(
        operation=ControlOperation.CONTRIBUTION_DISMISSED,
        actor=actor,
        actor_role=actor_role,
        reason=reason,
        idempotency_key=idempotency_key,
        next_state=None,
        target=contribution.commit,
        binding={
            "commit": contribution.commit,
            "review_url": contribution.review_url,
            **({SOURCE_REF_KEY: source_ref} if source_ref is not None else {}),
        },
    )
