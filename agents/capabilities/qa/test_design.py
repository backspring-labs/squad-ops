#!/usr/bin/env python3
"""
Test Design Capability
Designs test plans and test cases from requirements/PRDs.
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional
import re

logger = logging.getLogger(__name__)


class TestDesign:
    """
    Test Design - QA domain capability
    
    Designs test plans and test cases from requirements/PRDs.
    """
    
    def __init__(self, agent_instance):
        """
        Initialize TestDesign with agent instance.
        
        Args:
            agent_instance: Agent instance (must have BaseAgent methods/attributes)
        """
        self.agent = agent_instance
        self.name = agent_instance.name if hasattr(agent_instance, 'name') else 'unknown'
    
    async def design(self, requirements: str, prd_path: Optional[str] = None, context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Design test plan from requirements or PRD.
        
        Implements the qa.test_design capability.
        
        Args:
            requirements: Requirements text or description
            prd_path: Optional path to PRD document
            context: Optional context dictionary with additional information
            
        Returns:
            Dictionary containing:
            - test_plan_uri: Path where test plan was saved
            - test_cases: List of test cases
            - coverage_analysis: Coverage analysis dict
            - test_scenarios: List of test scenarios
        """
        try:
            # Load PRD if provided
            prd_content = None
            if prd_path:
                prd_content = await self.agent.read_file(prd_path)
                logger.info(f"{self.name} loaded PRD from {prd_path}")
            
            # Build prompt for test plan generation
            prompt = self._build_test_plan_prompt(requirements, prd_content, context)
            
            # Call LLM to generate test plan
            if not hasattr(self.agent, 'llm_client') or not self.agent.llm_client:
                raise ValueError("LLM client not initialized")
            
            llm_result = await self.agent.llm_client.complete(
                prompt=prompt,
                temperature=0.7,
                max_tokens=4000
            )
            
            test_plan_content = llm_result.get('response', '') if isinstance(llm_result, dict) else str(llm_result)
            
            if not test_plan_content:
                raise ValueError("LLM returned empty test plan content")
            
            # Generate test plan file path
            test_plan_dir = Path("warm-boot/testing")
            test_plan_dir.mkdir(parents=True, exist_ok=True)
            
            # Find next available test plan number
            existing_plans = list(test_plan_dir.glob("test-plan-*.md"))
            plan_numbers = []
            for plan_file in existing_plans:
                match = re.search(r'test-plan-(\d+)', plan_file.name)
                if match:
                    plan_numbers.append(int(match.group(1)))
            
            next_number = max(plan_numbers) + 1 if plan_numbers else 1
            test_plan_filename = f"test-plan-{next_number:03d}.md"
            test_plan_path = test_plan_dir / test_plan_filename
            
            # Save test plan
            await self.agent.write_file(str(test_plan_path), test_plan_content)
            
            logger.info(f"{self.name} saved test plan to {test_plan_path}")
            
            # Parse test cases and scenarios from test plan
            test_cases = self._extract_test_cases(test_plan_content)
            test_scenarios = self._extract_test_scenarios(test_plan_content)
            coverage_analysis = self._analyze_coverage(test_plan_content, requirements, prd_content)
            
            # Record memory for test plan creation
            if hasattr(self.agent, 'record_memory'):
                await self.agent.record_memory(
                    kind="test_plan_designed",
                    payload={
                        'requirements': requirements,
                        'prd_path': prd_path,
                        'test_plan_uri': str(test_plan_path),
                        'test_cases_count': len(test_cases),
                        'test_scenarios_count': len(test_scenarios)
                    },
                    importance=0.8
                )
            
            return {
                'test_plan_uri': str(test_plan_path),
                'test_cases': test_cases,
                'coverage_analysis': coverage_analysis,
                'test_scenarios': test_scenarios
            }
            
        except Exception as e:
            logger.error(f"{self.name} failed to design test plan: {e}", exc_info=True)
            raise
    
    def _build_test_plan_prompt(self, requirements: str, prd_content: Optional[str], context: Optional[Dict]) -> str:
        """Build prompt for LLM to generate test plan"""
        prompt_parts = [
            "You are a QA engineer designing a comprehensive test plan.",
            "",
            "Requirements:",
            requirements,
            ""
        ]
        
        if prd_content:
            prompt_parts.extend([
                "PRD Document:",
                prd_content[:2000],  # Limit PRD content to avoid token limits
                ""
            ])
        
        if context:
            prompt_parts.extend([
                "Additional Context:",
                str(context),
                ""
            ])
        
        prompt_parts.extend([
            "Please generate a comprehensive test plan that includes:",
            "1. Test objectives and scope",
            "2. Test strategy and approach",
            "3. Test cases with clear test steps, expected results, and priority",
            "4. Test scenarios covering positive, negative, and edge cases",
            "5. Coverage analysis showing which requirements are covered",
            "6. Test environment and data requirements",
            "",
            "Format the output as a markdown document with clear sections."
        ])
        
        return "\n".join(prompt_parts)
    
    def _extract_test_cases(self, test_plan_content: str) -> list:
        """Extract test cases from test plan markdown"""
        test_cases = []
        
        # Look for test case patterns
        # Pattern: Test Case ID, Description, Steps, Expected Result
        test_case_pattern = r'(?:Test Case|TC)[\s#]*(\d+)[:\-]?\s*(.+?)(?=(?:Test Case|TC|##|$)|\Z)'
        matches = re.finditer(test_case_pattern, test_plan_content, re.IGNORECASE | re.DOTALL)
        
        for match in matches:
            test_case_id = match.group(1)
            test_case_content = match.group(2).strip()
            
            # Extract steps and expected result
            steps_match = re.search(r'(?:Steps|Test Steps)[:\-]?\s*(.+?)(?=Expected Result|$)|\Z', test_case_content, re.IGNORECASE | re.DOTALL)
            expected_match = re.search(r'Expected Result[:\-]?\s*(.+?)(?=\n\n|\Z)', test_case_content, re.IGNORECASE | re.DOTALL)
            
            test_case = {
                'id': f"TC-{test_case_id}",
                'description': test_case_content[:200],  # First 200 chars as description
                'steps': steps_match.group(1).strip() if steps_match else "",
                'expected_result': expected_match.group(1).strip() if expected_match else ""
            }
            test_cases.append(test_case)
        
        return test_cases
    
    def _extract_test_scenarios(self, test_plan_content: str) -> list:
        """Extract test scenarios from test plan markdown"""
        test_scenarios = []
        
        # Look for scenario patterns
        scenario_pattern = r'(?:Scenario|Test Scenario)[\s#]*(\d+)[:\-]?\s*(.+?)(?=(?:Scenario|Test Scenario|##|$)|\Z)'
        matches = re.finditer(scenario_pattern, test_plan_content, re.IGNORECASE | re.DOTALL)
        
        for match in matches:
            scenario_id = match.group(1)
            scenario_content = match.group(2).strip()
            
            test_scenario = {
                'id': f"SCENARIO-{scenario_id}",
                'description': scenario_content[:300],  # First 300 chars as description
                'type': 'positive' if 'positive' in scenario_content.lower() else 'negative' if 'negative' in scenario_content.lower() else 'edge'
            }
            test_scenarios.append(test_scenario)
        
        return test_scenarios
    
    def _analyze_coverage(self, test_plan_content: str, requirements: str, prd_content: Optional[str]) -> Dict[str, Any]:
        """Analyze test coverage"""
        # Simple coverage analysis
        # Count requirements keywords mentioned in test plan
        requirements_keywords = re.findall(r'\b(?:requirement|feature|functionality|user story)\b', requirements.lower())
        test_plan_lower = test_plan_content.lower()
        
        covered_keywords = []
        for keyword in requirements_keywords:
            if keyword in test_plan_lower:
                covered_keywords.append(keyword)
        
        coverage_percentage = (len(covered_keywords) / len(requirements_keywords) * 100) if requirements_keywords else 0
        
        return {
            'requirements_count': len(requirements_keywords),
            'covered_requirements': len(covered_keywords),
            'coverage_percentage': round(coverage_percentage, 2),
            'gaps': []  # Could be enhanced to identify specific gaps
        }


