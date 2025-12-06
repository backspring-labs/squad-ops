"""
AppBuilder - JSON workflow application building using LLM.

Uses structured JSON output from LLMs for manifest and file generation.
"""

import logging
from pathlib import Path
from typing import Any

import yaml

from agents.llm.client import LLMClient

logger = logging.getLogger(__name__)


class AppBuilder:
    """Builds application artifacts using JSON-based LLM workflow"""
    
    def __init__(self, llm_client: LLMClient = None, agent=None):
        self.llm_client = llm_client
        self.agent = agent  # Optional agent reference for logging LLM calls (Task 1.1)
    
    def _load_prompt(self, template_name: str, **kwargs) -> str:
        """Load and format prompt template"""
        template_content = None
        safe_kwargs = {}
        
        try:
            template_path = Path(__file__).parent / 'prompts' / template_name
            with open(template_path) as f:
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
    
    async def _call_llm_json(self, prompt: str, context: str = "AppBuilder") -> dict:
        """Call LLM via router with JSON format enforcement and telemetry logging
        
        Uses the LLM router abstraction layer instead of direct HTTP calls.
        This ensures proper provider abstraction, USE_LOCAL_LLM handling, and unified config.
        """
        import json
        from datetime import datetime
        
        # Ensure we have an LLM client (from router)
        if not self.llm_client:
            raise Exception("AppBuilder requires an LLM client. Ensure DevAgent initializes with llm_client from router.")
        
        # Create telemetry span for LLM call if agent available (Task 1.1)
        span_ctx = None
        if self.agent:
            span_name = f"llm_call.{context.lower().replace(' ', '_')}"
            span_ctx = self.agent.create_span(span_name, {
                'agent.name': self.agent.name,
                'llm.operation': context,
                'llm.prompt_length': len(prompt),
                'cycle_id': getattr(self.agent, 'current_cycle_id', None)
            })
        
        # Call LLM via router with JSON format
        try:
            if span_ctx:
                with span_ctx:
                    response_text = await self.llm_client.complete(
                        prompt=prompt,
                        temperature=0.3,
                        max_tokens=4000,
                        format='json',  # Request JSON format
                        top_p=0.9
                    )
            else:
                response_text = await self.llm_client.complete(
                    prompt=prompt,
                    temperature=0.3,
                    max_tokens=4000,
                    format='json',  # Request JSON format
                    top_p=0.9
                )
            
            # Get token usage if available
            token_usage = None
            if hasattr(self.llm_client, 'get_token_usage'):
                token_usage = self.llm_client.get_token_usage()
            
            # Log to communication log if agent available (Task 1.1)
            if self.agent:
                # Get trace ID if span is active
                trace_id = None
                try:
                    from opentelemetry import trace
                    active_span = trace.get_current_span()
                    if active_span and hasattr(active_span, 'get_span_context'):
                        span_context = active_span.get_span_context()
                        if span_context and span_context.trace_id:
                            trace_id = format(span_context.trace_id, '032x')
                except Exception:
                    pass
                
                log_entry = {
                    'timestamp': datetime.utcnow().isoformat(),
                    'agent': self.agent.name,
                    'message_type': 'llm_reasoning',
                    'description': f"AppBuilder {context}: {response_text[:500]}...",
                    'cycle_id': getattr(self.agent, 'current_cycle_id', None),
                    'prompt': prompt,  # Task 1.1: Capture prompt
                    'full_response': response_text,
                    'trace_id': trace_id  # Task 1.1: Link to telemetry trace
                }
                
                # Include token usage in communication log (Task 1.3)
                if token_usage:
                    log_entry['token_usage'] = token_usage
                
                self.agent.communication_log.append(log_entry)
                
                # Record token usage metric if available
                if token_usage:
                    try:
                        cycle_id = getattr(self.agent, 'current_cycle_id', None)
                        labels = {
                            'agent': self.agent.name,
                            'operation': context.lower().replace(' ', '_'),
                        }
                        if cycle_id:
                            labels['cycle_id'] = cycle_id
                        
                        total_tokens = token_usage.get('total_tokens', 0)
                        self.agent.record_counter('agent_tokens_used_total', total_tokens, labels)
                        logger.debug(f"AppBuilder LLM call used {total_tokens} tokens ({token_usage.get('prompt_tokens', 0)} prompt + {token_usage.get('completion_tokens', 0)} completion)")
                    except Exception as e:
                        logger.debug(f"AppBuilder failed to record token usage metric: {e}")
            
            # Parse JSON response
            try:
                return json.loads(response_text)
            except json.JSONDecodeError as e:
                logger.error(f"AppBuilder JSON parse error: {e}")
                logger.error(f"AppBuilder raw response: {response_text[:500]}...")
                raise Exception(f"Invalid JSON response from LLM: {e}") from e
                
        except Exception as e:
            error_msg = str(e) if e else f"{type(e).__name__}: {repr(e)}"
            logger.error(f"AppBuilder LLM call failed: {error_msg}")
            logger.debug("AppBuilder exception details:", exc_info=True)
            raise Exception(f"LLM call failed: {error_msg}") from e
    
    
    async def generate_manifest_json(self, requirements: dict[str, Any]) -> dict[str, Any]:
        """Generate BuildManifest using JSON-based LLM call via router"""
        logger.info(f"AppBuilder generating manifest for {requirements.get('app_name', 'unknown')}")
        # Pass context for telemetry logging
        return await self._generate_manifest_with_context(requirements, context="manifest_generation")
    
    async def _generate_manifest_with_context(self, requirements: dict[str, Any], context: str) -> dict[str, Any]:
        """Generate manifest with context for telemetry"""
        
        # Load architect prompt with JSON output format
        architect_prompt = self._load_prompt(
            'architect.txt',
            app_name=requirements.get('app_name', 'unknown'),
            version=requirements.get('version', '1.0.0'),
            prd_analysis=requirements.get('prd_analysis', ''),
            features=', '.join(requirements.get('features', [])) if requirements.get('features') else 'General web application',
            constraints=yaml.dump(requirements.get('constraints', {})) if requirements.get('constraints') else 'None',
            output_format='json'
        )
        
        # Convert app name to kebab-case for nginx subpath
        app_name_kebab = self._to_kebab_case(requirements.get('app_name', 'application'))
        
        # Load SquadOps constraints with app name in kebab-case
        constraints = self._load_prompt(
            'squadops_constraints.txt',
            version=requirements.get('version', '1.0.0'),
            run_id=requirements.get('run_id', 'unknown'),
            app_name_kebab=app_name_kebab
        )
        
        # Inject constraints into architect prompt
        prompt = architect_prompt.replace('$squadops_constraints', constraints)
        
        try:
            # Call LLM via router with JSON format enforcement
            manifest_data = await self._call_llm_json(prompt, context=context)
            
            # ENFORCE FRAMEWORK CONSTRAINT: Always set to vanilla_js (SquadOps standard)
            logger.info(f"AppBuilder parsed manifest: {manifest_data.get('architecture_type', 'unknown')}, LLM framework: {manifest_data.get('framework', 'unknown')}")
            manifest_data['framework'] = "vanilla_js"  # Always override - no LLM choice
            logger.info(f"AppBuilder final manifest: {manifest_data.get('architecture_type', 'unknown')}, framework: {manifest_data.get('framework', 'vanilla_js')} (SquadOps standard)")
            
            return manifest_data
            
        except Exception as e:
            error_msg = str(e) if e else f"{type(e).__name__}: {repr(e)}"
            logger.error(f"AppBuilder failed to generate manifest: {error_msg}")
            logger.debug("AppBuilder exception details:", exc_info=True)
            raise Exception(f"Manifest generation failed: {error_msg}") from e
    
    async def generate_files_json(self, requirements: dict[str, Any], manifest: dict[str, Any]) -> list[dict[str, Any]]:
        """Generate application files using JSON-based LLM call via router"""
        logger.info(f"AppBuilder generating files for {requirements.get('app_name', 'unknown')}")
        # Pass context for telemetry logging
        return await self._generate_files_with_context(requirements, manifest, context="file_generation")
    
    async def _generate_files_with_context(self, requirements: dict[str, Any], manifest: dict[str, Any], context: str) -> list[dict[str, Any]]:
        """Generate files with context for telemetry"""
        # Convert app name to kebab-case for nginx subpath
        app_name_kebab = self._to_kebab_case(requirements.get('app_name', 'application'))
        
        # Load developer prompt with JSON output format
        developer_prompt = self._load_prompt(
            'developer.txt',
            app_name=requirements.get('app_name', 'unknown'),
            app_name_kebab=app_name_kebab,
            version=requirements.get('version', '1.0.0'),
            prd_analysis=requirements.get('prd_analysis', ''),
            features=', '.join(requirements.get('features', [])) if requirements.get('features') else 'General web application',
            constraints=yaml.dump(requirements.get('constraints', {})) if requirements.get('constraints') else 'None',
            manifest_summary=yaml.dump(manifest),
            output_format='json'
        )
        
        # Load SquadOps constraints with app name in kebab-case
        constraints = self._load_prompt(
            'squadops_constraints.txt',
            version=requirements.get('version', '1.0.0'),
            run_id=requirements.get('run_id', 'unknown'),
            app_name_kebab=app_name_kebab
        )
        
        # Inject constraints into developer prompt
        prompt = developer_prompt.replace('$squadops_constraints', constraints)
        
        try:
            # Call LLM via router with JSON format enforcement
            files_data = await self._call_llm_json(prompt, context=context)
            
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
                    'directory': file_data.get('directory') or ''  # Normalize None to empty string
                })
            
            logger.info(f"AppBuilder generated {len(file_list)} files from JSON response")
            return file_list
            
        except Exception as e:
            error_msg = str(e) if e else f"{type(e).__name__}: {repr(e)}"
            logger.error(f"AppBuilder failed to generate files: {error_msg}")
            logger.debug("AppBuilder exception details:", exc_info=True)
            raise Exception(f"File generation failed: {error_msg}") from e