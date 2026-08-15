"""Confidence scoring on an open-weight model.

``Draft.confidence`` is the buy/don't-buy signal and the single most-run
decision in the company: every order passes through it, and it decides whether
the firm spends cost of goods. Running that on a frontier model would be paying
premium rates for a bounded classification, so it runs on an open-weight model
(Qwen3-8B by default) hosted on Pioneer.

Degrades rather than raising. If Pioneer is unreachable, unfunded, or slow, the
caller gets a heuristic score and a note saying so -- an outage must not stop
the company trading, it must only make it more cautious.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass

DEFAULT_BASE = "https://api.pioneer.ai/v1"
DEFAULT_MODEL = "Qwen/Qwen3-8B"

# Kept deliberately terse: the model is asked for one number, nothing else.
PROMPT = (
    "You judge whether an AI assistant can answer a question reliably on its own.\n"
    'Return ONLY a JSON object: {{"confidence": <0.0-1.0>}}\n'
    "High confidence = a well-known fact or a matter of public record.\n"
    "Low confidence = consumer taste, local specifics, anything needing a real "
    "person's judgement or current knowledge.\n\n"
    "Question: {question}"
)


@dataclass(frozen=True)
class Score:
    confidence: float
    source: str  # "pioneer" when the model answered, "heuristic" when degraded
    model: str
    note: str = ""


# Words that signal the answer depends on a person's judgement rather than a
# fact. Used only when the model is unavailable.
_SUBJECTIVE = re.compile(
    r"\b(compelling|prefer|better|worse|like|appealing|attractive|"
    r"convincing|opinion|feel|taste|should i|which one)\b",
    re.I,
)


def _heuristic(question: str, note: str) -> Score:
    """A deliberately pessimistic fallback.

    When we cannot measure our own confidence we assume it is low, because the
    expensive mistake is answering confidently from ignorance, not buying an
    opinion we did not strictly need.
    """
    confidence = 0.30 if _SUBJECTIVE.search(question) else 0.55
    return Score(confidence=confidence, source="heuristic", model="none", note=note)


def score_confidence(
    question: str,
    *,
    api_key: str | None = None,
    base: str | None = None,
    model: str | None = None,
    timeout: float = 20.0,
) -> Score:
    """Return how confident the agent is that it can answer without buying help."""
    api_key = api_key if api_key is not None else os.environ.get("PIONEER_API_KEY", "").strip()
    base = base or os.environ.get("PIONEER_API_BASE", "").strip() or DEFAULT_BASE
    model = model or os.environ.get("PIONEER_MODEL", "").strip() or DEFAULT_MODEL

    if not api_key:
        return _heuristic(question, "PIONEER_API_KEY not set")

    body = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": PROMPT.format(question=question)}],
            "max_tokens": 32,
            "temperature": 0,
        }
    ).encode()
    req = urllib.request.Request(
        f"{base}/chat/completions",
        data=body,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.load(resp)
        content = payload["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as exc:
        return _heuristic(question, f"pioneer HTTP {exc.code}")
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError, IndexError) as exc:
        return _heuristic(question, f"pioneer unavailable: {type(exc).__name__}")

    return _parse(content, question, model)


def _parse(content: str, question: str, model: str) -> Score:
    """Pull the number out. Small models wrap JSON in prose more often than not."""
    match = re.search(r'"confidence"\s*:\s*([01](?:\.\d+)?)', content or "")
    if not match:
        match = re.search(r"\b([01]\.\d+)\b", content or "")
    if not match:
        return _heuristic(question, "model returned no parsable confidence")
    value = float(match.group(1))
    if not 0.0 <= value <= 1.0:
        return _heuristic(question, f"confidence {value} out of range")
    return Score(confidence=value, source="pioneer", model=model)
