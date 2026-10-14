"""The adapter sends G0's requests and reads G0's replies as the harness did (SIP-0111 §5.7).

The gates measured what ``scripts/dev/engine_replay.py`` sent and read. Production is the adapter,
so the two must agree, or the gates' pass describes an engine call production never makes. The
fixtures are three held-out calls from the 27B's run of 2026-10-12, kept raw as the harness wrote
them: the request (its messages elided to a count) and every stream line. One answered with
thinking off, one with it on, and the run's one call that ended at its cap.

What bug would this catch? A drift between the adapter and the harness on anything that changes
the generation: a sampling value, the thinking switch or effort, the seed, the completion
allowance. Or on the reading of a reply: the text, the reasoning, the token counts, how it ended.
"""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

import httpx
import pytest

from adapters.llm.tensorfold import TensorFoldAdapter
from squadops.llm.models import ChatMessage
from tests.unit.llm.conformance import TENSORFOLD_KEY, wire

_FIXTURES = Path(__file__).parent / "fixtures" / "tensorfold_g0"
_ROWS = json.loads((_FIXTURES / "summary.json").read_text())


def _recorded(row: dict) -> tuple[dict, list[str]]:
    lines = gzip.decompress((_FIXTURES / f"{row['raw']}.gz").read_bytes()).decode().splitlines()
    return json.loads(lines[0])["request"], [json.loads(line)["line"] for line in lines[1:]]


@pytest.mark.parametrize(
    "row", _ROWS, ids=lambda r: f"{r['task_type']}, reasoning {r['reasoning']}, {r['finish']}"
)
async def test_the_adapter_sends_g0s_request_and_reads_its_reply_as_the_harness_did(row):
    """Entered at ``chat_stream_with_usage``, the call every handler makes."""
    request, stream = _recorded(row)
    count = int(request["messages"].strip("<>").split()[0])
    sent: dict = {}

    def server(r: httpx.Request) -> httpx.Response:
        assert r.headers["Authorization"] == f"Bearer {TENSORFOLD_KEY}"
        if r.url.path == "/metrics":
            return httpx.Response(
                200, text="tensorfold:requests_running 0\ntensorfold:requests_waiting 0\n"
            )
        if r.url.path == "/tokenize":
            return httpx.Response(200, json={"max_model_len": 65536})
        sent.update(json.loads(r.content))
        return httpx.Response(200, content="".join(f"{line}\n\n" for line in stream).encode())

    adapter = TensorFoldAdapter(
        base_url="http://tensorfold:8080",
        default_model=request["model"],
        timeout_seconds=60.0,
        api_key=TENSORFOLD_KEY,
    )
    with wire(server):
        message = await adapter.chat_stream_with_usage(
            [ChatMessage(role="user", content=f"turn {i}") for i in range(count)],
            max_tokens=row["max_tokens"],
            reasoning=row["reasoning"],
            seed=row["seed"],
        )

    assert {**sent, "messages": f"<{count} messages>"} == request
    read = (message.reasoning_text or "") + "\x00" + message.content
    assert hashlib.sha256(read.encode()).hexdigest()[:16] == row["text_sha"]
    assert (message.prompt_tokens, message.completion_tokens, message.reasoning_tokens) == (
        row["prompt_tokens"],
        row["completion_tokens"],
        row["reasoning_tokens"],
    )
    assert message.termination == row["finish"]
