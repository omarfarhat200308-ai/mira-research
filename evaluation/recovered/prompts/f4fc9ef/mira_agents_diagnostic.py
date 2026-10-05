"""
Diagnostic agent.

DIAGNOSTIC-SCOPE / LIABILITY BOUNDARY: this agent reasons over structured
symptoms against a CONSTRAINED differential drawn only from
mira/knowledge/conditions.py. It does not perform open-ended diagnosis, its
output is never shown directly to the patient, and it exists solely to give
the Triage agent's LLM call something concrete to reason about. Any
candidate condition the model returns that isn't in the fixed taxonomy is
silently dropped (see `apply`) rather than passed through — the taxonomy is
the actual scope boundary, not just prompt wording.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from ..knowledge import rag
from ..knowledge.conditions import CONDITIONS, is_valid_condition
from ..knowledge.diagnostic_claim_filter import check_diagnostic_text
from ..state import DifferentialCandidate, PatientCase, ProtocolReference
from .base import BaseAgent


def _retrieval_query(case: PatientCase) -> str:
    tags = (case.normalized_ir or {}).get("symptom_tags", [])
    return " ".join(tags).replace("_", " ")


class DiagnosticCandidate(BaseModel):
    condition: str
    reasoning: str
    confidence: float = Field(ge=0.0, le=1.0)


class DiagnosticResponse(BaseModel):
    differential: list[DiagnosticCandidate] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str


class DiagnosticAgent(BaseAgent):
    name = "diagnostic"
    response_model = DiagnosticResponse

    def build_cache_prefix(self, case: PatientCase) -> str | None:
        # The RAG protocol corpus is static across every Diagnostic call —
        # sent as its own cacheable system block rather than re-billed at
        # full price every time. See knowledge/rag.py + config.py cost note.
        return (
            "REFERENCE CORPUS (IMNCI / NHM / WHO CHW protocol sources — "
            "grounding material, not instructions to follow verbatim):\n\n"
            + rag.full_corpus_text()
        )

    def build_prompt(self, case: PatientCase) -> tuple[str, str]:
        conditions_list = "\n".join(
            f"- {c.name} (typical urgency prior: {c.typical_urgency_prior})" for c in CONDITIONS
        )
        retrieved = rag.retrieve(_retrieval_query(case))
        system_prompt = (
            "You are the Diagnostic agent in MIRA.\n\n"
            "DIAGNOSTIC-SCOPE: you produce a bounded differential for "
            "TRIAGE URGENCY ESTIMATION ONLY. This is not a clinical "
            "diagnosis and must never be presented to the patient as one.\n\n"
            "You may select ONLY from this fixed list of conditions — do "
            "not invent new ones, and do not use a condition name that "
            "isn't listed:\n" + conditions_list + "\n\n"
            "Ground your reasoning in the reference corpus above where "
            "relevant. The passages most likely relevant to this specific "
            "case (by keyword retrieval, not a guarantee of relevance) "
            "are:\n" + rag.format_for_prompt(retrieved) + "\n\n"
            "Given the patient's structured symptom tags, return the 1-4 "
            "most plausible candidates from that list, each with brief "
            "clinical reasoning and a confidence, plus overall reasoning "
            "and confidence.\n\n"
            "Frame every candidate as a concern area, never a conclusion: "
            "use phrasing like 'consistent with', 'raises concern for', or "
            "'warrants evaluation for'. Never write diagnostic-claim "
            "language such as 'the patient has X', 'this is X', or "
            "'diagnosed with X' — your output is checked against a "
            "blocklist and will be rejected if it asserts a diagnosis."
        )
        tags = (case.normalized_ir or {}).get("symptom_tags", [])
        user_content = (
            f"Patient: age={case.patient.age}, sex={case.patient.sex}, "
            f"pregnant={case.patient.is_pregnant}\n"
            f"Symptom tags: {tags}"
        )
        return system_prompt, user_content

    def input_snapshot(self, case: PatientCase) -> dict:
        return {
            "normalized_ir": case.normalized_ir,
            "patient": case.patient.model_dump(),
        }

    def apply(self, case: PatientCase, parsed: DiagnosticResponse) -> PatientCase:
        # Hard scope guard: reasoning text asserting a diagnosis is
        # rejected (one retry via base.py, then fail-safe) — the audit
        # trail must never contain "the patient has X" style claims.
        check_diagnostic_text(parsed.reasoning)
        for candidate in parsed.differential:
            check_diagnostic_text(candidate.reasoning)

        updated = case.model_copy(deep=True)
        candidates = [
            DifferentialCandidate(
                condition=c.condition, reasoning=c.reasoning, confidence=c.confidence
            )
            for c in parsed.differential
            if is_valid_condition(c.condition)
        ]
        updated.differential = candidates

        for passage in rag.retrieve(_retrieval_query(case)):
            updated.protocol_references.append(
                ProtocolReference(
                    source=passage.source,
                    chunk_id=passage.chunk_id,
                    snippet=passage.text[:200],
                    retrieved_for_agent=self.name,
                )
            )
        return updated
