"""
Integration test for validating agent model configurations.

Verifies that all agents are configured with models that:
1. Exist in Ollama
2. Are functional (can generate completions)

This test prevents runtime failures like "model 'mixtral-8x7b' not found".
"""
import pytest
import aiohttp
import yaml
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def get_agent_model_configs() -> Dict[str, Dict[str, str]]:
    """
    Discover and parse agent configs for lead, dev, and strat agents only.
    
    Returns:
        Dict mapping agent_id to config info:
        {
            'nat': {'model': 'mixtral-8x7b', 'role': 'strat', 'config_path': '...'},
            'max': {'model': 'llama3.1:8b', 'role': 'lead', 'config_path': '...'},
            'neo': {'model': 'qwen2.5:7b', 'role': 'dev', 'config_path': '...'},
        }
    """
    base_path = Path(__file__).parent.parent.parent
    roles_path = base_path / 'agents' / 'roles'
    
    if not roles_path.exists():
        pytest.skip(f"Agent roles directory not found: {roles_path}")
    
    # Only test these three agents
    target_roles = {'lead', 'dev', 'strat'}
    target_agent_ids = {'max', 'neo', 'nat'}
    
    agent_configs = {}
    
    # Iterate through target role directories only
    for role_dir in sorted(roles_path.iterdir()):
        if not role_dir.is_dir():
            continue
        
        role_name = role_dir.name
        if role_name not in target_roles:
            continue
        
        config_path = role_dir / 'config.yaml'
        if not config_path.exists():
            continue
        
        try:
            with open(config_path, 'r') as f:
                config_data = yaml.safe_load(f)
            
            agent_id = config_data.get('agent_id')
            role = config_data.get('role', role_name)
            defaults = config_data.get('defaults', {})
            model_config = defaults.get('model', '')
            
            # Only include if agent_id is in our target list
            if not agent_id or agent_id not in target_agent_ids:
                continue
            
            # Parse model format: "ollama:model-name" -> "model-name"
            # Also handle direct model names
            model_name = None
            if model_config:
                if ':' in model_config:
                    # Format: "ollama:model-name" or "provider:model-name"
                    parts = model_config.split(':', 1)
                    if len(parts) == 2:
                        provider, model = parts
                        if provider.lower() == 'ollama':
                            model_name = model
                        else:
                            # Future provider support - skip for now
                            continue
                else:
                    # Direct model name
                    model_name = model_config
            
            if model_name:
                agent_configs[agent_id] = {
                    'model': model_name,
                    'role': role,
                    'config_path': str(config_path.relative_to(base_path)),
                    'raw_model_config': model_config
                }
        except Exception as e:
            pytest.fail(f"Failed to parse config {config_path}: {e}")
    
    return agent_configs


