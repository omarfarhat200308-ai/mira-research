"""
Triage agent.

This is the safety-critical stage: urgency is decided by cross-checking the
LLM's own judgment against the hardcoded, non-LLM red-flag rule engine
(mira/safety/red_flags.py). The combination logic is intentionally simple
and fully auditable:

1. Red-flag rules run first, against normalized_ir only (never against the
   LLM's output). If ANY rule fires, final_triage = EMERGENCY and
   triage_decided_by = rule_override — this cannot be changed by the LLM's
   assessment, which is still recorded for audit but has no vote once a
   rule has fired.
2. Otherwise, the LLM's assessment is used, but only if it's well-formed
   and its confidence clears TRIAGE_LLM_CONFIDENCE_FLOOR. If not, the
   pipeline escalates one urgency band rather than trusting a possibly
   wrong "routine" call — the system is built to fail toward caution, never
   toward silently downgrading a case.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from .. import config
from ..knowledge import rag
from ..safety.red_flags import evaluate_red_flags
from ..state import PatientCase, ProtocolReference, TriageAssessment, TriageDecidedBy, Urgency
from .base import BaseAgent


def _retrieval_query(case: PatientCase) -> str:
    tags = (case.normalized_ir or {}).get("symptom_tags", [])
    diff_conditions = [d.condition for d in case.differential]
    return " ".join(tags + diff_conditions).replace("_", " ")


class TriageResponse(BaseModel):
    urgency: str
    reasoning: str
    confidence: float = Field(ge=0.0, le=1.0)


def _escalate(urgency: Urgency) -> Urgency:
    if urgency == Urgency.ROUTINE:
        return Urgency.URGENT
    return Urgency.EMERGENCY


class TriageAgent(BaseAgent):
    name = "triage"
    response_model = TriageResponse

    def build_cache_prefix(self, case: PatientCase) -> str | None:
        # Same static corpus block as Diagnostic (see agents/diagnostic.py)
        # — identical prefix text means Anthropic can reuse the same cache
        # entry across both agent types, not just across repeated Triage
        # calls.
        return (
            "REFERENCE CORPUS (IMNCI / NHM / WHO CHW protocol sources — "
            "grounding material, not instructions to follow verbatim):\n\n"
            + rag.full_corpus_text()
        )

    def build_prompt(self, case: PatientCase) -> tuple[str, str]:
        retrieved = rag.retrieve(_retrieval_query(case))
        system_prompt = (
            "You are the Triage agent in MIRA. Classify urgency as exactly "
            "one of: emergency, urgent, routine, given the patient's "
            "symptom tags and the Diagnostic agent's differential. Give "
            "your reasoning and a confidence.\n\n"
            "Ground your reasoning in the reference corpus above where "
            "relevant. The passages most likely relevant to this specific "
            "case (by keyword retrieval, not a guarantee of relevance) "
            "are:\n" + rag.format_for_prompt(retrieved) + "\n\n"
            "Your output is independently cross-checked against a "
            "hardcoded clinical red-flag rule list you cannot see and "
            "cannot override — give your best independent clinical "
            "judgment regardless; do not try to guess what the rule list "
            "contains."
        )
        diffs = "\n".join(
            f"- {d.condition} (confidence {d.confidence}): {d.reasoning}"
            for d in case.differential
        )
        tags = (case.normalized_ir or {}).get("symptom_tags", [])
        user_content = (
            f"Patient: age={case.patient.age}, sex={case.patient.sex}, "
            f"pregnant={case.patient.is_pregnant}\n"
            f"Symptom tags: {tags}\n"
            f"Differential:\n{diffs}"
        )
        return system_prompt, user_content

    def input_snapshot(self, case: PatientCase) -> dict:
        return {
            "normalized_ir": case.normalized_ir,
            "differential": [d.model_dump() for d in case.differential],
        }

    def apply(self, case: PatientCase, parsed: TriageResponse) -> PatientCase:
        updated = case.model_copy(deep=True)

        for passage in rag.retrieve(_retrieval_query(case)):
            updated.protocol_references.append(
                ProtocolReference(
                    source=passage.source,
                    chunk_id=passage.chunk_id,
                    snippet=passage.text[:200],
                    retrieved_for_agent=self.name,
                )
            )

        try:
            llm_urgency: Urgency | None = Urgency(parsed.urgency.strip().lower())
        except ValueError:
            llm_urgency = None  # LLM returned something outside {emergency, urgent, routine}

        updated.llm_triage_assessment = TriageAssessment(
            urgency=llm_urgency or Urgency.URGENT,
            reasoning=parsed.reasoning,
            confidence=parsed.confidence,
        )

        # Step 1: hardcoded rule engine, always evaluated, always wins if it fires.
        red_flags = evaluate_red_flags(case.normalized_ir or {})
        updated.red_flags_triggered = red_flags

        if red_flags:
            updated.final_triage = Urgency.EMERGENCY
            updated.triage_decided_by = TriageDecidedBy.RULE_OVERRIDE
            return updated

        # Step 2: no rule fired — defer to the LLM, but only if it's
        # well-formed and confident enough. Never trust a low-confidence or
        # malformed "routine" at face value.
        if llm_urgency is None or parsed.confidence < config.TRIAGE_LLM_CONFIDENCE_FLOOR:
            updated.final_triage = _escalate(llm_urgency or Urgency.ROUTINE)
            updated.triage_decided_by = TriageDecidedBy.FAILSAFE_DEGRADED
            return updated

        updated.final_triage = llm_urgency
        updated.triage_decided_by = TriageDecidedBy.LLM
        return updated
