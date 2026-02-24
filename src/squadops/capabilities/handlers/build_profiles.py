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
            "You are a Python application assembler. You receive source code "
            "that a developer has already written and your job is to package "
            "it into a deployable artifact.\n\n"
            "DO NOT rewrite or regenerate the source code — it is already done.\n\n"
            "Your outputs are DEPLOYMENT artifacts only:\n"
            "- __main__.py entrypoint (wiring to the developer's main module)\n"
            "- Dockerfile for containerized deployment\n"
            "- requirements.txt (consolidate from source imports)\n"
            "- Any startup scripts or config files needed\n\n"
            "Emit each file as a fenced code block, e.g. ```python:main.py or ```dockerfile:Dockerfile\n"
            "After all deployment files, emit a QA handoff document as "
            "```markdown:qa_handoff.md with sections: "
            "## How to Run, ## How to Test, ## Expected Behavior."
        ),
        required_files=("Dockerfile", "__main__.py", "requirements.txt"),
        optional_files=("requirements.txt",),
        validation_rules=(
            "Dockerfile must be valid",
            "__main__.py must wire to developer's entry point",
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
            "Emit each file as a fenced code block, e.g. ```python:main.py or ```dockerfile:Dockerfile\n"
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
            "Emit each file as a fenced code block, e.g. ```python:main.py or ```dockerfile:Dockerfile\n"
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
    "fullstack_fastapi_react": BuildProfile(
        name="fullstack_fastapi_react",
        system_prompt_template=(
            "You are assembling a fullstack web application with a FastAPI backend "
            "and a React (Vite) frontend.\n\n"
            "Produce the following artifacts:\n"
            "1. A multi-stage Dockerfile: Python base for backend, Node build stage "
            "   for frontend static assets, final stage serves both.\n"
            "2. A docker-compose.yaml for local development (backend on :8000, "
            "   frontend dev server on :5173, with proxy config).\n"
            "3. A startup script (start.sh) that runs both services.\n"
            "4. CORS configuration notes for the backend.\n"
            "5. A qa_handoff.md covering how to run, test, and verify both stacks.\n\n"
            "The source code from the development step is provided as context. "
            "Do not regenerate application code — focus on packaging, configuration, "
            "and operational readiness."
        ),
        required_files=("Dockerfile", "qa_handoff.md"),
        optional_files=("docker-compose.yaml", "start.sh", ".env.example", "nginx.conf"),
        validation_rules=(
            "Dockerfile must use multi-stage build",
            "docker-compose.yaml must define backend and frontend services",
            "qa_handoff.md must include startup and test instructions for both stacks",
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
