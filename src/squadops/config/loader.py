"""
Configuration loader with layered precedence, profile support, and validation.
"""

import argparse
import logging
import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, get_args, get_origin

import yaml
from pydantic import BaseModel, ValidationError

from squadops.config.errors import ConfigValidationError
from squadops.config.fingerprint import config_fingerprint
from squadops.config.path_resolver import PathResolver
from squadops.config.redaction import redact_config
from squadops.config.schema import AppConfig, SecretsConfig

logger = logging.getLogger(__name__)

# Global singleton instance
_config_instance: AppConfig | None = None

# Schema path map cache
_schema_path_map: dict[str, "SchemaPathInfo"] | None = None


@dataclass
class SchemaPathInfo:
    """Metadata for a schema path."""

    dot_path: str  # e.g., "db.pool_size"
    tuple_path: tuple[str, ...]  # e.g., ("db", "pool_size")
    field_type: type  # e.g., int, bool, TasksBackend, Path
    is_optional: bool
    is_enum: bool = False
    enum_class: type | None = None


def _extract_field_type(annotation: Any) -> tuple[type, bool]:
    """
    Extract the actual field type and whether it's optional.

    Args:
        annotation: Field annotation (may be Union, Optional, etc.)

    Returns:
        Tuple of (field_type, is_optional)
    """
    origin = get_origin(annotation)

    # Handle Optional/Union[Type, None]
    if origin is not None:
        if origin is type(None) or (
            hasattr(origin, "__origin__") and origin.__origin__ is type(None)
        ):
            return (type(None), True)
        args = get_args(annotation)
        if len(args) == 2 and type(None) in args:
            # Optional[Type] -> Union[Type, None]
            non_none_type = next(arg for arg in args if arg is not type(None))
            return (_extract_field_type(non_none_type)[0], True)
        elif len(args) == 1:
            # Generic type like list[str]
            return (annotation, False)

    # Check if it's an Enum
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        return (annotation, False)

    # Direct type
    if isinstance(annotation, type):
        return (annotation, False)

    # Fallback: use annotation as-is
    return (annotation, False)


def _build_schema_path_map() -> dict[str, SchemaPathInfo]:
    """
    Build a complete map of all valid schema paths from AppConfig.

    Recursively traverses AppConfig.model_fields to build paths for all fields,
    including nested models at any depth.

    Returns:
        Dictionary mapping dot-notation paths to SchemaPathInfo objects
    """
    path_map: dict[str, SchemaPathInfo] = {}

    def traverse_model(model_class: type[BaseModel], parent_path: tuple[str, ...] = ()) -> None:
        """
        Recursively traverse a Pydantic model to extract all field paths.

        Args:
            model_class: Pydantic model class to traverse
            parent_path: Tuple of parent path segments (e.g., ("db",))
        """
        if not issubclass(model_class, BaseModel):
            return

        for field_name, field_info in model_class.model_fields.items():
            # Build current path
            current_tuple_path = parent_path + (field_name,)
            dot_path = ".".join(current_tuple_path)

            # Get field annotation
            annotation = field_info.annotation

            # Extract type and optional status
            field_type, is_optional = _extract_field_type(annotation)

            # Check if it's an Enum
            is_enum = False
            enum_class = None
            if isinstance(field_type, type) and issubclass(field_type, Enum):
                is_enum = True
                enum_class = field_type
            elif hasattr(field_type, "__origin__"):
                # Check if it's a generic type that might contain an enum
                args = get_args(field_type)
                for arg in args:
                    if isinstance(arg, type) and issubclass(arg, Enum):
                        is_enum = True
                        enum_class = arg
                        break

            # Check if this field is a nested BaseModel
            is_nested_model = False
            if isinstance(field_type, type) and issubclass(field_type, BaseModel):
                is_nested_model = True
            else:
                # Check if it's Optional[BaseModel] or similar
                origin = get_origin(annotation)
                if origin is not None:
                    args = get_args(annotation)
                    for arg in args:
                        if isinstance(arg, type) and issubclass(arg, BaseModel):
                            is_nested_model = True
                            break

            # Store this path
            path_map[dot_path] = SchemaPathInfo(
                dot_path=dot_path,
                tuple_path=current_tuple_path,
                field_type=field_type,
                is_optional=is_optional,
                is_enum=is_enum,
                enum_class=enum_class,
            )

            # If it's a nested model, recurse into it
            if is_nested_model:
                nested_model_class = field_type
                if not isinstance(nested_model_class, type) or not issubclass(
                    nested_model_class, BaseModel
                ):
                    # Extract from Optional/Union
                    origin = get_origin(annotation)
                    if origin is not None:
                        args = get_args(annotation)
                        for arg in args:
                            if isinstance(arg, type) and issubclass(arg, BaseModel):
                                nested_model_class = arg
                                break

                if isinstance(nested_model_class, type) and issubclass(
                    nested_model_class, BaseModel
                ):
                    traverse_model(nested_model_class, current_tuple_path)

    # Start traversal from AppConfig
    traverse_model(AppConfig)

    return path_map


