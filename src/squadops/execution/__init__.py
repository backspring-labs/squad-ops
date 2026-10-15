"""The cycle's orchestration (#1992): the executor, its correction protocol and its gates.

``DispatchedFlowExecutor`` implements ``FlowExecutionPort``; the collaborators beside it run a run's
admission, provisioning, task dispatch, correction rounds, patch acceptance, pulse boundaries, framing
and workload gates, completion and evidence. None of it speaks to infrastructure: it reaches the
registries, the vault, the queue, the tracker and the event bus through their ports, so it lives in the
domain, where other domain code can import it. ``adapters.cycles`` keeps the infrastructure and the
factory that composes the executor.

It sits above the packages it orchestrates: it imports ``cycles``, ``campaigns``, ``capabilities`` and
``stacks``, and none of them imports it (``test_package_import_direction.py``). Inside ``cycles`` it would
have made ``cycles`` and ``campaigns`` import each other, since the workload gate reads the campaign's
gate and escalations. This root imports nothing: import from the module that defines a name.
"""
