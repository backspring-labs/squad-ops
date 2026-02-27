"""Tests for in-memory pull job tracker (SIP-0075 §2.1)."""

import pytest

from squadops.api.runtime.pull_tracker import (
    clear_jobs,
    complete_pull_job,
    create_pull_job,
    fail_pull_job,
    get_pull_job,
)

pytestmark = [pytest.mark.domain_api]


@pytest.fixture(autouse=True)
def _clean_tracker():
    """Ensure clean state for each test."""
    clear_jobs()
    yield
    clear_jobs()


class TestCreatePullJob:
    def test_creates_job_with_pulling_status(self):
        job = create_pull_job("qwen2.5:7b")
        assert job.model_name == "qwen2.5:7b"
        assert job.status == "pulling"
        assert job.pull_id
        assert job.error is None

    def test_jobs_have_unique_ids(self):
        j1 = create_pull_job("model-a")
        j2 = create_pull_job("model-b")
        assert j1.pull_id != j2.pull_id


class TestGetPullJob:
    def test_returns_job_by_id(self):
        job = create_pull_job("qwen2.5:7b")
        found = get_pull_job(job.pull_id)
        assert found is not None
        assert found.pull_id == job.pull_id

    def test_returns_none_for_unknown_id(self):
        assert get_pull_job("nonexistent") is None


class TestCompletePullJob:
    def test_marks_complete(self):
        job = create_pull_job("qwen2.5:7b")
        complete_pull_job(job.pull_id)
        found = get_pull_job(job.pull_id)
        assert found.status == "complete"
        assert found.completed_at is not None

    def test_noop_for_unknown_id(self):
        complete_pull_job("nonexistent")  # Should not raise


class TestFailPullJob:
    def test_marks_failed_with_error(self):
        job = create_pull_job("qwen2.5:7b")
        fail_pull_job(job.pull_id, "connection refused")
        found = get_pull_job(job.pull_id)
        assert found.status == "failed"
        assert found.error == "connection refused"
        assert found.completed_at is not None

    def test_noop_for_unknown_id(self):
        fail_pull_job("nonexistent", "err")  # Should not raise


class TestClearJobs:
    def test_clears_all_jobs(self):
        create_pull_job("a")
        create_pull_job("b")
        clear_jobs()
        assert get_pull_job("a") is None
