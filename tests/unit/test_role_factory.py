import pytest
import yaml
import tempfile
import os
from unittest.mock import patch, mock_open
from agents.factory.role_factory import RoleFactory, RoleDefinition

class TestRoleFactory:
    """Test RoleFactory core functionality"""
    
    @pytest.mark.unit
    def test_role_factory_initialization(self):
        """Test RoleFactory initialization"""
        with patch('builtins.open', mock_open(read_data='roles:\n  test:\n    display_name: Test Role')):
            factory = RoleFactory("test_registry.yaml")
            
            assert factory.registry_file == "test_registry.yaml"
            assert factory.roles is not None
    
    @pytest.mark.unit
    def test_load_roles_from_yaml(self):
        """Test loading roles from YAML registry"""
        test_yaml = """
roles:
  lead:
    display_name: Lead Agent
    agent_type: governance
    reasoning_style: governance
    capabilities: ["task_delegation", "prd_analysis"]
    task_types: ["governance", "coordination"]
    metrics:
      efficiency: "tasks_delegated_per_hour"
      quality: "approval_rate"
    description: "Lead agent for governance and coordination"
  
  dev:
    display_name: Development Agent
    agent_type: code
    reasoning_style: deductive
    capabilities: ["code_generation", "testing"]
    task_types: ["development", "debugging"]
    metrics:
      efficiency: "lines_of_code_per_hour"
      quality: "test_coverage"
    description: "Development agent for coding tasks"
"""
        
        with patch('builtins.open', mock_open(read_data=test_yaml)):
            factory = RoleFactory("test_registry.yaml")
            
            assert len(factory.roles) == 2
            assert 'lead' in factory.roles
            assert 'dev' in factory.roles
            
            # Test lead role
            lead_role = factory.roles['lead']
            assert lead_role.name == 'lead'
            assert lead_role.display_name == 'Lead Agent'
            assert lead_role.agent_type == 'governance'
            assert lead_role.reasoning_style == 'governance'
            assert 'task_delegation' in lead_role.capabilities
            assert 'governance' in lead_role.task_types
            
            # Test dev role
            dev_role = factory.roles['dev']
            assert dev_role.name == 'dev'
            assert dev_role.display_name == 'Development Agent'
            assert dev_role.agent_type == 'code'
            assert dev_role.reasoning_style == 'deductive'
            assert 'code_generation' in dev_role.capabilities
            assert 'development' in dev_role.task_types
    
    @pytest.mark.unit
    def test_load_roles_with_defaults(self):
        """Test loading roles with default values"""
        test_yaml = """
roles:
  minimal:
    description: "Minimal role definition"
"""
        
        with patch('builtins.open', mock_open(read_data=test_yaml)):
            factory = RoleFactory("test_registry.yaml")
            
            minimal_role = factory.roles['minimal']
            assert minimal_role.name == 'minimal'
            assert minimal_role.display_name == 'Minimal'  # Default from name.title()
            assert minimal_role.agent_type == 'minimal'  # Default from name
            assert minimal_role.reasoning_style == 'logical'  # Default
            assert minimal_role.capabilities == []  # Default empty list
            assert minimal_role.task_types == []  # Default empty list
            assert minimal_role.metrics == {}  # Default empty dict
            assert minimal_role.description == 'Minimal role definition'
    
    @pytest.mark.unit
    def test_get_role(self):
        """Test getting a specific role"""
        test_yaml = """
roles:
  lead:
    display_name: Lead Agent
    agent_type: governance
    reasoning_style: governance
    capabilities: ["task_delegation"]
    task_types: ["governance"]
    metrics:
      efficiency: "tasks_per_hour"
    description: "Lead agent"
"""
        
        with patch('builtins.open', mock_open(read_data=test_yaml)):
            factory = RoleFactory("test_registry.yaml")
            
            role = factory.get_role('lead')
            assert role is not None
            assert role.name == 'lead'
            assert role.display_name == 'Lead Agent'
            
            # Test non-existent role
            non_existent = factory.get_role('non_existent')
            assert non_existent is None
    
    @pytest.mark.unit
    def test_get_all_roles(self):
        """Test getting all roles"""
        test_yaml = """
roles:
  lead:
    display_name: Lead Agent
    agent_type: governance
    reasoning_style: governance
    capabilities: ["task_delegation"]
    task_types: ["governance"]
    metrics: {}
    description: "Lead agent"
  
  dev:
    display_name: Dev Agent
    agent_type: code
    reasoning_style: deductive
    capabilities: ["coding"]
    task_types: ["development"]
    metrics: {}
    description: "Dev agent"
"""
        
        with patch('builtins.open', mock_open(read_data=test_yaml)):
            factory = RoleFactory("test_registry.yaml")
            
            roles = factory.get_all_roles()
            assert len(roles) == 2
            assert 'lead' in roles
            assert 'dev' in roles
    
    @pytest.mark.unit
    def test_generate_agent_class(self):
        """Test generating agent class code"""
        test_yaml = """
roles:
  lead:
    display_name: Lead Agent
    agent_type: governance
    reasoning_style: governance
    capabilities: ["task_delegation"]
    task_types: ["governance"]
    metrics: {}
    description: "Lead agent"
"""
        
        template_content = """
class {{CLASS_NAME}}(BaseAgent):
    def __init__(self, identity: str):
        super().__init__(
            name=identity,
            agent_type="{{AGENT_TYPE}}",
            reasoning_style="{{REASONING_STYLE}}"
        )
        # {{DESCRIPTION}}
"""
        
        with patch('builtins.open', mock_open(read_data=test_yaml)):
            factory = RoleFactory("test_registry.yaml")
            
            with patch('pathlib.Path.exists', return_value=True), \
                 patch('builtins.open', mock_open(read_data=template_content)):
                
                agent_code = factory.generate_agent_class('lead')
                
                assert 'class LeadAgent(BaseAgent):' in agent_code
                assert 'agent_type="governance"' in agent_code
                assert 'reasoning_style="governance"' in agent_code
                assert '# Lead agent' in agent_code
    
    @pytest.mark.unit
    def test_generate_config(self):
        """Test generating config file"""
        test_yaml = """
roles:
  lead:
    display_name: Lead Agent
    agent_type: governance
    reasoning_style: governance
    capabilities: ["task_delegation", "coordination"]
    task_types: ["governance"]
    metrics: {}
    description: "Lead agent"
"""
        
        template_content = """
ROLE_NAME = "{{ROLE_NAME}}"
DISPLAY_NAME = "{{DISPLAY_NAME}}"
AGENT_TYPE = "{{AGENT_TYPE}}"
REASONING_STYLE = "{{REASONING_STYLE}}"
CAPABILITIES = {{CAPABILITIES}}
TASK_TYPES = {{TASK_TYPES}}
"""
        
        with patch('builtins.open', mock_open(read_data=test_yaml)):
            factory = RoleFactory("test_registry.yaml")
            
            with patch('pathlib.Path.exists', return_value=True), \
                 patch('builtins.open', mock_open(read_data=template_content)):
                
                config_code = factory.generate_config('lead')
                
                assert 'ROLE_NAME = "lead"' in config_code
                assert 'DISPLAY_NAME = "Lead Agent"' in config_code
                assert 'AGENT_TYPE = "governance"' in config_code
                assert 'REASONING_STYLE = "governance"' in config_code
                assert '"task_delegation"' in config_code
                assert '"coordination"' in config_code
    
    @pytest.mark.unit
    def test_generate_dockerfile(self):
        """Test generating Dockerfile"""
        test_yaml = """
roles:
  lead:
    display_name: Lead Agent
    agent_type: governance
    reasoning_style: governance
    capabilities: ["task_delegation"]
    task_types: ["governance"]
    metrics: {}
    description: "Lead agent"
"""
        
        template_content = """
FROM python:3.9-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
CMD ["python", "{{ROLE_NAME}}_agent.py"]
"""
        
        with patch('builtins.open', mock_open(read_data=test_yaml)):
            factory = RoleFactory("test_registry.yaml")
            
            with patch('pathlib.Path.exists', return_value=True), \
                 patch('builtins.open', mock_open(read_data=template_content)):
                
                dockerfile = factory.generate_dockerfile('lead')
                
                assert 'FROM python:3.9-slim' in dockerfile
                assert 'CMD ["python", "lead_agent.py"]' in dockerfile
    
    @pytest.mark.unit
    def test_generate_agent_class_non_existent_role(self):
        """Test generating agent class for non-existent role"""
        test_yaml = """
roles:
  lead:
    display_name: Lead Agent
    agent_type: governance
    reasoning_style: governance
    capabilities: ["task_delegation"]
    task_types: ["governance"]
    metrics: {}
    description: "Lead agent"
"""
        
        with patch('builtins.open', mock_open(read_data=test_yaml)):
            factory = RoleFactory("test_registry.yaml")
            
            with pytest.raises(ValueError, match="Role 'non_existent' not found in registry"):
                factory.generate_agent_class('non_existent')
    
    @pytest.mark.unit
    def test_file_not_found_error(self):
        """Test handling of missing registry file"""
        with patch('builtins.open', side_effect=FileNotFoundError("File not found")):
            factory = RoleFactory("non_existent.yaml")
            
            # Should handle gracefully and return empty roles
            assert factory.roles == {}
    
    @pytest.mark.unit
    def test_yaml_parse_error(self):
        """Test handling of YAML parse errors"""
        with patch('builtins.open', mock_open(read_data='invalid: yaml: content: [')):
            factory = RoleFactory("invalid.yaml")
            
            # Should handle gracefully and return empty roles
            assert factory.roles == {}
    
    @pytest.mark.unit
    def test_generate_agent_class_template_not_found(self):
        """Test generating agent class when template file is missing"""
        test_yaml = """
roles:
  lead:
    display_name: Lead Agent
    agent_type: governance
    reasoning_style: governance
    capabilities: ["task_delegation"]
    task_types: ["governance"]
    metrics: {}
    description: "Lead agent"
"""
        
        with patch('builtins.open', mock_open(read_data=test_yaml)):
            factory = RoleFactory("test_registry.yaml")
            
            with patch('pathlib.Path.exists', return_value=False):
                with pytest.raises(FileNotFoundError, match="Agent template not found"):
                    factory.generate_agent_class('lead')
    
    @pytest.mark.unit
    def test_generate_config_template_not_found(self):
        """Test generating config when template file is missing"""
        test_yaml = """
roles:
  lead:
    display_name: Lead Agent
    agent_type: governance
    reasoning_style: governance
    capabilities: ["task_delegation"]
    task_types: ["governance"]
    metrics: {}
    description: "Lead agent"
"""
        
        with patch('builtins.open', mock_open(read_data=test_yaml)):
            factory = RoleFactory("test_registry.yaml")
            
            with patch('pathlib.Path.exists', return_value=False):
                with pytest.raises(FileNotFoundError, match="Config template not found"):
                    factory.generate_config('lead')
    
    @pytest.mark.unit
    def test_generate_config_non_existent_role(self):
        """Test generating config for non-existent role"""
        test_yaml = """
roles:
  lead:
    display_name: Lead Agent
    agent_type: governance
    reasoning_style: governance
    capabilities: ["task_delegation"]
    task_types: ["governance"]
    metrics: {}
    description: "Lead agent"
"""
        
        with patch('builtins.open', mock_open(read_data=test_yaml)):
            factory = RoleFactory("test_registry.yaml")
            
            with pytest.raises(ValueError, match="Role 'non_existent' not found in registry"):
                factory.generate_config('non_existent')
    
    @pytest.mark.unit
    def test_generate_dockerfile_template_not_found(self):
        """Test generating Dockerfile when template is missing"""
        test_yaml = """
roles:
  lead:
    display_name: Lead Agent
    agent_type: governance
    reasoning_style: governance
    capabilities: ["task_delegation"]
    task_types: ["governance"]
    metrics: {}
    description: "Lead agent"
"""
        
        with patch('builtins.open', mock_open(read_data=test_yaml)):
            factory = RoleFactory("test_registry.yaml")
            
            with patch('pathlib.Path.exists', return_value=False):
                with pytest.raises(FileNotFoundError, match="Dockerfile template not found"):
                    factory.generate_dockerfile('lead')
    
    @pytest.mark.unit
    def test_dependency_injection_custom_file_reader(self):
        """Test using custom file reader for dependency injection"""
        test_yaml = """
roles:
  test:
    display_name: Test Role
    agent_type: test
    reasoning_style: test
    capabilities: []
    task_types: []
    metrics: {}
    description: "Test role"
"""
        
        def mock_file_reader(path):
            return test_yaml
        
        factory = RoleFactory("test_registry.yaml", file_reader=mock_file_reader)
        
        assert len(factory.roles) == 1
        assert 'test' in factory.roles
        test_role = factory.roles['test']
        assert test_role.display_name == "Test Role"
    
    @pytest.mark.unit
    def test_empty_yaml_file(self):
        """Test loading from empty YAML file"""
        with patch('builtins.open', mock_open(read_data='')):
            factory = RoleFactory("empty.yaml")
            
            # Should handle gracefully
            assert factory.roles == {}
    
    @pytest.mark.unit
    def test_yaml_with_no_roles_key(self):
        """Test loading YAML without 'roles' key"""
        test_yaml = """
other_config:
  value: test
"""
        
        with patch('builtins.open', mock_open(read_data=test_yaml)):
            factory = RoleFactory("test.yaml")
            
            # Should handle gracefully
            assert factory.roles == {}
    
    @pytest.mark.unit
    def test_generate_config_with_empty_capabilities(self):
        """Test generating config with empty capabilities and task_types lists"""
        test_yaml = """
roles:
  minimal:
    display_name: Minimal Agent
    agent_type: minimal
    reasoning_style: logical
    capabilities: []
    task_types: []
    metrics: {}
    description: "Minimal agent"
"""
        
        template_content = """
CAPABILITIES = {{CAPABILITIES}}
TASK_TYPES = {{TASK_TYPES}}
"""
        
        with patch('builtins.open', mock_open(read_data=test_yaml)):
            factory = RoleFactory("test_registry.yaml")
            
            with patch('pathlib.Path.exists', return_value=True), \
                 patch('builtins.open', mock_open(read_data=template_content)):
                
                config_code = factory.generate_config('minimal')
                
                # Should generate empty lists properly
                assert '[\n    \n]' in config_code or '[]' in config_code
    
    @pytest.mark.unit
    def test_create_role_files(self):
        """Test creating all role files"""
        test_yaml = """
roles:
  test:
    display_name: Test Agent
    agent_type: test
    reasoning_style: logical
    capabilities: ["testing"]
    task_types: ["test"]
    metrics: {}
    description: "Test agent"
"""
        
        template_content = "test template"
        
        with patch('builtins.open', mock_open(read_data=test_yaml)):
            factory = RoleFactory("test_registry.yaml")
            
            with patch('pathlib.Path.mkdir') as mock_mkdir, \
                 patch('pathlib.Path.exists', return_value=True), \
                 patch('builtins.open', mock_open(read_data=template_content)) as mock_file, \
                 patch('shutil.copy') as mock_copy:
                
                factory.create_role_files('test', 'output/test')
                
                # Verify directory was created
                mock_mkdir.assert_called()
                
                # Verify files were written
                # Mock open is called multiple times, so we just check it was called
                assert mock_file.call_count > 0
    
    @pytest.mark.unit
    def test_create_role_files_default_output_dir(self):
        """Test creating role files with default output directory"""
        test_yaml = """
roles:
  test:
    display_name: Test Agent
    agent_type: test
    reasoning_style: logical
    capabilities: ["testing"]
    task_types: ["test"]
    metrics: {}
    description: "Test agent"
"""
        
        template_content = "test template"
        
        with patch('builtins.open', mock_open(read_data=test_yaml)):
            factory = RoleFactory("test_registry.yaml")
            
            with patch('pathlib.Path.mkdir') as mock_mkdir, \
                 patch('pathlib.Path.exists', return_value=True), \
                 patch('builtins.open', mock_open(read_data=template_content)), \
                 patch('shutil.copy'):
                
                factory.create_role_files('test')
                
                # Verify mkdir was called with default path
                mock_mkdir.assert_called()
    
    @pytest.mark.unit
    def test_create_role_files_without_requirements(self):
        """Test creating role files when requirements.txt doesn't exist"""
        test_yaml = """
roles:
  test:
    display_name: Test Agent
    agent_type: test
    reasoning_style: logical
    capabilities: ["testing"]
    task_types: ["test"]
    metrics: {}
    description: "Test agent"
"""
        
        template_content = "test template"
        
        with patch('builtins.open', mock_open(read_data=test_yaml)):
            factory = RoleFactory("test_registry.yaml")
            
            # Mock Path.exists to return True for templates, False for requirements.txt
            def mock_exists(self):
                path_str = str(self)
                if 'requirements.txt' in path_str:
                    return False
                return True  # Templates exist
            
            with patch('pathlib.Path.mkdir'), \
                 patch('pathlib.Path.exists', mock_exists), \
                 patch('builtins.open', mock_open(read_data=template_content)):
                
                # Should not raise an error even if requirements.txt doesn't exist
                factory.create_role_files('test', 'output/test')
    
    @pytest.mark.unit
    def test_validate_role_registry_success(self):
        """Test successful role registry validation"""
        test_yaml = """
roles:
  test:
    display_name: Test Agent
    agent_type: test
    reasoning_style: logical
    capabilities: ["testing"]
    task_types: ["test"]
    metrics: {}
    description: "Test agent"
"""
        
        with patch('builtins.open', mock_open(read_data=test_yaml)):
            factory = RoleFactory("test_registry.yaml")
            
            result = factory.validate_role_registry()
            assert result is True
    
    @pytest.mark.unit
    def test_validate_role_registry_missing_field(self):
        """Test role registry validation with missing required field"""
        test_yaml = """
roles:
  incomplete:
    display_name: Incomplete Agent
    agent_type: test
    # Missing reasoning_style, capabilities, task_types
"""
        
        with patch('builtins.open', mock_open(read_data=test_yaml)):
            factory = RoleFactory("test_registry.yaml")
            
            result = factory.validate_role_registry()
            # Should fail due to missing required fields
            assert result is False
    
    @pytest.mark.unit
    def test_validate_role_registry_error_handling(self):
        """Test role registry validation error handling"""
        def error_file_reader(path):
            raise Exception("Simulated error")
        
        factory = RoleFactory("test_registry.yaml", file_reader=lambda p: "roles: {}")
        
        # Replace _load_roles to raise an exception
        with patch.object(factory, '_load_roles', side_effect=Exception("Test error")):
            result = factory.validate_role_registry()
            assert result is False
