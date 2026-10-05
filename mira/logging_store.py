"""
Append-only structured logging for the clinical testing phase (July 20 -
Aug 5) and for the eventual paper's audit trail.

Every agent call is logged with its input, output, confidence/reasoning
where applicable, latency, and a timestamp. Logs are JSONL — one file per
UTC day — chosen deliberately over a database for this phase: it's
directly readable and diffable by the clinical co-advisor without any
tooling, and append-only files are hard to accidentally mutate. If log
volume grows past what's comfortable in the July-August window, this is the
place to swap in SQLite without touching callers (the public functions
below are the whole interface).
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel

from . import config


class AgentLogEntry(BaseModel):
    case_id: str
    agent_name: str
    timestamp: datetime
    status: str  # "ok" | "failed" | "degraded"
    input_snapshot: dict[str, Any]
    output_snapshot: dict[str, Any] | None = None
    confidence: float | None = None
    reasoning: str | None = None
    latency_ms: float | None = None
    error: str | None = None
    # Model provenance / cost audit — which provider+model actually answered
    # this call, its token spend, and whether a Groq failover happened (see
    # mira/llm_client.py). None for calls that never reached a client (e.g.
    # a guard rejection logged before completion).
    provider: str | None = None
    model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    fallback_used: bool = False
    fallback_reason: str | None = None


def _log_path_for(dt: datetime) -> str:
    os.makedirs(config.LOG_DIR, exist_ok=True)
    return os.path.join(config.LOG_DIR, f"{dt.date().isoformat()}.jsonl")


def _append_jsonl(path: str, record: dict) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=str) + "\n")


def log_agent_call(entry: AgentLogEntry) -> None:
    path = _log_path_for(entry.timestamp)
    _append_jsonl(path, entry.model_dump(mode="json"))


def log_case_final_state(case) -> None:
    """Persist the full final PatientCase for a completed (or degraded/
    failed) pipeline run, so the whole audit trail for a case can be
    reconstructed from the logs directory alone."""
    now = datetime.now(timezone.utc)
    path = os.path.join(config.LOG_DIR, f"{now.date().isoformat()}_cases.jsonl")
    os.makedirs(config.LOG_DIR, exist_ok=True)
    record = {
        "logged_at": now.isoformat(),
        "case": case.model_dump(mode="json"),
    }
    _append_jsonl(path, record)


def read_log_entries(date_str: str) -> list[dict]:
    """Utility for the clinical review / test harness to read back a day's
    agent-call log entries."""
    path = os.path.join(config.LOG_DIR, f"{date_str}.jsonl")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def read_case_records(date_str: str, data_source: str | None = None) -> list[dict]:
    """Reads back a day's final-case records (the *_cases.jsonl file), for
    the clinical review / paper-results pipeline. Pass data_source
    ("simulated" | "pilot") to filter — the whole reason this parameter
    exists is so a results table can never silently blend synthetic and
    real pilot cases; when in doubt, callers should pass it explicitly
    rather than reading unfiltered."""
    path = os.path.join(config.LOG_DIR, f"{date_str}_cases.jsonl")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]
    if data_source is None:
        return records
    return [r for r in records if r.get("case", {}).get("data_source") == data_source]
