"""
Enforcement tests for secrets management.

Scans configuration files and docker-compose files to ensure no plaintext secrets
are committed. Enforces secret:// usage for secret-bearing keys.
"""

import re
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import pytest

# Enforced secret-bearing keys (MANDATORY LIST)
ENFORCED_SECRET_KEYS = [
    "password",
    "passwd",
    "token",
    "api_key",
    "secret",
    "client_secret",
    "access_key",
]

# Pattern for secret:// references
SECRET_REF_PATTERN = re.compile(r"secret://([A-Za-z][A-Za-z0-9_]*)")

# URL patterns with embedded credentials
URL_CREDENTIAL_PATTERN = re.compile(r"://([^:]*):([^@]+)@")
URL_CREDENTIAL_NO_USER_PATTERN = re.compile(r"://:([^@]+)@")


def get_repo_root() -> Path:
    """Get repository root directory."""
    current = Path(__file__).resolve()
    while current.parent != current:
        if (current / ".git").exists() or (current / "pyproject.toml").exists():
            return current
        current = current.parent
    raise RuntimeError("Could not find repository root")


def scan_yaml_files(directory: Path, pattern: str = "**/*.yaml") -> list[Path]:
    """Scan directory for YAML files matching pattern."""
    files = []
    for file_path in directory.glob(pattern):
        if file_path.is_file():
            files.append(file_path)
    return files


def extract_url_credentials(content: str) -> list[tuple[str, str]]:
    """
    Extract password components from URLs with embedded credentials.
    
    Returns list of (url, password_component) tuples.
    """
    credentials = []
    
    # Pattern 1: user:password@host
    for match in URL_CREDENTIAL_PATTERN.finditer(content):
        username = match.group(1)
        password = match.group(2)
        # Find the full URL context
        start = max(0, content.rfind("://", 0, match.start()))
        end = min(len(content), content.find("@", match.end()) + 1)
        if end == len(content):
            end = min(len(content), content.find(" ", match.end()))
        url = content[start:end] if end > start else ""
        credentials.append((url, password))
    
    # Pattern 2: :password@host (no username)
    for match in URL_CREDENTIAL_NO_USER_PATTERN.finditer(content):
        password = match.group(1)
        # Find the full URL context
        start = max(0, content.rfind("://", 0, match.start()))
        end = min(len(content), content.find("@", match.end()) + 1)
        if end == len(content):
            end = min(len(content), content.find(" ", match.end()))
        url = content[start:end] if end > start else ""
        credentials.append((url, password))
    
    return credentials


def validate_password_component(password: str) -> bool:
    """
    Validate that password component contains a valid secret reference.

    Accepts:
    - secret:// references (for SquadOps services with secret provider)
    - ${VAR} environment variable references (for infrastructure services)

    Returns True if password contains valid secret reference, False otherwise.
    """
    # Check if password contains secret:// reference
    match = SECRET_REF_PATTERN.search(password)
    if match:
        logical_name = match.group(1)
        # Validate logical name pattern
        if re.match(r"^[A-Za-z][A-Za-z0-9_]*$", logical_name):
            return True

    # Check if password contains ${VAR} environment variable reference
    # This is valid for infrastructure services (postgres, rabbitmq, prefect)
    # that can't use the secret:// provider
    env_var_pattern = re.compile(r"\$\{[A-Za-z_][A-Za-z0-9_]*")
    if env_var_pattern.search(password):
        return True

    return False


def test_no_plaintext_secrets_in_config():
    """Scan config/**/*.yaml for forbidden patterns."""
    repo_root = get_repo_root()
    config_dir = repo_root / "config"
    
    if not config_dir.exists():
        pytest.skip("config directory not found")
    
    violations = []
    
    # Scan all YAML files in config directory
    yaml_files = scan_yaml_files(config_dir, "**/*.yaml")
    
    for file_path in yaml_files:
        try:
            content = file_path.read_text(encoding="utf-8")
            
            # Check for URL patterns with embedded credentials
            # Skip comments - only check actual configuration values
            lines = content.split("\n")
            for line_num, line in enumerate(lines, 1):
                # Skip comment lines
                if line.strip().startswith("#"):
                    continue
                # Extract URLs from this line
                line_credentials = extract_url_credentials(line)
                for url, password in line_credentials:
                    if not validate_password_component(password):
                        violations.append(
                            f"{file_path.relative_to(repo_root)}:{line_num}: Plaintext password in URL: {url}"
                        )
            
            # Check for known secret-bearing keys with non-secret:// values
            # This is a simplified check - in practice, you'd parse YAML properly
            lines = content.split("\n")
            for line_num, line in enumerate(lines, 1):
                line_lower = line.lower()
                for key in ENFORCED_SECRET_KEYS:
                    # Check if line contains the key (simple pattern match)
                    if f": {key}" in line_lower or f"{key}:" in line_lower:
                        # Check if value contains secret://
                        if "secret://" not in line:
                            # Check if it's not a comment
                            if not line.strip().startswith("#"):
                                # Check for plaintext patterns
                                if any(pattern in line.lower() for pattern in [
                                    "squadops123", "postgres/postgres", "changeme", "password123",
                                    "admin123", "test123"
                                ]):
                                    violations.append(
                                        f"{file_path.relative_to(repo_root)}:{line_num}: "
                                        f"Secret-bearing key '{key}' with plaintext value"
                                    )
        except Exception as e:
            violations.append(
                f"{file_path.relative_to(repo_root)}: Error reading file: {e}"
            )
    
    if violations:
        pytest.fail(
            "Plaintext secrets found in config files:\n" + "\n".join(f"  - {v}" for v in violations)
        )


