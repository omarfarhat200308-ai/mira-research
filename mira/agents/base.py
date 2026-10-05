"""
Shared agent contract.

Every agent: takes a PatientCase in, returns an updated copy out — never
mutates shared chat history, never gets to see or change fields another
agent is responsible for except by the explicit state fields it's granted
(see mira/state.py). Every call, successful or not, is logged (input,
output, confidence/reasoning, latency, timestamp) via mira.logging_store,
so the July 20 - Aug 5 clinical testing phase has a complete audit trail.

Any exception from the LLM client, or a response that fails schema
validation, is wrapped into AgentFailure and re-raised. Agents never catch
their own failures and improvise a fallback — that decision belongs to the
pipeline (mira/pipeline.py), which always degrades toward the safe
"refer to nearest clinic" default rather than letting an agent guess.
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Type, TypeVar

from pydantic import BaseModel

from .. import logging_store
from ..knowledge.guards import GuardViolation
from ..llm_client import LLMCallError, LLMClient
from ..state import PatientCase

T = TypeVar("T", bound=BaseModel)


class AgentFailure(Exception):
    def __init__(self, agent_name: str, reason: str):
        self.agent_name = agent_name
        self.reason = reason
        super().__init__(f"{agent_name} failed: {reason}")


class BaseAgent(ABC):
    name: str
    response_model: Type[BaseModel]

    @abstractmethod
    def build_prompt(self, case: PatientCase) -> tuple[str, str]:
        """Return (system_prompt, user_content) for this agent's LLM call."""

    @abstractmethod
    def input_snapshot(self, case: PatientCase) -> dict[str, Any]:
        """The subset of case state this agent actually reads, for logging."""

    @abstractmethod
    def apply(self, case: PatientCase, parsed: BaseModel) -> PatientCase:
        """Pure function: given the case and the validated LLM output,
        return an updated copy of the case. Must not call the LLM again."""

    def build_cache_prefix(self, case: PatientCase) -> str | None:
        """Optional static/reusable text (e.g. the RAG protocol corpus) sent
        as its own Anthropic prompt-caching-eligible system block ahead of
        build_prompt's dynamic system_prompt. None (default) means no
        caching for this agent — override in agents whose prompt includes
        genuinely static, reused-every-call content. See llm_client.py."""
        return None

    def extract_confidence_and_reasoning(self, parsed: BaseModel) -> tuple[float | None, str | None]:
        return (
            getattr(parsed, "confidence", None),
            getattr(parsed, "reasoning", None),
        )

    # One retry is allowed when `apply` rejects the output via a
    # GuardViolation (drug/dosage or diagnostic-claim filter): the model
    # may simply rephrase acceptably on a second attempt. Anything else —
    # LLM call failure, schema violation, a second guard rejection — goes
    # straight to AgentFailure and the pipeline's fail-safe path. Guards
    # never strip-and-continue.
    GUARD_RETRIES = 1

    def run(self, case: PatientCase, client: LLMClient) -> PatientCase:
        system_prompt, user_content = self.build_prompt(case)
        cache_prefix = self.build_cache_prefix(case)
        for attempt in range(self.GUARD_RETRIES + 1):
            start = time.monotonic()
            timestamp = datetime.now(timezone.utc)
            try:
                result = client.complete(
                    agent_name=self.name,
                    system_prompt=system_prompt,
                    user_content=user_content,
                    response_model=self.response_model,
                    cache_prefix=cache_prefix,
                )
            except LLMCallError as exc:
                logging_store.log_agent_call(
                    logging_store.AgentLogEntry(
                        case_id=case.case_id,
                        agent_name=self.name,
                        timestamp=timestamp,
                        status="failed",
                        input_snapshot=self.input_snapshot(case),
                        latency_ms=(time.monotonic() - start) * 1000,
                        error=str(exc),
                    )
                )
                raise AgentFailure(self.name, str(exc)) from exc

            parsed = result.parsed
            latency_ms = (time.monotonic() - start) * 1000
            confidence, reasoning = self.extract_confidence_and_reasoning(parsed)

            try:
                updated_case = self.apply(case, parsed)
                break
            except Exception as exc:  # guard rejection or other apply failure
                retrying = isinstance(exc, GuardViolation) and attempt < self.GUARD_RETRIES
                logging_store.log_agent_call(
                    logging_store.AgentLogEntry(
                        case_id=case.case_id,
                        agent_name=self.name,
                        timestamp=timestamp,
                        status="failed",
                        input_snapshot=self.input_snapshot(case),
                        output_snapshot=parsed.model_dump(mode="json"),
                        confidence=confidence,
                        reasoning=reasoning,
                        latency_ms=latency_ms,
                        error=f"{exc}" + (" [retrying once]" if retrying else ""),
                        provider=result.provider,
                        model=result.model,
                        input_tokens=result.input_tokens,
                        output_tokens=result.output_tokens,
                        fallback_used=result.fallback_used,
                        fallback_reason=result.fallback_reason,
                    )
                )
                if not retrying:
                    raise AgentFailure(self.name, str(exc)) from exc

        # Provenance/cost audit lands on the case itself, not just the
        # per-call log, so "which model produced which output" is visible
        # on the case without cross-referencing logs — see state.py.
        updated_case.model_provenance[self.name] = f"{result.provider}:{result.model}"
        if result.fallback_used:
            updated_case.fallback_events.append(
                f"{self.name}: Anthropic->Groq failover ({result.fallback_reason})"
            )

        logging_store.log_agent_call(
            logging_store.AgentLogEntry(
                case_id=case.case_id,
                agent_name=self.name,
                timestamp=timestamp,
                status="ok",
                input_snapshot=self.input_snapshot(case),
                output_snapshot=parsed.model_dump(mode="json"),
                confidence=confidence,
                reasoning=reasoning,
                latency_ms=latency_ms,
                provider=result.provider,
                model=result.model,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                fallback_used=result.fallback_used,
                fallback_reason=result.fallback_reason,
            )
        )
        return updated_case
