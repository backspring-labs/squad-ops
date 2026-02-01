"""
Unit tests for PulseContext module
"""

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from agents.context import (
    PulseContext,
    create_pulse_context,
    list_pulses_for_cycle,
    load_pulse_context,
    update_pulse_context,
)


class TestPulseContext:
    """Test PulseContext model and functions"""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for cycle data"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def mock_cycle_store(self, temp_dir):
        """Create mock CycleDataStore"""
        from agents.cycle_data import CycleDataStore

        return CycleDataStore(temp_dir, "test-project", "cycle-001")

    @pytest.mark.unit
    def test_pulse_context_model(self):
        """Test PulseContext Pydantic model"""
        pulse = PulseContext(
            pulse_id="pulse-001",
            cycle_id="cycle-001",
            name="Test Pulse",
            description="Test description",
        )

        assert pulse.pulse_id == "pulse-001"
        assert pulse.cycle_id == "cycle-001"
        assert pulse.name == "Test Pulse"
        assert pulse.description == "Test description"
        assert isinstance(pulse.created_at, datetime)
        assert isinstance(pulse.updated_at, datetime)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_create_pulse_context(self, temp_dir):
        """Test creating a PulseContext"""
        with patch("agents.context.pulse_context._get_cycle_data_store_async") as mock_get_store:
            from agents.cycle_data import CycleDataStore

            cycle_store = CycleDataStore(temp_dir, "test-project", "cycle-001")
            mock_get_store.return_value = cycle_store

            pulse = await create_pulse_context(
                pulse_id="pulse-001",
                cycle_id="cycle-001",
                name="Test Pulse",
                description="Test description",
                project_id="test-project",
            )

            assert pulse.pulse_id == "pulse-001"
            assert pulse.cycle_id == "cycle-001"
            assert pulse.name == "Test Pulse"

            # Verify file was created
            pulse_path = (
                temp_dir
                / "test-project"
                / "cycle-001"
                / "pulses"
                / "pulse-001"
                / "pulse_context.json"
            )
            assert pulse_path.exists()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_load_pulse_context(self, temp_dir):
        """Test loading a PulseContext"""
        # First create a pulse
        with patch("agents.context.pulse_context._get_cycle_data_store_async") as mock_get_store:
            from agents.cycle_data import CycleDataStore

            cycle_store = CycleDataStore(temp_dir, "test-project", "cycle-001")
            mock_get_store.return_value = cycle_store

            # Create pulse
            await create_pulse_context(
                pulse_id="pulse-001",
                cycle_id="cycle-001",
                name="Test Pulse",
                description="Test description",
                project_id="test-project",
            )

            # Load pulse
            loaded = await load_pulse_context("pulse-001", "cycle-001", "test-project")

            assert loaded is not None
            assert loaded.pulse_id == "pulse-001"
            assert loaded.name == "Test Pulse"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_load_pulse_context_not_found(self, temp_dir):
        """Test loading a non-existent PulseContext"""
        with patch("agents.context.pulse_context._get_cycle_data_store_async") as mock_get_store:
            from agents.cycle_data import CycleDataStore

            cycle_store = CycleDataStore(temp_dir, "test-project", "cycle-001")
            mock_get_store.return_value = cycle_store

            loaded = await load_pulse_context("nonexistent", "cycle-001", "test-project")
            assert loaded is None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_update_pulse_context(self, temp_dir):
        """Test updating a PulseContext"""
        from agents.cycle_data import CycleDataStore

        cycle_store = CycleDataStore(temp_dir, "test-project", "cycle-001")

        with patch(
            "agents.context.pulse_context._get_cycle_data_store_async", return_value=cycle_store
        ):
            # Create pulse
            pulse = await create_pulse_context(
                pulse_id="pulse-001",
                cycle_id="cycle-001",
                name="Test Pulse",
                description="Test description",
                project_id="test-project",
            )

            # Store original updated_at
            original_updated_at = pulse.updated_at

            # Update pulse (mock should still be active)
            updated = await update_pulse_context(
                pulse,
                agents_involved=["agent-1", "agent-2"],
                task_ids=["task-1", "task-2"],
            )

            assert len(updated.agents_involved) == 2
            assert len(updated.task_ids) == 2
            assert updated.updated_at >= original_updated_at

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_list_pulses_for_cycle(self, temp_dir):
        """Test listing pulses for a cycle"""
        with patch("agents.context.pulse_context._get_cycle_data_store_async") as mock_get_store:
            from agents.cycle_data import CycleDataStore

            cycle_store = CycleDataStore(temp_dir, "test-project", "cycle-001")
            mock_get_store.return_value = cycle_store

            # Create multiple pulses
            await create_pulse_context(
                pulse_id="pulse-001",
                cycle_id="cycle-001",
                name="Pulse 1",
                description="Description 1",
                project_id="test-project",
            )

            await create_pulse_context(
                pulse_id="pulse-002",
                cycle_id="cycle-001",
                name="Pulse 2",
                description="Description 2",
                project_id="test-project",
            )

            # List pulses
            pulses = await list_pulses_for_cycle("cycle-001", "test-project")

            assert len(pulses) == 2
            pulse_ids = [p.pulse_id for p in pulses]
            assert "pulse-001" in pulse_ids
            assert "pulse-002" in pulse_ids

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_pulse_context_persistence(self, temp_dir):
        """Test that PulseContext is persisted correctly"""
        with patch("agents.context.pulse_context._get_cycle_data_store_async") as mock_get_store:
            from agents.cycle_data import CycleDataStore

            cycle_store = CycleDataStore(temp_dir, "test-project", "cycle-001")
            mock_get_store.return_value = cycle_store

            # Create pulse with all fields
            pulse = await create_pulse_context(
                pulse_id="pulse-001",
                cycle_id="cycle-001",
                name="Test Pulse",
                description="Test description",
                project_id="test-project",
                agents_involved=["agent-1"],
                task_ids=["task-1"],
                artifacts={"artifact-1": {"type": "code", "path": "/path/to/file"}},
                constraints={"time_limit": "1h"},
                acceptance_criteria={"tests_pass": True},
                metadata={"custom": "value"},
            )

            # Load and verify
            loaded = await load_pulse_context("pulse-001", "cycle-001", "test-project")

            assert loaded.pulse_id == pulse.pulse_id
            assert loaded.name == pulse.name
            assert loaded.agents_involved == pulse.agents_involved
            assert loaded.task_ids == pulse.task_ids
            assert loaded.artifacts == pulse.artifacts
            assert loaded.constraints == pulse.constraints
            assert loaded.acceptance_criteria == pulse.acceptance_criteria
            assert loaded.metadata == pulse.metadata
