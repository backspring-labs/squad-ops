"""The stack registry and its stacks (#1993): what a stack declares and what the scaffold renders.

The registry (``scaffold``), each stack's module (``stack_fastapi_react``, ``stack_nextjs_ts``), the
scaffold contract and the verification scaffold. Both sides read it: the runtime's cycle code and the
agents' capability handlers. So it imports neither ``squadops.capabilities`` nor ``squadops.cycles``
(``tests/unit/architecture/test_package_import_direction.py``), and a stack change is a change to this
package. This root imports nothing: import from the module that defines a name.
"""
