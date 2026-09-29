"""The correction path's task ids, in one place (#1697).

A correction round dispatches up to three kinds of task: the protocol's own steps (``corr-``,
the analyzer and the decision), the repair (``repair-``), and the retest of a repaired suite
(``retest-``). Their ids join per-round evidence everywhere it is read: Prefect task names,
LangFuse traces, the ``from=repair-…`` attribution in stored evidence, and #1627's refusal list.
"""

from __future__ import annotations


def correction_task_id(
    prefix: str, run_id: str, attempt: int, round_seq: int, task_type: str
) -> str:
    """``{prefix}-{run}-{attempt:02d}-s{round_seq:02d}-{task_type}``.

    ``attempt`` is the round index. The budget, the refunds and the fault hook's first-attempt
    reading all key on it, and a refunded round reuses it by design (#1053). So on its own it is
    not unique: on 1.8.2, two repairs of different suites both carried
    ``repair-run_99242d1e-00-qa.test_repair``. ``round_seq`` is the run's round sequence, which
    nothing resets, so two rounds that share an attempt index never share an id.

    The sequence sits AFTER the index, and behind an ``s``. The fault hook reads the first
    ``-NN-`` in an id (``fault_injection._is_first_attempt``), and the verification-set driver
    anchors the index right after the run id. Both keep reading the index, from old ids and new.
    """
    return f"{prefix}-{run_id[:12]}-{attempt:02d}-s{round_seq:02d}-{task_type}"
