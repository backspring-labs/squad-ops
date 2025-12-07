#!/usr/bin/env python3
"""
Unit tests for CycleSnapshotCollector capability
Tests cycle snapshot collection capability
"""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.capabilities.data.collect_cycle_snapshot import CycleSnapshotCollector


class TestCycleSnapshotCollector:
    """Test CycleSnapshotCollector capability"""

    @pytest.fixture
    def mock_agent(self):
        """Create mock agent instance"""
        agent = MagicMock()
        agent.name = "test-agent"
        agent.runtime_api_url = "http://localhost:8001"
        agent.config = MagicMock()
        # Use a temporary directory path instead of MagicMock to avoid creating "MagicMock" directory
        # Use TemporaryDirectory context manager for automatic cleanup
        temp_dir_ctx = TemporaryDirectory()
        temp_dir = Path(temp_dir_ctx.name)
        # Store context manager on agent so it persists for the test duration
        agent._temp_dir_ctx = temp_dir_ctx
        agent.config.get_cycle_data_root = MagicMock(return_value=temp_dir)
        yield agent
        # Cleanup temporary directory after test
        temp_dir_ctx.cleanup()

    @pytest.fixture
    def collector(self, mock_agent):
        """Create CycleSnapshotCollector instance"""
        return CycleSnapshotCollector(mock_agent)

    @pytest.mark.unit
    def test_collector_initialization(self, mock_agent):
        """Test CycleSnapshotCollector initialization"""
        collector = CycleSnapshotCollector(mock_agent)
        assert collector.agent == mock_agent
        assert collector.name == "test-agent"
        assert collector.runtime_api_url == "http://localhost:8001"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_collect_success(self, collector):
        """Test successful cycle snapshot collection"""
        ecid = "ECID-WB-001"

        mock_snapshot_data = {
            "cycle_id": ecid,
            "tasks": [{"task_id": "task-1", "status": "completed"}],
            "agents": ["agent1", "agent2"],
        }

        # Use a temporary directory path instead of MagicMock to avoid creating "MagicMock" directory
        # Use TemporaryDirectory context manager for automatic cleanup
        with TemporaryDirectory() as tmpdir:
            temp_dir = Path(tmpdir)

            # Mock agent's record_memory
            collector.agent.record_memory = AsyncMock()

            with (
                patch(
                    "agents.utils.path_resolver.PathResolver.get_base_path", return_value=temp_dir
                ),
                patch("agents.cycle_data.CycleDataStore") as mock_cycle_store_class,
                patch.object(
                    collector,
                    "_fetch_execution_cycle",
                    new_callable=AsyncMock,
                    return_value=mock_snapshot_data,
                ),
                patch.object(
                    collector,
                    "_fetch_tasks",
                    new_callable=AsyncMock,
                    return_value=mock_snapshot_data.get("tasks", []),
                ),
                patch("pathlib.Path.mkdir"),
                patch.object(collector, "_scan_artifacts", new_callable=AsyncMock, return_value={}),
                patch.object(
                    collector,
                    "_aggregate_by_agent",
                    return_value=mock_snapshot_data.get("agents", []),
                ),
            ):
                mock_cycle_store = MagicMock()
                mock_cycle_store.write_text_artifact = MagicMock(return_value=True)
                mock_path = MagicMock()
                mock_path.__truediv__ = MagicMock(
                    return_value=MagicMock() / "meta" / "cycle-snapshot-ECID-WB-001.json"
                )
                mock_cycle_store.get_cycle_path.return_value = mock_path
                mock_cycle_store_class.return_value = mock_cycle_store

                result = await collector.collect(ecid)

                assert "ecid" in result or "snapshot_path" in result

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_collect_with_output_dir(self, collector):
        """Test collection with custom output directory"""
        ecid = "ECID-WB-001"
        output_dir = "/test/output"

        # Use a temporary directory path instead of MagicMock to avoid creating "MagicMock" directory
        # Use TemporaryDirectory context manager for automatic cleanup
        with TemporaryDirectory() as tmpdir:
            temp_dir = Path(tmpdir)

            # Mock agent's record_memory
            collector.agent.record_memory = AsyncMock()

            with (
                patch(
                    "agents.utils.path_resolver.PathResolver.get_base_path", return_value=temp_dir
                ),
                patch("agents.cycle_data.CycleDataStore") as mock_cycle_store_class,
                patch.object(
                    collector, "_fetch_execution_cycle", new_callable=AsyncMock, return_value={}
                ),
                patch.object(collector, "_fetch_tasks", new_callable=AsyncMock, return_value=[]),
                patch("pathlib.Path.mkdir"),
                patch.object(collector, "_scan_artifacts", new_callable=AsyncMock, return_value={}),
                patch.object(collector, "_aggregate_by_agent", return_value=[]),
            ):
                mock_cycle_store = MagicMock()
                mock_cycle_store.write_text_artifact = MagicMock(return_value=True)
                mock_path = MagicMock()
                mock_path.__truediv__ = MagicMock(
                    return_value=MagicMock() / "meta" / "cycle-snapshot-ECID-WB-001.json"
                )
                mock_cycle_store.get_cycle_path.return_value = mock_path
                mock_cycle_store_class.return_value = mock_cycle_store

                result = await collector.collect(ecid, output_dir)

                assert result is not None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_collect_api_error(self, collector):
        """Test collection when API call fails"""
        ecid = "ECID-WB-001"

        # Use a temporary directory path instead of MagicMock to avoid creating "MagicMock" directory
        # Use TemporaryDirectory context manager for automatic cleanup
        with TemporaryDirectory() as tmpdir:
            temp_dir = Path(tmpdir)

            mock_session_instance = AsyncMock()
            mock_session_instance.get = AsyncMock(side_effect=Exception("API error"))
            mock_session_context = AsyncMock()
            mock_session_context.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session_context.__aexit__ = AsyncMock(return_value=None)

            with (
                patch(
                    "agents.utils.path_resolver.PathResolver.get_base_path", return_value=temp_dir
                ),
                patch("aiohttp.ClientSession", return_value=mock_session_context),
            ):
                with pytest.raises(Exception):
                    await collector.collect(ecid)

    @pytest.mark.unit
    def test_extract_run_directory(self, collector):
        """Test extracting run directory from ECID"""
        ecid = "ECID-WB-001"
        warmboot_runs_dir = MagicMock()

        result = collector._extract_run_directory(ecid, warmboot_runs_dir)

        # Should return a path or None
        assert result is None or hasattr(result, "__truediv__")
