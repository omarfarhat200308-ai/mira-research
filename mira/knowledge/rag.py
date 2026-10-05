"""
Lightweight retrieval layer grounding Diagnostic and Triage calls in the
three-source protocol corpus (mira/knowledge/protocol_corpus/): IMNCI
training manuals, NHM protocol documents, WHO CHW guidelines. Deliberately
NOT fine-tuning: grounding via retrieval keeps every classification
traceable back to a specific passage (PatientCase.protocol_references),
which fine-tuning would silently erase — you'd lose the ability to point at
which protocol rule drove a given output, which is the whole point of the
"Verifiable Workflow Automator" framing.

IMPORTANT — corpus status: mira/knowledge/protocol_corpus/*.md are
currently PLACEHOLDER stand-ins (see each file's header), not the real
IMNCI/NHM/WHO source documents. The retrieval mechanism below is real and
tested; the content it retrieves is not yet the real protocol text. Swap
the corpus files before any pilot or paper result depends on retrieval
quality — no code change needed here to do that.

Retrieval method: no embeddings API key is configured for this project, so
this uses a dependency-free TF-IDF-cosine-similarity ranking over the
locally chunked corpus (stdlib only). This is a reasonable, honestly-labeled
placeholder retrieval method — swap in a real embeddings API (e.g. once one
is provisioned) by replacing `_score` below; `retrieve()`'s signature and
PatientCase.protocol_references' shape don't need to change either way.
"""
from __future__ import annotations

import math
import os
import re
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache

_CORPUS_DIR = os.path.join(os.path.dirname(__file__), "protocol_corpus")

# source key -> filename, in a fixed order so citations are stable/readable.
CORPUS_SOURCES: dict[str, str] = {
    "imnci": "imnci.md",
    "nhm": "nhm.md",
    "who_chw": "who_chw.md",
}

_TOKEN_RE = re.compile(r"[a-z]+")


@dataclass(frozen=True)
class Chunk:
    source: str
    chunk_id: str
    text: str


@dataclass(frozen=True)
class RetrievedPassage:
    source: str
    chunk_id: str
    text: str
    score: float


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def _load_chunks() -> list[Chunk]:
    """Split each corpus file into paragraph-level chunks (blank-line
    separated), skipping the HTML placeholder-disclosure comment block at
    the top of each file so it never gets retrieved and quoted as if it
    were content."""
    chunks: list[Chunk] = []
    for source, filename in CORPUS_SOURCES.items():
        path = os.path.join(_CORPUS_DIR, filename)
        with open(path, encoding="utf-8") as f:
            raw = f.read()
        raw = re.sub(r"<!--.*?-->", "", raw, flags=re.DOTALL)
        paragraphs = [p.strip() for p in raw.split("\n\n") if p.strip()]
        for i, para in enumerate(paragraphs):
            chunks.append(Chunk(source=source, chunk_id=f"{source}#{i}", text=para))
    return chunks


@lru_cache(maxsize=1)
def _index() -> tuple[list[Chunk], list[Counter], dict[str, float]]:
    """Builds a simple TF-IDF index once per process. Cached because the
    corpus files don't change at runtime; call `_index.cache_clear()` in
    tests if a test needs to reload after editing corpus files on disk."""
    chunks = _load_chunks()
    term_freqs = [Counter(_tokenize(c.text)) for c in chunks]

    doc_freq: Counter[str] = Counter()
    for tf in term_freqs:
        for term in tf:
            doc_freq[term] += 1

    n_docs = len(chunks) or 1
    idf = {term: math.log((n_docs + 1) / (df + 1)) + 1.0 for term, df in doc_freq.items()}
    return chunks, term_freqs, idf


def _vector(tf: Counter, idf: dict[str, float]) -> dict[str, float]:
    return {term: count * idf.get(term, 0.0) for term, count in tf.items()}


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    common = set(a) & set(b)
    dot = sum(a[t] * b[t] for t in common)
    norm_a = math.sqrt(sum(v * v for v in a.values()))
    norm_b = math.sqrt(sum(v * v for v in b.values()))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def retrieve(query: str, top_k: int = 3, min_score: float = 0.05) -> list[RetrievedPassage]:
    """Returns up to `top_k` corpus chunks most relevant to `query`, ranked
    by TF-IDF cosine similarity, dropping anything below `min_score` (an
    irrelevant top match is worse than no match — an agent's prompt should
    not be padded with noise it then has to ignore)."""
    chunks, term_freqs, idf = _index()
    query_vec = _vector(Counter(_tokenize(query)), idf)

    scored = []
    for chunk, tf in zip(chunks, term_freqs):
        score = _cosine(query_vec, _vector(tf, idf))
        if score >= min_score:
            scored.append((score, chunk))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [
        RetrievedPassage(source=c.source, chunk_id=c.chunk_id, text=c.text, score=score)
        for score, c in scored[:top_k]
    ]


def full_corpus_text() -> str:
    """Returns the entire (placeholder, see module docstring) corpus,
    concatenated and source-labeled. Used as a cacheable system-prompt
    prefix (see mira/agents/base.py's build_cache_prefix hook) so Diagnostic
    and Triage calls ground against the whole corpus — not just the top-k
    retrieved for the audit citation — at near-zero marginal token cost
    once cached. This is only practical while the corpus is small enough to
    comfortably fit in a cached prefix; once real IMNCI/NHM/WHO source text
    is ingested and the corpus grows well past a few thousand tokens, switch
    this call site to injecting only retrieve()'s top-k directly instead."""
    chunks, _, _ = _index()
    by_source: dict[str, list[str]] = {}
    for c in chunks:
        by_source.setdefault(c.source, []).append(c.text)
    parts = [
        f"=== SOURCE: {source} ===\n" + "\n\n".join(by_source.get(source, []))
        for source in CORPUS_SOURCES
    ]
    return "\n\n".join(parts)


def format_for_prompt(passages: list[RetrievedPassage]) -> str:
    """Renders retrieved passages as a labeled, clearly-bounded reference
    block for inclusion in a system prompt — grounding only, explicitly not
    an instruction to follow blindly."""
    if not passages:
        return (
            "No protocol reference passages retrieved above the relevance "
            "threshold for this case — reason from the symptom tags alone "
            "and note the absence of a grounding passage in your reasoning."
        )
    lines = [
        "Reference passages retrieved from the protocol corpus (grounding "
        "only — use to inform your reasoning, do not quote verbatim as if "
        "diagnostic, and note explicitly if the input doesn't clearly match "
        "any passage below):",
    ]
    for p in passages:
        lines.append(f"\n[{p.chunk_id}] (source: {p.source})\n{p.text}")
    return "\n".join(lines)
