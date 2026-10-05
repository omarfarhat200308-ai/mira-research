"""
Tests for the Anthropic-primary / Groq-emergency-fallback wiring in
mira/llm_client.py: FailoverLLMClient must (a) use the primary silently on
success, (b) transparently fall back and stamp fallback_used/fallback_reason
when the primary fails, (c) raise a combined LLMCallError when BOTH fail,
never guess. GroqLLMClient's own HTTP layer is exercised against a fake
transport so no real network/API key is needed.
"""
from __future__ import annotations

import httpx
import pytest
from pydantic import BaseModel, Field

from mira.llm_client import (
    FailoverLLMClient,
    GroqLLMClient,
    LLMCallError,
    LLMCompletion,
    MockLLMClient,
)


class _DummyResponse(BaseModel):
    urgency: str
    reasoning: str
    confidence: float = Field(ge=0.0, le=1.0)


class _AlwaysFailsClient:
    def __init__(self, message: str = "simulated primary failure"):
        self.message = message

    def complete(self, **kwargs):
        raise LLMCallError(self.message)


class _AlwaysSucceedsClient:
    def __init__(self):
        self.calls = 0

    def complete(self, **kwargs):
        self.calls += 1
        return LLMCompletion(
            parsed=_DummyResponse(urgency="routine", reasoning="ok", confidence=0.9),
            provider="stub",
            model="stub-model",
        )


def test_failover_uses_primary_on_success_without_touching_fallback():
    primary = _AlwaysSucceedsClient()
    fallback = _AlwaysFailsClient("fallback should never be called")
    client = FailoverLLMClient(primary=primary, fallback=fallback)

    result = client.complete(
        agent_name="triage", system_prompt="sys", user_content="user", response_model=_DummyResponse
    )
    assert result.provider == "stub"
    assert result.fallback_used is False
    assert primary.calls == 1


def test_failover_falls_back_and_stamps_fallback_metadata():
    primary = _AlwaysFailsClient("anthropic exhausted")
    fallback = _AlwaysSucceedsClient()
    client = FailoverLLMClient(primary=primary, fallback=fallback)

    result = client.complete(
        agent_name="triage", system_prompt="sys", user_content="user", response_model=_DummyResponse
    )
    assert result.fallback_used is True
    assert "anthropic exhausted" in result.fallback_reason
    assert fallback.calls == 1


def test_failover_raises_when_both_fail():
    primary = _AlwaysFailsClient("primary down")
    fallback = _AlwaysFailsClient("fallback down")
    client = FailoverLLMClient(primary=primary, fallback=fallback)

    with pytest.raises(LLMCallError) as exc_info:
        client.complete(
            agent_name="triage", system_prompt="sys", user_content="user", response_model=_DummyResponse
        )
    assert "primary down" in str(exc_info.value)
    assert "fallback down" in str(exc_info.value)


def test_mock_client_returns_llm_completion_with_provider_mock():
    client = MockLLMClient()
    client.register("triage", {"urgency": "routine", "reasoning": "fine", "confidence": 0.9})
    result = client.complete(
        agent_name="triage", system_prompt="sys", user_content="user", response_model=_DummyResponse
    )
    assert isinstance(result, LLMCompletion)
    assert result.provider == "mock"
    assert result.parsed.urgency == "routine"


def test_groq_client_requires_api_key(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(LLMCallError):
        GroqLLMClient()


def test_groq_client_parses_tool_call_response(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key-not-real")
    client = GroqLLMClient()

    def fake_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "tool_calls": [
                                {
                                    "function": {
                                        "name": "emit_dummyresponse",
                                        "arguments": '{"urgency": "urgent", "reasoning": "groq said so", "confidence": 0.7}',
                                    }
                                }
                            ]
                        }
                    }
                ],
                "usage": {"prompt_tokens": 42, "completion_tokens": 13},
            },
        )

    client._client = httpx.Client(
        base_url="https://api.groq.com/openai/v1",
        transport=httpx.MockTransport(fake_handler),
    )

    result = client.complete(
        agent_name="triage", system_prompt="sys", user_content="user", response_model=_DummyResponse
    )
    assert result.provider == "groq"
    assert result.parsed.urgency == "urgent"
    assert result.input_tokens == 42
    assert result.output_tokens == 13


def test_groq_client_raises_llm_call_error_on_http_failure(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key-not-real")
    # Avoid paying real retry/backoff delay (call_with_retries' max_retries
    # default is bound at import time, so patch time.sleep instead of the
    # config value) for a test that only cares about the eventual failure
    # contract, not retry timing.
    monkeypatch.setattr("mira.reliability.time.sleep", lambda _seconds: None)
    client = GroqLLMClient()

    def fake_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "internal"})

    client._client = httpx.Client(
        base_url="https://api.groq.com/openai/v1",
        transport=httpx.MockTransport(fake_handler),
    )

    with pytest.raises(LLMCallError):
        client.complete(
            agent_name="triage", system_prompt="sys", user_content="user", response_model=_DummyResponse
        )
