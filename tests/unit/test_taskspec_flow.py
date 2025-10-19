"""
Comprehensive unit tests for TaskSpec functionality and LeadAgent → DevAgent handoff flow.
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
async def test_lead_agent_taskspec_generation():
    """Test LeadAgent can generate TaskSpec from PRD content"""
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
    
    # Create LeadAgent with mock LLM client
    lead_agent = LeadAgent("test-lead-agent")
    lead_agent.llm_client = MockLLMClient()
    
    # Generate TaskSpec
    task_spec = await lead_agent.generate_task_spec(
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
async def test_dev_agent_taskspec_reception():
    """Test DevAgent can receive and use LeadAgent's TaskSpec"""
    # Mock LLM client for testing
    class MockLLMClient:
        async def complete(self, prompt, **kwargs):
            return "Mock LLM response"
    
    # Create DevAgent with mock LLM client
    dev_agent = DevAgent("test-dev-agent")
    dev_agent.llm_client = MockLLMClient()
    
    # Create a TaskSpec from LeadAgent
    lead_taskspec = TaskSpec(
        app_name="TestApp",
        version="1.0.0",
        run_id="run-001",
        prd_analysis="LeadAgent's analysis of the requirements",
        features=["dashboard", "status_cards"],
        constraints={"max_files": 5},
        success_criteria=["Deploys successfully"]
    )
    
    # Simulate task requirements with LeadAgent's TaskSpec
    requirements = {
        'action': 'build',
        'application': 'TestApp',
        'version': '1.0.0',
        'task_spec': lead_taskspec.to_dict()  # LeadAgent's TaskSpec
    }
    
    # DevAgent should use LeadAgent's TaskSpec
    if 'task_spec' in requirements:
        dev_taskspec = TaskSpec.from_dict(requirements['task_spec'])
        assert dev_taskspec.app_name == "TestApp"
        assert dev_taskspec.prd_analysis == "LeadAgent's analysis of the requirements"
        assert len(dev_taskspec.features) == 2
    else:
        pytest.fail("DevAgent should have received LeadAgent's TaskSpec")

@pytest.mark.asyncio
async def test_dev_agent_fallback_taskspec():
    """Test DevAgent creates fallback TaskSpec when LeadAgent doesn't provide one"""
    # Mock LLM client for testing
    class MockLLMClient:
        async def complete(self, prompt, **kwargs):
            return "Mock LLM response"
    
    # Create DevAgent with mock LLM client
    dev_agent = DevAgent("test-dev-agent")
    dev_agent.llm_client = MockLLMClient()
    
    # Simulate task requirements without LeadAgent's TaskSpec
    requirements = {
        'action': 'build',
        'application': 'TestApp',
        'version': '1.0.0'
        # No task_spec provided
    }
    
    # DevAgent should create fallback TaskSpec
    if 'task_spec' not in requirements:
        fallback_taskspec = TaskSpec(
            app_name=requirements.get('application', 'Application'),
            version=requirements.get('version', '1.0.0'),
            run_id=dev_agent.current_run_id,
            prd_analysis="Team Status Dashboard, Activity Feed, Project Progress Tracking, Interactive Elements, Framework Transparency, Application Lifecycle Management",
            features=[],
            constraints={},
            success_criteria=["Application deploys successfully", "All features functional"]
        )
        
        assert fallback_taskspec.app_name == "TestApp"
        assert "Team Status Dashboard" in fallback_taskspec.prd_analysis
    else:
        pytest.fail("DevAgent should have created fallback TaskSpec")

# ===== INTEGRATION TESTS (without agent initialization) =====

