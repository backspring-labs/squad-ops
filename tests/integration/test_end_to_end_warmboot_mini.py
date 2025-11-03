"""
End-to-End WarmBoot Integration Test

Tests the complete WarmBoot workflow:
1. Submit WarmBoot request via Task API
2. Verify Max receives and processes PRD
3. Verify Max delegates to Neo
4. Verify Neo generates manifest and files
5. Verify application files are created
6. Check governance artifacts
7. Verify task completion status
"""

import pytest
import asyncio
import json
import os
import tempfile
import time
import requests
from typing import Dict, Any
from pathlib import Path


class TestEndToEndWarmBoot:
    """End-to-end integration tests for WarmBoot workflow."""
    
    @pytest.fixture
    def sample_prd_content(self):
        """Sample PRD content for testing."""
        return """
# HelloSquad Test Application

## Overview
A simple web application for testing SquadOps WarmBoot workflow.

## Core Features
- **Web Interface**: Clean, responsive web application
- **Interactive Elements**: Dynamic content and user interactions
- **API Integration**: RESTful API endpoints for data access

## Technical Requirements
- **Frontend**: HTML5, CSS3, JavaScript (ES6+)
- **Framework**: Vanilla JavaScript (no external frameworks)
- **Styling**: Modern CSS with responsive design
- **Deployment**: Docker container with Nginx

## Success Criteria
- Application loads successfully in browser
- All interactive elements work correctly
- Responsive design works on mobile and desktop
- Application runs in Docker container
- Performance meets requirements (< 2s load time)

## User Stories
1. **As a user**, I want to see a welcoming homepage
2. **As a user**, I want to interact with dynamic content
3. **As a user**, I want the application to work on my mobile device

## Technical Constraints
- Must use vanilla JavaScript (no frameworks)
- Must be deployable via Docker
- Must follow modern web standards
- Must be accessible and responsive
"""
    
    @pytest.fixture
    def warmboot_request_data(self, sample_prd_content):
        """WarmBoot request data for testing."""
        return {
            "application": "HelloSquadTest",
            "request_type": "from_scratch",
            "agents": ["max", "neo"],
            "priority": "HIGH",
            "description": "End-to-end integration test for WarmBoot workflow",
            "requirements": None,
            "prd_content": sample_prd_content.strip()
        }
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_complete_warmboot_workflow(self, integration_config, ensure_agents_running_fixture, warmboot_request_data):
        """Test complete WarmBoot workflow from request to completion."""
        
        # Step 1: Submit WarmBoot request via Task API
        print("🚀 Step 1: Submitting WarmBoot request...")
        
        task_api_url = integration_config['task_api_url']
        submit_url = f"{task_api_url}/warmboot/submit"
        
        try:
            response = requests.post(
                submit_url,
                json=warmboot_request_data,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            response.raise_for_status()
            
            submit_result = response.json()
            assert submit_result.get('status') == 'success'
            run_id = submit_result.get('run_id')
            assert run_id is not None
            
            print(f"✅ WarmBoot request submitted successfully: {run_id}")
            
        except requests.RequestException as e:
            pytest.skip(f"Task API not available: {e}")
        
        # Step 2: Monitor task progress
        print("📊 Step 2: Monitoring task progress...")
        
        max_wait_time = 300  # 5 minutes
        check_interval = 10  # 10 seconds
        start_time = time.time()
        
        tasks_completed = []
        
        while time.time() - start_time < max_wait_time:
            try:
                # Check task status
                status_url = f"{task_api_url}/api/v1/tasks"
                response = requests.get(status_url, timeout=10)
                response.raise_for_status()
                
                tasks = response.json()
                
                # Check for our run_id tasks
                run_tasks = [task for task in tasks if run_id in task.get('task_id', '')]
                
                if run_tasks:
                    print(f"📋 Found {len(run_tasks)} tasks for run {run_id}")
                    
                    for task in run_tasks:
                        task_id = task['task_id']
                        status = task.get('status', 'unknown')
                        
                        if status == 'completed' and task_id not in tasks_completed:
                            tasks_completed.append(task_id)
                            print(f"✅ Task completed: {task_id}")
                
                # Check if all expected tasks are completed
                expected_task_types = ['application-design', 'application-build', 'application-deploy']
                completed_types = set()
                
                for task in run_tasks:
                    task_id = task['task_id']
                    if task_id in tasks_completed:
                        for task_type in expected_task_types:
                            if task_type in task_id:
                                completed_types.add(task_type)
                
                if len(completed_types) >= 2:  # At least design and build
                    print(f"✅ Core tasks completed: {completed_types}")
                    break
                
                print(f"⏳ Waiting for tasks to complete... ({len(tasks_completed)}/{len(run_tasks)})")
                await asyncio.sleep(check_interval)
                
            except requests.RequestException as e:
                print(f"⚠️  Error checking task status: {e}")
                await asyncio.sleep(check_interval)
        
        # Step 3: Verify application files were created
        print("📁 Step 3: Verifying application files...")
        
        app_dir = Path("warm-boot/apps/HelloSquadTest")
        
        if app_dir.exists():
            print(f"✅ Application directory exists: {app_dir}")
            
            # Check for expected files
            expected_files = ['index.html', 'app.js', 'styles.css', 'nginx.conf', 'Dockerfile']
            found_files = []
            
            for file_name in expected_files:
                file_path = app_dir / file_name
                if file_path.exists():
                    found_files.append(file_name)
                    print(f"✅ Found file: {file_name}")
                else:
                    print(f"❌ Missing file: {file_name}")
            
            assert len(found_files) >= 3, f"Expected at least 3 files, found: {found_files}"
            
            # Verify file contents
            if (app_dir / 'index.html').exists():
                html_content = (app_dir / 'index.html').read_text()
                assert '<!DOCTYPE html>' in html_content
                assert '<html' in html_content
                print("✅ HTML file has valid structure")
            
            if (app_dir / 'app.js').exists():
                js_content = (app_dir / 'app.js').read_text()
                assert len(js_content) > 10
                print("✅ JavaScript file has content")
            
            if (app_dir / 'Dockerfile').exists():
                dockerfile_content = (app_dir / 'Dockerfile').read_text()
                assert 'FROM' in dockerfile_content
                assert 'nginx' in dockerfile_content.lower()
                print("✅ Dockerfile has valid structure")
                
        else:
            print(f"❌ Application directory not found: {app_dir}")
            pytest.fail("Application files were not created")
        
        # Step 4: Check governance artifacts
        print("📋 Step 4: Checking governance artifacts...")
        
        # Check for execution cycle in database
        try:
            import asyncpg
            db_url = integration_config['database_url']
            
            async with asyncpg.connect(db_url) as conn:
                # Check execution cycle
                ecid_query = "SELECT * FROM execution_cycles WHERE ecid = $1"
                ecid_result = await conn.fetchrow(ecid_query, run_id)
                
                if ecid_result:
                    print(f"✅ Execution cycle found: {ecid_result['ecid']}")
                    print(f"   Status: {ecid_result['status']}")
                    print(f"   Created: {ecid_result['created_at']}")
                else:
                    print(f"⚠️  Execution cycle not found for: {run_id}")
                
                # Check task logs
                task_logs_query = "SELECT * FROM agent_task_logs WHERE task_id LIKE $1"
                task_logs = await conn.fetch(task_logs_query, f"%{run_id}%")
                
                if task_logs:
                    print(f"✅ Found {len(task_logs)} task log entries")
                    for log in task_logs:
                        print(f"   {log['agent_name']}: {log['task_name']} - {log['task_status']}")
                else:
                    print("⚠️  No task logs found")
                    
        except Exception as e:
            print(f"⚠️  Could not check governance artifacts: {e}")
        
        # Step 5: Verify final status
        print("🎯 Step 5: Verifying final status...")
        
        try:
            # Check final WarmBoot status
            status_url = f"{task_api_url}/warmboot/status/{run_id}"
            response = requests.get(status_url, timeout=10)
            response.raise_for_status()
            
            status_result = response.json()
            print(f"📊 Final WarmBoot status: {status_result}")
            
            # Verify completion
            assert len(tasks_completed) > 0, "No tasks were completed"
            assert app_dir.exists(), "Application directory was not created"
            
            print("🎉 End-to-end WarmBoot test completed successfully!")
            
        except requests.RequestException as e:
            print(f"⚠️  Could not check final status: {e}")
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_warmboot_with_prd_file(self, integration_config, ensure_agents_running_fixture, sample_prd_content):
        """Test WarmBoot workflow with PRD file instead of inline content."""
        
        # Create temporary PRD file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as temp_prd:
            temp_prd.write(sample_prd_content)
            temp_prd_path = temp_prd.name
        
        try:
            # Submit WarmBoot request with PRD file path
            warmboot_data = {
                "application": "HelloSquadFileTest",
                "request_type": "from_scratch",
                "agents": ["max", "neo"],
                "priority": "HIGH",
                "description": "WarmBoot test with PRD file",
                "requirements": None,
                "prd_path": temp_prd_path
            }
            
            task_api_url = integration_config['task_api_url']
            submit_url = f"{task_api_url}/warmboot/submit"
            
            try:
                response = requests.post(
                    submit_url,
                    json=warmboot_data,
                    headers={'Content-Type': 'application/json'},
                    timeout=30
                )
                response.raise_for_status()
                
                submit_result = response.json()
                assert submit_result.get('status') == 'success'
                run_id = submit_result.get('run_id')
                assert run_id is not None
                
                print(f"✅ WarmBoot request with PRD file submitted: {run_id}")
                
                # Wait a bit for processing to start
                await asyncio.sleep(5)
                
                # Check that tasks were created
                status_url = f"{task_api_url}/api/v1/tasks"
                response = requests.get(status_url, timeout=10)
                response.raise_for_status()
                
                tasks = response.json()
                run_tasks = [task for task in tasks if run_id in task.get('task_id', '')]
                
                assert len(run_tasks) > 0, "No tasks were created for the WarmBoot request"
                print(f"✅ Found {len(run_tasks)} tasks created for run {run_id}")
                
            except requests.RequestException as e:
                pytest.skip(f"Task API not available: {e}")
                
        finally:
            # Clean up temporary file
            if os.path.exists(temp_prd_path):
                os.unlink(temp_prd_path)
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_agent_communication_during_warmboot(self, integration_config, ensure_agents_running_fixture):
        """Test that agents can communicate during WarmBoot processing."""
        
        # This test verifies that the agent communication infrastructure
        # is working during actual WarmBoot processing
        
        print("🤖 Testing agent communication during WarmBoot...")
        
        # Submit a simple WarmBoot request
        warmboot_data = {
            "application": "CommTestApp",
            "request_type": "from_scratch",
            "agents": ["max", "neo"],
            "priority": "MEDIUM",
            "description": "Agent communication test",
            "requirements": None,
            "prd_content": """
# Communication Test App

## Overview
Simple app to test agent communication during WarmBoot.

## Features
- Basic web interface
- Simple functionality

## Requirements
- HTML/CSS/JavaScript
- Docker deployment
"""
        }
        
        task_api_url = integration_config['task_api_url']
        submit_url = f"{task_api_url}/warmboot/submit"
        
        try:
            response = requests.post(
                submit_url,
                json=warmboot_data,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            response.raise_for_status()
            
            submit_result = response.json()
            run_id = submit_result.get('run_id')
            
            print(f"✅ Communication test WarmBoot submitted: {run_id}")
            
            # Monitor for a short time to see if agents are processing
            max_wait = 60  # 1 minute
            check_interval = 5
            start_time = time.time()
            
            while time.time() - start_time < max_wait:
                try:
                    status_url = f"{task_api_url}/api/v1/tasks"
                    response = requests.get(status_url, timeout=10)
                    response.raise_for_status()
                    
                    tasks = response.json()
                    run_tasks = [task for task in tasks if run_id in task.get('task_id', '')]
                    
                    if run_tasks:
                        print(f"📋 Found {len(run_tasks)} tasks for communication test")
                        
                        # Check if any tasks are in progress
                        in_progress = [task for task in run_tasks if task.get('status') == 'in_progress']
                        if in_progress:
                            print(f"🔄 {len(in_progress)} tasks in progress - agents are communicating!")
                            break
                        
                        # Check if any tasks are completed
                        completed = [task for task in run_tasks if task.get('status') == 'completed']
                        if completed:
                            print(f"✅ {len(completed)} tasks completed - communication successful!")
                            break
                    
                    await asyncio.sleep(check_interval)
                    
                except requests.RequestException as e:
                    print(f"⚠️  Error checking communication: {e}")
                    await asyncio.sleep(check_interval)
            
            print("✅ Agent communication test completed")
            
        except requests.RequestException as e:
            pytest.skip(f"Task API not available: {e}")

