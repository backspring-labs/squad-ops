"""Unit tests for build_generation_record helper (SIP-0061).

No LangFuse SDK needed — only domain models.
"""

import uuid

import pytest

from squadops.execution.observability import build_generation_record
from squadops.llm.models import LLMResponse
from squadops.telemetry.models import GenerationRecord


class TestBuildGenerationRecord:
    """build_generation_record produces valid GenerationRecord with UUID4."""

    def test_produces_valid_record(self):
        response = LLMResponse(
            text="Hello world",
            model="llama3",
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
        )
        record = build_generation_record(
            llm_response=response,
            model="llama3",
            prompt_text="Say hello",
            latency_ms=42.5,
        )
        assert isinstance(record, GenerationRecord)
        assert record.model == "llama3"
        assert record.prompt_text == "Say hello"
        assert record.response_text == "Hello world"
        assert record.prompt_tokens == 10
        assert record.completion_tokens == 5
        assert record.total_tokens == 15
        assert record.latency_ms == 42.5

    def test_generation_id_is_uuid4(self):
        response = LLMResponse(text="hi", model="m")
        record = build_generation_record(llm_response=response, model="m", prompt_text="p")
        # Should be a valid UUID4 string
        parsed = uuid.UUID(record.generation_id, version=4)
        assert str(parsed) == record.generation_id

    def test_generation_id_is_unique(self):
        response = LLMResponse(text="hi", model="m")
        r1 = build_generation_record(llm_response=response, model="m", prompt_text="p")
        r2 = build_generation_record(llm_response=response, model="m", prompt_text="p")
        assert r1.generation_id != r2.generation_id

    def test_optional_token_counts(self):
        response = LLMResponse(text="hi", model="m")
        record = build_generation_record(llm_response=response, model="m", prompt_text="p")
        assert record.prompt_tokens is None
        assert record.completion_tokens is None
        assert record.total_tokens is None

    def test_optional_latency(self):
        response = LLMResponse(text="hi", model="m")
        record = build_generation_record(llm_response=response, model="m", prompt_text="p")
        assert record.latency_ms is None

    def test_record_is_frozen(self):
        response = LLMResponse(text="hi", model="m")
        record = build_generation_record(llm_response=response, model="m", prompt_text="p")
        with pytest.raises(AttributeError):
            record.model = "changed"  # type: ignore
