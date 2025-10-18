"""
Integration tests for manifest-first workflow.
"""

import pytest

@pytest.mark.integration
@pytest.mark.asyncio
async def test_manifest_first_workflow():
    """Integration test: Manifest-first build workflow"""
    from agents.llm.router import LLMRouter
    from agents.roles.dev.app_builder import AppBuilder
    from agents.contracts.task_spec import TaskSpec
    
    router = LLMRouter.from_config('config/llm_config.yaml')
    client = router.get_default_client()
    
    builder = AppBuilder(llm_client=client)
    
    # Create TaskSpec
    task_spec = TaskSpec(
        app_name="TestApp",
        version="0.1.0",
        run_id="test-001",
        prd_analysis="Simple test dashboard with status cards",
        features=["dashboard", "status_display"],
        constraints={},
        success_criteria=["Application deploys"]
    )
    
    # Build from TaskSpec
    result = await builder.build_from_task_spec(task_spec)
    
    # Verify result structure
    assert result['success'] is True
    assert 'manifest' in result
    assert 'files' in result
    
    # Verify manifest
    manifest = result['manifest']
    assert manifest['architecture']['type'] in ['spa_web_app', 'multi_page_app']
    assert len(manifest['files']) > 0
    
    # Verify files generated
    files = result['files']
    assert len(files) >= 3  # At least HTML, CSS, JS
    
    # Verify HTML is clean
    html_file = next((f for f in files if f['file_path'].endswith('index.html')), None)
    assert html_file is not None
    assert '```' not in html_file['content']
    assert html_file['content'].startswith('<!DOCTYPE')


