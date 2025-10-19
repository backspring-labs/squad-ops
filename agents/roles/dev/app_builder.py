"""
AppBuilder - JSON workflow application building using LLM.

Uses structured JSON output from LLMs for manifest and file generation.
"""

from pathlib import Path
from typing import List, Dict, Any
from agents.llm.client import LLMClient
from agents.contracts.task_spec import TaskSpec
from agents.contracts.build_manifest import BuildManifest
import logging
import yaml
import json

logger = logging.getLogger(__name__)


class AppBuilder:
    """Builds application artifacts using JSON-based LLM workflow"""
    
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client
    
    def _load_prompt(self, template_name: str, **kwargs) -> str:
        """Load and format prompt template"""
        template_content = None
        safe_kwargs = {}
        
        try:
            template_path = Path(__file__).parent / 'prompts' / template_name
            with open(template_path, 'r') as f:
                template_content = f.read()
            
            # Use string.Template for safer substitution
            from string import Template
            template = Template(template_content)
            
            # Convert kwargs to safe format for Template
            for key, value in kwargs.items():
                if isinstance(value, str):
                    # Escape $ signs to prevent template injection
                    safe_kwargs[key] = value.replace('$', '$$')
                else:
                    safe_kwargs[key] = str(value).replace('$', '$$')
            
            return template.safe_substitute(**safe_kwargs)
            
        except Exception as e:
            logger.error(f"AppBuilder failed to format template: {e}")
            if template_content:
                logger.error(f"AppBuilder template preview: {template_content[:200]}...")
            logger.error(f"AppBuilder safe kwargs: {safe_kwargs}")
            raise
    
    def _to_kebab_case(self, name: str) -> str:
        """Convert app name to kebab-case"""
        import re
        name = re.sub(r'([a-z0-9])([A-Z])', r'\1-\2', name)
        return name.lower().replace(' ', '-')
    
    async def _call_ollama_json(self, prompt: str, model: str = "qwen2.5:7b") -> Dict:
        """Call Ollama with JSON format enforcement"""
        import aiohttp
        
        async with aiohttp.ClientSession() as session:
            payload = {
                "model": model,
                "prompt": prompt,
                "format": "json",  # Forces JSON output
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "top_p": 0.9,
                    "max_tokens": 4000
                }
            }
            
            try:
                async with session.post(
                    'http://localhost:11434/api/generate',
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=120)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        response_text = result.get('response', '{}')
                        
                        # Parse JSON response
                        try:
                            return json.loads(response_text)
                        except json.JSONDecodeError as e:
                            logger.error(f"AppBuilder JSON parse error: {e}")
                            logger.error(f"AppBuilder raw response: {response_text[:500]}...")
                            raise Exception(f"Invalid JSON response from LLM: {e}")
                    else:
                        raise Exception(f"Ollama API error: {response.status}")
                        
            except aiohttp.ClientError as e:
                logger.error(f"AppBuilder HTTP error: {e}")
                raise Exception(f"Network error calling Ollama: {e}")
    
    async def generate_manifest_json(self, task_spec: TaskSpec) -> BuildManifest:
        """Generate BuildManifest using JSON-based Ollama call"""
        logger.info(f"AppBuilder generating manifest for {task_spec.app_name}")
        
        # Load architect prompt with JSON output format
        architect_prompt = self._load_prompt(
            'architect.txt',
            app_name=task_spec.app_name,
            version=task_spec.version,
            prd_analysis=task_spec.prd_analysis,
            features=', '.join(task_spec.features) if task_spec.features else 'General web application',
            constraints=yaml.dump(task_spec.constraints) if task_spec.constraints else 'None',
            output_format='json'
        )
        
        # Load SquadOps constraints
        constraints = self._load_prompt(
            'squadops_constraints.txt',
            version=task_spec.version,
            run_id=task_spec.run_id
        )
        
        # Inject constraints into architect prompt
        prompt = architect_prompt.replace('$squadops_constraints', constraints)
        
        try:
            # Call Ollama with JSON format enforcement
            manifest_data = await self._call_ollama_json(prompt)
            
            # Create BuildManifest from JSON data
            manifest = BuildManifest.from_dict(manifest_data)
            
            # ENFORCE FRAMEWORK CONSTRAINT: Always set to vanilla_js (SquadOps standard)
            logger.info(f"AppBuilder parsed manifest: {manifest.architecture_type}, LLM framework: {manifest.framework}")
            manifest.framework = "vanilla_js"  # Always override - no LLM choice
            logger.info(f"AppBuilder final manifest: {manifest.architecture_type}, framework: {manifest.framework} (SquadOps standard)")
            
            return manifest
            
        except Exception as e:
            logger.error(f"AppBuilder failed to generate manifest: {e}")
            raise Exception(f"Manifest generation failed: {e}")
    
    async def generate_files_json(self, task_spec: TaskSpec, manifest: BuildManifest) -> List[Dict[str, Any]]:
        """Generate application files using JSON-based Ollama call"""
        logger.info(f"AppBuilder generating files for {task_spec.app_name}")
        
        # Load developer prompt with JSON output format
        developer_prompt = self._load_prompt(
            'developer.txt',
            app_name=task_spec.app_name,
            version=task_spec.version,
            prd_analysis=task_spec.prd_analysis,
            features=', '.join(task_spec.features) if task_spec.features else 'General web application',
            constraints=yaml.dump(task_spec.constraints) if task_spec.constraints else 'None',
            manifest_summary=yaml.dump(manifest.to_dict()),
            output_format='json'
        )
        
        # Load SquadOps constraints
        constraints = self._load_prompt(
            'squadops_constraints.txt',
            version=task_spec.version,
            run_id=task_spec.run_id
        )
        
        # Inject constraints into developer prompt
        prompt = developer_prompt.replace('$squadops_constraints', constraints)
        
        try:
            # Call Ollama with JSON format enforcement
            files_data = await self._call_ollama_json(prompt)
            
            # Extract files from JSON response
            if 'files' not in files_data:
                raise Exception("No 'files' key in LLM response")
            
            files = files_data['files']
            if not isinstance(files, list):
                raise Exception("'files' must be a list")
            
            # Convert to expected format
            file_list = []
            for file_data in files:
                if not isinstance(file_data, dict):
                    continue
                    
                # Handle both "path" and "file_path" for backward compatibility
                file_path = file_data.get('file_path') or file_data.get('path')
                if not file_path:
                    logger.warning(f"AppBuilder skipping file data missing file_path/path: {file_data}")
                    continue
                    
                if 'content' not in file_data:
                    raise Exception(f"File {file_path} missing content field")
                
                file_list.append({
                    'type': 'create_file',
                    'file_path': file_path,
                    'content': file_data['content'],
                    'directory': file_data.get('directory')
                })
            
            logger.info(f"AppBuilder generated {len(file_list)} files from JSON response")
            return file_list
            
        except Exception as e:
            logger.error(f"AppBuilder failed to generate files: {e}")
            raise Exception(f"File generation failed: {e}")