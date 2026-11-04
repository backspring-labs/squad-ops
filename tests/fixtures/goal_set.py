"""An invented goal set for the goal-set tests (SIP-0115 §4, #2884). Invented: no held-out
suite's values, goals or steps."""


def goal_set_document() -> dict:
    """An invented goal set, every kind of field present."""
    return {
        "goal": "A reader keeps a log of reading sessions and sees their weekly total",
        "expected_results": [
            {
                "id": "ER-log",
                "statement": "A session is recorded with its book and minutes",
                "surface": {"kind": "http_endpoint", "ref": "POST /api/sessions"},
            },
            {
                "id": "ER-week",
                "statement": "The week's total minutes are shown",
                "surface": {"kind": "page", "ref": "/week"},
            },
            {
                "id": "ER-calm",
                "statement": "The log feels calm to use",
                "surface": {"kind": "none", "reason": "judged by the owner, not observed"},
            },
        ],
        "constraints": ["No account is needed"],
        "out_of_scope": ["Sharing a log"],
        "backlog": [
            {
                "id": "B-1",
                "title": "Record a session",
                "description": "",
                "serves": ["ER-log"],
                "size": "one increment",
            },
            {"id": "B-2", "title": "Weekly total", "description": "", "serves": ["ER-week"]},
        ],
        "candidates": [
            {
                "id": "C-1",
                "title": "Edit a session",
                "description": "Found when a typo could not be fixed",
                "found_by": "cyc_0a1b2c",
                "found_at": "2026-11-02T09:30:00+00:00",
                "evidence": ["vault://cyc_0a1b2c/qa_report.md"],
            }
        ],
    }


def backlog_document(*item_ids: str) -> dict:
    """The invented goal set with its backlog's items ``item_ids``, in that order, each serving
    the weekly total. No candidate: a candidate's id may not be an item's."""
    doc = goal_set_document()
    doc["backlog"] = [{"id": i, "title": f"Item {i}", "serves": ["ER-week"]} for i in item_ids]
    doc["candidates"] = []
    return doc


class GoalSetStore:
    """A goal-set store holding revisions as written (``GoalSetRegistryPort``), for the tests
    that read a Campaign's backlog and the ones that act on a goal set. ``write`` appends the next
    revision of ``doc`` directly; ``record_revision`` keeps the port's rules: the next revision
    only, and a key replays what it wrote or refuses another body."""

    def __init__(self) -> None:
        self.revisions: dict[str, list] = {}
        self.by_key: dict[str, tuple[str, object]] = {}
        self.assessments: dict[str, list] = {}
        self.assessment_by_key: dict[str, tuple[str, object]] = {}

    async def record_revision(self, revision, *, idempotency_key: str, request_hash: str):
        from squadops.cycles.models import RegistrationKeyConflictError, StaleGoalSetRevisionError

        if idempotency_key in self.by_key:
            written_hash, written = self.by_key[idempotency_key]
            if written_hash != request_hash:
                raise RegistrationKeyConflictError(
                    f"idempotency key {idempotency_key!r} wrote different content"
                )
            return written, True
        held = self.revisions.setdefault(revision.project_id, [])
        if revision.revision != len(held) + 1:
            raise StaleGoalSetRevisionError(
                f"Project {revision.project_id}'s goal set is at revision {len(held)}; revision "
                f"{revision.revision} doesn't follow it"
            )
        held.append(revision)
        self.by_key[idempotency_key] = (request_hash, revision)
        return revision, False

    async def revision_under_key(self, idempotency_key: str, request_hash: str):
        written_hash, written = self.by_key.get(idempotency_key, (None, None))
        return written if written_hash == request_hash else None

    def write(self, project_id: str, doc: dict, *, change=None) -> int:
        """``change`` is the action the revision was (``Change``), when it was one."""
        from datetime import UTC, datetime

        from squadops.projects.goal_set import GoalSetRevision, parse_goal_set

        held = self.revisions.setdefault(project_id, [])
        held.append(
            GoalSetRevision(
                project_id=project_id,
                revision=len(held) + 1,
                goal_set=parse_goal_set(doc),
                author="owner",
                reason=f"revision {len(held) + 1}",
                created_at=datetime(2026, 11, 3, 9, 0, tzinfo=UTC),
                change=change,
            )
        )
        return len(held)

    async def get_revision(self, project_id: str, revision: int | None = None):
        from squadops.cycles.models import GoalSetNotFoundError

        held = self.revisions.get(project_id) or []
        found = held[-1:] if revision is None else [r for r in held if r.revision == revision]
        if not found:
            raise GoalSetNotFoundError(f"{project_id} r{revision}")
        return found[0]

    async def list_revisions(self, project_id: str):
        return list(reversed(self.revisions.get(project_id) or []))

    async def record_assessment(self, assessment, *, idempotency_key: str, request_hash: str):
        from dataclasses import replace

        from squadops.cycles.models import RegistrationKeyConflictError

        if idempotency_key in self.assessment_by_key:
            written_hash, written = self.assessment_by_key[idempotency_key]
            if written_hash != request_hash:
                raise RegistrationKeyConflictError(
                    f"idempotency key {idempotency_key!r} wrote different content"
                )
            return written, True
        held = self.assessments.setdefault(assessment.project_id, [])
        recorded = replace(assessment, sequence=len(held) + 1)
        held.append(recorded)
        self.assessment_by_key[idempotency_key] = (request_hash, recorded)
        return recorded, False

    async def list_assessments(
        self, project_id, *, campaign_id=None, expected_result=None, limit=None, offset=0
    ):
        found = [
            a
            for a in self.assessments.get(project_id) or []
            if campaign_id in (None, a.campaign_id) and expected_result in (None, a.expected_result)
        ]
        return found[offset:] if limit is None else found[offset : offset + limit]


