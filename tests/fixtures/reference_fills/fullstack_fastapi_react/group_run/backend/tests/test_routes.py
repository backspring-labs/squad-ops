"""Generated suite for the group_run reference fill — the ``tests_pass`` behavioral.

Order-independent (module-level store reset per test) and covers the contract's
coverage_expectations: create/list/get/join/leave happy paths plus the error codes
(duplicate join -> 409, unknown run/participant -> 404).
"""

from fastapi.testclient import TestClient

from backend import routes
from backend.main import app

client = TestClient(app)


def setup_function():
    routes._RUNS.clear()  # module-level state reset per test (order-independence)


def _create(title="Saturday Long Run"):
    resp = client.post(
        "/runs", json={"title": title, "datetime": "2026-08-01T08:00", "location": "Park Gate"}
    )
    assert resp.status_code == 201
    return resp.json()


def test_create_then_list_then_get():
    run = _create()
    assert run["id"] and run["participants"] == []

    assert [r["id"] for r in client.get("/runs").json()] == [run["id"]]

    got = client.get(f"/runs/{run['id']}").json()
    assert got["id"] == run["id"]
    assert got["title"] == "Saturday Long Run"


def test_get_unknown_run_is_404():
    resp = client.get("/runs/does-not-exist")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "run_not_found"


def test_join_returns_full_run_and_rejects_case_insensitive_duplicate():
    run = _create()

    joined = client.post(f"/runs/{run['id']}/join", json={"name": "Alice"})
    assert joined.status_code == 200
    # mutation returns the FULL updated RunEvent, not just the participant
    assert joined.json()["id"] == run["id"]
    assert [p["name"] for p in joined.json()["participants"]] == ["Alice"]

    dup = client.post(f"/runs/{run['id']}/join", json={"name": "alice"})
    assert dup.status_code == 409
    assert dup.json()["error"]["code"] == "duplicate_participant"


def test_leave_removes_participant_and_unknown_is_404():
    run = _create()
    client.post(f"/runs/{run['id']}/join", json={"name": "Bob"})

    left = client.post(f"/runs/{run['id']}/leave", json={"name": "bob"})  # case-insensitive
    assert left.status_code == 200
    assert left.json()["participants"] == []

    unknown = client.post(f"/runs/{run['id']}/leave", json={"name": "ghost"})
    assert unknown.status_code == 404
    assert unknown.json()["error"]["code"] == "participant_not_found"


def test_create_requires_title_datetime_location():
    resp = client.post("/runs", json={"title": "missing the rest"})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"
