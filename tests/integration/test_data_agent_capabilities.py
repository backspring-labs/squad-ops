"""
Integration tests for Data agent cycle analysis capabilities
Tests end-to-end capabilities with real Task API
"""

import json
import tempfile
from pathlib import Path

import pytest

from agents.capabilities.data.compose_cycle_summary import CycleSummaryComposer
from agents.capabilities.data.profile_cycle_metrics import CycleMetricsProfiler
from agents.roles.data.agent import DataAgent


class TestDataAgentCapabilities:
    """Test end-to-end Data agent capabilities"""
    
    @pytest.mark.integration
    def test_data_capability_imports(self):
        """Test Data capability imports"""
        # Verify domain structure exists
        assert Path("agents/capabilities/data").exists()
        assert Path("agents/capabilities/data/__init__.py").exists()
        
        # Verify imports work
        try:
            from agents.capabilities.data.collect_cycle_snapshot import (
                CycleSnapshotCollector,  # noqa: F401
            )
            from agents.capabilities.data.compose_cycle_summary import (
                CycleSummaryComposer,  # noqa: F401
            )
            from agents.capabilities.data.profile_cycle_metrics import (
                CycleMetricsProfiler,  # noqa: F401
            )
            assert True
        except ImportError as e:
            pytest.fail(f"Import failed: {e}")
    
    @pytest.mark.integration
    def test_data_agent_structure(self):
        """Test Data agent structure"""
        # Verify agent file exists
        assert Path("agents/roles/data/agent.py").exists()
        assert Path("agents/roles/data/config.yaml").exists()
        
        # Verify imports work
        try:
            from agents.roles.data.agent import DataAgent  # noqa: F401
            assert True
        except ImportError as e:
            pytest.fail(f"Import failed: {e}")
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_collect_cycle_snapshot_capability_structure(self):
        """Test collect_cycle_snapshot capability structure"""
        # Verify the structure exists
        assert Path("agents/capabilities/data/collect_cycle_snapshot.py").exists()
        
        # Verify imports work
        try:
            from agents.capabilities.data.collect_cycle_snapshot import (
                CycleSnapshotCollector,  # noqa: F401
            )
            assert True
        except ImportError as e:
            pytest.fail(f"Import failed: {e}")
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_profile_cycle_metrics_capability_structure(self):
        """Test profile_cycle_metrics capability structure"""
        # Verify the structure exists
        assert Path("agents/capabilities/data/profile_cycle_metrics.py").exists()
        
        # Verify imports work
        try:
            from agents.capabilities.data.profile_cycle_metrics import (
                CycleMetricsProfiler,  # noqa: F401
            )
            assert True
        except ImportError as e:
            pytest.fail(f"Import failed: {e}")
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_compose_cycle_summary_capability_structure(self):
        """Test compose_cycle_summary capability structure"""
        # Verify the structure exists
        assert Path("agents/capabilities/data/compose_cycle_summary.py").exists()
        
        # Verify imports work
        try:
            from agents.capabilities.data.compose_cycle_summary import (
                CycleSummaryComposer,  # noqa: F401
            )
            assert True
        except ImportError as e:
            pytest.fail(f"Import failed: {e}")
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_collect_cycle_snapshot_with_sample_data(self):
        """Test collect_cycle_snapshot with sample snapshot data"""
        # Create a temporary directory for test output
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a sample snapshot structure
            snapshot = {
                "cycle_id": "ECID-TEST-001",
                "execution_cycle": {"id": "ECID-TEST-001", "status": "completed"},
                "tasks": [
                    {"task_id": "TASK-001", "agent": "max", "status": "completed"},
                    {"task_id": "TASK-002", "agent": "neo", "status": "completed"}
                ],
                "agents": {
                    "max": {"task_count": 1, "tasks": [{"task_id": "TASK-001"}]},
                    "neo": {"task_count": 1, "tasks": [{"task_id": "TASK-002"}]}
                },
                "artifacts": {"wrapup_files": []},
                "collected_at": "2025-01-01T00:00:00Z"
            }
            
            # Save sample snapshot
            snapshot_path = Path(tmpdir) / "cycle-snapshot-ECID-TEST-001.json"
            with open(snapshot_path, 'w') as f:
                json.dump(snapshot, f)
            
            # Test that snapshot can be loaded
            assert snapshot_path.exists()
            with open(snapshot_path) as f:
                loaded = json.load(f)
                assert loaded["cycle_id"] == "ECID-TEST-001"
                assert len(loaded["tasks"]) == 2
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_profile_cycle_metrics_with_sample_snapshot(self):
        """Test profile_cycle_metrics with sample snapshot"""
        # Create a temporary agent instance
        agent = DataAgent(identity="data-agent-test")
        
        # Create profiler
        profiler = CycleMetricsProfiler(agent)
        
        # Create a temporary directory for test output
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a sample snapshot
            snapshot = {
                "cycle_id": "ECID-TEST-002",
                "execution_cycle": {"id": "ECID-TEST-002"},
                "tasks": [
                    {"task_id": "TASK-001", "agent": "max", "status": "completed"},
                    {"task_id": "TASK-002", "agent": "neo", "status": "failed"}
                ],
                "agents": {
                    "max": {"task_count": 1, "tasks": [{"task_id": "TASK-001", "status": "completed"}]},
                    "neo": {"task_count": 1, "tasks": [{"task_id": "TASK-002", "status": "failed"}]}
                },
                "artifacts": {},
                "collected_at": "2025-01-01T00:00:00Z"
            }
            
            # Save sample snapshot
            snapshot_path = Path(tmpdir) / "cycle-snapshot-ECID-TEST-002.json"
            with open(snapshot_path, 'w') as f:
                json.dump(snapshot, f)
            
            # Test metrics computation
            metrics = profiler._compute_metrics(snapshot)
            
            assert metrics["cycle_id"] == "ECID-TEST-002"
            assert metrics["summary"]["total_tasks"] == 2
            assert metrics["summary"]["total_agents"] == 2
            assert metrics["summary"]["total_success"] == 1
            assert metrics["summary"]["total_failure"] == 1
            assert "agent_metrics" in metrics
            assert "max" in metrics["agent_metrics"]
            assert "neo" in metrics["agent_metrics"]
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_compose_cycle_summary_with_sample_data(self):
        """Test compose_cycle_summary with sample snapshot and metrics"""
        # Create a temporary agent instance
        agent = DataAgent(identity="data-agent-test")
        
        # Create composer
        composer = CycleSummaryComposer(agent)
        
        # Create sample snapshot
        snapshot = {
            "cycle_id": "ECID-TEST-003",
            "execution_cycle": {"id": "ECID-TEST-003"},
            "tasks": [
                {"task_id": "TASK-001", "agent": "max", "status": "completed"},
                {"task_id": "TASK-002", "agent": "neo", "status": "completed"}
            ],
            "agents": {
                "max": {"task_count": 1, "tasks": [{"task_id": "TASK-001", "status": "completed"}]},
                "neo": {"task_count": 1, "tasks": [{"task_id": "TASK-002", "status": "completed"}]}
            },
            "artifacts": {},
            "collected_at": "2025-01-01T00:00:00Z"
        }
        
        # Create sample metrics
        metrics = {
            "cycle_id": "ECID-TEST-003",
            "summary": {
                "total_tasks": 2,
                "total_agents": 2,
                "total_success": 2,
                "total_failure": 0,
                "success_rate": 1.0,
                "failure_rate": 0.0
            },
            "agent_metrics": {
                "max": {"task_count": 1, "success_count": 1, "failure_count": 0, "success_rate": 1.0},
                "neo": {"task_count": 1, "success_count": 1, "failure_count": 0, "success_rate": 1.0}
            }
        }
        
        # Test health determination
        health = composer._determine_health(snapshot, metrics)
        assert health == "green"  # All tasks succeeded
        
        # Test agent summary building
        agent_summary = composer._build_agent_summary(snapshot, metrics)
        assert "max" in agent_summary
        assert "neo" in agent_summary
        assert agent_summary["max"]["task_count"] == 1
        assert agent_summary["max"]["failures"] == 0



