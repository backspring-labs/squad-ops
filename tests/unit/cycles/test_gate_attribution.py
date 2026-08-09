"""Who decided a gate, in a vocabulary that can tell them apart (#812).

Every API-made gate decision recorded the literal `"system"` — a hardcoded value with a
`TODO: extract from auth context` beside it. So all 140 human approvals in the project's
history carry the word that means *no human was involved*, in the same namespace the machine
paths use (`system:plan_validation`, `system:no_open_questions`).

Bug classes guarded:

- **an agent's decision recorded as a person's**, which is the reason this exists: the
  authored-mode window has to be able to state whether its questions were adjudicated by a
  human or an LLM, and 1.8's memory seeds itself from this history;
- the reverse — a person's decision demoted to a machine's — which would launder a real
  approval into something nobody has to answer for;
- **inferring the actor** from timing, notes, or usage. A guess that is usually right makes
  the field unreliable in exactly the cases anyone would check it;
- a caller declaring an actor class that is not theirs to declare (`system`, `service`);
- attribution silently promoting an unauthenticated caller to a person when auth is off;
- the machine-decision predicate matching the bare legacy `"system"`, which would relabel
  140 real human approvals as machine ones.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from squadops.cycles.gate_attribution import (
    ACTOR_AGENT,
    ACTOR_HUMAN,
    ACTOR_SERVICE,
    DECLARABLE_ACTORS,
    UNATTRIBUTED,
    compose_decided_by,
    is_machine_decision,
)
from squadops.cycles.manifest_authoring import GATE_DECIDED_BY_NO_QUESTIONS

pytestmark = [pytest.mark.domain_contracts]


@dataclass(frozen=True)
class _Identity:
    user_id: str = "squadops-admin"
    display_name: str = "Admin"
    identity_type: str = ACTOR_HUMAN


def test_a_person_is_recorded_as_a_person():
    assert compose_decided_by(_Identity()) == "human:squadops-admin"


def test_an_agent_declaring_itself_is_not_filed_as_the_human_it_authenticated_as():
    """The case that motivated this. An agent answered V5's two design questions on a human
    account; the record said a person did. Declaring is the only mechanism available —
    the token cannot tell."""
    assert compose_decided_by(_Identity(), ACTOR_AGENT) == "agent:squadops-admin"


def test_a_service_account_keeps_its_own_type():
    assert (
        compose_decided_by(_Identity(user_id="squadops-agent", identity_type=ACTOR_SERVICE))
        == "service:squadops-agent"
    )


@pytest.mark.parametrize("declared", ["system", "service", "robot", "", None])
def test_an_undeclarable_actor_falls_back_to_the_identity(declared):
    """`system` is the executor's alone and `service` comes from the token. A caller that
    could claim either could dress an agent's decision as a machine's — which is the same
    laundering from the other direction."""
    assert compose_decided_by(_Identity(), declared) == "human:squadops-admin"
    assert declared not in DECLARABLE_ACTORS or declared in ("human", "agent")


def test_no_identity_is_recorded_as_unattributed_not_as_a_person():
    """Auth can be off in a local deployment. Naming what is known — that something
    unauthenticated decided it — beats promoting it to a human."""
    assert compose_decided_by(None) == UNATTRIBUTED
    assert compose_decided_by(_Identity(user_id="", display_name="")) == UNATTRIBUTED


def test_display_name_is_the_fallback_principal():
    """A token with no user_id still identifies someone; losing that to `unattributed`
    would discard real attribution."""
    assert compose_decided_by(_Identity(user_id="", display_name="Jane")) == "human:Jane"


# --------------------------------------------------------------------------- #
# Telling machine decisions apart
# --------------------------------------------------------------------------- #


def test_machine_decisions_are_recognised_by_prefix_so_new_ones_are_covered():
    assert is_machine_decision("system:plan_validation")
    assert is_machine_decision(GATE_DECIDED_BY_NO_QUESTIONS)
    assert is_machine_decision("system:some_future_mechanism")


@pytest.mark.parametrize(
    "value", ["human:squadops-admin", "agent:squadops-admin", "service:x", UNATTRIBUTED]
)
def test_principal_decisions_are_not_machine_decisions(value):
    assert not is_machine_decision(value)


def test_the_legacy_bare_system_is_not_treated_as_a_machine_decision():
    """The 140 historical rows saying `"system"` are decisions people actually made — the
    field simply could not say so. Matching them as machine decisions would launder exactly
    the confusion this module ends, and it would do it retroactively."""
    assert not is_machine_decision("system")


def test_the_machine_and_declared_vocabularies_cannot_collide():
    """A declarable actor that shared the machine prefix would make the two indistinguishable
    again the moment someone declared it."""
    for actor in DECLARABLE_ACTORS:
        assert not is_machine_decision(f"{actor}:someone")