def _get_schema_path_map() -> dict[str, SchemaPathInfo]:
    """
    Get the schema path map, building it if necessary.

    Returns:
        Dictionary mapping dot-notation paths to SchemaPathInfo objects
    """
    global _schema_path_map
    if _schema_path_map is None:
        _schema_path_map = _build_schema_path_map()
    return _schema_path_map


def _generate_path_segmentations(parts: list[str]) -> list[str]:
    """
    Generate all valid ways to join path parts with underscores.

    Given path parts like ["db", "pool", "size"], generates all valid segmentations:
    - "db.pool.size" (all separate)
    - "db.pool_size" (last two joined)
    - "db_pool.size" (first two joined)
    - "db_pool_size" (all joined)

    Args:
        parts: List of path parts (e.g., ["db", "pool", "size"])

    Returns:
        List of dot-notation paths (e.g., ["db.pool.size", "db.pool_size", ...])
    """
    if not parts:
        return []

    if len(parts) == 1:
        return [parts[0]]

    def generate_recursive(remaining: list[str], current_segments: list[str]) -> list[str]:
        """
        Recursively generate all segmentations.
        """
        if not remaining:
            return [".".join(current_segments)]

        results = []
        current_part = remaining[0]
        rest = remaining[1:]

        # Option 1: Add current part as a new segment
        new_segments = current_segments + [current_part]
        results.extend(generate_recursive(rest, new_segments))

        # Option 2: Join current part with last segment (if exists)
        if current_segments:
            last_segment = current_segments[-1]
            joined_segment = f"{last_segment}_{current_part}"
            new_segments = current_segments[:-1] + [joined_segment]
            results.extend(generate_recursive(rest, new_segments))

        return results

    return generate_recursive(parts, [])


def _resolve_env_var_path(
    env_var_path: str, schema_map: dict[str, SchemaPathInfo]
) -> SchemaPathInfo | None:
    """
    Resolve an environment variable path to a schema path unambiguously.

    Args:
        env_var_path: Environment variable path (e.g., "DB__POOL__SIZE")
        schema_map: Schema path map from _get_schema_path_map()

    Returns:
        SchemaPathInfo for the resolved path, or None if unknown

    Raises:
        ConfigValidationError: If path is ambiguous (>1 matches)
    """
    # Split by double underscore and convert to lowercase
    path_parts = [part.lower() for part in env_var_path.split("__")]

    # Generate all valid segmentations
    segmentations = _generate_path_segmentations(path_parts)

    # Match against schema map
    matches = []
    for seg in segmentations:
        if seg in schema_map:
            matches.append((seg, schema_map[seg]))

    # Apply resolution rules
    if len(matches) == 0:
        return None
    elif len(matches) == 1:
        return matches[0][1]
    else:
        ambiguous_paths = [path for path, _ in matches]
        raise ConfigValidationError(
            f"Environment variable SQUADOPS__{env_var_path} is ambiguous.\n"
            f"It matches multiple schema paths:\n"
            + "\n".join(f"  - {path}" for path in ambiguous_paths)
            + "\nPlease use a more specific environment variable name.",
            field=env_var_path,
            expected="Unambiguous schema path",
        )


