"""
LLM client abstraction.

Every agent calls an LLMClient rather than a provider SDK directly, and
always asks for a specific Pydantic response model back. Implementations:

- AnthropicLLMClient: real calls to Claude Sonnet 5 (primary, for every
  stage including dev/test — see config.py's Sonnet-primary policy), using
  a forced tool-call so confidence + reasoning are required, typed fields
  rather than free text an agent has to parse and hope is well-formed.
  Supports an optional `cache_prefix` (static text, e.g. the RAG protocol
  corpus) sent as a separate Anthropic prompt-caching-eligible system block
  so it isn't re-sent/re-billed at full price on every call.
- GroqLLMClient: a TRUE EMERGENCY FALLBACK ONLY, activated by
  FailoverLLMClient when the Anthropic call itself fails. Same
  OpenAI-compatible forced-tool-call shape, different endpoint/model.
- FailoverLLMClient: wraps primary+fallback; every failover is logged
  (logging.warning) and recorded on the returned LLMCompletion
  (fallback_used/fallback_reason) so it's auditable which model produced
  which output — never a silent substitution.
- MockLLMClient: deterministic, scenario-keyed responses used by default
  (config.MOCK_LLM / MIRA_MOCK_LLM=1) so the test harness and clinical
  review runs are reproducible without an API key or network access, and so
  we can script deliberately malformed/failing responses to exercise the
  pipeline's fail-safe behavior.

Anything that fails to produce a valid response_model instance raises
LLMCallError — agents (mira/agents/base.py) turn this into an AgentFailure,
which the pipeline treats as a reason to degrade toward the safe fallback,
never to guess.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Optional, Protocol, Type, TypeVar

from pydantic import BaseModel, ValidationError

from . import config
from .reliability import ExternalCallFailed, call_with_retries

T = TypeVar("T", bound=BaseModel)

logger = logging.getLogger("mira.llm_client")


class LLMCallError(Exception):
    """Raised whenever an LLM call fails or returns output that doesn't
    validate against the requested response model."""


@dataclass
class LLMCompletion:
    """What every LLMClient.complete() returns: the validated response
    model plus provenance (which provider/model actually answered, token
    spend, and whether a failover happened) — the audit trail this system
    is built around doesn't stop at "the model said X", it also records
    which model."""

    parsed: BaseModel
    provider: str
    model: str
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    fallback_used: bool = False
    fallback_reason: Optional[str] = None


class LLMClient(Protocol):
    def complete(
        self,
        *,
        agent_name: str,
        system_prompt: str,
        user_content: str,
        response_model: Type[T],
        cache_prefix: Optional[str] = None,
    ) -> LLMCompletion:
        ...


class AnthropicLLMClient:
    """Real Claude Sonnet 5 calls via forced structured tool output."""

    def __init__(self, model: str = config.CLAUDE_MODEL, timeout: float = config.AGENT_CALL_TIMEOUT_SECONDS):
        import anthropic  # local import: only required if real calls are used

        self._client = anthropic.Anthropic(timeout=timeout)
        self._model = model

    def complete(
        self,
        *,
        agent_name: str,
        system_prompt: str,
        user_content: str,
        response_model: Type[T],
        cache_prefix: Optional[str] = None,
    ) -> LLMCompletion:
        schema = response_model.model_json_schema()
        tool_name = f"emit_{response_model.__name__.lower()}"

        if cache_prefix:
            # Static/reusable content (e.g. the RAG protocol corpus) as its
            # own system block with cache_control, so Anthropic can reuse it
            # across calls instead of re-billing it at full price every
            # time — see config.py's cost-discipline note.
            system_param = [
                {"type": "text", "text": cache_prefix, "cache_control": {"type": "ephemeral"}},
                {"type": "text", "text": system_prompt},
            ]
        else:
            system_param = system_prompt

        def _call():
            return self._client.messages.create(
                model=self._model,
                max_tokens=1024,
                system=system_param,
                messages=[{"role": "user", "content": user_content}],
                tools=[
                    {
                        "name": tool_name,
                        "description": (
                            f"Return the {agent_name} agent's structured output."
                        ),
                        "input_schema": schema,
                    }
                ],
                tool_choice={"type": "tool", "name": tool_name},
            )

        try:
            response = call_with_retries(_call, call_name=f"anthropic:{agent_name}")
        except ExternalCallFailed as exc:
            raise LLMCallError(f"{agent_name}: Anthropic API call failed: {exc}") from exc

        for block in response.content:
            if getattr(block, "type", None) == "tool_use" and block.name == tool_name:
                try:
                    parsed = response_model.model_validate(block.input)
                except ValidationError as exc:
                    raise LLMCallError(
                        f"{agent_name}: model output failed schema validation: {exc}"
                    ) from exc
                usage = getattr(response, "usage", None)
                return LLMCompletion(
                    parsed=parsed,
                    provider="anthropic",
                    model=self._model,
                    input_tokens=getattr(usage, "input_tokens", None),
                    output_tokens=getattr(usage, "output_tokens", None),
                )

        raise LLMCallError(f"{agent_name}: no tool_use block found in Anthropic response")


class GroqLLMClient:
    """TRUE EMERGENCY FALLBACK ONLY (see config.py) — same forced-tool-call
    contract as AnthropicLLMClient, via Groq's OpenAI-compatible endpoint.
    Never selected proactively for cost; only reached through
    FailoverLLMClient after a primary Anthropic call has already failed."""

    def __init__(self, model: str = config.GROQ_MODEL, timeout: float = config.EXTERNAL_CALL_TIMEOUT_SECONDS):
        import httpx  # local import: only required if the fallback path is used

        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise LLMCallError("GROQ_API_KEY is not set — cannot construct GroqLLMClient")

        self._client = httpx.Client(
            base_url="https://api.groq.com/openai/v1",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=timeout,
        )
        self._model = model

    def complete(
        self,
        *,
        agent_name: str,
        system_prompt: str,
        user_content: str,
        response_model: Type[T],
        cache_prefix: Optional[str] = None,
    ) -> LLMCompletion:
        # Groq has no equivalent of Anthropic's cache_control on this API
        # surface — a cache_prefix here would be re-billed (and re-counted
        # against the free-tier tokens-per-minute budget) in full on every
        # single call, no caching benefit at all. Deliberately dropped, not
        # concatenated in: diagnostic.py/triage.py already put the
        # relevant top-k RAG passages directly in system_prompt (via
        # build_prompt, separately from build_cache_prefix's full-corpus
        # text), so grounding isn't lost — just the broader, cache-only-
        # economical full-corpus context. Confirmed live 2026-08-18: with
        # this included, a single pipeline run's Diagnostic+Triage calls
        # alone (~2.3k tokens of corpus each) blew through Groq's 8000 TPM
        # free-tier limit and 429'd almost immediately.
        full_system = system_prompt
        schema = response_model.model_json_schema()
        tool_name = f"emit_{response_model.__name__.lower()}"

        def _call():
            resp = self._client.post(
                "/chat/completions",
                json={
                    "model": self._model,
                    "max_tokens": 1024,
                    "messages": [
                        {"role": "system", "content": full_system},
                        {"role": "user", "content": user_content},
                    ],
                    "tools": [
                        {
                            "type": "function",
                            "function": {
                                "name": tool_name,
                                "description": f"Return the {agent_name} agent's structured output.",
                                "parameters": schema,
                            },
                        }
                    ],
                    "tool_choice": {"type": "function", "function": {"name": tool_name}},
                },
            )
            resp.raise_for_status()
            return resp.json()

        try:
            data = call_with_retries(_call, call_name=f"groq:{agent_name}")
        except ExternalCallFailed as exc:
            raise LLMCallError(f"{agent_name}: Groq API call failed: {exc}") from exc

        try:
            message = data["choices"][0]["message"]
            tool_calls = message.get("tool_calls") or []
            if not tool_calls:
                raise LLMCallError(f"{agent_name}: no tool_calls in Groq response")
            arguments_json = tool_calls[0]["function"]["arguments"]
            parsed = response_model.model_validate_json(arguments_json)
        except (KeyError, IndexError, ValidationError, json.JSONDecodeError) as exc:
            raise LLMCallError(f"{agent_name}: Groq output failed schema validation: {exc}") from exc

        usage = data.get("usage") or {}
        return LLMCompletion(
            parsed=parsed,
            provider="groq",
            model=self._model,
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
        )


class OpenAILLMClient:
    """TEMPORARY, EXPLICIT-OPT-IN ONLY — for the paper's cross-model
    benchmark (Table 5: gpt-4o vs. Claude Sonnet vs. the Groq/NVIDIA
    fallbacks used for the primary 30-case run), NOT part of the
    documented Sonnet-primary/Groq-fallback production policy. Only
    reachable via MIRA_LLM_PROVIDER=openai in build_default_client()
    below.

    This is the REAL OpenAI API (api.openai.com), not the gpt-oss family
    hosted on NVIDIA NIM (see NvidiaLLMClient) — genuinely GPT-4o-class,
    not an open-weight stand-in. Uses the same named forced-tool-call
    shape as GroqLLMClient (OpenAI's own Chat Completions API, which Groq's
    endpoint mimics), not the "required" string variant NvidiaLLMClient
    needed for the DeepSeek/Nemotron models on NIM.
    """

    def __init__(self, model: str = None, timeout: float = config.EXTERNAL_CALL_TIMEOUT_SECONDS):
        import httpx  # local import: only required if this opt-in path is used

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise LLMCallError("OPENAI_API_KEY is not set — cannot construct OpenAILLMClient")

        self._model = model or os.environ.get("OPENAI_MODEL", "gpt-4o")
        self._client = httpx.Client(
            base_url="https://api.openai.com/v1",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=timeout,
        )

    def complete(
        self,
        *,
        agent_name: str,
        system_prompt: str,
        user_content: str,
        response_model: Type[T],
        cache_prefix: Optional[str] = None,
    ) -> LLMCompletion:
        # cache_prefix dropped, not concatenated — same reasoning as
        # GroqLLMClient/NvidiaLLMClient above: no caching benefit on this
        # API surface for a benchmark run, only re-billed tokens per call.
        full_system = system_prompt
        schema = response_model.model_json_schema()
        tool_name = f"emit_{response_model.__name__.lower()}"

        def _call():
            resp = self._client.post(
                "/chat/completions",
                json={
                    "model": self._model,
                    "max_tokens": 1024,
                    "messages": [
                        {"role": "system", "content": full_system},
                        {"role": "user", "content": user_content},
                    ],
                    "tools": [
                        {
                            "type": "function",
                            "function": {
                                "name": tool_name,
                                "description": f"Return the {agent_name} agent's structured output.",
                                "parameters": schema,
                            },
                        }
                    ],
                    "tool_choice": {"type": "function", "function": {"name": tool_name}},
                },
            )
            resp.raise_for_status()
            return resp.json()

        try:
            data = call_with_retries(_call, call_name=f"openai:{agent_name}")
        except ExternalCallFailed as exc:
            raise LLMCallError(f"{agent_name}: OpenAI API call failed: {exc}") from exc

        try:
            message = data["choices"][0]["message"]
            tool_calls = message.get("tool_calls") or []
            if not tool_calls:
                raise LLMCallError(f"{agent_name}: no tool_calls in OpenAI response")
            arguments_json = tool_calls[0]["function"]["arguments"]
            parsed = response_model.model_validate_json(arguments_json)
        except (KeyError, IndexError, ValidationError, json.JSONDecodeError) as exc:
            raise LLMCallError(f"{agent_name}: OpenAI output failed schema validation: {exc}") from exc

        usage = data.get("usage") or {}
        return LLMCompletion(
            parsed=parsed,
            provider="openai",
            model=self._model,
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
        )


class GeminiLLMClient:
    """TEMPORARY, EXPLICIT-OPT-IN ONLY — added for local mechanical testing
    when no ANTHROPIC_API_KEY is available, NOT a documented supported
    provider and NOT part of the Sonnet-primary/Groq-fallback policy (see
    config.py). Only reachable via MIRA_LLM_PROVIDER=gemini in
    build_default_client() below; the default path is unaffected. Do not
    use output from this client to validate clinical-reasoning quality —
    it exists to exercise the pipeline/webhook plumbing, not to stand in
    for Sonnet.

    Uses Gemini's function-calling (forced via toolConfig mode=ANY) for
    the same structured-output contract the other clients use. Model
    defaults to the "gemini-flash-latest" alias rather than a pinned
    version — Gemini's model lineup had moved well past this session's
    training-data knowledge by the time this was written (confirmed by
    querying the live ListModels endpoint), so an alias Google itself
    keeps pointed at a current model is safer than guessing a specific
    version string. Override via GEMINI_MODEL if needed.
    """

    def __init__(self, model: str = None, timeout: float = config.EXTERNAL_CALL_TIMEOUT_SECONDS):
        import httpx  # local import: only required if this opt-in path is used

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise LLMCallError("GEMINI_API_KEY is not set — cannot construct GeminiLLMClient")

        self._model = model or os.environ.get("GEMINI_MODEL", "gemini-flash-latest")
        self._client = httpx.Client(
            base_url="https://generativelanguage.googleapis.com/v1beta",
            headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
            timeout=timeout,
        )

    def complete(
        self,
        *,
        agent_name: str,
        system_prompt: str,
        user_content: str,
        response_model: Type[T],
        cache_prefix: Optional[str] = None,
    ) -> LLMCompletion:
        # cache_prefix deliberately dropped, not concatenated — see the
        # identical note in GroqLLMClient.complete above. Gemini has its
        # own real caching API (createCachedContent) but this codebase
        # doesn't wire it up; sending the full RAG corpus uncached on every
        # call would burn the same free-tier-quota budget for no benefit.
        full_system = system_prompt
        schema = _to_gemini_schema(response_model.model_json_schema())
        tool_name = f"emit_{response_model.__name__.lower()}"

        def _call():
            resp = self._client.post(
                f"/models/{self._model}:generateContent",
                json={
                    "systemInstruction": {"parts": [{"text": full_system}]},
                    "contents": [{"role": "user", "parts": [{"text": user_content}]}],
                    "tools": [
                        {
                            "functionDeclarations": [
                                {
                                    "name": tool_name,
                                    "description": f"Return the {agent_name} agent's structured output.",
                                    "parameters": schema,
                                }
                            ]
                        }
                    ],
                    "toolConfig": {
                        "functionCallingConfig": {
                            "mode": "ANY",
                            "allowedFunctionNames": [tool_name],
                        }
                    },
                },
            )
            resp.raise_for_status()
            return resp.json()

        try:
            data = call_with_retries(_call, call_name=f"gemini:{agent_name}")
        except ExternalCallFailed as exc:
            raise LLMCallError(f"{agent_name}: Gemini API call failed: {exc}") from exc

        try:
            parts = data["candidates"][0]["content"]["parts"]
            function_call = next(p["functionCall"] for p in parts if "functionCall" in p)
            parsed = response_model.model_validate(function_call["args"])
        except (KeyError, IndexError, StopIteration, ValidationError) as exc:
            raise LLMCallError(f"{agent_name}: Gemini output failed schema validation: {exc}") from exc

        usage = data.get("usageMetadata") or {}
        return LLMCompletion(
            parsed=parsed,
            provider="gemini",
            model=self._model,
            input_tokens=usage.get("promptTokenCount"),
            output_tokens=usage.get("candidatesTokenCount"),
        )


class NvidiaLLMClient:
    """TEMPORARY, EXPLICIT-OPT-IN ONLY — same status as GeminiLLMClient
    above: not the documented Sonnet-primary/Groq-fallback policy, only
    reachable via MIRA_LLM_PROVIDER=nvidia. Added 2026-09-11 as a third
    fallback after groq (hard 8000 TPM account-wide cap) and gemini
    (frequent 503s/timeouts) both proved unreliable for a real multi-call
    pipeline run — see eval/README.md for the full story.

    Uses NVIDIA NIM's OpenAI-compatible endpoint (build.nvidia.com),
    default model deepseek-ai/deepseek-v4-flash-0731. Two things verified
    live against a real key on 2026-09-11 that matter for correctness:

    1. tool_choice MUST be the string "required", not the named
       {"type": "function", "function": {"name": ...}} form GroqLLMClient/
       AnthropicLLMClient use — the named form hung with zero bytes
       received for 60+ seconds against this model on NIM every time it
       was tried. "required" (forces some tool call, and only one tool is
       ever offered) gets the same guaranteed-structured-output contract
       in ~2-6s. If this client is ever extended to offer more than one
       tool at once, this stops being equivalent to naming one explicitly
       — revisit then.
    2. chat_template_kwargs={"thinking": True} -- verified live 2026-09-11
       that turning thinking OFF measurably degrades structured-extraction
       quality on MIRA's actual Intake schema (patient/symptom fields came
       back empty/null on cases that extracted correctly with thinking on,
       and a Diagnostic call used literal "diagnosis" language that the
       diagnostic_claim_filter guard correctly rejected). Costs more
       latency/tokens than thinking=False but is required for usable
       output on this task.
    """

    def __init__(self, model: str = config.NVIDIA_MODEL, timeout: float = config.EXTERNAL_CALL_TIMEOUT_SECONDS):
        import httpx  # local import: only required if this opt-in path is used

        api_key = os.environ.get("NVIDIA_API_KEY")
        if not api_key:
            raise LLMCallError("NVIDIA_API_KEY is not set — cannot construct NvidiaLLMClient")

        self._client = httpx.Client(
            base_url="https://integrate.api.nvidia.com/v1",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=timeout,
        )
        self._model = model

    def complete(
        self,
        *,
        agent_name: str,
        system_prompt: str,
        user_content: str,
        response_model: Type[T],
        cache_prefix: Optional[str] = None,
    ) -> LLMCompletion:
        # cache_prefix deliberately dropped, not concatenated — same
        # reasoning as GroqLLMClient/GeminiLLMClient above: no caching
        # benefit on this API surface, only re-billed/re-counted tokens.
        full_system = system_prompt
        schema = response_model.model_json_schema()
        tool_name = f"emit_{response_model.__name__.lower()}"

        def _call():
            resp = self._client.post(
                "/chat/completions",
                json={
                    "model": self._model,
                    # Higher than GroqLLMClient's 1024 -- thinking=True
                    # spends part of this budget on reasoning_content
                    # before ever reaching the tool call; too tight a
                    # budget truncates mid-reasoning and the tool call
                    # never happens.
                    "max_tokens": 2048,
                    "messages": [
                        {"role": "system", "content": full_system},
                        {"role": "user", "content": user_content},
                    ],
                    "tools": [
                        {
                            "type": "function",
                            "function": {
                                "name": tool_name,
                                "description": f"Return the {agent_name} agent's structured output.",
                                "parameters": schema,
                            },
                        }
                    ],
                    "tool_choice": "required",
                    "chat_template_kwargs": {"thinking": True},
                },
            )
            resp.raise_for_status()
            return resp.json()

        try:
            data = call_with_retries(_call, call_name=f"nvidia:{agent_name}")
        except ExternalCallFailed as exc:
            raise LLMCallError(f"{agent_name}: NVIDIA NIM API call failed: {exc}") from exc

        try:
            message = data["choices"][0]["message"]
            tool_calls = message.get("tool_calls") or []
            if not tool_calls:
                raise LLMCallError(f"{agent_name}: no tool_calls in NVIDIA NIM response")
            arguments_json = tool_calls[0]["function"]["arguments"]
            parsed = response_model.model_validate_json(arguments_json)
        except (KeyError, IndexError, ValidationError, json.JSONDecodeError) as exc:
            raise LLMCallError(f"{agent_name}: NVIDIA NIM output failed schema validation: {exc}") from exc

        usage = data.get("usage") or {}
        return LLMCompletion(
            parsed=parsed,
            provider="nvidia",
            model=self._model,
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
        )


def _to_gemini_schema(pydantic_schema: dict) -> dict:
    """Converts a pydantic v2 JSON Schema (draft 2020-12) into what
    Gemini's function-declaration `parameters` field actually accepts —
    a restricted OpenAPI-3.0-style subset. Two incompatibilities matter
    here, both of which broke real requests before this was written:

    1. Pydantic emits `$ref`/`$defs` for nested models (e.g. a
       `list[SomeModel]` field) — Gemini's schema has no $ref support, so
       every $ref is inlined recursively instead.
    2. Pydantic emits `Optional[X]` as `anyOf: [{type: X}, {type: "null"}]`
       — Gemini rejects the null-type union; collapse it to `{type: X,
       nullable: true}` instead, which is the OpenAPI-subset equivalent.

    Also drops `title` and `default` keys, which Gemini's schema parser
    doesn't use and which caused 400s when present alongside the above.
    """
    defs = pydantic_schema.get("$defs", {})

    def convert(node):
        if isinstance(node, list):
            return [convert(v) for v in node]
        if not isinstance(node, dict):
            return node

        if "$ref" in node:
            ref_name = node["$ref"].rsplit("/", 1)[-1]
            return convert(defs[ref_name])

        if "anyOf" in node:
            variants = node["anyOf"]
            is_nullable = any(v.get("type") == "null" for v in variants)
            non_null = [v for v in variants if v.get("type") != "null"]
            converted = convert(non_null[0]) if non_null else {"type": "string"}
            if is_nullable:
                converted = {**converted, "nullable": True}
            return converted

        return {
            k: convert(v)
            for k, v in node.items()
            if k not in ("title", "default", "$defs")
        }

    return convert(pydantic_schema)


class FailoverLLMClient:
    """Anthropic-primary, Groq-emergency-fallback wrapper. The failover
    itself is always logged (never silent) and stamped onto the returned
    LLMCompletion so PatientCase.model_provenance / fallback_events (see
    mira/agents/base.py) show exactly which model produced a given case's
    output."""

    def __init__(self, primary: LLMClient, fallback: LLMClient):
        self._primary = primary
        self._fallback = fallback

    def complete(self, **kwargs) -> LLMCompletion:
        try:
            return self._primary.complete(**kwargs)
        except LLMCallError as primary_exc:
            agent_name = kwargs.get("agent_name", "?")
            logger.warning(
                "FAILOVER: %s — primary (Anthropic) call failed (%s), "
                "falling back to Groq. This is a logged, transparent "
                "failover, never silent.",
                agent_name, primary_exc,
            )
            try:
                result = self._fallback.complete(**kwargs)
            except LLMCallError as fallback_exc:
                raise LLMCallError(
                    f"{agent_name}: both primary and fallback failed. "
                    f"primary={primary_exc} fallback={fallback_exc}"
                ) from fallback_exc

            result.fallback_used = True
            result.fallback_reason = str(primary_exc)
            return result


class MockLLMClient:
    """
    Deterministic client for tests and clinical dry-runs. Scenarios are
    registered by (agent_name, scenario_key) -> either a dict (parsed into
    response_model) or an exception instance/class to raise, or the string
    "__malformed__" to simulate a schema-validation failure.

    scenario_key defaults to "default" so a single scenario can serve every
    case unless a test explicitly wants per-case control.

    A scenario registered as a list is consumed sequentially, one item per
    call to that agent (the last item repeats once exhausted) — used to
    script multi-turn flows like Intake asking for clarification on the
    first call and succeeding on the second.
    """

    MALFORMED = "__malformed__"

    def __init__(self):
        self._scenarios: dict[tuple[str, str], object] = {}

    def register(self, agent_name: str, response: object, scenario_key: str = "default") -> None:
        self._scenarios[(agent_name, scenario_key)] = response

    def complete(
        self,
        *,
        agent_name: str,
        system_prompt: str,
        user_content: str,
        response_model: Type[T],
        cache_prefix: Optional[str] = None,  # unused by the mock; accepted for interface parity
        scenario_key: str = "default",
    ) -> LLMCompletion:
        key = (agent_name, scenario_key)
        if key not in self._scenarios:
            key = (agent_name, "default")
        if key not in self._scenarios:
            raise LLMCallError(
                f"MockLLMClient has no registered scenario for agent={agent_name!r} "
                f"scenario_key={scenario_key!r}"
            )

        scenario = self._scenarios[key]

        if isinstance(scenario, list):
            if not scenario:
                raise LLMCallError(f"{agent_name}: mock scenario list is empty")
            scenario = scenario.pop(0) if len(scenario) > 1 else scenario[0]

        if scenario == self.MALFORMED:
            raise LLMCallError(
                f"{agent_name}: mock scenario simulates malformed/unparseable output"
            )
        # Mirror AnthropicLLMClient: any underlying failure (network error,
        # timeout, whatever a test wants to simulate) surfaces to callers
        # as LLMCallError, never as an arbitrary exception type — agents
        # and the pipeline only need to handle one failure contract.
        if isinstance(scenario, BaseException):
            raise LLMCallError(f"{agent_name}: mock scenario simulates failure: {scenario}") from scenario
        if isinstance(scenario, type) and issubclass(scenario, BaseException):
            exc = scenario(f"{agent_name}: mock scenario simulates failure")
            raise LLMCallError(f"{agent_name}: mock scenario simulates failure: {exc}") from exc

        payload = scenario
        if isinstance(payload, str):
            payload = json.loads(payload)
        try:
            parsed = response_model.model_validate(payload)
        except ValidationError as exc:
            raise LLMCallError(
                f"{agent_name}: mock scenario failed schema validation: {exc}"
            ) from exc
        return LLMCompletion(parsed=parsed, provider="mock", model="mock")


def build_default_client() -> LLMClient:
    if config.MOCK_LLM:
        return MockLLMClient()

    # TEMPORARY test-only override — see GeminiLLMClient's docstring. Not
    # part of the documented Sonnet-primary/Groq-fallback policy; must be
    # explicitly requested via MIRA_LLM_PROVIDER=gemini|groq, never a silent
    # default, and never combined with the Groq-as-fallback path below (that
    # path is Groq reached only after a real Anthropic failure; this path is
    # Groq used directly, standing in for Sonnet entirely, when no
    # ANTHROPIC_API_KEY is available at all).
    override = os.environ.get("MIRA_LLM_PROVIDER", "").strip().lower()
    if override == "gemini":
        logger.warning(
            "MIRA_LLM_PROVIDER=gemini — using Gemini instead of Sonnet as "
            "primary. This is a local-test-only override, not the "
            "documented production policy; do not treat this run's "
            "reasoning quality as representative of Sonnet."
        )
        return GeminiLLMClient()
    if override == "groq":
        logger.warning(
            "MIRA_LLM_PROVIDER=groq — using Groq directly as primary "
            "(not as the Anthropic-failure fallback it's normally reserved "
            "for). This is a local-test-only override, not the documented "
            "production policy; do not treat this run's reasoning quality "
            "as representative of Sonnet."
        )
        return GroqLLMClient()
    if override == "nvidia":
        logger.warning(
            "MIRA_LLM_PROVIDER=nvidia — using NVIDIA NIM "
            f"({config.NVIDIA_MODEL}) instead of Sonnet as primary. This "
            "is a local-test-only override, not the documented production "
            "policy; do not treat this run's reasoning quality as "
            "representative of Sonnet."
        )
        return NvidiaLLMClient()
    if override == "openai":
        model = os.environ.get("OPENAI_MODEL", "gpt-4o")
        logger.warning(
            f"MIRA_LLM_PROVIDER=openai — using OpenAI ({model}) instead "
            "of Sonnet as primary. This is a local-test-only override for "
            "the paper's cross-model benchmark, not the documented "
            "production policy; do not treat this run's reasoning quality "
            "as representative of Sonnet."
        )
        return OpenAILLMClient()

    primary = AnthropicLLMClient()
    if os.environ.get("GROQ_API_KEY"):
        return FailoverLLMClient(primary=primary, fallback=GroqLLMClient())
    return primary
