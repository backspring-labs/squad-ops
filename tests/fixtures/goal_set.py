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
    """A goal-set store holding revisions as written (``GoalSetRegistryPort``'s reads), for the
    tests that read a Campaign's backlog. ``write`` appends the next revision of ``doc``."""

    def __init__(self) -> None:
        self.revisions: dict[str, list] = {}

    def write(self, project_id: str, doc: dict) -> int:
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
