"""Tests for bootstrap state file management (SIP-0081)."""

from __future__ import annotations

import json

from squadops.bootstrap.setup.state import BootstrapState, read_state, write_state


def _sample_state(profile: str = "dev-mac") -> BootstrapState:
    return BootstrapState(
        profile=profile,
        schema_version=1,
        last_run="2026-01-15T10:30:00Z",
        steps_completed=["python", "docker"],
        detected_versions={"python": "3.11.8"},
        doctor_summary={"total": 5, "passed": 4, "failed": 1, "heuristic": 0},
    )


class TestWriteState:
    def test_creates_directory(self, tmp_path):
        """write_state creates the state directory if it doesn't exist."""
        state_dir = tmp_path / "nested" / "dir"
        assert not state_dir.exists()
        path = write_state(_sample_state(), state_dir=state_dir)
        assert path.is_file()
        assert state_dir.is_dir()

    def test_overwrites_existing(self, tmp_path):
        """Second write replaces first, not appends."""
        state1 = _sample_state()
        state2 = _sample_state()
        state2.steps_completed = ["python", "docker", "models"]

        write_state(state1, state_dir=tmp_path)
        path = write_state(state2, state_dir=tmp_path)

        data = json.loads(path.read_text())
        assert data["steps_completed"] == ["python", "docker", "models"]


class TestReadState:
    def test_missing_file_returns_none(self, tmp_path):
        """Returns None for non-existent profile, not crash."""
        result = read_state("nonexistent", state_dir=tmp_path)
        assert result is None

    def test_round_trip(self, tmp_path):
        """State round-trips through write then read."""
        original = _sample_state("dev-pc")
        write_state(original, state_dir=tmp_path)
        loaded = read_state("dev-pc", state_dir=tmp_path)

        assert loaded is not None
        assert loaded.profile == "dev-pc"
        assert loaded.schema_version == 1
        assert loaded.last_run == "2026-01-15T10:30:00Z"
        assert loaded.steps_completed == ["python", "docker"]
        assert loaded.detected_versions == {"python": "3.11.8"}
        assert loaded.doctor_summary == {"total": 5, "passed": 4, "failed": 1, "heuristic": 0}

    def test_corrupt_json_returns_none(self, tmp_path):
        """Corrupt JSON returns None with logged warning, not crash."""
        bad_file = tmp_path / "broken.json"
        bad_file.write_text("{not valid json!!!")
        result = read_state("broken", state_dir=tmp_path)
        assert result is None
