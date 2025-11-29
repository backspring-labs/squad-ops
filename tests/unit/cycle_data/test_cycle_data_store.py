"""
Unit tests for CycleDataStore (SIP-0047)
"""

import json
import pytest
import tempfile
from pathlib import Path

from agents.cycle_data import CycleDataStore


class TestCycleDataStore:
    """Test CycleDataStore functionality"""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for cycle data"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def cycle_store(self, temp_dir):
        """Create CycleDataStore instance"""
        return CycleDataStore(temp_dir, "test_project", "ECID-TEST-001")
    
    def test_initialization(self, cycle_store, temp_dir):
        """Test CycleDataStore initialization"""
        assert cycle_store.cycle_data_root == temp_dir
        assert cycle_store.project_id == "test_project"
        assert cycle_store.ecid == "ECID-TEST-001"
    
    def test_get_cycle_path(self, cycle_store, temp_dir):
        """Test cycle path resolution"""
        expected_path = temp_dir / "test_project" / "ECID-TEST-001"
        assert cycle_store.get_cycle_path() == expected_path
    
    def test_write_text_artifact(self, cycle_store):
        """Test writing text artifacts"""
        content = "Test content"
        success = cycle_store.write_text_artifact("meta", "test.txt", content)
        
        assert success is True
        file_path = cycle_store.get_cycle_path() / "meta" / "test.txt"
        assert file_path.exists()
        assert file_path.read_text() == content
    
    def test_write_binary_artifact(self, cycle_store):
        """Test writing binary artifacts"""
        data = b"Binary test data"
        success = cycle_store.write_binary_artifact("artifacts", "test.bin", data)
        
        assert success is True
        file_path = cycle_store.get_cycle_path() / "artifacts" / "test.bin"
        assert file_path.exists()
        assert file_path.read_bytes() == data
    
    def test_read_text_artifact(self, cycle_store):
        """Test reading text artifacts"""
        content = "Test content to read"
        cycle_store.write_text_artifact("shared", "read_test.txt", content)
        
        read_content = cycle_store.read_text_artifact("shared", "read_test.txt")
        assert read_content == content
    
    def test_read_binary_artifact(self, cycle_store):
        """Test reading binary artifacts"""
        data = b"Binary data to read"
        cycle_store.write_binary_artifact("artifacts", "read_test.bin", data)
        
        read_data = cycle_store.read_binary_artifact("artifacts", "read_test.bin")
        assert read_data == data
    
    def test_read_missing_artifact(self, cycle_store):
        """Test reading non-existent artifacts"""
        text_result = cycle_store.read_text_artifact("meta", "nonexistent.txt")
        assert text_result is None
        
        binary_result = cycle_store.read_binary_artifact("artifacts", "nonexistent.bin")
        assert binary_result is None
    
    def test_append_telemetry_event(self, cycle_store):
        """Test appending telemetry events"""
        event1 = {"timestamp": "2025-01-01T00:00:00Z", "event": "start"}
        event2 = {"timestamp": "2025-01-01T00:01:00Z", "event": "end"}
        
        success1 = cycle_store.append_telemetry_event(event1)
        success2 = cycle_store.append_telemetry_event(event2)
        
        assert success1 is True
        assert success2 is True
        
        telemetry_file = cycle_store.get_cycle_path() / "telemetry" / "events.jsonl"
        assert telemetry_file.exists()
        
        lines = telemetry_file.read_text().strip().split('\n')
        assert len(lines) == 2
        assert json.loads(lines[0]) == event1
        assert json.loads(lines[1]) == event2
    
    def test_append_telemetry_with_agent(self, cycle_store):
        """Test appending agent-specific telemetry"""
        event = {"timestamp": "2025-01-01T00:00:00Z", "agent": "neo", "event": "task_complete"}
        
        success = cycle_store.append_telemetry_event(event, agent_name="neo")
        assert success is True
        
        telemetry_file = cycle_store.get_cycle_path() / "telemetry" / "neo" / "neo.jsonl"
        assert telemetry_file.exists()
    
    def test_directory_structure_creation(self, cycle_store):
        """Test that directory structure is created on first write"""
        # Directory shouldn't exist yet
        cycle_path = cycle_store.get_cycle_path()
        assert not cycle_path.exists()
        
        # Write something to trigger directory creation
        cycle_store.write_text_artifact("meta", "test.txt", "content")
        
        # Now all directories should exist
        assert (cycle_path / "meta").exists()
        assert (cycle_path / "shared").exists()
        assert (cycle_path / "agents").exists()
        assert (cycle_path / "artifacts").exists()
        assert (cycle_path / "tests").exists()
        assert (cycle_path / "telemetry").exists()
    
    def test_invalid_area(self, cycle_store):
        """Test that invalid areas raise ValueError"""
        with pytest.raises(ValueError, match="Invalid area"):
            cycle_store.write_text_artifact("invalid_area", "test.txt", "content")
    
    def test_nested_paths(self, cycle_store):
        """Test writing artifacts with nested paths"""
        content = "Nested content"
        success = cycle_store.write_text_artifact("artifacts", "nested/path/file.txt", content)
        
        assert success is True
        file_path = cycle_store.get_cycle_path() / "artifacts" / "nested" / "path" / "file.txt"
        assert file_path.exists()
        assert file_path.read_text() == content
    
    def test_agent_specific_area(self, cycle_store):
        """Test writing to agent-specific areas"""
        content = "Agent-specific content"
        success = cycle_store.write_text_artifact("agents", "notes.md", content, agent_name="neo")
        
        assert success is True
        file_path = cycle_store.get_cycle_path() / "agents" / "neo" / "notes.md"
        assert file_path.exists()
        assert file_path.read_text() == content

