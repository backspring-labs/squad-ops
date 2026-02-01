"""
Regression tests to prevent config externalization violations (SIP-051).

These tests ensure that no new direct environment variable reads are added
for configuration in runtime code.
"""

import ast
import os
from pathlib import Path

import pytest


def find_os_getenv_calls(file_path: Path) -> list[tuple[int, str]]:
    """
    Find all os.getenv calls in a Python file using AST parsing.
    
    Returns:
        List of (line_number, variable_name) tuples
    """
    findings = []
    
    try:
        with open(file_path, encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=str(file_path))
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # Check if it's os.getenv(...)
                if (
                    isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "os"
                    and node.func.attr == "getenv"
                ):
                    # Extract the variable name (first argument)
                    if node.args and isinstance(node.args[0], ast.Constant):
                        var_name = node.args[0].value
                        findings.append((node.lineno, var_name))
                    elif node.args and isinstance(node.args[0], ast.Str):  # Python < 3.8
                        var_name = node.args[0].s
                        findings.append((node.lineno, var_name))
    except (SyntaxError, UnicodeDecodeError):
        # Skip files that can't be parsed
        pass
    
    return findings


# Allowed environment variables (not config)
ALLOWED_ENV_VARS = {
    "SQUADOPS_STRICT_CONFIG",  # Loader's own config
    "SQUADOPS_PROFILE",  # Loader's own config
    "SQUADOPS_BASE_PATH",  # Path resolver (chicken-and-egg: needed before config can load)
    "USER",  # System info
    "HOSTNAME",  # System info
    "PATH",  # System info
    "HOME",  # System info
    "PWD",  # System info
}


def is_allowed_env_var(var_name: str) -> bool:
    """Check if an environment variable is allowed (not config)."""
    return var_name in ALLOWED_ENV_VARS


class TestNoDirectConfigReads:
    """Test that runtime code doesn't read config via os.getenv."""

    @pytest.mark.parametrize(
        "code_path",
        [
            "agents",
            "infra/runtime-api",
            "infra/health-check",
        ],
    )
    def test_no_config_env_reads_in_runtime_code(self, code_path):
        """Test that runtime code doesn't use os.getenv for configuration."""
        repo_root = Path(__file__).parent.parent.parent
        code_dir = repo_root / code_path
        
        if not code_dir.exists():
            pytest.skip(f"Code path {code_path} does not exist")
        
        violations = []
        
        # Find all Python files
        for py_file in code_dir.rglob("*.py"):
            # Skip test files
            if "test" in py_file.name or py_file.parent.name == "tests":
                continue
            
            # Skip __pycache__
            if "__pycache__" in str(py_file):
                continue
            
            findings = find_os_getenv_calls(py_file)
            for line_num, var_name in findings:
                if not is_allowed_env_var(var_name):
                    rel_path = py_file.relative_to(repo_root)
                    violations.append(f"{rel_path}:{line_num} - os.getenv('{var_name}')")
        
        if violations:
            violation_list = "\n".join(f"  - {v}" for v in violations)
            pytest.fail(
                f"Found {len(violations)} direct config reads in runtime code:\n{violation_list}\n\n"
                "All configuration should use AppConfig via infra.config.loader.get_config()"
            )

    def test_config_loader_uses_appconfig(self):
        """Test that config loader returns AppConfig instances."""
        from infra.config.loader import load_config
        from infra.config.schema import AppConfig
        
        config = load_config()
        assert isinstance(config, AppConfig)

    def test_all_services_use_get_config(self):
        """Test that migrated services use get_config() pattern."""
        # This is a smoke test - actual verification is in test_no_config_env_reads_in_runtime_code
        # But we can verify that key services import the loader
        repo_root = Path(__file__).parent.parent.parent
        
        key_files = [
            repo_root / "infra" / "runtime-api" / "main.py",
            repo_root / "infra" / "health-check" / "main.py",
            repo_root / "agents" / "base_agent.py",
        ]
        
        for file_path in key_files:
            if not file_path.exists():
                continue
            
            content = file_path.read_text()
            # Should import load_config or get_config
            assert (
                "from infra.config.loader import" in content
                or "infra.config.loader" in content
            ), f"{file_path} should import from infra.config.loader"

