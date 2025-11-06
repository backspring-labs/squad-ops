"""
Integration tests for Lead Agent -> Dev Agent task delegation workflow.
Tests the complete workflow from design manifest completion to build task delegation.

This test would have caught the bug where Lead Agent wasn't passing the manifest to Dev Agent's build task.
"""

import pytest
import asyncio
from typing import Dict, Any
from agents.roles.lead.agent import LeadAgent
from agents.roles.dev.agent import DevAgent
from base_agent import AgentMessage


@pytest.mark.integration
@pytest.mark.asyncio
async def test_design_manifest_to_build_task_delegation(integration_config, clean_database):
    """
    Test that when Lead Agent receives design manifest completion, it properly delegates
    the build task WITH the manifest included.
    
    This test would have caught the bug where manifest was None in build task requirements.
    """
    lead_agent = LeadAgent("lead-agent")
    dev_agent = DevAgent("dev-agent")
    
    # Create a mock design manifest completion message
    mock_manifest = {
        'architecture': {
            'type': 'spa_web_app',
            'framework': 'vanilla_js'
        },
        'files': [
            {'path': 'index.html', 'purpose': 'Main HTML', 'dependencies': []},
            {'path': 'app.js', 'purpose': 'JS functionality', 'dependencies': ['index.html']}
        ],
        'deployment': {'container': 'nginx:alpine', 'port': 80}
    }
    
    # Create a mock task creation first (simulating what happens in process_prd_request)
    ecid = "TEST-ECID-001"
    tasks = await lead_agent.create_development_tasks(
        prd_analysis={'core_features': ['Feature1'], 'technical_requirements': []},
        app_name="TestApp",
        ecid=ecid
    )
    
    # Find the build task
    build_task = next((t for t in tasks if t.get('requirements', {}).get('action') == 'build'), None)
    assert build_task is not None, "Build task should be created"
    
    # Verify build task initially has manifest=None (as designed)
    assert build_task['requirements'].get('manifest') is None, "Build task should start with manifest=None"
    
    # Create design manifest completion message
    design_completion_message = AgentMessage(
        sender="dev-agent",
        recipient="lead-agent",
        message_type="task.developer.completed",
        payload={
            'task_id': 'test-design-task',
            'status': 'completed',
            'manifest': mock_manifest,
            'created_files': ['index.html', 'app.js']
        },
        context={'ecid': ecid}
    )
    
    # Simulate Lead Agent receiving design manifest completion
    await lead_agent.handle_developer_completion(design_completion_message)
    
    # Verify Lead Agent stored the manifest
    assert lead_agent.warmboot_state.get('manifest') == mock_manifest, "Lead Agent should store manifest"
    
    # Now verify that when Lead Agent delegates the build task, it includes the manifest
    # This requires checking the actual delegation logic
    
    # Mock the task API to return our build task
    import aiohttp
    from unittest.mock import patch, AsyncMock
    
    with patch('aiohttp.ClientSession') as mock_session:
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=[build_task])
        
        mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_resp
        
        # Call the delegation method
        await lead_agent._delegate_build_task_with_manifest(ecid, mock_manifest)
        
        # Verify the build task was updated with manifest
        assert build_task['requirements']['manifest'] == mock_manifest, \
            "Build task should have manifest after delegation"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_build_task_received_with_manifest(integration_config, clean_database):
    """
    Test that Dev Agent can successfully process a build task when it includes a manifest.
    
    This test verifies Dev Agent's build task handler works correctly with a valid manifest.
    """
    dev_agent = DevAgent("dev-agent")
    
    # Create a build task with a valid manifest
    mock_manifest = {
        'architecture': {
            'type': 'spa_web_app',
            'framework': 'vanilla_js'
        },
        'files': [
            {'path': 'index.html', 'purpose': 'Main HTML', 'dependencies': []}
        ],
        'deployment': {'container': 'nginx:alpine', 'port': 80}
    }
    
    build_task = {
        'task_id': 'test-build-task',
        'task_type': 'development',
        'ecid': 'TEST-ECID-001',
        'requirements': {
            'action': 'build',
            'application': 'TestApp',
            'version': '1.0.0',
            'manifest': mock_manifest,  # This is what was missing!
            'warm_boot_sequence': 'run-001',
            'features': [],
            'target_directory': 'warm-boot/apps/testapp/'
        }
    }
    
    # Mock file_manager to return True for directory_exists (files already created)
    from unittest.mock import AsyncMock, patch
    with patch.object(dev_agent.file_manager, 'directory_exists', return_value=True):
        with patch.object(dev_agent.file_manager, 'list_files', return_value=['index.html', 'app.js']):
            # Mock docker_manager to return success
            with patch.object(dev_agent.docker_manager, 'build_image', return_value={
                'status': 'success',
                'image_name': 'testapp',
                'version': '1.0.0'
            }):
                # Process the build task
                result = await dev_agent.process_task(build_task)
                
                # Verify build succeeded
                assert result['status'] == 'completed', \
                    f"Build task should succeed with manifest, got: {result.get('error', 'no error')}"
                assert result['action'] == 'build'
                assert 'image' in result


@pytest.mark.integration
@pytest.mark.asyncio
async def test_build_task_fails_without_manifest(integration_config, clean_database):
    """
    Test that Dev Agent correctly rejects a build task without a manifest.
    
    This test verifies Dev Agent's error handling for missing manifest.
    """
    dev_agent = DevAgent("dev-agent")
    
    # Create a build task WITHOUT a manifest (the bug scenario)
    build_task = {
        'task_id': 'test-build-task',
        'task_type': 'development',
        'ecid': 'TEST-ECID-001',
        'requirements': {
            'action': 'build',
            'application': 'TestApp',
            'version': '1.0.0',
            'manifest': None,  # This is the bug!
            'warm_boot_sequence': 'run-001',
            'features': []
        }
    }
    
    # Process the build task
    result = await dev_agent.process_task(build_task)
    
    # Verify build task correctly rejects it
    assert result['status'] == 'error', \
        "Build task should fail when manifest is None"
    assert 'manifest' in result.get('error', '').lower() or \
           'missing' in result.get('error', '').lower(), \
        f"Error should mention manifest: {result.get('error')}"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_end_to_end_design_to_build_workflow(integration_config, clean_database, ensure_agents_running_fixture):
    """
    End-to-end test: Design manifest -> Build task delegation -> Build success.
    
    This integration test would catch the entire bug chain:
    1. Lead Agent creates tasks with manifest=None for build
    2. Dev Agent completes design manifest task
    3. Lead Agent receives completion and should delegate build task WITH manifest
    4. Dev Agent receives build task and should successfully build
    """
    # This would require:
    # - Real agents communicating via RabbitMQ
    # - Real task API
    # - Mocked file operations and Docker (for speed)
    # - Full message flow verification
    
    pytest.skip("End-to-end test requires full agent orchestration - implement as WarmBoot test")

