import pytest
from unittest.mock import patch, MagicMock
from agents.factory.agent_factory import AgentFactory, AgentInstance

class TestAgentFactory:
    """Test AgentFactory core functionality"""
    
    @pytest.mark.unit
    def test_agent_instance_dataclass(self):
        """Test AgentInstance dataclass"""
        instance = AgentInstance(
            id="test-agent-001",
            display_name="Test Agent",
            role="lead",
            model="gpt-4",
            enabled=True,
            description="Test agent instance"
        )
        
        assert instance.id == "test-agent-001"
        assert instance.display_name == "Test Agent"
        assert instance.role == "lead"
        assert instance.model == "gpt-4"
        assert instance.enabled is True
        assert instance.description == "Test agent instance"
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_create_agent_success(self):
        """Test successful agent creation"""
        instance_config = {
            'id': 'test-agent-001',
            'role': 'lead',
            'display_name': 'Test Lead Agent',
            'model': 'gpt-4',
            'enabled': True,
            'description': 'Test lead agent'
        }
        
        # Create all mocks BEFORE entering the patch context
        mock_agent_instance = MagicMock()
        mock_agent_class = MagicMock(return_value=mock_agent_instance)
        mock_module = MagicMock()
        
        with patch('agents.factory.agent_factory.importlib.import_module', return_value=mock_module) as mock_import, \
             patch('agents.factory.agent_factory.getattr', return_value=mock_agent_class) as mock_getattr:
            
            agent = AgentFactory.create_agent(instance_config)
            
            assert agent == mock_agent_instance
            mock_import.assert_called_once_with('agents.roles.lead.agent')
            mock_getattr.assert_called_once_with(mock_module, 'LeadAgent')
            mock_agent_class.assert_called_once_with(identity='test-agent-001')
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_create_agent_missing_role(self):
        """Test agent creation with missing role"""
        instance_config = {
            'id': 'test-agent-001',
            'display_name': 'Test Agent',
            'model': 'gpt-4',
            'enabled': True,
            'description': 'Test agent'
        }
        
        with pytest.raises(Exception):
            AgentFactory.create_agent(instance_config)
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_create_agent_missing_id(self):
        """Test agent creation with missing id"""
        instance_config = {
            'role': 'lead',
            'display_name': 'Test Lead Agent',
            'model': 'gpt-4',
            'enabled': True,
            'description': 'Test lead agent'
        }
        
        with pytest.raises(Exception):
            AgentFactory.create_agent(instance_config)
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_create_agent_import_error(self):
        """Test agent creation with import error"""
        instance_config = {
            'id': 'test-agent-001',
            'role': 'non_existent',
            'display_name': 'Test Agent',
            'model': 'gpt-4',
            'enabled': True,
            'description': 'Test agent'
        }
        
        with patch('importlib.import_module', side_effect=ImportError("Module not found")):
            with pytest.raises(Exception):
                AgentFactory.create_agent(instance_config)
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_create_agent_attribute_error(self):
        """Test agent creation with attribute error"""
        instance_config = {
            'id': 'test-agent-001',
            'role': 'lead',
            'display_name': 'Test Lead Agent',
            'model': 'gpt-4',
            'enabled': True,
            'description': 'Test lead agent'
        }
        
        # Create mock module before patch context
        mock_module = MagicMock()
        
        with patch('agents.factory.agent_factory.importlib.import_module', return_value=mock_module) as mock_import, \
             patch('agents.factory.agent_factory.getattr', side_effect=AttributeError("Class not found")):
            
            with pytest.raises(Exception):
                AgentFactory.create_agent(instance_config)
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_create_agent_instantiation_error(self):
        """Test agent creation with instantiation error"""
        instance_config = {
            'id': 'test-agent-001',
            'role': 'lead',
            'display_name': 'Test Lead Agent',
            'model': 'gpt-4',
            'enabled': True,
            'description': 'Test lead agent'
        }
        
        # Create all mocks BEFORE entering the patch context
        mock_agent_class = MagicMock(side_effect=Exception("Instantiation failed"))
        mock_module = MagicMock()
        
        with patch('agents.factory.agent_factory.importlib.import_module', return_value=mock_module) as mock_import, \
             patch('agents.factory.agent_factory.getattr', return_value=mock_agent_class) as mock_getattr:
            
            with pytest.raises(Exception):
                AgentFactory.create_agent(instance_config)
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_create_agent_different_roles(self):
        """Test creating agents with different roles"""
        test_cases = [
            {
                'role': 'dev',
                'expected_class': 'DevAgent',
                'expected_module': 'agents.roles.dev.agent'
            },
            {
                'role': 'qa',
                'expected_class': 'QaAgent',
                'expected_module': 'agents.roles.qa.agent'
            },
            {
                'role': 'audit',
                'expected_class': 'AuditAgent',
                'expected_module': 'agents.roles.audit.agent'
            }
        ]
        
        for test_case in test_cases:
            instance_config = {
                'id': f'test-{test_case["role"]}-001',
                'role': test_case['role'],
                'display_name': f'Test {test_case["role"].title()} Agent',
                'model': 'gpt-4',
                'enabled': True,
                'description': f'Test {test_case["role"]} agent'
            }
            
            # Create all mocks BEFORE entering the patch context
            mock_agent_instance = MagicMock()
            mock_agent_class = MagicMock(return_value=mock_agent_instance)
            mock_module = MagicMock()
            
            with patch('agents.factory.agent_factory.importlib.import_module', return_value=mock_module) as mock_import, \
                 patch('agents.factory.agent_factory.getattr', return_value=mock_agent_class) as mock_getattr:
                
                agent = AgentFactory.create_agent(instance_config)
                
                assert agent == mock_agent_instance
                mock_import.assert_called_once_with(test_case['expected_module'])
                mock_getattr.assert_called_once_with(mock_module, test_case['expected_class'])
                mock_agent_class.assert_called_once_with(identity=instance_config['id'])
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_create_agent_with_additional_config(self):
        """Test creating agent with additional configuration"""
        instance_config = {
            'id': 'test-agent-001',
            'role': 'lead',
            'display_name': 'Test Lead Agent',
            'model': 'gpt-4',
            'enabled': True,
            'description': 'Test lead agent',
            'additional_param': 'test_value',
            'nested_config': {
                'param1': 'value1',
                'param2': 'value2'
            }
        }
        
        # Create all mocks BEFORE entering the patch context
        mock_agent_instance = MagicMock()
        mock_agent_class = MagicMock(return_value=mock_agent_instance)
        mock_module = MagicMock()
        
        with patch('agents.factory.agent_factory.importlib.import_module', return_value=mock_module) as mock_import, \
             patch('agents.factory.agent_factory.getattr', return_value=mock_agent_class) as mock_getattr:
            
            agent = AgentFactory.create_agent(instance_config)
            
            assert agent == mock_agent_instance
            # Should only pass identity to agent constructor
            mock_agent_class.assert_called_once_with(identity='test-agent-001')
    
    @pytest.mark.unit
    def test_validate_instance_config_valid(self):
        """Test validating valid instance configuration"""
        instance_config = {
            'id': 'test-agent-001',
            'role': 'lead',
            'display_name': 'Test Lead Agent',
            'model': 'gpt-4',
            'enabled': True,
            'description': 'Test lead agent'
        }
        
        is_valid = AgentFactory.validate_instance_config(instance_config)
        assert is_valid is True
    
    @pytest.mark.unit
    def test_validate_instance_config_missing_required(self):
        """Test validating instance configuration with missing required fields"""
        test_cases = [
            # Missing id
            {
                'role': 'lead',
                'display_name': 'Test Lead Agent',
                'model': 'gpt-4',
                'enabled': True,
                'description': 'Test lead agent'
            },
            # Missing role
            {
                'id': 'test-agent-001',
                'display_name': 'Test Lead Agent',
                'model': 'gpt-4',
                'enabled': True,
                'description': 'Test lead agent'
            },
            # Missing display_name
            {
                'id': 'test-agent-001',
                'role': 'lead',
                'model': 'gpt-4',
                'enabled': True,
                'description': 'Test lead agent'
            }
        ]
        
        for config in test_cases:
            is_valid = AgentFactory.validate_instance_config(config)
            assert is_valid is False
    
    @pytest.mark.unit
    def test_validate_instance_config_invalid_role(self):
        """Test validating instance configuration with invalid role"""
        # Create a config with all required fields but invalid role
        config = {
            'id': 'test-agent-001',
            'role': 'non_existent_role',  # Invalid role
            'display_name': 'Test Agent',
            'model': 'gpt-4',
            'enabled': True,
            'description': 'Test agent'
        }
        
        # validate_instance_config checks if role exists in available roles
        is_valid = AgentFactory.validate_instance_config(config)
        assert is_valid is False  # Should be False because role doesn't exist