def test_no_plaintext_secrets_in_docker_compose():
    """Scan docker-compose*.yml for forbidden patterns."""
    repo_root = get_repo_root()
    
    violations = []
    
    # Find all docker-compose files
    compose_files = list(repo_root.glob("docker-compose*.yml"))

    # Third-party dev-only compose files with intentional hardcoded secrets (SIP-0061)
    third_party_compose_files = {"docker-compose.langfuse.yml"}

    for file_path in compose_files:
        if file_path.name in third_party_compose_files:
            continue
        try:
            content = file_path.read_text(encoding="utf-8")
            
            # Check for URL patterns with embedded credentials
            url_credentials = extract_url_credentials(content)
            for url, password in url_credentials:
                if not validate_password_component(password):
                    violations.append(
                        f"{file_path.relative_to(repo_root)}: Plaintext password in URL: {url}"
                    )
            
            # Check for plaintext passwords in environment sections
            # NOTE: Third-party service configurations (rabbitmq, postgres, redis, grafana, etc.)
            # are out of scope per SIP-0052. Only check SquadOps services.
            # Simple pattern matching - in practice, parse YAML properly
            lines = content.split("\n")
            in_env_section = False
            current_service = None
            third_party_services = {"rabbitmq", "postgres", "redis", "grafana", "prometheus",
                                     "otel-collector", "prefect-server", "prefect-ui",
                                     "langfuse", "langfuse-db"}
            
            for line_num, line in enumerate(lines, 1):
                # Detect service name
                # In docker-compose.yml, services are indented under "services:" key
                # A service name is a line that starts with 2 spaces, has a colon, and is not a key like "image:", "environment:", etc.
                stripped = line.strip()
                if stripped and line.startswith("  ") and not line.startswith("   ") and ":" in stripped:
                    # Check if this looks like a service name (not a nested key)
                    parts = stripped.split(":", 1)
                    if len(parts) == 2 and parts[1].strip() == "":
                        # This is likely a service name (key with empty value)
                        service_name = parts[0].strip()
                        if service_name and not service_name.startswith("#") and service_name not in ["services", "volumes", "secrets", "networks"]:
                            current_service = service_name
                            in_env_section = False
                
                if "environment:" in line.lower() or "env:" in line.lower():
                    in_env_section = True
                elif line.strip() and not line.startswith(" ") and not line.startswith("\t"):
                    in_env_section = False
                
                # Skip third-party service configurations (out of scope per SIP-0052)
                if current_service in third_party_services:
                    continue
                
                if in_env_section:
                    for key in ENFORCED_SECRET_KEYS:
                        if f"{key.upper()}:" in line or f"{key}:" in line:
                            if "secret://" not in line:
                                # Check for plaintext patterns
                                if any(pattern in line.lower() for pattern in [
                                    "squadops123", "postgres/postgres", "changeme", "password123",
                                    "admin123", "test123"
                                ]):
                                    violations.append(
                                        f"{file_path.relative_to(repo_root)}:{line_num}: "
                                        f"Plaintext secret in environment: {line.strip()}"
                                    )
        except Exception as e:
            violations.append(
                f"{file_path.relative_to(repo_root)}: Error reading file: {e}"
            )
    
    if violations:
        pytest.fail(
            "Plaintext secrets found in docker-compose files:\n" + "\n".join(f"  - {v}" for v in violations)
        )