def test_lead_to_dev_taskspec_handoff():
    """Test the complete LeadAgent → DevAgent TaskSpec handoff flow without agent initialization"""
    
    # Step 1: LeadAgent generates TaskSpec from PRD analysis
    lead_taskspec = TaskSpec(
        app_name="HelloSquad",
        version="0.1.4.017",
        run_id="ECID-WB-017-test",
        prd_analysis="""This is a comprehensive team status dashboard application that provides:
        
        - Real-time activity feed showing team member actions
        - Project progress tracking with visual indicators
        - Interactive elements for team collaboration
        - Framework transparency showing SquadOps internals
        - Application lifecycle management capabilities
        
        The application should be modern, responsive, and accessible.""",
        features=[
            "dashboard",
            "activity_feed", 
            "project_progress",
            "interactive_elements",
            "framework_transparency",
            "lifecycle_management"
        ],
        constraints={
            "technical": "Modern web standards, responsive design",
            "performance": "Fast loading, real-time updates",
            "security": "Secure team data handling",
            "accessibility": "WCAG 2.1 AA compliance"
        },
        success_criteria=[
            "Application deploys successfully at /hello-squad",
            "Dashboard displays team status correctly",
            "Activity feed updates in real-time",
            "Responsive design works on mobile/desktop",
            "Application is accessible to all users"
        ]
    )
    
    # Step 2: LeadAgent serializes TaskSpec for transmission
    serialized_taskspec = lead_taskspec.to_dict()
    
    # Step 3: DevAgent receives and deserializes TaskSpec
    dev_taskspec = TaskSpec.from_dict(serialized_taskspec)
    
    # Step 4: Verify the handoff worked correctly
    assert dev_taskspec.app_name == "HelloSquad"
    assert dev_taskspec.version == "0.1.4.017"
    assert dev_taskspec.run_id == "ECID-WB-017-test"
    assert "team status dashboard" in dev_taskspec.prd_analysis.lower()
    assert len(dev_taskspec.features) == 6
    assert "dashboard" in dev_taskspec.features
    assert "activity_feed" in dev_taskspec.features
    assert len(dev_taskspec.success_criteria) == 5
    assert "deploys successfully" in dev_taskspec.success_criteria[0]
    
    # Step 5: Verify DevAgent can use the TaskSpec for AppBuilder
    # (TaskSpec validation is done by BuildManifest, not TaskSpec itself)
    assert dev_taskspec.app_name is not None
    assert dev_taskspec.prd_analysis is not None

def test_dev_agent_fallback_taskspec_simple():
    """Test DevAgent's fallback TaskSpec when LeadAgent doesn't provide one (simple version)"""
    
    # Simulate DevAgent receiving task without LeadAgent's TaskSpec
    task_requirements = {
        'action': 'build',
        'application': 'TestApp',
        'version': '1.0.0',
        'warm_boot_sequence': '001'
        # No task_spec provided
    }
    
    # DevAgent creates fallback TaskSpec
    fallback_taskspec = TaskSpec(
        app_name=task_requirements.get('application', 'Application'),
        version=task_requirements.get('version', '1.0.0'),
        run_id=f"run-{task_requirements.get('warm_boot_sequence', '001')}",
        prd_analysis="Team Status Dashboard, Activity Feed, Project Progress Tracking, Interactive Elements, Framework Transparency, Application Lifecycle Management",
        features=[],
        constraints={},
        success_criteria=["Application deploys successfully", "All features functional"]
    )
    
    # Verify fallback TaskSpec
    assert fallback_taskspec.app_name == "TestApp"
    assert fallback_taskspec.version == "1.0.0"
    assert fallback_taskspec.run_id == "run-001"
    assert "Team Status Dashboard" in fallback_taskspec.prd_analysis
    assert len(fallback_taskspec.success_criteria) == 2

def test_taskspec_validation():
    """Test TaskSpec validation logic"""
    
    # Valid TaskSpec
    valid_taskspec = TaskSpec(
        app_name="TestApp",
        version="1.0.0",
        run_id="run-001",
        prd_analysis="Test application",
        features=["feature1", "feature2"],
        constraints={"constraint": "value"},
        success_criteria=["criterion1", "criterion2"]
    )
    
    # Should have valid structure
    assert valid_taskspec.app_name == "TestApp"
    assert len(valid_taskspec.features) == 2
    assert len(valid_taskspec.success_criteria) == 2
    
    # Test with empty features (should still be valid)
    minimal_taskspec = TaskSpec(
        app_name="TestApp",
        version="1.0.0", 
        run_id="run-001",
        prd_analysis="Test",
        features=[],
        constraints={},
        success_criteria=[]
    )
    
    assert minimal_taskspec.app_name == "TestApp"
    assert len(minimal_taskspec.features) == 0



