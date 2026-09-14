"""The builder's optional notes to the qa author, and what they may not restate (#1312).

`qa_handoff.md` was required, checked by four surfaces, and read by nothing. It was also
the only required builder artifact that is a *document about* the work rather than a part
of the deliverable, and the builder intermittently completed the packaging archetype
instead — emitting `.env.example` and `docker-compose.yaml` and dropping the report, on
~9% of cycles. A required document nobody reads is a generator: it produces failures, not
information.

`assembly_notes.md` replaces it with a positive definition:

    optional builder-to-qa context containing only assembly facts that are not already
    represented by the stack's deterministic contracts.

The definition is the thing; the exclusion list this module renders *enforces* it by
naming, from the declarations themselves, what those contracts already supply — the
environment contract's operation commands, the application's invocation and port, the
directories the qa suite lives in, and the interface manifest. Rendering it from the
declarations rather than restating them is the #918 rule: a hand-written list would drift
the moment a stack changed a command, and the builder would be told to omit something the
qa author never received.

A stack with no registered environment contract (the three legacy profiles) gets the
definition and no exclusion list — there are no declarations to derive one from, and an
invented list would be exactly the drift this module exists to prevent.

**#598 (owner ruling 2026-09-13): required on the two scaffolded stacks.** Once the scaffold
renders the container packaging, the notes are the builder's whole deliverable there, and an
emission with no file fails as contentless. So the profiles for `fullstack_fastapi_react` and
`nextjs_ts` require them, and the block below says so. The #1312 objection was a required
document *nobody read*; the qa author now reads these (`request.qa_test_assembly_notes_appendix`).
When the builder has nothing beyond the declarations, one sentence saying so is the complete
answer. The legacy profiles keep them optional.
"""

from __future__ import annotations

#: The builder's optional notes document. One name, in one place — the failure mode this
#: replaces was a filename appearing in five registries.
ASSEMBLY_NOTES_DOCUMENT = "assembly_notes.md"

#: The document this replaced. Retired as a requirement, a check surface and a prompt
#: instruction — but the planner is a language model with a strong prior about "qa
#: handoff", and a criterion it authors over a file nothing produces any more evaluates to
#: `file_not_found` and rejects a correct roll. Named here so the dispatch strip can say
#: what it dropped and why, rather than leaving the failure to be diagnosed live.
RETIRED_HANDOFF_DOCUMENT = "qa_handoff.md"

#: The environment contract's operations, in the order a reader would run them, with the
#: sentence each contributes to the exclusion list. An operation the contract does not
#: provide contributes nothing (`read_build_diagnostics` is deliberately unprovided on
#: stack #1) rather than a line claiming a command that does not exist.
_OPERATION_LABELS: tuple[tuple[str, str], ...] = (
    ("install_dependencies", "how dependencies are installed"),
    ("build_frontend", "how the frontend is built"),
    ("run_backend_tests", "how the backend suite is run"),
    ("start_application", "how the application is started"),
)


def already_supplied_lines(stack: str) -> tuple[str, ...]:
    """What the stack's own declarations already give the qa author, one line each.

    Derived from the registered declarations — never a hand list. Returns ``()`` for a
    stack with no environment contract, which is the honest answer for the legacy
    profiles: nothing is declared, so nothing can be claimed as already supplied.
    """
    from squadops.capabilities.scaffold import qa_test_namespace_for_stack
    from squadops.sandbox.environment import get_environment_contract

    try:
        contract = get_environment_contract(stack)
    except ValueError:
        return ()

    lines: list[str] = []
    commands = contract.commands()
    for operation, label in _OPERATION_LABELS:
        argv = commands.get(operation)
        if argv:
            lines.append(f"- {label} — `{' '.join(argv)}`")
    # The port, not the image: the image is the SANDBOX's, and naming it here would read
    # to the builder as a decision about the deliverable's own container, which it is not.
    lines.append(f"- where the application listens — port `{contract.app_port}`")
    # #598: the packaging the scaffold renders is a declaration too.
    from squadops.capabilities.rendered_packaging import render_packaging

    try:
        packaged = ", ".join(f"`{item['name']}`" for item in render_packaging(stack))
    except ValueError:
        packaged = ""
    if packaged:
        lines.append(
            f"- how the application is packaged — {packaged}, rendered by the scaffold and frozen"
        )

    namespace = qa_test_namespace_for_stack(stack)
    if namespace:
        namespaces = ", ".join(f"`{ns}`" for ns in namespace)
        lines.append(f"- where the test suite lives — {namespaces}")
    lines.append(
        "- every interface the application exposes — the interface manifest, which the "
        "test author is given in full"
    )
    return tuple(lines)


def assembly_notes_block(stack: str, *, required: bool = False) -> str:
    """The builder-facing block: what the notes are for, and what they may not restate.

    Empty string for a stack that declares nothing, so a profile with no contract does
    not carry a heading with nothing under it. ``required`` (#598) changes only what the
    builder is told about omitting the file; what the notes may say is the same either way.
    """
    supplied = already_supplied_lines(stack)
    if not supplied:
        return ""
    if required:
        return (
            f"\n\n## `{ASSEMBLY_NOTES_DOCUMENT}` — required, and deliberately narrow\n\n"
            "You MUST emit this file. It carries **only assembly facts the test author cannot "
            "already have** — a credential or fixture the deployment needs, a runtime setting "
            "that changes how the application behaves, something you found the declarations do "
            "not cover. A summary of your own work does not belong in it.\n\n"
            "**Already supplied to the test author — do not restate any of it:**\n\n"
            f"{chr(10).join(supplied)}\n\n"
            "If you have nothing that is not in that list, write one sentence saying the "
            "scaffold's packaging and declarations are used unchanged. That is a complete and "
            "correct answer."
        )
    return (
        f"\n\n## `{ASSEMBLY_NOTES_DOCUMENT}` — optional, and deliberately narrow\n\n"
        "You may emit this file. It is not required, and emitting it empty or emitting a "
        "summary of your own work is worse than omitting it.\n\n"
        "It carries **only assembly facts the test author cannot already have** — a "
        "decision you made while packaging that changes how the application behaves, a "
        "credential or fixture the deployment needs, a deviation you had to make from the "
        "obvious packaging. Nothing else.\n\n"
        "**Already supplied to the test author — do not restate any of it:**\n\n"
        f"{chr(10).join(supplied)}\n\n"
        "If you have nothing that is not in that list, omit the file. Saying nothing is a "
        "complete and correct answer here."
    )
