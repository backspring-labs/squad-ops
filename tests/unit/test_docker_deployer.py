#!/usr/bin/env python3
"""
Unit tests for DockerDeployer capability
Tests Docker container deployment capability
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.capabilities.docker_deployer import DockerDeployer


class TestDockerDeployer:
    """Test DockerDeployer capability"""
    
    @pytest.fixture
    def mock_agent(self):
        """Create mock agent instance"""
        agent = MagicMock()
        agent.name = "test-agent"
        agent.llm_client = MagicMock()
        agent.current_ecid = "ec-001"
        agent.emit_reasoning_event = AsyncMock()
        agent.record_memory = AsyncMock()
        return agent
    
    @pytest.fixture
    def docker_deployer(self, mock_agent):
        """Create DockerDeployer instance"""
        return DockerDeployer(mock_agent)
    
    @pytest.mark.unit
    def test_docker_deployer_initialization(self, mock_agent):
        """Test DockerDeployer initialization"""
        deployer = DockerDeployer(mock_agent)
        assert deployer.agent == mock_agent
        assert deployer.name == "test-agent"
        assert deployer.docker_manager is not None
        assert deployer.app_builder is not None
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_deploy_success(self, docker_deployer, mock_agent):
        """Test successful container deployment"""
        requirements = {
            'application': 'TestApp',
            'version': '1.0.0',
            'ecid': 'ec-001',
            'source_dir': '/test/source'
        }
        
        with patch.object(docker_deployer.docker_manager, 'build_image', new_callable=AsyncMock) as mock_build, \
             patch.object(docker_deployer.docker_manager, 'deploy_container', new_callable=AsyncMock) as mock_deploy:
            
            mock_build.return_value = {'status': 'success'}
            mock_deploy.return_value = {
                'status': 'success',
                'container_name': 'squadops-test-app',
                'image': 'test-app:1.0.0'
            }
            
            result = await docker_deployer.deploy('task-001', requirements)
            
            assert result['status'] == 'completed'
            assert result['action'] == 'deploy'
            assert result['app_name'] == 'TestApp'
            assert result['version'] == '1.0.0'
            assert result['container_name'] == 'squadops-test-app'
            mock_build.assert_called_once()
            mock_deploy.assert_called_once()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_deploy_build_fails(self, docker_deployer):
        """Test deployment when build fails"""
        requirements = {
            'application': 'TestApp',
            'version': '1.0.0',
            'source_dir': '/test/source'
        }
        
        with patch.object(docker_deployer.docker_manager, 'build_image', new_callable=AsyncMock) as mock_build:
            mock_build.return_value = {
                'status': 'error',
                'error': 'Build failed'
            }
            
            result = await docker_deployer.deploy('task-001', requirements)
            
            assert result['status'] == 'error'
            assert 'Build failed' in result['error']
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_deploy_container_fails(self, docker_deployer):
        """Test deployment when container deployment fails"""
        requirements = {
            'application': 'TestApp',
            'version': '1.0.0',
            'source_dir': '/test/source'
        }
        
        with patch.object(docker_deployer.docker_manager, 'build_image', new_callable=AsyncMock) as mock_build, \
             patch.object(docker_deployer.docker_manager, 'deploy_container', new_callable=AsyncMock) as mock_deploy:
            
            mock_build.return_value = {'status': 'success'}
            mock_deploy.return_value = {
                'status': 'error',
                'error': 'Deployment failed'
            }
            
            result = await docker_deployer.deploy('task-001', requirements)
            
            assert result['status'] == 'error'
            assert 'Deployment failed' in result['error']
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_deploy_default_source_dir(self, docker_deployer):
        """Test deployment with default source directory"""
        requirements = {
            'application': 'TestApp',
            'version': '1.0.0'
        }
        
        with patch.object(docker_deployer.docker_manager, 'build_image', new_callable=AsyncMock, return_value={'status': 'success'}), \
             patch.object(docker_deployer.docker_manager, 'deploy_container', new_callable=AsyncMock, return_value={'status': 'success', 'container_name': 'test', 'image': 'test:1.0.0'}):
            
            result = await docker_deployer.deploy('task-001', requirements)
            
            assert result['status'] == 'completed'
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_deploy_exception_handling(self, docker_deployer):
        """Test deployment exception handling"""
        requirements = {
            'application': 'TestApp',
            'version': '1.0.0'
        }
        
        with patch.object(docker_deployer.docker_manager, 'build_image', new_callable=AsyncMock, side_effect=Exception("Unexpected error")):
            result = await docker_deployer.deploy('task-001', requirements)
            
            assert result['status'] == 'error'
            assert 'error' in result

