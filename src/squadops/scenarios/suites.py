"""What the scenario store may hold, and when (SIP-0113 §4.1, §4.7; the 2.4 plan's D2; #2413).

- **Drafted** by the supervisor's seat (``scenarios:draft``). The same content drafted again is
  the same suite, so a retry replays.
- **Approved** by the owner (``scenarios:approve``) before any campaign can pin it. Approval is
  once: an approved suite's content is frozen by its digest.
- **Refused, at either, when a browser step or check is malformed** (§10p ruling 9), and never
  when a stored suite is read.
- **Pinned** on a campaign at its creation, once. The same pin again replays; a different suite
  for a pinned campaign is refused.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from squadops.scenarios.models import CampaignSuitePin, ScenarioSuite, SuiteRecord, SuiteState
from squadops.scenarios.steps import vocabulary_refusals

if TYPE_CHECKING:  # the port names this package's models; the rules only take one
    from squadops.ports.scenarios import ScenarioStorePort


class SuiteRefused(Exception):
    """A request the store's rules refuse, with the code the route answers with."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def malformed(suite: ScenarioSuite) -> list[str]:
    """§10p ruling 9: every malformed browser step and check in ``suite``, by its scenario, step
    and check, never by a value."""
    return [
        f"scenario {s.scenario_id!r}: {why}"
        for s in suite.scenarios
        for why in vocabulary_refusals(s.steps, s.checks)
    ]


def _refuse_malformed(suite: ScenarioSuite) -> None:
    problems = malformed(suite)
    if problems:
        raise SuiteRefused("SUITE_INVALID", "; ".join(problems))


async def draft_suite(
    store: ScenarioStorePort, suite: ScenarioSuite, *, actor: str, at: datetime
) -> SuiteRecord:
    _refuse_malformed(suite)
    held = await store.get_suite(suite.digest)
    if held is not None:
        return held
    record = SuiteRecord(suite=suite, state=SuiteState.DRAFT, drafted_by=actor, drafted_at=at)
    await store.save_suite(record)
    return record


async def approve_suite(
    store: ScenarioStorePort, digest: str, *, actor: str, at: datetime
) -> SuiteRecord:
    held = await store.get_suite(digest)
    if held is None:
        raise SuiteRefused("SUITE_NOT_FOUND", f"no suite {digest}")
    if held.state is SuiteState.APPROVED:
        return held
    _refuse_malformed(held.suite)
    approved = SuiteRecord(
        suite=held.suite,
        state=SuiteState.APPROVED,
        drafted_by=held.drafted_by,
        drafted_at=held.drafted_at,
        approved_by=actor,
        approved_at=at,
    )
    await store.save_suite(approved)
    return approved


async def require_pinnable(store: ScenarioStorePort, digest: str) -> SuiteRecord:
    """The suite a campaign may be created with: stored and approved (D2)."""
    held = await store.get_suite(digest)
    if held is None:
        raise SuiteRefused("SUITE_NOT_FOUND", f"no suite {digest}: draft and approve it first")
    if held.state is not SuiteState.APPROVED:
        raise SuiteRefused(
            "SUITE_NOT_APPROVED", f"suite {digest} is a draft: the owner approves it before use"
        )
    return held


async def pin_campaign_suite(
    store: ScenarioStorePort,
    campaign_id: str,
    digest: str,
    *,
    draft: bool,
    actor: str,
    at: datetime,
) -> CampaignSuitePin:
    """Pin ``digest`` on the campaign, once. The same suite again returns the pin; another is
    refused. A campaign takes a new pin only while it is a ``draft``: the creation's replay hash
    doesn't carry the suite, so past its draft a retried creation could otherwise attach a suite
    to a campaign created without one, in any later state (#2448's review). A retry while it is
    still a draft recovers a pin its first creation failed to write."""
    await require_pinnable(store, digest)
    held = await store.get_pin(campaign_id)
    if held is not None:
        if held.suite_digest == digest:
            return held
        raise SuiteRefused(
            "SUITE_ALREADY_PINNED",
            f"campaign {campaign_id} is pinned to suite {held.suite_digest}, not {digest}",
        )
    if not draft:
        raise SuiteRefused(
            "SUITE_PIN_PAST_DRAFT",
            f"campaign {campaign_id} is past its draft with no suite pinned: a suite is pinned "
            "while the campaign is a draft",
        )
    pin = CampaignSuitePin(campaign_id, digest, pinned_by=actor, pinned_at=at)
    await store.save_pin(pin)
    return pin