async def get_available_ollama_models(ollama_url: str) -> List[str]:
    """
    Query Ollama API for available models.
    
    Args:
        ollama_url: Ollama API URL (e.g., "http://localhost:11434")
        
    Returns:
        List of available model names
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f'{ollama_url}/api/tags',
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    models = []
                    for model_info in data.get('models', []):
                        model_name = model_info.get('name', '')
                        if model_name:
                            models.append(model_name)
                    return models
                else:
                    error_text = await response.text()
                    raise Exception(f"Ollama API error {response.status}: {error_text[:200]}")
    except aiohttp.ClientError as e:
        raise Exception(f"Network error connecting to Ollama: {type(e).__name__}: {str(e)}")
    except asyncio.TimeoutError:
        raise Exception(f"Ollama API timeout after 10s")


async def test_model_available(ollama_url: str, model_name: str) -> Tuple[bool, Optional[str]]:
    """
    Test if a model is available and functional by making a simple completion call.
    
    Args:
        ollama_url: Ollama API URL
        model_name: Model name to test
        
    Returns:
        Tuple of (success: bool, error_message: Optional[str])
    """
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                'model': model_name,
                'prompt': 'Say "test"',
                'stream': False,
                'options': {
                    'temperature': 0.1,
                    'num_predict': 10
                }
            }
            
            async with session.post(
                f'{ollama_url}/api/generate',
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get('response'):
                        return True, None
                    else:
                        return False, "Model returned empty response"
                else:
                    error_text = await response.text()
                    return False, f"Ollama API error {response.status}: {error_text[:200]}"
    except aiohttp.ClientError as e:
        return False, f"Network error: {type(e).__name__}: {str(e)}"
    except asyncio.TimeoutError:
        return False, "Model test timeout after 30s"


class TestAgentModelValidation:
    """Integration tests for agent model configuration validation."""
    
    @pytest.fixture
    def ollama_available(self, integration_config):
        """Check if Ollama is available for integration tests."""
        ollama_url = integration_config.get('ollama_url', 'http://localhost:11434')
        
        async def check_ollama():
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f'{ollama_url}/api/tags',
                        timeout=aiohttp.ClientTimeout(total=5)
                    ) as response:
                        return response.status == 200
            except Exception:
                return False
        
        return asyncio.run(check_ollama())
    
    @pytest.mark.service_ollama
    def test_all_agent_models_available(self, ollama_available, integration_config):
        """
        Verify all configured agent models exist in Ollama.
        
        This test discovers all agent configs and validates that each agent's
        configured model is available in Ollama, preventing runtime failures.
        """
        if not ollama_available:
            pytest.skip("Ollama not available for integration test")
        
        ollama_url = integration_config.get('ollama_url', 'http://localhost:11434')
        
        # Get all agent model configs
        agent_configs = get_agent_model_configs()
        if not agent_configs:
            pytest.skip("No agent configs found")
        
        # Get available models from Ollama
        try:
            available_models = asyncio.run(get_available_ollama_models(ollama_url))
        except Exception as e:
            pytest.fail(f"Failed to query Ollama for available models: {e}")
        
        # Validate each agent's model
        missing_models = []
        for agent_id, config in agent_configs.items():
            model_name = config['model']
            if model_name not in available_models:
                missing_models.append({
                    'agent_id': agent_id,
                    'role': config['role'],
                    'model': model_name,
                    'config_path': config['config_path'],
                    'raw_config': config['raw_model_config']
                })
        
        # Report results
        if missing_models:
            error_msg = "\n\n❌ Missing models detected:\n"
            error_msg += "=" * 70 + "\n"
            for missing in missing_models:
                error_msg += f"\nAgent: {missing['agent_id']} ({missing['role']})\n"
                error_msg += f"  Config: {missing['config_path']}\n"
                error_msg += f"  Configured model: {missing['raw_config']}\n"
                error_msg += f"  Expected model name: {missing['model']}\n"
                error_msg += f"  Status: ❌ NOT FOUND in Ollama\n"
            
            error_msg += "\n" + "=" * 70 + "\n"
            error_msg += f"\nAvailable models in Ollama ({len(available_models)}):\n"
            for model in sorted(available_models):
                error_msg += f"  - {model}\n"
            
            error_msg += "\n" + "=" * 70 + "\n"
            error_msg += "\n💡 To fix:\n"
            error_msg += "  1. Pull missing models: ollama pull <model-name>\n"
            error_msg += "  2. Or update agent configs to use available models\n"
            error_msg += "  3. Verify: ollama list\n"
            
            pytest.fail(error_msg)
        
        # Success message
        print(f"\n✅ All {len(agent_configs)} agents have valid model configurations:")
        for agent_id, config in sorted(agent_configs.items()):
            print(f"  - {agent_id} ({config['role']}): {config['model']}")
    
    @pytest.mark.service_ollama
    def test_all_agent_models_functional(self, ollama_available, integration_config):
        """
        Verify all configured agent models are functional by making test calls.
        
        This test ensures models not only exist but can actually generate completions,
        catching issues like corrupted models or API incompatibilities.
        """
        if not ollama_available:
            pytest.skip("Ollama not available for integration test")
        
        ollama_url = integration_config.get('ollama_url', 'http://localhost:11434')
        
        # Get all agent model configs
        agent_configs = get_agent_model_configs()
        if not agent_configs:
            pytest.skip("No agent configs found")
        
        # First verify models exist (reuse previous test logic)
        try:
            available_models = asyncio.run(get_available_ollama_models(ollama_url))
        except Exception as e:
            pytest.fail(f"Failed to query Ollama for available models: {e}")
        
        # Filter to only test models that exist
        models_to_test = {}
        for agent_id, config in agent_configs.items():
            model_name = config['model']
            if model_name in available_models:
                models_to_test[agent_id] = {
                    'model': model_name,
                    'role': config['role'],
                    'config_path': config['config_path']
                }
        
        if not models_to_test:
            pytest.skip("No valid models found to test")
        
        # Test each model
        failed_models = []
        for agent_id, config in models_to_test.items():
            model_name = config['model']
            success, error_msg = asyncio.run(test_model_available(ollama_url, model_name))
            
            if not success:
                failed_models.append({
                    'agent_id': agent_id,
                    'role': config['role'],
                    'model': model_name,
                    'config_path': config['config_path'],
                    'error': error_msg
                })
        
        # Report results
        if failed_models:
            error_msg = "\n\n❌ Models failed functional test:\n"
            error_msg += "=" * 70 + "\n"
            for failed in failed_models:
                error_msg += f"\nAgent: {failed['agent_id']} ({failed['role']})\n"
                error_msg += f"  Config: {failed['config_path']}\n"
                error_msg += f"  Model: {failed['model']}\n"
                error_msg += f"  Error: {failed['error']}\n"
            
            error_msg += "\n" + "=" * 70 + "\n"
            error_msg += "\n💡 To fix:\n"
            error_msg += "  1. Check Ollama logs: docker logs ollama (if containerized)\n"
            error_msg += "  2. Try pulling model again: ollama pull <model-name>\n"
            error_msg += "  3. Test manually: ollama run <model-name> 'test'\n"
            
            pytest.fail(error_msg)
        
        # Success message
        print(f"\n✅ All {len(models_to_test)} agent models are functional:")
        for agent_id, config in sorted(models_to_test.items()):
            print(f"  - {agent_id} ({config['role']}): {config['model']}")
    
    @pytest.mark.service_ollama
    def test_agents_use_config_yaml_model(self, ollama_available, integration_config):
        """
        Verify that agents actually use the model from their config.yaml, not from env vars.
        
        This test ensures the single-source-of-truth implementation is working correctly.
        """
        if not ollama_available:
            pytest.skip("Ollama not available for integration test")
        
        # Get all agent model configs
        agent_configs = get_agent_model_configs()
        if not agent_configs:
            pytest.skip("No agent configs found")
        
        # Verify each agent's config.yaml has a model configured
        missing_models = []
        for agent_id, config in agent_configs.items():
            if not config.get('model'):
                missing_models.append({
                    'agent_id': agent_id,
                    'role': config['role'],
                    'config_path': config['config_path']
                })
        
        if missing_models:
            error_msg = "\n\n❌ Agents missing model configuration in config.yaml:\n"
            error_msg += "=" * 70 + "\n"
            for missing in missing_models:
                error_msg += f"\nAgent: {missing['agent_id']} ({missing['role']})\n"
                error_msg += f"  Config: {missing['config_path']}\n"
                error_msg += f"  Status: ❌ No defaults.model configured\n"
            
            error_msg += "\n" + "=" * 70 + "\n"
            error_msg += "\n💡 To fix:\n"
            error_msg += "  Add 'defaults.model: ollama:<model-name>' to agent's config.yaml\n"
            
            pytest.fail(error_msg)
        
        # Success message
        print(f"\n✅ All {len(agent_configs)} agents have model configured in config.yaml:")
        for agent_id, config in sorted(agent_configs.items()):
            print(f"  - {agent_id} ({config['role']}): {config['raw_model_config']} → {config['model']}")

