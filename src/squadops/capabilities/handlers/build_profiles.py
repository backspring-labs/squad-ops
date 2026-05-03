"""Build profile registry for builder role (SIP-0071).

Typed build profiles that control handler behavior: prompt templates,
required files, validation rules, and QA handoff expectations.
V1 profiles are code-defined frozen dataclass instances.

Issue #92 (2026-05-03): each profile's `required_files` and `optional_files`
are the single source of truth. The system prompt that the builder LLM sees
is composed at access time via `BuildProfile.full_system_prompt` so the
narrative `system_prompt_template` cannot drift away from what the validator
will accept. Adding a file to `required_files` automatically adds it to the
prompt; the file list cannot be edited in the prompt without also editing
the validator's `required_files`.
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

    `system_prompt_template` holds only the *narrative* portion (stack
    description and stack-specific guidance). The concrete file list seen
    by the builder LLM is generated from `required_files`/`optional_files`/
    `qa_handoff_expectations` via `full_system_prompt`. Do not list specific
    filenames inside `system_prompt_template`.
    """

    name: str
    system_prompt_template: str
    required_files: tuple[str, ...]
    optional_files: tuple[str, ...] = ()
    validation_rules: tuple[str, ...] = ()
    artifact_output_mode: str = ARTIFACT_MODE_MULTI_FILE
    qa_handoff_expectations: tuple[str, ...] = QA_HANDOFF_REQUIRED_SECTIONS
    default_task_tags: dict[str, str] = field(default_factory=dict)

    @property
    def full_system_prompt(self) -> str:
        """Compose the narrative template with the canonical file list block.

        The file list is derived from `required_files`/`optional_files` so
        the prompt stays in lockstep with what the validator enforces.

        Cycle-1 evidence (cyc_11367982fd06, 2026-05-03): the build profile
        validator and the plan author can disagree about which qa_handoff
        sections are required. The plan task description named different
        sections (e.g. "Implemented Scope", "Known Limitations") than the
        validator's hard-coded set. Bob followed the more specific task
        description and the validator rejected on a missing canonical
        section. We surface the validator's section list as
        "non-negotiable" with a worked skeleton so the user prompt's task
        description cannot quietly override it. Additional sections
        requested by the task are welcome on top of the required ones.
        """
        required_lines = "\n".join(f"- `{name}`" for name in self.required_files)
        optional_block = ""
        if self.optional_files:
            optional_lines = "\n".join(f"- `{name}`" for name in self.optional_files)
            optional_block = f"\n\n## Optional artifacts (emit only if needed)\n\n{optional_lines}"
        qa_lines = "\n".join(f"- `{name}`" for name in self.qa_handoff_expectations)
        skeleton_sections = "\n\n".join(
            f"{heading}\n\n<content>" for heading in self.qa_handoff_expectations
        )

        return (
            f"{self.system_prompt_template}\n\n"
            "## Required artifacts (you MUST emit every file in this list)\n\n"
            f"{required_lines}"
            f"{optional_block}\n\n"
            "## qa_handoff.md required sections (NON-NEGOTIABLE)\n\n"
            f"{qa_lines}\n\n"
            "These section headings are **mandatory** and must appear in "
            "`qa_handoff.md` **exactly as written above**, including the "
            "leading `## ` and the exact casing. The validator does literal "
            "substring matching with a small set of fallbacks; paraphrased "
            "or reworded headings will be rejected. The user prompt's task "
            "description may ask for additional sections — include those "
            "after the required ones, but the required headings above must "
            "always be present.\n\n"
            "Skeleton (copy these headings exactly, then fill in content):\n\n"
            "```markdown:qa_handoff.md\n"
            f"{skeleton_sections}\n"
            "```"
        )


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
            "DO NOT rewrite or regenerate the source code — it is already done. "
            "Your outputs are deployment artifacts only: container packaging, "
            "an entrypoint that wires to the developer's existing main module, "
            "and a consolidated dependency manifest derived from the source imports."
        ),
        required_files=("Dockerfile", "__main__.py", "requirements.txt", "qa_handoff.md"),
        optional_files=(),
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
            "All assets must use relative paths (no CDN dependencies). The "
            "result must open by double-clicking the HTML entry point."
        ),
        required_files=("index.html", "styles.css", "main.js", "qa_handoff.md"),
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
            "runnable Python web application from the implementation plan.\n\n"
            "Use a lightweight framework (Flask preferred). The application "
            "must start with a single command."
        ),
        required_files=("app.py", "index.html", "requirements.txt", "qa_handoff.md"),
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
            "You are assembling a fullstack web application with a FastAPI "
            "backend and a React (Vite) frontend.\n\n"
            "The source code from the development step is provided as context. "
            "Do not regenerate application code — focus on packaging, "
            "configuration, and operational readiness. The container build "
            "must be multi-stage: a Python base for the backend, a Node build "
            "stage for the frontend static assets, and a final stage that "
            "serves both. The QA handoff document must include CORS "
            "configuration notes for the backend."
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
        raise ValueError(f"Unknown build profile {name!r}. Available profiles: {available}")
    return profile
