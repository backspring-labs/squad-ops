#!/usr/bin/env python3
"""
Test Development Capability
Develops test code/scripts from test plans.
"""

import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class TestDev:
    """
    Test Development - QA domain capability
    
    Develops test code/scripts from test plans.
    """
    
    def __init__(self, agent_instance):
        """
        Initialize TestDev with agent instance.
        
        Args:
            agent_instance: Agent instance (must have BaseAgent methods/attributes)
        """
        self.agent = agent_instance
        self.name = agent_instance.name if hasattr(agent_instance, 'name') else 'unknown'
    
    async def develop(self, test_plan_uri: str, code_structure: str | None = None, framework: str | None = None) -> dict[str, Any]:
        """
        Develop test code from test plan.
        
        Implements the qa.test_dev capability.
        
        Args:
            test_plan_uri: Path to test plan document
            code_structure: Optional description of application code structure
            framework: Optional testing framework preference (e.g., pytest, unittest, jest)
            
        Returns:
            Dictionary containing:
            - test_files_uri: List of paths where test files were saved
            - test_code: Dictionary mapping test file paths to code content
            - fixtures_uri: Path to test fixtures file (if created)
            - test_framework: Framework used for test code generation
        """
        try:
            # Load test plan
            test_plan_content = await self.agent.read_file(test_plan_uri)
            logger.info(f"{self.name} loaded test plan from {test_plan_uri}")
            
            # Determine framework (default to pytest for Python)
            if not framework:
                framework = "pytest"  # Default to pytest
            
            # Build prompt for test code generation
            prompt = self._build_test_code_prompt(test_plan_content, code_structure, framework)
            
            # Call LLM to generate test code
            if not hasattr(self.agent, 'llm_client') or not self.agent.llm_client:
                raise ValueError("LLM client not initialized")
            
            llm_result = await self.agent.llm_client.complete(
                prompt=prompt,
                temperature=0.5,  # Lower temperature for code generation
                max_tokens=4000
            )
            
            test_code_content = llm_result.get('response', '') if isinstance(llm_result, dict) else str(llm_result)
            
            if not test_code_content:
                raise ValueError("LLM returned empty test code content")
            
            # Parse test code into separate files
            test_files = self._parse_test_code(test_code_content, framework)
            
            # Generate test files directory
            test_plan_path = Path(test_plan_uri)
            test_files_dir = test_plan_path.parent / "test_code"
            test_files_dir.mkdir(parents=True, exist_ok=True)
            
            # Save test files
            test_files_uri = []
            test_code_dict = {}
            
            for i, (filename, code) in enumerate(test_files.items(), 1):
                test_file_path = test_files_dir / filename
                await self.agent.write_file(str(test_file_path), code)
                test_files_uri.append(str(test_file_path))
                test_code_dict[str(test_file_path)] = code
                logger.info(f"{self.name} saved test file {filename} to {test_file_path}")
            
            # Create fixtures file if needed
            fixtures_uri = None
            if framework == "pytest":
                fixtures_content = self._generate_fixtures(test_plan_content, framework)
                fixtures_path = test_files_dir / "conftest.py"
                await self.agent.write_file(str(fixtures_path), fixtures_content)
                fixtures_uri = str(fixtures_path)
                logger.info(f"{self.name} saved fixtures to {fixtures_path}")
            
            # Record memory for test code development
            if hasattr(self.agent, 'record_memory'):
                await self.agent.record_memory(
                    kind="test_code_developed",
                    payload={
                        'test_plan_uri': test_plan_uri,
                        'test_files_count': len(test_files),
                        'test_framework': framework,
                        'test_files_uri': test_files_uri
                    },
                    importance=0.8
                )
            
            return {
                'test_files_uri': test_files_uri,
                'test_code': test_code_dict,
                'fixtures_uri': fixtures_uri,
                'test_framework': framework
            }
            
        except Exception as e:
            logger.error(f"{self.name} failed to develop test code: {e}", exc_info=True)
            raise
    
    def _build_test_code_prompt(self, test_plan_content: str, code_structure: str | None, framework: str) -> str:
        """Build prompt for LLM to generate test code"""
        prompt_parts = [
            f"You are a QA engineer writing test code using {framework}.",
            "",
            "Test Plan:",
            test_plan_content[:3000],  # Limit test plan content
            ""
        ]
        
        if code_structure:
            prompt_parts.extend([
                "Application Code Structure:",
                code_structure,
                ""
            ])
        
        prompt_parts.extend([
            f"Please generate {framework} test code that:",
            "1. Implements all test cases from the test plan",
            "2. Uses appropriate assertions and test structure",
            "3. Includes proper setup and teardown",
            "4. Is well-commented and maintainable",
            "5. Follows best practices for the testing framework",
            "",
            f"Format the output as {framework} test code with clear test functions."
        ])
        
        if framework == "pytest":
            prompt_parts.append("Use pytest fixtures and markers where appropriate.")
        elif framework == "unittest":
            prompt_parts.append("Use unittest.TestCase class structure.")
        elif framework == "jest":
            prompt_parts.append("Use Jest test structure with describe/it blocks.")
        
        return "\n".join(prompt_parts)
    
    def _parse_test_code(self, test_code_content: str, framework: str) -> dict[str, str]:
        """Parse generated test code into separate files"""
        test_files = {}
        
        # Try to split by file markers if present
        file_markers = re.split(r'(?:^|\n)#+\s*File:\s*(.+?)(?:\n|$)', test_code_content, re.MULTILINE)
        
        if len(file_markers) > 1:
            # Files are marked
            for i in range(1, len(file_markers), 2):
                filename = file_markers[i].strip()
                code = file_markers[i + 1] if i + 1 < len(file_markers) else ""
                if filename and code:
                    test_files[filename] = code.strip()
        else:
            # Single file - determine filename based on framework
            if framework == "pytest":
                filename = "test_application.py"
            elif framework == "unittest":
                filename = "test_application.py"
            elif framework == "jest":
                filename = "application.test.js"
            else:
                filename = "test_application.py"
            
            test_files[filename] = test_code_content.strip()
        
        return test_files
    
    def _generate_fixtures(self, test_plan_content: str, framework: str) -> str:
        """Generate test fixtures file"""
        if framework == "pytest":
            fixtures_content = '''"""
Test fixtures for pytest
"""
import pytest

@pytest.fixture
def sample_data():
    """Sample test data fixture"""
    return {
        "test": "data"
    }

@pytest.fixture
def test_client():
    """Test client fixture"""
    # Add your test client setup here
    pass
'''
            return fixtures_content
        else:
            return "# Fixtures not needed for this framework\n"


