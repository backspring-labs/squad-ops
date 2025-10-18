"""
AppBuilder - Manifest-first application building using LLM.

Replaces the old CodeGenerator with a structured workflow:
TaskSpec → BuildManifest → Files → Validation
"""

from pathlib import Path
from typing import List, Dict, Any
from agents.llm.client import LLMClient
from agents.llm.validators import (
    validate_html,
    validate_css,
    validate_js,
    parse_delimited_files
)
from agents.contracts.task_spec import TaskSpec
from agents.contracts.build_manifest import BuildManifest
import logging
import yaml
import json

logger = logging.getLogger(__name__)


class AppBuilder:
    """Builds application artifacts using manifest-first LLM workflow"""
    
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client
        self.prompts_dir = Path(__file__).parent / "prompts"
    
    def _load_prompt(self, template_name: str, **kwargs) -> str:
        """Load and format prompt template"""
        from string import Template
        
        template_path = self.prompts_dir / template_name
        logger.info(f"AppBuilder loading prompt from: {template_path}")
        template_content = template_path.read_text()
        logger.info(f"AppBuilder loaded template, length: {len(template_content)}")
        logger.info(f"AppBuilder formatting template with kwargs: {list(kwargs.keys())}")
        
        # Sanitize kwargs to prevent template formatting issues
        sanitized_kwargs = {}
        for key, value in kwargs.items():
            if isinstance(value, str):
                # Only sanitize prd_analysis which contains error messages
                if key == 'prd_analysis':
                    # Replace problematic characters that break string formatting
                    sanitized_value = value.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
                    # Remove any remaining control characters
                    sanitized_value = ''.join(char for char in sanitized_value if ord(char) >= 32 or char in '\n\r\t')
                else:
                    # Keep other strings as-is (like file_list which needs newlines)
                    sanitized_value = value
                sanitized_kwargs[key] = sanitized_value
                logger.info(f"AppBuilder kwarg {key}: {repr(sanitized_value[:100])}...")
            else:
                sanitized_kwargs[key] = value
                logger.info(f"AppBuilder kwarg {key}: {repr(value)}")
        
        try:
            # Use string.Template which is more robust with special characters
            template = Template(template_content)
            formatted = template.safe_substitute(**sanitized_kwargs)
            logger.info(f"AppBuilder formatted template, length: {len(formatted)}")
            return formatted
        except Exception as e:
            logger.error(f"AppBuilder failed to format template: {e}")
            logger.error(f"AppBuilder template preview: {template_content[:200]}...")
            logger.error(f"AppBuilder sanitized kwargs: {sanitized_kwargs}")
            raise
    
    async def build_from_task_spec(self, task_spec: TaskSpec) -> Dict[str, Any]:
        """
        Manifest-first build workflow:
        1. Generate BuildManifest from TaskSpec
        2. Validate manifest
        3. Generate files based on manifest
        4. Validate files match manifest
        5. Return build result
        """
        logger.info(f"AppBuilder starting manifest-first build for {task_spec.app_name}")
        
        # Step 1: Generate BuildManifest
        manifest = await self._generate_manifest(task_spec)
        logger.info(f"AppBuilder generated manifest with {len(manifest.files)} files")
        
        # Step 2: Validate manifest against TaskSpec
        manifest.validate_against_task_spec(task_spec)
        logger.info("AppBuilder validated manifest against TaskSpec")
        
        # Step 2.5: Validate framework constraint
        if manifest.framework != "vanilla_js":
            raise ValueError(f"Framework constraint violation: got '{manifest.framework}', must be 'vanilla_js'")
        logger.info("AppBuilder validated framework constraint: vanilla_js")
        
        # Step 3: Generate files from manifest
        try:
            files = await self._generate_files_from_manifest(task_spec, manifest)
            logger.info(f"AppBuilder generated {len(files)} files successfully")
        except Exception as e:
            logger.error(f"AppBuilder failed in _generate_files_from_manifest: {e}")
            raise
        
        # Step 4: Validate files match manifest
        self._validate_files_match_manifest(files, manifest)
        logger.info("AppBuilder validated files match manifest")
        
        # Step 5: Add deployment files
        files.extend(self._generate_deployment_files(task_spec, manifest))
        
        return {
            'task_spec': task_spec.to_dict(),
            'manifest': manifest.to_dict(),
            'files': files,
            'success': True
        }
    
    async def _generate_manifest(self, task_spec: TaskSpec) -> BuildManifest:
        """Step 1: LLM generates BuildManifest from TaskSpec"""
        # Load pure architect prompt
        architect_prompt = self._load_prompt(
            'architect.txt',
            app_name=task_spec.app_name,
            version=task_spec.version,
            prd_analysis=task_spec.prd_analysis,
            features=', '.join(task_spec.features) if task_spec.features else 'General web application',
            constraints=yaml.dump(task_spec.constraints) if task_spec.constraints else 'None',
            output_format='yaml'
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
            response = await self.llm_client.complete(
                prompt=prompt,
                temperature=0.5,  # Lower temp for structured output
                max_tokens=2000
            )
            
            # Clean and parse YAML response
            from agents.llm.validators import clean_yaml_response
            cleaned_response = clean_yaml_response(response)
            manifest = BuildManifest.from_yaml(cleaned_response)
            
            # ENFORCE FRAMEWORK CONSTRAINT: Always set to vanilla_js (SquadOps standard)
            logger.info(f"AppBuilder parsed manifest: {manifest.architecture_type}, LLM framework: {manifest.framework}")
            manifest.framework = "vanilla_js"  # Always override - no LLM choice
            logger.info(f"AppBuilder final manifest: {manifest.architecture_type}, framework: {manifest.framework} (SquadOps standard)")
            return manifest
            
        except Exception as e:
            logger.error(f"AppBuilder failed to generate manifest: {e}")
            raise Exception(f"Manifest generation failed: {e}")
    
    async def _generate_files_from_manifest(
        self, 
        task_spec: TaskSpec, 
        manifest: BuildManifest
    ) -> List[Dict[str, Any]]:
        """Step 3: LLM generates all files based on manifest"""
        
        # Load pure developer prompt
        developer_prompt = self._load_prompt(
            'developer.txt',
            app_name=task_spec.app_name,
            version=task_spec.version,
            run_id=task_spec.run_id,
            prd_analysis=task_spec.prd_analysis,
            output_format='delimited'
        )
        
        # Create manifest summary
        file_list = '\n'.join([
            f"  - {f.path}: {f.purpose}"
            for f in manifest.files
        ])
        manifest_summary = f"""Type: {manifest.architecture_type}
Files to generate:
{file_list}"""
        
        # Load SquadOps constraints
        constraints = self._load_prompt(
            'squadops_constraints.txt',
            version=task_spec.version,
            run_id=task_spec.run_id
        )
        
        # Inject context
        prompt = developer_prompt.replace('$manifest_summary', manifest_summary)
        prompt = prompt.replace('$squadops_constraints', constraints)
        
        logger.info(f"AppBuilder loaded developer prompt, length: {len(prompt)}")
        
        try:
            logger.info("AppBuilder making LLM call for file generation...")
            response = await self.llm_client.complete(
                prompt=prompt,
                temperature=0.7,
                max_tokens=8000  # Higher limit for multiple files
            )
            
            logger.info(f"AppBuilder received LLM response length: {len(response)}")
            logger.info(f"AppBuilder LLM response preview: {response[:500]}...")
            
            # Parse delimited response
            parsed_files = parse_delimited_files(response)
            logger.info(f"AppBuilder parsed {len(parsed_files)} files from LLM response")
            
            if not parsed_files:
                logger.error("AppBuilder: No files parsed from LLM response")
                logger.error(f"AppBuilder full LLM response: {response}")
                raise Exception("No files generated by LLM")
            
            # Convert to internal format and validate
            files = []
            app_dir = f"/app/warm-boot/apps/{self._to_kebab_case(task_spec.app_name)}"
            
            for i, parsed_file in enumerate(parsed_files):
                logger.info(f"AppBuilder processing file {i+1}: {parsed_file.get('path', 'unknown')}")
                file_path = parsed_file['path']
                content = parsed_file['content']
                
                # Strip markdown markers from file content
                from agents.llm.validators import strip_markdown_markers
                content = strip_markdown_markers(content)
                
                # Validate based on file type
                if file_path.endswith('.html'):
                    content = validate_html(content)
                elif file_path.endswith('.css'):
                    content = validate_css(content)
                elif file_path.endswith('.js'):
                    content = validate_js(content)
                
                files.append({
                    'type': 'create_file',
                    'file_path': f'{app_dir}/{file_path}',
                    'content': content,
                    'directory': app_dir
                })
            
            return files
            
        except Exception as e:
            logger.error(f"AppBuilder failed to generate files: {e}")
            raise Exception(f"File generation failed: {e}")
    
    def _validate_files_match_manifest(
        self, 
        files: List[Dict[str, Any]], 
        manifest: BuildManifest
    ) -> None:
        """Step 4: Validate generated files match manifest"""
        
        generated_paths = set([
            Path(f['file_path']).name for f in files
        ])
        
        expected_paths = set([f.path for f in manifest.files])
        
        missing = expected_paths - generated_paths
        if missing:
            raise ValueError(f"Manifest promised files not generated: {missing}")
        
        logger.info("AppBuilder: all manifest files generated")
    
    def _generate_deployment_files(
        self, 
        task_spec: TaskSpec, 
        manifest: BuildManifest
    ) -> List[Dict[str, Any]]:
        """Generate Dockerfile and package.json"""
        app_dir = f"/app/warm-boot/apps/{self._to_kebab_case(task_spec.app_name)}"
        
        files = []
        
        # Dockerfile - generic to copy all files
        dockerfile = f'''FROM nginx:alpine
COPY . /usr/share/nginx/html/
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]'''
        
        files.append({
            'type': 'create_file',
            'file_path': f'{app_dir}/Dockerfile',
            'content': dockerfile,
            'directory': app_dir
        })
        
        # package.json
        package = {
            "name": self._to_kebab_case(task_spec.app_name),
            "version": task_spec.version,
            "description": f"{task_spec.app_name} - AI Squad built application",
            "scripts": {
                "serve": "python -m http.server 8080"
            }
        }
        
        files.append({
            'type': 'create_file',
            'file_path': f'{app_dir}/package.json',
            'content': json.dumps(package, indent=2),
            'directory': app_dir
        })
        
        return files
    
    def _to_kebab_case(self, name: str) -> str:
        """Convert app name to kebab-case"""
        import re
        name = re.sub(r'([a-z0-9])([A-Z])', r'\1-\2', name)
        return name.lower().replace(' ', '-')
    
    async def _call_ollama_json(self, prompt: str, model: str = "qwen2.5-coder:7b") -> Dict:
        """Call Ollama with JSON format enforcement"""
        import aiohttp
        
        async with aiohttp.ClientSession() as session:
            payload = {
                "model": model,
                "prompt": prompt,
                "format": "json",  # Forces JSON output
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "num_ctx": 8192  # Context window
                }
            }
            
            async with session.post(
                "http://localhost:11434/api/generate",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=300)  # 5 min timeout
            ) as response:
                if response.status != 200:
                    raise Exception(f"Ollama API error: {response.status}")
                
                result = await response.json()
                
                # Parse JSON from response
                return json.loads(result['response'])
    
    async def generate_manifest_json(self, task_spec: TaskSpec) -> BuildManifest:
        """Generate BuildManifest using JSON-based Ollama call"""
        logger.info(f"AppBuilder generating manifest JSON for {task_spec.app_name}")
        
        # Load JSON architect prompt
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
            # Call Ollama with JSON format
            response = await self._call_ollama_json(prompt)
            
            # Convert JSON response to BuildManifest
            manifest = BuildManifest.from_dict(response)
            
            # ENFORCE FRAMEWORK CONSTRAINT: Always set to vanilla_js (SquadOps standard)
            logger.info(f"AppBuilder parsed manifest JSON: {manifest.architecture_type}, LLM framework: {manifest.framework}")
            manifest.framework = "vanilla_js"  # Always override - no LLM choice
            logger.info(f"AppBuilder final manifest JSON: {manifest.architecture_type}, framework: {manifest.framework} (SquadOps standard)")
            
            return manifest
            
        except Exception as e:
            logger.error(f"AppBuilder failed to generate manifest JSON: {e}")
            raise Exception(f"Manifest JSON generation failed: {e}")
    
    async def generate_files_json(self, task_spec: TaskSpec, manifest: BuildManifest) -> List[Dict[str, Any]]:
        """Generate application files using JSON-based Ollama call"""
        logger.info(f"AppBuilder generating files JSON for {task_spec.app_name}")
        
        # Load JSON developer prompt
        developer_prompt = self._load_prompt(
            'developer.txt',
            app_name=task_spec.app_name,
            version=task_spec.version,
            run_id=task_spec.run_id,
            prd_analysis=task_spec.prd_analysis,
            output_format='json'
        )
        
        # Create manifest summary
        file_list = '\n'.join([
            f"  - {f.path}: {f.purpose}"
            for f in manifest.files
        ])
        manifest_summary = f"""Type: {manifest.architecture_type}
Files to generate:
{file_list}"""
        
        # Load SquadOps constraints
        constraints = self._load_prompt(
            'squadops_constraints.txt',
            version=task_spec.version,
            run_id=task_spec.run_id
        )
        
        # Inject context
        prompt = developer_prompt.replace('$manifest_summary', manifest_summary)
        prompt = prompt.replace('$squadops_constraints', constraints)
        
        logger.info(f"AppBuilder loaded developer JSON prompt, length: {len(prompt)}")
        
        try:
            logger.info("AppBuilder making Ollama JSON call for file generation...")
            response = await self._call_ollama_json(prompt)
            
            logger.info(f"AppBuilder received Ollama JSON response with {len(response.get('files', []))} files")
            
            # Convert to internal format
            files = []
            app_dir = f"/app/warm-boot/apps/{self._to_kebab_case(task_spec.app_name)}"
            
            for file_data in response.get('files', []):
                file_path = file_data['path']
                content = file_data['content']
                
                logger.info(f"AppBuilder processing JSON file: {file_path}")
                
                files.append({
                    'type': 'create_file',
                    'file_path': f'{app_dir}/{file_path}',
                    'content': content,
                    'directory': app_dir
                })
            
            logger.info(f"AppBuilder generated {len(files)} files from JSON response")
            return files
            
        except Exception as e:
            logger.error(f"AppBuilder failed to generate files JSON: {e}")
            raise Exception(f"File JSON generation failed: {e}")
