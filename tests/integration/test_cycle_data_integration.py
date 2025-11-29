"""
Integration test for CycleDataStore and project registry (SIP-0047)
"""

import json
import pytest
import tempfile
from pathlib import Path
import asyncpg

from agents.cycle_data import CycleDataStore
from agents.tasks.sql_adapter import SqlTasksAdapter
from config.unified_config import get_config


@pytest.mark.asyncio
async def test_cycle_data_integration(postgres_container):
    """
    Integration test: Create project, execution cycle, and use CycleDataStore
    """
    # Get database connection
    postgres_url = postgres_container.get_connection_url()
    if postgres_url.startswith('postgresql+psycopg2://'):
        postgres_url = postgres_url.replace('postgresql+psycopg2://', 'postgresql://')
    
    db_pool = await asyncpg.create_pool(postgres_url, min_size=1, max_size=3)
    
    try:
        async with db_pool.acquire() as conn:
            # Create projects table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    project_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT now(),
                    updated_at TIMESTAMP DEFAULT now()
                )
            """)
            
            # Create execution_cycle table with project_id
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS execution_cycle (
                    ecid TEXT PRIMARY KEY,
                    pid TEXT NOT NULL,
                    project_id TEXT REFERENCES projects(project_id),
                    run_type TEXT,
                    title TEXT,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT now(),
                    initiated_by TEXT,
                    status TEXT DEFAULT 'active',
                    notes TEXT
                )
            """)
            
            # Register test project
            await conn.execute("""
                INSERT INTO projects (project_id, name, description)
                VALUES ('test_project', 'Test Project', 'Integration test project')
                ON CONFLICT (project_id) DO NOTHING
            """)
        
        # Create execution cycle with project_id
        adapter = SqlTasksAdapter(db_pool)
        ecid = "ECID-TEST-INTEGRATION-001"
        
        flow = await adapter.create_flow(
            ecid,
            "PID-TEST-001",
            meta={
                "project_id": "test_project",
                "run_type": "project",
                "title": "Integration Test Cycle",
                "description": "Test cycle for integration testing",
                "initiated_by": "test_agent"
            }
        )
        
        assert flow.ecid == ecid
        assert flow.project_id == "test_project"
        
        # Create temporary directory for cycle data
        with tempfile.TemporaryDirectory() as tmpdir:
            cycle_data_root = Path(tmpdir)
            
            # Initialize CycleDataStore
            cycle_store = CycleDataStore(cycle_data_root, "test_project", ecid)
            
            # Write cycle manifest
            manifest = {
                "ecid": ecid,
                "project_id": "test_project",
                "created_at": "2025-01-29T00:00:00Z"
            }
            manifest_json = json.dumps(manifest, indent=2)
            success = cycle_store.write_text_artifact("meta", "cycle_manifest.json", manifest_json)
            assert success is True
            
            # Write shared artifact
            plan_content = "# Test Plan\n\nThis is a test plan."
            success = cycle_store.write_text_artifact("shared", "plan.md", plan_content)
            assert success is True
            
            # Write test artifact
            test_report = {
                "total_tests": 10,
                "passed": 9,
                "failed": 1
            }
            test_json = json.dumps(test_report, indent=2)
            success = cycle_store.write_text_artifact("tests", "test_report.json", test_json)
            assert success is True
            
            # Append telemetry event
            telemetry_event = {
                "timestamp": "2025-01-29T00:00:00Z",
                "event_type": "cycle_start",
                "ecid": ecid
            }
            success = cycle_store.append_telemetry_event(telemetry_event)
            assert success is True
            
            # Verify filesystem structure
            cycle_path = cycle_store.get_cycle_path()
            assert cycle_path.exists()
            assert (cycle_path / "meta").exists()
            assert (cycle_path / "shared").exists()
            assert (cycle_path / "tests").exists()
            assert (cycle_path / "telemetry").exists()
            
            # Verify files can be read back
            read_manifest = cycle_store.read_text_artifact("meta", "cycle_manifest.json")
            assert read_manifest is not None
            assert json.loads(read_manifest)["ecid"] == ecid
            
            read_plan = cycle_store.read_text_artifact("shared", "plan.md")
            assert read_plan == plan_content
            
            read_test = cycle_store.read_text_artifact("tests", "test_report.json")
            assert read_test is not None
            assert json.loads(read_test)["total_tests"] == 10
            
            # Verify telemetry file
            telemetry_file = cycle_path / "telemetry" / "events.jsonl"
            assert telemetry_file.exists()
            lines = telemetry_file.read_text().strip().split('\n')
            assert len(lines) == 1
            assert json.loads(lines[0])["event_type"] == "cycle_start"
            
    finally:
        await db_pool.close()

