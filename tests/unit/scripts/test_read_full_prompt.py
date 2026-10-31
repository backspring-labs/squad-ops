"""``scripts/dev/read_full_prompt.py``: a generation's full request, by its id (#1756)."""

from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path

from squadops.telemetry.full_text import FULL_PROMPT_KEY, encode_full_text

_PATH = Path(__file__).resolve().parents[3] / "scripts" / "dev" / "read_full_prompt.py"
_spec = importlib.util.spec_from_file_location("read_full_prompt", _PATH)
reader = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(reader)

LONG = "x" * 25_000 + " the part the cap cut off"


def _opener(body: dict, asked: list):
    def opener(request):
        asked.append((request.full_url, request.get_header("Authorization")))
        return io.BytesIO(json.dumps(body).encode())

    return opener


def test_the_reader_prints_the_whole_request_by_generation_id():
    """Readable by id: the script asks LangFuse's public API for the generation and decodes it.
    Bug caught: the reader printing the capped display text when a full copy exists, or asking
    the wrong resource."""
    asked: list = []
    body = {
        "id": "gen-1",
        "input": LONG[:10_000],
        "metadata": {FULL_PROMPT_KEY: encode_full_text(LONG)},
    }

    observation = reader.fetch_observation(
        "gen-1",
        host="http://langfuse:3000/",
        public_key="pk",
        secret_key="sk",
        opener=_opener(body, asked),
    )

    assert reader.full_prompt(observation) == LONG
    assert asked == [("http://langfuse:3000/api/public/observations/gen-1", "Basic cGs6c2s=")]


def test_a_prompt_within_the_cap_is_its_display_text():
    """Bug caught: a short generation, stored once, read as having no request at all."""
    assert reader.full_prompt({"input": "a short prompt", "metadata": {}}) == "a short prompt"
