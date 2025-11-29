#!/usr/bin/env python3
"""
Unit tests for CapabilityLoader
Tests capability loading, routing, and execution
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.capabilities.loader import CapabilityLoader


class TestCapabilityLoader:
    """Test CapabilityLoader functionality"""
    
    @pytest.fixture
    def loader(self, tmp_path):
        """Create CapabilityLoader instance with temporary path"""
        return CapabilityLoader(base_path=tmp_path)
    
    @pytest.mark.unit
    def test_loader_initialization(self, tmp_path):
        """Test CapabilityLoader initialization"""
        loader = CapabilityLoader(base_path=tmp_path)
        assert loader.base_path == Path(tmp_path)
        assert loader.catalog_path == Path(tmp_path) / "agents" / "capabilities" / "catalog.yaml"
        assert loader.bindings_path == Path(tmp_path) / "agents" / "capability_bindings.yaml"
    
    @pytest.mark.unit
    def test_load_catalog_success(self, loader, tmp_path):
        """Test loading capability catalog successfully"""
        catalog_file = tmp_path / "agents" / "capabilities" / "catalog.yaml"
        catalog_file.parent.mkdir(parents=True, exist_ok=True)
        
        catalog_data = {
            'capabilities': [
                {
                    'name': 'test.capability',
                    'capability_version': '1.0.0',
                    'description': 'Test capability',
                    'result': {'status': 'success'}
                }
            ]
        }
        
        import yaml
        with open(catalog_file, 'w') as f:
            yaml.dump(catalog_data, f)
        
        catalog = loader.load_catalog()
        
        assert 'test.capability' in catalog
        assert catalog['test.capability'].name == 'test.capability'
        assert catalog['test.capability'].capability_version == '1.0.0'
    
    @pytest.mark.unit
    def test_load_catalog_cached(self, loader, tmp_path):
        """Test catalog caching"""
        catalog_file = tmp_path / "agents" / "capabilities" / "catalog.yaml"
        catalog_file.parent.mkdir(parents=True, exist_ok=True)
        
        catalog_data = {'capabilities': []}
        import yaml
        with open(catalog_file, 'w') as f:
            yaml.dump(catalog_data, f)
        
        catalog1 = loader.load_catalog()
        catalog2 = loader.load_catalog()
        
        # Should return same object (cached)
        assert catalog1 is catalog2
    
    @pytest.mark.unit
    def test_load_catalog_error(self, loader, tmp_path):
        """Test loading catalog error handling"""
        catalog_file = tmp_path / "agents" / "capabilities" / "catalog.yaml"
        catalog_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Create invalid YAML
        with open(catalog_file, 'w') as f:
            f.write('invalid: yaml: content: [')
        
        with pytest.raises(Exception):
            loader.load_catalog()
    
    @pytest.mark.unit
    def test_load_agent_config_success(self, loader, tmp_path):
        """Test loading agent config successfully"""
        config_file = tmp_path / "agents" / "roles" / "dev" / "config.yaml"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        
        config_data = {
            'agent_id': 'test-agent',
            'role': 'dev',
            'spec_version': '1.0.0',
            'implements': [{'capability': 'docker.build'}],
            'constraints': {},
            'defaults': {}
        }
        
        import yaml
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        config = loader.load_agent_config('dev')
        
        assert config is not None
        assert config.agent_id == 'test-agent'
        assert config.role == 'dev'
    
    @pytest.mark.unit
    def test_load_agent_config_not_found(self, loader):
        """Test loading agent config when file doesn't exist"""
        config = loader.load_agent_config('nonexistent')
        
        assert config is None
    
    @pytest.mark.unit
    def test_load_bindings_success(self, loader, tmp_path):
        """Test loading capability bindings successfully"""
        bindings_file = tmp_path / "agents" / "capability_bindings.yaml"
        bindings_file.parent.mkdir(parents=True, exist_ok=True)
        
        bindings_data = {
            'bindings': {
                'docker.build': 'dev-agent',
                'docker.deploy': 'dev-agent'
            }
        }
        
        import yaml
        with open(bindings_file, 'w') as f:
            yaml.dump(bindings_data, f)
        
        bindings = loader.load_bindings()
        
        assert bindings['docker.build'] == 'dev-agent'
        assert bindings['docker.deploy'] == 'dev-agent'
    
    @pytest.mark.unit
    def test_load_bindings_not_found(self, loader):
        """Test loading bindings when file doesn't exist"""
        bindings = loader.load_bindings()
        
        # Should return empty dict, not raise
        assert bindings == {}
    
    @pytest.mark.unit
    def test_get_agent_for_capability(self, loader, tmp_path):
        """Test getting agent for capability"""
        bindings_file = tmp_path / "agents" / "capability_bindings.yaml"
        bindings_file.parent.mkdir(parents=True, exist_ok=True)
        
        bindings_data = {
            'bindings': {
                'docker.build': 'dev-agent'
            }
        }
        
        import yaml
        with open(bindings_file, 'w') as f:
            yaml.dump(bindings_data, f)
        
        agent_id = loader.get_agent_for_capability('docker.build')
        
        assert agent_id == 'dev-agent'
    
    @pytest.mark.unit
    def test_validate_capability_exists(self, loader, tmp_path):
        """Test validating capability that exists"""
        catalog_file = tmp_path / "agents" / "capabilities" / "catalog.yaml"
        catalog_file.parent.mkdir(parents=True, exist_ok=True)
        
        catalog_data = {
            'capabilities': [
                {
                    'name': 'test.capability',
                    'capability_version': '1.0.0',
                    'description': 'Test',
                    'result': {}
                }
            ]
        }
        
        import yaml
        with open(catalog_file, 'w') as f:
            yaml.dump(catalog_data, f)
        
        assert loader.validate_capability('test.capability') is True
    
    @pytest.mark.unit
    def test_validate_capability_not_exists(self, loader, tmp_path):
        """Test validating capability that doesn't exist"""
        catalog_file = tmp_path / "agents" / "capabilities" / "catalog.yaml"
        catalog_file.parent.mkdir(parents=True, exist_ok=True)
        
        catalog_data = {'capabilities': []}
        import yaml
        with open(catalog_file, 'w') as f:
            yaml.dump(catalog_data, f)
        
        assert loader.validate_capability('nonexistent.capability') is False
    
    @pytest.mark.unit
    def test_validate_capability_with_version(self, loader, tmp_path):
        """Test validating capability with version check"""
        catalog_file = tmp_path / "agents" / "capabilities" / "catalog.yaml"
        catalog_file.parent.mkdir(parents=True, exist_ok=True)
        
        catalog_data = {
            'capabilities': [
                {
                    'name': 'test.capability',
                    'capability_version': '1.0.0',
                    'description': 'Test',
                    'result': {}
                }
            ]
        }
        
        import yaml
        with open(catalog_file, 'w') as f:
            yaml.dump(catalog_data, f)
        
        assert loader.validate_capability('test.capability', '1.0.0') is True
        assert loader.validate_capability('test.capability', '2.0.0') is False
    
    @pytest.mark.unit
    def test_get_capability(self, loader, tmp_path):
        """Test getting capability definition"""
        catalog_file = tmp_path / "agents" / "capabilities" / "catalog.yaml"
        catalog_file.parent.mkdir(parents=True, exist_ok=True)
        
        catalog_data = {
            'capabilities': [
                {
                    'name': 'test.capability',
                    'capability_version': '1.0.0',
                    'description': 'Test',
                    'result': {}
                }
            ]
        }
        
        import yaml
        with open(catalog_file, 'w') as f:
            yaml.dump(catalog_data, f)
        
        capability = loader.get_capability('test.capability')
        
        assert capability is not None
        assert capability.name == 'test.capability'
    
    @pytest.mark.unit
    def test_get_agent_capabilities(self, loader, tmp_path):
        """Test getting agent capabilities"""
        config_file = tmp_path / "agents" / "roles" / "dev" / "config.yaml"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        
        config_data = {
            'agent_id': 'test-agent',
            'role': 'dev',
            'spec_version': '1.0.0',
            'implements': [
                {'capability': 'docker.build'},
                {'capability': 'docker.deploy'}
            ],
            'constraints': {},
            'defaults': {}
        }
        
        import yaml
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        capabilities = loader.get_agent_capabilities('dev')
        
        assert 'docker.build' in capabilities
        assert 'docker.deploy' in capabilities
    
    @pytest.mark.unit
    def test_get_capability_for_task_explicit(self, loader):
        """Test getting capability from task with explicit capability field"""
        task = {
            'capability': 'docker.build',
            'task_type': 'development'
        }
        
        capability = loader.get_capability_for_task(task)
        
        assert capability == 'docker.build'
    
    @pytest.mark.unit
    def test_get_capability_for_task_prd_path(self, loader):
        """Test getting capability from task with prd_path"""
        task = {
            'prd_path': '/test/prd.md'
        }
        
        capability = loader.get_capability_for_task(task)
        
        assert capability == 'prd.process'
    
    @pytest.mark.unit
    def test_get_capability_for_task_type_mapping(self, loader):
        """Test getting capability from task_type mapping"""
        task = {
            'task_type': 'warmboot_wrapup'
        }
        
        capability = loader.get_capability_for_task(task)
        
        assert capability == 'warmboot.wrapup'
    
    @pytest.mark.unit
    def test_get_capability_for_task_action_mapping(self, loader):
        """Test getting capability from requirements.action mapping"""
        task = {
            'requirements': {
                'action': 'build'
            }
        }
        
        capability = loader.get_capability_for_task(task)
        
        assert capability == 'docker.build'
    
    @pytest.mark.unit
    def test_get_capability_for_task_no_mapping(self, loader):
        """Test getting capability when no mapping found"""
        task = {
            'task_type': 'unknown_type'
        }
        
        capability = loader.get_capability_for_task(task)
        
        assert capability is None
    
    @pytest.mark.unit
    def test_accepts_task_dict(self, loader):
        """Test checking if capability accepts task dict"""
        assert loader.accepts_task_dict('warmboot.wrapup') is True
        assert loader.accepts_task_dict('docker.build') is False
    
    @pytest.mark.unit
    def test_get_calling_convention(self, loader):
        """Test getting calling convention for capability"""
        assert loader.get_calling_convention('warmboot.wrapup') == 'task_dict'
        assert loader.get_calling_convention('docker.build') == 'task_id_requirements'
        assert loader.get_calling_convention('build.artifact') == 'requirements_only'
        assert loader.get_calling_convention('unknown.capability') == 'payload_as_is'
    
    @pytest.mark.unit
    def test_prepare_capability_args_task_dict(self, loader):
        """Test preparing args for task_dict convention"""
        payload = {'task_id': 'task-001', 'ecid': 'ec-001'}
        
        args = loader.prepare_capability_args('warmboot.wrapup', payload)
        
        assert args == (payload,)
    
    @pytest.mark.unit
    def test_prepare_capability_args_requirements_only(self, loader):
        """Test preparing args for requirements_only convention"""
        payload = {'requirements': {'app_name': 'TestApp'}}
        
        args = loader.prepare_capability_args('build.artifact', payload)
        
        assert args == ({'app_name': 'TestApp'},)
    
    @pytest.mark.unit
    def test_prepare_capability_args_task_id_requirements(self, loader):
        """Test preparing args for task_id_requirements convention"""
        payload = {
            'task_id': 'task-001',
            'requirements': {'app_name': 'TestApp'}
        }
        
        args = loader.prepare_capability_args('docker.build', payload)
        
        assert args == ('task-001', {'app_name': 'TestApp'})
    
    @pytest.mark.unit
    def test_prepare_capability_args_payload_and_metadata(self, loader):
        """Test preparing args for payload_and_metadata convention"""
        payload = {'test': 'data'}
        metadata = {'ecid': 'ec-001'}
        
        args = loader.prepare_capability_args('governance.task_coordination', payload, metadata)
        
        assert len(args) == 2
        assert args[0] == payload
        assert args[1] == metadata
    
    @pytest.mark.unit
    def test_prepare_capability_args_payload_as_is(self, loader):
        """Test preparing args for payload_as_is convention"""
        payload = {'test': 'data'}
        
        args = loader.prepare_capability_args('unknown.capability', payload)
        
        assert args == (payload,)
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_execute_capability(self, loader):
        """Test executing capability"""
        mock_agent = MagicMock()
        mock_capability_class = MagicMock()
        mock_instance = MagicMock()
        mock_method = AsyncMock(return_value={'status': 'success'})
        mock_capability_class.return_value = mock_instance
        mock_instance.build = mock_method
        
        # Clear cache first
        loader._class_cache.clear()
        
        # Patch resolve to return our mock class directly
        with patch.object(loader, 'resolve', return_value=mock_capability_class):
            result = await loader.execute('docker.build', mock_agent, 'task-001', {'app_name': 'TestApp'})
            
            assert result['status'] == 'success'
            mock_method.assert_called_once_with('task-001', {'app_name': 'TestApp'})
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_execute_capability_not_found(self, loader):
        """Test executing capability that doesn't exist"""
        mock_agent = MagicMock()
        
        with pytest.raises(ValueError, match="Capability 'nonexistent.capability' could not be resolved"):
            await loader.execute('nonexistent.capability', mock_agent, 'task-001', {})
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_execute_capability_import_error(self, loader):
        """Test executing capability when import fails"""
        mock_agent = MagicMock()
        
        with patch('importlib.import_module', side_effect=ImportError("Module not found")):
            with pytest.raises(ValueError, match="Capability 'docker.build' could not be resolved"):
                await loader.execute('docker.build', mock_agent, 'task-001', {})