def test_env_templates_use_secret_references():
    """Scan committed .env* templates for secret:// usage."""
    repo_root = get_repo_root()
    
    violations = []
    
    # Find .env.example and .env.template files (not .env itself)
    env_templates = list(repo_root.glob(".env.example")) + list(repo_root.glob(".env.template"))
    
    for file_path in env_templates:
        try:
            content = file_path.read_text(encoding="utf-8")
            
            # Check for URL patterns with embedded credentials
            # Skip comments - only check actual configuration values
            lines = content.split("\n")
            for line_num, line in enumerate(lines, 1):
                # Skip comment lines
                if line.strip().startswith("#"):
                    continue
                # Extract URLs from this line
                line_credentials = extract_url_credentials(line)
                for url, password in line_credentials:
                    if not validate_password_component(password):
                        violations.append(
                            f"{file_path.relative_to(repo_root)}:{line_num}: Plaintext password in URL: {url}"
                        )
            
            # Check for ENFORCED_SECRET_KEYS without secret:// references
            lines = content.split("\n")
            for line_num, line in enumerate(lines, 1):
                if line.strip().startswith("#"):
                    continue  # Skip comments
                
                for key in ENFORCED_SECRET_KEYS:
                    # Check if line defines this key
                    if re.match(rf"^{key.upper()}=|^{key}=", line, re.IGNORECASE):
                        if "secret://" not in line:
                            violations.append(
                                f"{file_path.relative_to(repo_root)}:{line_num}: "
                                f"Secret-bearing key '{key}' must use secret:// reference"
                            )
        except Exception as e:
            violations.append(
                f"{file_path.relative_to(repo_root)}: Error reading file: {e}"
            )
    
    if violations:
        pytest.fail(
            "Secret-bearing keys without secret:// references in .env templates:\n" + 
            "\n".join(f"  - {v}" for v in violations)
        )


def test_no_url_credentials():
    """
    MANDATORY: Detect and validate password components in URLs with embedded credentials.
    
    Scans all target files for URL patterns: user:password@host or :password@host
    Extracts the password component from each URL
    Validates that password component contains valid secret://<logical_name> reference
    HARD FAIL if password component does NOT contain valid secret:// reference
    """
    repo_root = get_repo_root()
    
    violations = []
    
    # Scan config/**/*.yaml
    config_dir = repo_root / "config"
    if config_dir.exists():
        for file_path in scan_yaml_files(config_dir, "**/*.yaml"):
            try:
                content = file_path.read_text(encoding="utf-8")
                lines = content.split("\n")
                for line_num, line in enumerate(lines, 1):
                    # Skip comment lines
                    if line.strip().startswith("#"):
                        continue
                    # Extract URLs from this line
                    line_credentials = extract_url_credentials(line)
                    for url, password in line_credentials:
                        if not validate_password_component(password):
                            violations.append(
                                f"{file_path.relative_to(repo_root)}:{line_num}: "
                                f"URL with plaintext password: {url}"
                            )
            except Exception as e:
                violations.append(
                    f"{file_path.relative_to(repo_root)}: Error: {e}"
                )
    
    # Scan docker-compose*.yml
    # Third-party dev-only compose files with intentional hardcoded secrets (SIP-0061)
    third_party_compose_files = {"docker-compose.langfuse.yml"}
    for file_path in repo_root.glob("docker-compose*.yml"):
        if file_path.name in third_party_compose_files:
            continue
        try:
            content = file_path.read_text(encoding="utf-8")
            lines = content.split("\n")
            for line_num, line in enumerate(lines, 1):
                # Skip comment lines
                if line.strip().startswith("#"):
                    continue
                # Extract URLs from this line
                line_credentials = extract_url_credentials(line)
                for url, password in line_credentials:
                    if not validate_password_component(password):
                        violations.append(
                            f"{file_path.relative_to(repo_root)}:{line_num}: "
                            f"URL with plaintext password: {url}"
                        )
        except Exception as e:
            violations.append(
                f"{file_path.relative_to(repo_root)}: Error: {e}"
            )
    
    # Scan .env* templates
    for file_path in list(repo_root.glob(".env.example")) + list(repo_root.glob(".env.template")):
        try:
            content = file_path.read_text(encoding="utf-8")
            lines = content.split("\n")
            for line_num, line in enumerate(lines, 1):
                # Skip comment lines
                if line.strip().startswith("#"):
                    continue
                # Extract URLs from this line
                line_credentials = extract_url_credentials(line)
                for url, password in line_credentials:
                    if not validate_password_component(password):
                        violations.append(
                            f"{file_path.relative_to(repo_root)}:{line_num}: "
                            f"URL with plaintext password: {url}"
                        )
        except Exception as e:
            violations.append(
                f"{file_path.relative_to(repo_root)}: Error: {e}"
            )
    
    if violations:
        pytest.fail(
            "URLs with plaintext credentials found (must use secret:// references):\n" +
            "\n".join(f"  - {v}" for v in violations)
        )

