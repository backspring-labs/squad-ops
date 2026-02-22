"""Build profile registry for builder role (SIP-0071).

Typed build profiles that control handler behavior: prompt templates,
required files, validation rules, and QA handoff expectations.
V1 profiles are code-defined frozen dataclass instances.
"""
from __future__ import annotations

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# QA handoff section name constants (D12 — single source of truth)
# ---------------------------------------------------------------------------

QA_HANDOFF_REQUIRED_SECTIONS = (
    "## How to Run",
    "## How to Test",
    "## Expected Behavior",
)

QA_HANDOFF_OPTIONAL_SECTIONS = (
    "## Files Created",
    "## Implemented Scope",
    "## Known Limitations",
    "## Build Results",
)

# ---------------------------------------------------------------------------
# Routing reason constants (D14)
# ---------------------------------------------------------------------------

ROUTING_BUILDER_PRESENT = "builder_role_present"
ROUTING_FALLBACK_NO_BUILDER = "fallback_no_builder"

# ---------------------------------------------------------------------------
# Artifact output mode constants
# ---------------------------------------------------------------------------

ARTIFACT_MODE_MULTI_FILE = "multi_file"
ARTIFACT_MODE_SINGLE_FILE = "single_file"
ARTIFACT_MODE_STRUCTURED_BUNDLE = "structured_bundle"


# ---------------------------------------------------------------------------
# Build profile dataclass (D2)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BuildProfile:
    """Typed build profile definition (SIP-0071 §5.2).

    Handlers must not mutate profile fields; treat get_profile() return
    as read-only.
    """

    name: str
    system_prompt_template: str
    required_files: tuple[str, ...]
    optional_files: tuple[str, ...] = ()
    validation_rules: tuple[str, ...] = ()
    artifact_output_mode: str = ARTIFACT_MODE_MULTI_FILE
    qa_handoff_expectations: tuple[str, ...] = QA_HANDOFF_REQUIRED_SECTIONS
    default_task_tags: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# V1 profile registry
# ---------------------------------------------------------------------------

BUILD_PROFILES: dict[str, BuildProfile] = {
    "python_cli_builder": BuildProfile(
        name="python_cli_builder",
        system_prompt_template=(
            "You are a Python CLI application builder. Generate a complete, "
            "runnable Python package from the implementation plan.\n\n"
            "Requirements:\n"
            "- Use the project name as the top-level package directory.\n"
            "- Include __init__.py and __main__.py for package execution.\n"
            "- Use relative imports within the package.\n"
            "- Include requirements.txt if external dependencies are needed.\n"
            "- All files must be runnable via `python -m <package_name>`.\n\n"
            "Emit each file as a fenced code block: ```<lang>:<path>\n"
            "After all source files, emit a QA handoff document as "
            "```markdown:qa_handoff.md with sections: "
            "## How to Run, ## How to Test, ## Expected Behavior."
        ),
        required_files=("main.py", "__init__.py", "__main__.py"),
        optional_files=("requirements.txt",),
        validation_rules=(
            "All .py files must parse without SyntaxError",
            "Package must include __main__.py for -m execution",
        ),
        artifact_output_mode=ARTIFACT_MODE_MULTI_FILE,
        qa_handoff_expectations=QA_HANDOFF_REQUIRED_SECTIONS,
    ),
    "static_web_builder": BuildProfile(
        name="static_web_builder",
        system_prompt_template=(
            "You are a static web application builder. Generate a complete, "
            "browser-openable web application from the implementation plan.\n\n"
            "Requirements:\n"
            "- Include an index.html as the entry point.\n"
            "- Include a styles.css for styling.\n"
            "- Include a main.js for interactivity.\n"
            "- All assets must use relative paths (no CDN dependencies).\n"
            "- The result must be openable by double-clicking index.html.\n\n"
            "Emit each file as a fenced code block: ```<lang>:<path>\n"
            "After all source files, emit a QA handoff document as "
            "```markdown:qa_handoff.md with sections: "
            "## How to Run, ## How to Test, ## Expected Behavior."
        ),
        required_files=("index.html", "styles.css", "main.js"),
        optional_files=("favicon.ico", "manifest.json"),
        validation_rules=(
            "index.html must be valid HTML5",
            "All asset references must use relative paths",
        ),
        artifact_output_mode=ARTIFACT_MODE_MULTI_FILE,
        qa_handoff_expectations=QA_HANDOFF_REQUIRED_SECTIONS,
    ),
    "web_app_builder": BuildProfile(
        name="web_app_builder",
        system_prompt_template=(
            "You are a web application builder. Generate a complete, "
            "runnable web application from the implementation plan.\n\n"
            "Requirements:\n"
            "- Include a server entry point (app.py or main.py).\n"
            "- Include an index.html template for the UI.\n"
            "- Include requirements.txt for Python dependencies.\n"
            "- Use a lightweight framework (Flask preferred).\n"
            "- The application must start with a single command.\n\n"
            "Emit each file as a fenced code block: ```<lang>:<path>\n"
            "After all source files, emit a QA handoff document as "
            "```markdown:qa_handoff.md with sections: "
            "## How to Run, ## How to Test, ## Expected Behavior."
        ),
        required_files=("app.py", "index.html", "requirements.txt"),
        optional_files=("static/styles.css", "static/main.js", "templates/"),
        validation_rules=(
            "app.py must be valid Python",
            "requirements.txt must list all dependencies",
        ),
        artifact_output_mode=ARTIFACT_MODE_MULTI_FILE,
        qa_handoff_expectations=QA_HANDOFF_REQUIRED_SECTIONS,
    ),
}


def get_profile(name: str) -> BuildProfile:
    """Resolve build profile by name.

    Args:
        name: Profile name to look up.

    Returns:
        The matching BuildProfile.

    Raises:
        ValueError: If name is not a registered profile.
    """
    profile = BUILD_PROFILES.get(name)
    if profile is None:
        available = sorted(BUILD_PROFILES.keys())
        raise ValueError(
            f"Unknown build profile {name!r}. Available profiles: {available}"
        )
    return profile
