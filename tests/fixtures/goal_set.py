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
