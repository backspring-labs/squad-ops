"""Unit tests for Tools domain models."""
import pytest

from squadops.tools.models import ContainerResult, ContainerSpec, VCSStatus


class TestContainerSpec:
    """Tests for ContainerSpec dataclass."""

    def test_minimal_spec(self):
        spec = ContainerSpec(image="python:3.11")
        assert spec.image == "python:3.11"
        assert spec.command is None
        assert spec.env == ()
        assert spec.volumes == ()
        assert spec.working_dir is None
        assert spec.timeout_seconds == 300.0

    def test_full_spec(self):
        spec = ContainerSpec(
            image="python:3.11",
            command=["python", "-c", "print('hello')"],
            env=(("FOO", "bar"),),
            volumes=(("/host", "/container"),),
            working_dir="/app",
            timeout_seconds=60.0,
        )
        assert spec.command == ["python", "-c", "print('hello')"]
        assert spec.env == (("FOO", "bar"),)
        assert spec.volumes == (("/host", "/container"),)
        assert spec.working_dir == "/app"
        assert spec.timeout_seconds == 60.0

    def test_spec_is_frozen(self):
        spec = ContainerSpec(image="python:3.11")
        with pytest.raises(AttributeError):
            spec.image = "modified"  # type: ignore


class TestContainerResult:
    """Tests for ContainerResult dataclass."""

    def test_result(self):
        result = ContainerResult(
            container_id="abc123",
            exit_code=0,
            stdout="output",
            stderr="",
        )
        assert result.container_id == "abc123"
        assert result.exit_code == 0
        assert result.stdout == "output"
        assert result.stderr == ""

    def test_result_is_frozen(self):
        result = ContainerResult(
            container_id="abc",
            exit_code=0,
            stdout="",
            stderr="",
        )
        with pytest.raises(AttributeError):
            result.exit_code = 1  # type: ignore


class TestVCSStatus:
    """Tests for VCSStatus dataclass."""

    def test_minimal_status(self):
        status = VCSStatus(branch="main", is_clean=True)
        assert status.branch == "main"
        assert status.is_clean is True
        assert status.modified_files == ()
        assert status.untracked_files == ()
        assert status.ahead == 0
        assert status.behind == 0

    def test_full_status(self):
        status = VCSStatus(
            branch="feature",
            is_clean=False,
            modified_files=("file1.py", "file2.py"),
            untracked_files=("new.py",),
            ahead=2,
            behind=1,
        )
        assert status.modified_files == ("file1.py", "file2.py")
        assert status.untracked_files == ("new.py",)
        assert status.ahead == 2
        assert status.behind == 1

    def test_status_is_frozen(self):
        status = VCSStatus(branch="main", is_clean=True)
        with pytest.raises(AttributeError):
            status.branch = "modified"  # type: ignore
