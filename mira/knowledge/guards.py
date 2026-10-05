"""
Shared base for output-text guards (drug/dosage, diagnostic-claim).

A GuardViolation raised from an agent's `apply` gets one retry of the LLM
call (see mira/agents/base.py) — the model may simply rephrase acceptably —
and then, if the second attempt also violates, the normal AgentFailure /
fail-safe degradation path. Guards never strip-and-continue: partially
sanitized clinical text is worse than the hardcoded safe fallback.
"""


class GuardViolation(Exception):
    """Base class for hard output-text guard rejections."""
