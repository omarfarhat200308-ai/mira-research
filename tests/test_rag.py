"""
Tests for the RAG retrieval layer (mira/knowledge/rag.py) and its wiring
into Diagnostic/Triage (protocol_references on PatientCase). See the module
docstring in rag.py: the corpus itself is a placeholder, but the retrieval
mechanism and its audit-trail wiring are real and tested here.
"""
from __future__ import annotations

from mira.knowledge import rag
from mira.pipeline import run_pipeline

from .fixtures.cases import CASES_BY_KEY


def test_retrieve_returns_topically_relevant_passages():
    passages = rag.retrieve("child fast breathing cough pneumonia")
    assert passages, "expected at least one passage above the relevance threshold"
    assert all(p.source in rag.CORPUS_SOURCES for p in passages)
    # The IMNCI fast-breathing passage should be the top (or a top) hit.
    assert any(p.source == "imnci" for p in passages)


def test_retrieve_respects_top_k():
    passages = rag.retrieve("fever cough headache bleeding pregnancy weakness", top_k=2)
    assert len(passages) <= 2


def test_retrieve_empty_query_returns_no_passages():
    assert rag.retrieve("") == []


def test_format_for_prompt_handles_empty_and_nonempty():
    assert "No protocol reference passages" in rag.format_for_prompt([])
    passages = rag.retrieve("pregnant severe headache visual disturbance")
    rendered = rag.format_for_prompt(passages)
    for p in passages:
        assert p.chunk_id in rendered


def test_full_corpus_text_includes_all_three_sources():
    text = rag.full_corpus_text()
    for source in rag.CORPUS_SOURCES:
        assert f"SOURCE: {source}" in text
    # The placeholder-disclosure HTML comments must never leak into what's
    # actually sent to the model as content.
    assert "<!--" not in text


def test_pipeline_run_records_protocol_references_for_diagnostic_and_triage():
    case = CASES_BY_KEY["pre_eclampsia_regression"]
    result = run_pipeline(case.raw_input_text, llm_client=case.build_client())

    agents_cited = {ref.retrieved_for_agent for ref in result.protocol_references}
    assert "diagnostic" in agents_cited
    assert "triage" in agents_cited
    for ref in result.protocol_references:
        assert ref.source in rag.CORPUS_SOURCES
        assert ref.snippet  # never an empty citation
