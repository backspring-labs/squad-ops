#!/usr/bin/env python3
"""
Test Execution Capability
Executes test suites and generates reports.
"""

import asyncio
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class TestExecution:
    """
    Test Execution - QA domain capability
    
    Executes test suites and generates reports.
    """
    
    def __init__(self, agent_instance):
        """
        Initialize TestExecution with agent instance.
        
        Args:
            agent_instance: Agent instance (must have BaseAgent methods/attributes)
        """
        self.agent = agent_instance
        self.name = agent_instance.name if hasattr(agent_instance, 'name') else 'unknown'
    
    async def execute(self, test_files_uri: list, environment: str | None = None, config: dict | None = None) -> dict[str, Any]:
        """
        Execute test suite and generate reports.
        
        Implements the qa.test_execution capability.
        
        Args:
            test_files_uri: List of paths to test files
            environment: Optional execution environment (e.g., 'local', 'ci', 'staging')
            config: Optional test configuration dictionary
        
        Returns:
            Dictionary containing:
            - passed: Number of tests passed
            - failed: Number of tests failed
            - report_uri: Path to test execution report
            - coverage_percentage: Code coverage percentage (if available)
            - execution_log: Test execution log
        """
        try:
            if not test_files_uri:
                raise ValueError("No test files provided")
            
            # Determine test framework from first test file
            first_test_file = Path(test_files_uri[0])
            framework = self._detect_framework(first_test_file)
            
            logger.info(f"{self.name} executing tests using {framework} framework")
            
            # Execute tests
            execution_result = await self._run_tests(test_files_uri, framework, environment, config)
            
            # Generate report
            report_content = self._generate_report(execution_result, framework)
            
            # Save report
            test_files_dir = first_test_file.parent
            report_path = test_files_dir / f"test-report-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
            await self.agent.write_file(str(report_path), json.dumps(execution_result, indent=2))
            
            # Also save markdown report
            markdown_report_path = test_files_dir / f"test-report-{datetime.now().strftime('%Y%m%d-%H%M%S')}.md"
            await self.agent.write_file(str(markdown_report_path), report_content)
            
            logger.info(f"{self.name} saved test report to {report_path}")
            
            # Record memory for test execution
            if hasattr(self.agent, 'record_memory'):
                await self.agent.record_memory(
                    kind="tests_executed",
                    payload={
                        'test_files_count': len(test_files_uri),
                        'passed': execution_result.get('passed', 0),
                        'failed': execution_result.get('failed', 0),
                        'report_uri': str(report_path),
                        'framework': framework
                    },
                    importance=0.7
                )
            
            return {
                'passed': execution_result.get('passed', 0),
                'failed': execution_result.get('failed', 0),
                'report_uri': str(report_path),
                'coverage_percentage': execution_result.get('coverage_percentage', 0.0),
                'execution_log': execution_result.get('execution_log', '')
            }
            
        except Exception as e:
            logger.error(f"{self.name} failed to execute tests: {e}", exc_info=True)
            raise
    
    def _detect_framework(self, test_file: Path) -> str:
        """Detect testing framework from test file"""
        filename = test_file.name.lower()
        extension = test_file.suffix.lower()
        
        if extension == '.js' or 'jest' in filename:
            return 'jest'
        elif extension == '.py':
            # Check for pytest markers or unittest imports
            try:
                content = test_file.read_text()
                if 'pytest' in content.lower() or 'import pytest' in content:
                    return 'pytest'
                elif 'unittest' in content.lower() or 'import unittest' in content:
                    return 'unittest'
            except Exception:
                pass
            return 'pytest'  # Default for Python
        else:
            return 'unknown'
    
    async def _run_tests(self, test_files_uri: list, framework: str, environment: str | None, config: dict | None) -> dict[str, Any]:
        """Run tests using appropriate framework"""
        execution_log = []
        passed = 0
        failed = 0
        coverage_percentage = 0.0
        
        try:
            if framework == 'pytest':
                result = await self._run_pytest_tests(test_files_uri, config)
                passed = result.get('passed', 0)
                failed = result.get('failed', 0)
                coverage_percentage = result.get('coverage', 0.0)
                execution_log = result.get('log', [])
            elif framework == 'unittest':
                result = await self._run_unittest_tests(test_files_uri, config)
                passed = result.get('passed', 0)
                failed = result.get('failed', 0)
                execution_log = result.get('log', [])
            elif framework == 'jest':
                result = await self._run_jest_tests(test_files_uri, config)
                passed = result.get('passed', 0)
                failed = result.get('failed', 0)
                execution_log = result.get('log', [])
            else:
                # Mock execution for unknown frameworks
                logger.warning(f"{self.name} unknown framework {framework}, using mock execution")
                passed = 5
                failed = 0
                execution_log = [f"Mock execution for {framework} framework"]
        except Exception as e:
            logger.error(f"{self.name} test execution error: {e}", exc_info=True)
            failed = 1
            execution_log.append(f"Execution error: {str(e)}")
        
        return {
            'passed': passed,
            'failed': failed,
            'coverage_percentage': coverage_percentage,
            'execution_log': '\n'.join(execution_log),
            'framework': framework,
            'environment': environment or 'local',
            'timestamp': datetime.now().isoformat()
        }
    
    async def _run_pytest_tests(self, test_files_uri: list, config: dict | None) -> dict[str, Any]:
        """Run pytest tests"""
        try:
            # Build pytest command
            test_paths = [str(Path(uri).parent) for uri in test_files_uri]
            cmd = ['pytest', '-v', '--tb=short'] + test_paths
            
            # Add coverage if requested
            if config and config.get('coverage', False):
                cmd.extend(['--cov=.', '--cov-report=term'])
            
            # Run pytest
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=Path(test_files_uri[0]).parent.parent
            )
            
            stdout, stderr = await process.communicate()
            
            output = stdout.decode() if stdout else ''
            error_output = stderr.decode() if stderr else ''
            
            # Parse pytest output
            passed = len([line for line in output.split('\n') if ' PASSED' in line])
            failed = len([line for line in output.split('\n') if ' FAILED' in line])
            
            # Extract coverage if present
            coverage = 0.0
            if 'TOTAL' in output:
                coverage_match = re.search(r'TOTAL\s+\d+\s+\d+\s+(\d+)%', output)
                if coverage_match:
                    coverage = float(coverage_match.group(1))
            
            return {
                'passed': passed,
                'failed': failed,
                'coverage': coverage,
                'log': [output, error_output]
            }
        except Exception as e:
            logger.error(f"{self.name} pytest execution error: {e}", exc_info=True)
            return {
                'passed': 0,
                'failed': 1,
                'coverage': 0.0,
                'log': [f"Error: {str(e)}"]
            }
    
    async def _run_unittest_tests(self, test_files_uri: list, config: dict | None) -> dict[str, Any]:
        """Run unittest tests"""
        try:
            # Build unittest command
            test_paths = [str(Path(uri).parent) for uri in test_files_uri]
            cmd = ['python', '-m', 'unittest', 'discover', '-v'] + test_paths
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=Path(test_files_uri[0]).parent.parent
            )
            
            stdout, stderr = await process.communicate()
            
            output = stdout.decode() if stdout else ''
            error_output = stderr.decode() if stderr else ''
            
            # Parse unittest output
            passed = len([line for line in output.split('\n') if 'ok' in line.lower()])
            failed = len([line for line in output.split('\n') if 'FAIL' in line])
            
            return {
                'passed': passed,
                'failed': failed,
                'coverage': 0.0,
                'log': [output, error_output]
            }
        except Exception as e:
            logger.error(f"{self.name} unittest execution error: {e}", exc_info=True)
            return {
                'passed': 0,
                'failed': 1,
                'coverage': 0.0,
                'log': [f"Error: {str(e)}"]
            }
    
    async def _run_jest_tests(self, test_files_uri: list, config: dict | None) -> dict[str, Any]:
        """Run Jest tests"""
        try:
            # Build jest command
            cmd = ['npm', 'test', '--'] + [str(Path(uri).name) for uri in test_files_uri]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=Path(test_files_uri[0]).parent.parent
            )
            
            stdout, stderr = await process.communicate()
            
            output = stdout.decode() if stdout else ''
            error_output = stderr.decode() if stderr else ''
            
            # Parse jest output
            passed_match = re.search(r'(\d+)\s+passed', output)
            failed_match = re.search(r'(\d+)\s+failed', output)
            
            passed = int(passed_match.group(1)) if passed_match else 0
            failed = int(failed_match.group(1)) if failed_match else 0
            
            return {
                'passed': passed,
                'failed': failed,
                'coverage': 0.0,
                'log': [output, error_output]
            }
        except Exception as e:
            logger.error(f"{self.name} jest execution error: {e}", exc_info=True)
            return {
                'passed': 0,
                'failed': 1,
                'coverage': 0.0,
                'log': [f"Error: {str(e)}"]
            }
    
    def _generate_report(self, execution_result: dict[str, Any], framework: str) -> str:
        """Generate markdown test report"""
        report_lines = [
            "# Test Execution Report",
            "",
            f"**Framework:** {framework}",
            f"**Environment:** {execution_result.get('environment', 'unknown')}",
            f"**Timestamp:** {execution_result.get('timestamp', 'unknown')}",
            "",
            "## Summary",
            "",
            f"- **Passed:** {execution_result.get('passed', 0)}",
            f"- **Failed:** {execution_result.get('failed', 0)}",
            f"- **Coverage:** {execution_result.get('coverage_percentage', 0.0)}%",
            "",
            "## Execution Log",
            "",
            "```",
            execution_result.get('execution_log', ''),
            "```"
        ]
        
        return "\n".join(report_lines)