def campaign_on(
    project_id: str, campaign_id: str, *, created_by: str = "owner", goals: bool = True
):
    """A draft Campaign on ``project_id`` reading its goal set at ``current`` (or, ``goals``
    false, a requirements Campaign), as ``create_campaign`` takes it. ``created_by`` is who
    started it: the owner, or a crew principal (SIP-0115 Q41)."""
    from datetime import UTC, datetime

    from squadops.campaigns.models import CampaignGoals, CampaignObjective
    from tests.unit.campaigns.builders import campaign

    objective = CampaignObjective(
        statement="the log gains its weekly total",
        allowed_scope=("app/**",),
        measurement="one accepted increment",
        target_accepted_increments=1,
        work_class=None,
        goals=CampaignGoals(project_id, "current") if goals else None,
        requirements=None if goals else "repo:file:README.md@current",
    )
    return campaign(
        campaign_id,
        project_id=project_id,
        objective=objective,
        created_by=created_by,
        created_at=datetime(2026, 11, 3, 10, 0, tzinfo=UTC),
    )


async def started(
    registry,
    campaign_id: str,
    *,
    created_by: str = "owner",
    granted: bool = False,
    **campaign_fields,
):
    """``campaign_on``'s Campaign, created in ``registry``, its calibration tree accepted and
    the Campaign at its proposal. ``granted``: the owner's goal delegation recorded on it."""
    from squadops.campaigns.goal_delegation import goal_delegation_transition
    from squadops.campaigns.models import AcceptedTree, CampaignState, ControlOperation
    from tests.unit.campaigns.builders import move

    project_id = campaign_fields.pop("project_id", "prj-lantern")
    held = campaign_on(project_id, campaign_id, created_by=created_by, **campaign_fields)
    await registry.create_campaign(
        held,
        actor=created_by,
        actor_role="r",
        reason="a campaign",
        idempotency_key=f"c:{campaign_id}",
    )
    await registry.transition(
        campaign_id,
        move(CampaignState.CALIBRATING, f"s:{campaign_id}", operation=ControlOperation.START),
    )
    await registry.transition(
        campaign_id,
        move(CampaignState.CALIBRATING, f"p:{campaign_id}", operation=ControlOperation.PROMOTE,
             accepted=AcceptedTree(ACCEPTED_TREE, "cyc_cal")),
    )  # fmt: skip
    await registry.transition(campaign_id, move(CampaignState.AT_PROPOSAL, f"d:{campaign_id}"))
    if granted:
        await registry.transition(
            campaign_id,
            goal_delegation_transition(
                held,
                actor="owner",
                actor_role="admin",
                reason="the owner approved it",
                idempotency_key=f"grant:{campaign_id}",
            ),
        )
    return held


#: The accepted tree every proposal in these tests is against, and every ruling binds to.
ACCEPTED_TREE = "sha-accepted"


async def proposed(registry, campaign_id: str, item: str, *, revision: int = 1, ruled=None):
    """A proposal naming ``item`` submitted at ``campaign_id``'s increment gate, as the executor
    submits one, and, ``ruled`` a gate decision, ruled so: approved reads ``in_increment``, a
    return or rejection leaves the item ``pending``."""
    from squadops.campaigns.gate import ruling_transition
    from squadops.campaigns.models import (
        CampaignState,
        CampaignTransition,
        ControlOperation,
        ProposalBinding,
        SubmittedProposal,
    )

    cycle = f"cyc_{campaign_id[-4:]}_{item}"
    binding = ProposalBinding(f"prop_{cycle}", 1, "c", ACCEPTED_TREE)
    await registry.transition(
        campaign_id,
        CampaignTransition(
            operation=ControlOperation.SUBMIT, actor="squadops", actor_role="executor",
            reason="at the gate", idempotency_key=f"submit:{cycle}",
            next_state=CampaignState.AWAITING_RULING, target=f"run_{cycle}",
            binding={
                "proposal_id": binding.proposal_id, "version": 1, "content_hash": "c",
                "baseline_tree": ACCEPTED_TREE, "cycle_id": cycle, "backlog_item": item,
                "goals_revision": revision,
            },
            submitted=SubmittedProposal(binding, cycle, f"run_{cycle}"),
        ),
    )  # fmt: skip
    if ruled is not None:
        await registry.transition(
            campaign_id,
            ruling_transition(
                ruled, binding, run_id=f"run_{cycle}", actor="supervisor", actor_role="r",
                reason=f"ruled {ruled.value}", idempotency_key=f"rule:{cycle}",
                classification=None if ruled.value == "approved" else "scope_too_large",
            ),
        )  # fmt: skip
