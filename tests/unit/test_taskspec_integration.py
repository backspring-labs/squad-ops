"""
Integration tests for TaskSpec flow without full agent initialization.
"""

import pytest
from agents.contracts.task_spec import TaskSpec

def test_max_to_neo_taskspec_handoff():
    """Test the complete Max → Neo TaskSpec handoff flow"""
    
    # Step 1: Max generates TaskSpec from PRD analysis
    max_taskspec = TaskSpec(
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
    
    # Step 2: Max serializes TaskSpec for transmission
    serialized_taskspec = max_taskspec.to_dict()
    
    # Step 3: Neo receives and deserializes TaskSpec
    neo_taskspec = TaskSpec.from_dict(serialized_taskspec)
    
    # Step 4: Verify the handoff worked correctly
    assert neo_taskspec.app_name == "HelloSquad"
    assert neo_taskspec.version == "0.1.4.017"
    assert neo_taskspec.run_id == "ECID-WB-017-test"
    assert "team status dashboard" in neo_taskspec.prd_analysis.lower()
    assert len(neo_taskspec.features) == 6
    assert "dashboard" in neo_taskspec.features
    assert "activity_feed" in neo_taskspec.features
    assert len(neo_taskspec.success_criteria) == 5
    assert "deploys successfully" in neo_taskspec.success_criteria[0]
    
    # Step 5: Verify Neo can use the TaskSpec for AppBuilder
    # (TaskSpec validation is done by BuildManifest, not TaskSpec itself)
    assert neo_taskspec.app_name is not None
    assert neo_taskspec.prd_analysis is not None

def test_neo_fallback_taskspec():
    """Test Neo's fallback TaskSpec when Max doesn't provide one"""
    
    # Simulate Neo receiving task without Max's TaskSpec
    task_requirements = {
        'action': 'build',
        'application': 'TestApp',
        'version': '1.0.0',
        'warm_boot_sequence': '001'
        # No task_spec provided
    }
    
    # Neo creates fallback TaskSpec
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
