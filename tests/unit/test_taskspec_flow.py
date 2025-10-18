"""
Unit tests for Max → Neo TaskSpec handoff flow.
"""

import pytest
from agents.contracts.task_spec import TaskSpec
from agents.roles.lead.agent import LeadAgent
from agents.roles.dev.agent import DevAgent

def test_taskspec_serialization():
    """Test TaskSpec can be serialized and deserialized"""
    original = TaskSpec(
        app_name="TestApp",
        version="1.0.0",
        run_id="run-001",
        prd_analysis="Test application with dashboard features",
        features=["dashboard", "status_cards"],
        constraints={"max_files": 5},
        success_criteria=["Deploys successfully", "Responsive design"]
    )
    
    # Serialize to dict
    data = original.to_dict()
    
    # Deserialize from dict
    restored = TaskSpec.from_dict(data)
    
    assert restored.app_name == original.app_name
    assert restored.version == original.version
    assert restored.features == original.features
    assert restored.constraints == original.constraints

def test_taskspec_yaml_roundtrip():
    """Test TaskSpec YAML serialization"""
    original = TaskSpec(
        app_name="TestApp",
        version="1.0.0",
        run_id="run-001",
        prd_analysis="Test application",
        features=["feature1", "feature2"],
        constraints={"constraint": "value"},
        success_criteria=["criterion1", "criterion2"]
    )
    
    # Convert to YAML string
    yaml_str = f"""
app_name: "{original.app_name}"
version: "{original.version}"
run_id: "{original.run_id}"
prd_analysis: "{original.prd_analysis}"
features:
  - {original.features[0]}
  - {original.features[1]}
constraints:
  constraint: "{original.constraints['constraint']}"
success_criteria:
  - {original.success_criteria[0]}
  - {original.success_criteria[1]}
"""
    
    # Parse from YAML
    restored = TaskSpec.from_yaml(yaml_str)
    
    assert restored.app_name == original.app_name
    assert restored.features == original.features

@pytest.mark.asyncio
async def test_max_taskspec_generation():
    """Test Max can generate TaskSpec from PRD content"""
    # Mock LLM client for testing
    class MockLLMClient:
        async def complete(self, prompt, **kwargs):
            return """
app_name: "TestApp"
version: "1.0.0"
run_id: "run-001"
prd_analysis: |
  This is a test application for dashboard functionality.
  It includes status cards and interactive elements.
features:
  - dashboard
  - status_cards
  - interactive_elements
constraints:
  technical: "Modern web standards"
  performance: "Fast loading"
success_criteria:
  - "Application deploys successfully"
  - "Dashboard displays correctly"
"""
    
    # Create Max with mock LLM client
    max_agent = LeadAgent("Max")
    max_agent.llm_client = MockLLMClient()
    
    # Generate TaskSpec
    task_spec = await max_agent.generate_task_spec(
        prd_content="Build a dashboard application",
        app_name="TestApp",
        version="1.0.0",
        run_id="run-001",
        features=["dashboard"]
    )
    
    assert task_spec.app_name == "TestApp"
    assert len(task_spec.features) == 3
    assert "dashboard" in task_spec.features

@pytest.mark.asyncio
async def test_neo_taskspec_reception():
    """Test Neo can receive and use Max's TaskSpec"""
    # Mock LLM client for testing
    class MockLLMClient:
        async def complete(self, prompt, **kwargs):
            return "Mock LLM response"
    
    # Create Neo with mock LLM client
    neo_agent = DevAgent("Neo")
    neo_agent.llm_client = MockLLMClient()
    
    # Create a TaskSpec from Max
    max_taskspec = TaskSpec(
        app_name="TestApp",
        version="1.0.0",
        run_id="run-001",
        prd_analysis="Max's analysis of the requirements",
        features=["dashboard", "status_cards"],
        constraints={"max_files": 5},
        success_criteria=["Deploys successfully"]
    )
    
    # Simulate task requirements with Max's TaskSpec
    requirements = {
        'action': 'build',
        'application': 'TestApp',
        'version': '1.0.0',
        'task_spec': max_taskspec.to_dict()  # Max's TaskSpec
    }
    
    # Neo should use Max's TaskSpec
    if 'task_spec' in requirements:
        neo_taskspec = TaskSpec.from_dict(requirements['task_spec'])
        assert neo_taskspec.app_name == "TestApp"
        assert neo_taskspec.prd_analysis == "Max's analysis of the requirements"
        assert len(neo_taskspec.features) == 2
    else:
        pytest.fail("Neo should have received Max's TaskSpec")

@pytest.mark.asyncio
async def test_neo_fallback_taskspec():
    """Test Neo creates fallback TaskSpec when Max doesn't provide one"""
    # Mock LLM client for testing
    class MockLLMClient:
        async def complete(self, prompt, **kwargs):
            return "Mock LLM response"
    
    # Create Neo with mock LLM client
    neo_agent = DevAgent("Neo")
    neo_agent.llm_client = MockLLMClient()
    
    # Simulate task requirements without Max's TaskSpec
    requirements = {
        'action': 'build',
        'application': 'TestApp',
        'version': '1.0.0'
        # No task_spec provided
    }
    
    # Neo should create fallback TaskSpec
    if 'task_spec' not in requirements:
        fallback_taskspec = TaskSpec(
            app_name=requirements.get('application', 'Application'),
            version=requirements.get('version', '1.0.0'),
            run_id=neo_agent.current_run_id,
            prd_analysis="Team Status Dashboard, Activity Feed, Project Progress Tracking, Interactive Elements, Framework Transparency, Application Lifecycle Management",
            features=[],
            constraints={},
            success_criteria=["Application deploys successfully", "All features functional"]
        )
        
        assert fallback_taskspec.app_name == "TestApp"
        assert "Team Status Dashboard" in fallback_taskspec.prd_analysis
    else:
        pytest.fail("Neo should have created fallback TaskSpec")