def _get_repo_root() -> Path:
    """Get repository root directory."""
    return PathResolver.get_base_path()


def _select_profile(cli_profile: str | None = None) -> str:
    """
    Select deployment profile with explicit precedence.

    Precedence: CLI --profile → env SQUADOPS_PROFILE → default "local"
    """
    if cli_profile:
        return cli_profile
    env_profile = os.getenv("SQUADOPS_PROFILE")
    if env_profile:
        return env_profile
    return "local"


def _load_yaml_file(file_path: Path) -> dict[str, Any]:
    """Load YAML file safely."""
    if not file_path.exists():
        return {}

    try:
        with open(file_path) as f:
            content = yaml.safe_load(f)
            return content if isinstance(content, dict) else {}
    except Exception as e:
        logger.warning(f"Failed to load YAML file {file_path}: {e}")
        return {}


def _merge_dicts(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Deep merge two dictionaries."""
    result = base.copy()

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _merge_dicts(result[key], value)
        else:
            result[key] = value

    return result


def _coerce_value(value: str, field_type: type, enum_class: type | None = None) -> Any:
    """Coerce a string value to the appropriate type based on field type."""
    # Handle enum types
    if enum_class is not None and issubclass(enum_class, Enum):
        try:
            value_upper = value.upper()
            for enum_member in enum_class:
                if enum_member.name.upper() == value_upper:
                    return enum_member.value
            return enum_class(value)
        except (ValueError, KeyError):
            raise ValueError(f"Invalid enum value '{value}' for {enum_class.__name__}")

    # Handle bool
    if field_type is bool:
        if value.lower() in ("true", "false", "1", "0", "yes", "no"):
            return value.lower() in ("true", "1", "yes")
        raise ValueError(f"Cannot convert '{value}' to bool")

    # Handle int
    if field_type is int:
        try:
            return int(value)
        except ValueError:
            raise ValueError(f"Cannot convert '{value}' to int")

    # Handle float
    if field_type is float:
        try:
            return float(value)
        except ValueError:
            raise ValueError(f"Cannot convert '{value}' to float")

    # Handle Path
    if field_type is Path:
        return Path(value)

    # Handle str (default)
    return value


def _parse_env_overrides(prefix: str = "SQUADOPS__", strict: bool = False) -> dict[str, Any]:
    """Parse environment variable overrides using schema-authoritative resolution."""
    schema_map = _get_schema_path_map()
    overrides: dict[str, Any] = {}
    prefix_len = len(prefix)
    unknown_paths: list[str] = []

    for key, value in os.environ.items():
        if not key.startswith(prefix):
            continue

        env_var_path = key[prefix_len:]

        try:
            path_info = _resolve_env_var_path(env_var_path, schema_map)

            if path_info is None:
                unknown_paths.append(key)
                if strict:
                    raise ConfigValidationError(
                        f"Unknown configuration path: {env_var_path}",
                        field=env_var_path,
                        expected="Valid schema path",
                    )
                continue

            try:
                coerced_value = _coerce_value(value, path_info.field_type, path_info.enum_class)
            except ValueError as e:
                if strict:
                    raise ConfigValidationError(
                        f"Invalid value for {path_info.dot_path}: {e}",
                        field=path_info.dot_path,
                        expected=str(path_info.field_type.__name__),
                    )
                logger.warning(f"Invalid value for {path_info.dot_path}: {e}, using as string")
                coerced_value = value

            current = overrides
            for segment in path_info.tuple_path[:-1]:
                if segment not in current:
                    current[segment] = {}
                current = current[segment]

            final_key = path_info.tuple_path[-1]
            current[final_key] = coerced_value

        except ConfigValidationError:
            raise

    if unknown_paths and not strict:
        logger.warning(
            f"Unknown environment variable paths (ignored in non-strict mode): {', '.join(unknown_paths)}"
        )

    return overrides


def _validate_config(
    config_dict: dict[str, Any],
    strict: bool = False,
    schema_keys: set[str] | None = None,
) -> None:
    """Validate configuration dictionary."""
    valid_fields = set(AppConfig.model_fields.keys())

    if not strict:
        unknown_keys = [key for key in config_dict.keys() if key not in valid_fields]
        if unknown_keys:
            logger.warning(
                f"Unknown configuration keys (ignored in non-strict mode): {', '.join(unknown_keys)}"
            )
            for key in unknown_keys:
                config_dict.pop(key, None)

    try:
        AppConfig.model_validate(config_dict, strict=strict)
    except ValidationError as e:
        errors = []
        for error in e.errors():
            field = ".".join(str(loc) for loc in error["loc"])
            msg = error["msg"]
            errors.append(f"{field}: {msg}")

        raise ConfigValidationError(
            f"Configuration validation failed: {'; '.join(errors)}",
            expected="Valid AppConfig schema",
        )


def _flatten_keys(d: dict[str, Any], parent: str = "") -> list[str]:
    """Flatten nested dictionary keys to dot-notation paths."""
    keys = []
    for key, value in d.items():
        full_key = f"{parent}.{key}" if parent else key
        keys.append(full_key)
        if isinstance(value, dict):
            keys.extend(_flatten_keys(value, full_key))
    return keys


def load_config(
    profile: str | None = None,
    *,
    strict: bool = False,
    cli_overrides: dict[str, Any] | None = None,
) -> AppConfig:
    """
    Load configuration with layered precedence.

    Precedence (lowest → highest):
    1. Built-in defaults (in schema.py)
    2. config/defaults.yaml
    3. config/base.yaml
    4. config/profiles/<profile>.yaml
    5. config/local.yaml (if exists, gitignored)
    6. Environment variables (SQUADOPS__* format)
    7. CLI overrides

    Args:
        profile: Profile name (overrides CLI/env/default selection)
        strict: If True, unknown keys cause errors; if False, they cause warnings
        cli_overrides: Optional CLI override dictionary

    Returns:
        Validated AppConfig instance

    Raises:
        ConfigValidationError: If configuration is invalid
    """
    repo_root = _get_repo_root()
    config_dir = repo_root / "config"

    # 1. Select profile
    resolved_profile = _select_profile(profile)
    logger.info(f"Configuration profile: {resolved_profile} (strict={strict})")

    # 2. Start with empty dict (built-in defaults are in Pydantic model)
    merged: dict[str, Any] = {}

    # 3. Load config/defaults.yaml
    defaults_path = config_dir / "defaults.yaml"
    defaults = _load_yaml_file(defaults_path)
    merged = _merge_dicts(merged, defaults)

    # 4. Load config/base.yaml
    base_path = config_dir / "base.yaml"
    base = _load_yaml_file(base_path)
    merged = _merge_dicts(merged, base)

    # 5. Load config/profiles/<profile>.yaml
    profile_path = config_dir / "profiles" / f"{resolved_profile}.yaml"
    profile_config = _load_yaml_file(profile_path)
    merged = _merge_dicts(merged, profile_config)

    # 6. Load config/local.yaml (if exists, gitignored)
    local_path = config_dir / "local.yaml"
    if local_path.exists():
        local_config = _load_yaml_file(local_path)
        merged = _merge_dicts(merged, local_config)

    # 7. Apply environment variable overrides
    env_overrides = _parse_env_overrides(strict=strict)
    merged = _merge_dicts(merged, env_overrides)

    # 8. Apply CLI overrides (highest precedence)
    if cli_overrides:
        merged = _merge_dicts(merged, cli_overrides)

    # SECRET RESOLUTION (STRICT 7-STEP SEQUENCE)
    secrets_config_dict = merged.get("secrets", {})
    if secrets_config_dict:
        try:
            secrets_config = SecretsConfig(**secrets_config_dict)
        except Exception as e:
            raise ConfigValidationError(
                f"Invalid secrets configuration: {e}",
                field="secrets",
                expected="Valid SecretsConfig schema",
            ) from e
    else:
        secrets_config = None

    # Scan secrets section for secret:// references (hard fail if found)
    from squadops.core.secrets import SecretManager

    if secrets_config_dict:
        has_secrets_in_secrets = SecretManager.has_secret_references(
            secrets_config_dict,
            exclude_keys=[],
        )
        if has_secrets_in_secrets:
            raise ConfigValidationError(
                "secret:// references are forbidden inside the secrets configuration section",
                field="secrets",
                expected="secrets section must not contain secret:// references",
            )

    # Scan for secret:// references (excluding secrets section)
    has_references = SecretManager.has_secret_references(merged, exclude_keys=["secrets"])

    # If references found but no config, hard error
    if has_references and not secrets_config:
        raise ConfigValidationError(
            "secret:// references found but no secrets configuration provided",
            field="secrets",
            expected="secrets.provider configuration",
        )

    # Resolve all secret:// references (excluding secrets section)
    if secrets_config:
        from adapters.secrets.factory import create_provider

        name_map = secrets_config.name_map if secrets_config.name_map is not None else {}

        provider = create_provider(
            provider=secrets_config.provider,
            env_prefix=secrets_config.env_prefix,
            file_dir=secrets_config.file_dir,
        )

        manager = SecretManager(provider=provider, name_map=name_map)
        merged = manager.resolve_all_references(merged)

    # Validate configuration
    _validate_config(merged, strict=strict, schema_keys=None)

    if not strict:
        valid_fields = set(AppConfig.model_fields.keys())
        filtered_merged = {k: v for k, v in merged.items() if k in valid_fields}
        merged = filtered_merged

    # Create AppConfig instance
    app_config = AppConfig.model_validate(merged)

    # Store resolved profile as private attribute
    app_config._profile = resolved_profile

    # Create DbRuntime instance using persistence factory
    db_runtime = None
    if secrets_config:
        try:
            from adapters.persistence.factory import get_db_runtime

            db_runtime = get_db_runtime(merged, manager)
            logger.info("Created DbRuntime instance via persistence factory")
        except Exception as e:
            logger.warning(
                f"Failed to create DbRuntime instance: {e}. Database access may be limited."
            )

    app_config._db_runtime = db_runtime

    # Set global singleton
    global _config_instance
    _config_instance = app_config

    # Log fingerprint (redacted)
    redacted_merged = redact_config(merged)
    fingerprint = config_fingerprint(redacted_merged)
    logger.info(f"Configuration fingerprint: {fingerprint}")

    return app_config


def get_config() -> AppConfig:
    """
    Get global configuration instance (singleton pattern).

    Returns:
        Cached AppConfig instance, or raises error if not loaded
    """
    global _config_instance
    if _config_instance is None:
        raise RuntimeError(
            "Configuration not loaded. Call load_config() first, or ensure services call it at startup."
        )
    return _config_instance


def reset_config() -> None:
    """Reset global config instance (useful for testing)."""
    global _config_instance
    _config_instance = None


def parse_cli_args() -> argparse.Namespace:
    """Parse CLI arguments for configuration overrides."""
    parser = argparse.ArgumentParser(description="SquadOps Service")
    parser.add_argument(
        "--profile",
        type=str,
        help="Deployment profile (local, dev, stage, prod)",
    )
    parser.add_argument(
        "--strict-config",
        action="store_true",
        help="Enable strict configuration validation",
    )
    parser.add_argument(
        "--config-local-path",
        type=str,
        help="Path to local config override file",
    )
    return parser.parse_args()
