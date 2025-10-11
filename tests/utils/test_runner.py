#!/usr/bin/env python3
"""
Test runner utility for SquadOps test harness
Provides convenient commands for running different test suites
"""

import subprocess
import sys
import argparse
from pathlib import Path

class SquadOpsTestRunner:
    """Test runner for SquadOps framework"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.tests_dir = self.project_root / "tests"
    
    def run_unit_tests(self, verbose=True, coverage=True):
        """Run unit tests"""
        cmd = ["python", "-m", "pytest", "tests/unit/"]
        
        if verbose:
            cmd.append("-v")
        
        if coverage:
            cmd.extend(["--cov=agents", "--cov-report=html", "--cov-report=term"])
        
        return self._run_command(cmd)
    
    def run_integration_tests(self, verbose=True):
        """Run integration tests"""
        cmd = ["python", "-m", "pytest", "tests/integration/"]
        
        if verbose:
            cmd.append("-v")
        
        return self._run_command(cmd)
    
    def run_regression_tests(self, verbose=True):
        """Run regression tests"""
        cmd = ["python", "-m", "pytest", "tests/regression/"]
        
        if verbose:
            cmd.append("-v")
        
        return self._run_command(cmd)
    
    def run_performance_tests(self, verbose=True):
        """Run performance tests"""
        cmd = ["python", "-m", "pytest", "tests/performance/"]
        
        if verbose:
            cmd.append("-v")
        
        return self._run_command(cmd)
    
    def run_all_tests(self, verbose=True, coverage=True):
        """Run all tests"""
        cmd = ["python", "-m", "pytest", "tests/"]
        
        if verbose:
            cmd.append("-v")
        
        if coverage:
            cmd.extend(["--cov=agents", "--cov-report=html", "--cov-report=term"])
        
        return self._run_command(cmd)
    
    def run_specific_test(self, test_path, verbose=True):
        """Run a specific test file or test function"""
        cmd = ["python", "-m", "pytest", test_path]
        
        if verbose:
            cmd.append("-v")
        
        return self._run_command(cmd)
    
    def run_tests_with_markers(self, markers, verbose=True):
        """Run tests with specific markers"""
        cmd = ["python", "-m", "pytest", "-m", markers]
        
        if verbose:
            cmd.append("-v")
        
        return self._run_command(cmd)
    
    def generate_coverage_report(self):
        """Generate detailed coverage report"""
        cmd = [
            "python", "-m", "pytest", "tests/",
            "--cov=agents",
            "--cov=config",
            "--cov=infra/task-api",
            "--cov=infra/health-check",
            "--cov-report=html",
            "--cov-report=term-missing",
            "--cov-report=xml"
        ]
        
        return self._run_command(cmd)
    
    def run_quick_smoke_test(self):
        """Run quick smoke test for basic functionality"""
        cmd = [
            "python", "-m", "pytest", "tests/unit/test_base_agent.py::test_agent_initialization",
            "-v"
        ]
        
        return self._run_command(cmd)
    
    def run_regression_suite(self):
        """Run comprehensive regression test suite"""
        cmd = [
            "python", "-m", "pytest", "tests/regression/",
            "-v",
            "--tb=short",
            "--durations=10"
        ]
        
        return self._run_command(cmd)
    
    def _run_command(self, cmd):
        """Run command and return result"""
        try:
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                check=False
            )
            
            print(f"Command: {' '.join(cmd)}")
            print(f"Return code: {result.returncode}")
            
            if result.stdout:
                print("STDOUT:")
                print(result.stdout)
            
            if result.stderr:
                print("STDERR:")
                print(result.stderr)
            
            return result.returncode == 0
            
        except Exception as e:
            print(f"Error running command: {e}")
            return False

def main():
    """Main CLI interface"""
    parser = argparse.ArgumentParser(description="SquadOps Test Runner")
    parser.add_argument("command", choices=[
        "unit", "integration", "regression", "performance", "all",
        "coverage", "smoke", "specific"
    ], help="Test command to run")
    
    parser.add_argument("--test-path", help="Specific test path (for 'specific' command)")
    parser.add_argument("--markers", help="Test markers (e.g., 'unit and not slow')")
    parser.add_argument("--no-verbose", action="store_true", help="Run without verbose output")
    parser.add_argument("--no-coverage", action="store_true", help="Run without coverage")
    
    args = parser.parse_args()
    
    runner = SquadOpsTestRunner()
    verbose = not args.no_verbose
    coverage = not args.no_coverage
    
    success = False
    
    if args.command == "unit":
        success = runner.run_unit_tests(verbose, coverage)
    elif args.command == "integration":
        success = runner.run_integration_tests(verbose)
    elif args.command == "regression":
        success = runner.run_regression_tests(verbose)
    elif args.command == "performance":
        success = runner.run_performance_tests(verbose)
    elif args.command == "all":
        success = runner.run_all_tests(verbose, coverage)
    elif args.command == "coverage":
        success = runner.generate_coverage_report()
    elif args.command == "smoke":
        success = runner.run_quick_smoke_test()
    elif args.command == "specific":
        if not args.test_path:
            print("Error: --test-path required for 'specific' command")
            sys.exit(1)
        success = runner.run_specific_test(args.test_path, verbose)
    
    if args.markers:
        success = runner.run_tests_with_markers(args.markers, verbose)
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()


