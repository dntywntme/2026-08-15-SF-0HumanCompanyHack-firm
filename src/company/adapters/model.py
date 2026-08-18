"""The agent's own attempt, on an open-weight model — with a floor under it.

Two things come off one call: the draft answer, and the confidence the agent has
in it. Confidence is the buy/don't-buy signal and the single most-run decision
in the company -- every order passes through it and it decides whether real
money is committed -- so it runs on a small open-weight model rather than a
frontier one. Paying premium rates for a bounded classification is how unit
economics die.

**Provider-neutral on purpose.** This speaks the OpenAI chat-completions shape,
which is a protocol rather than a vendor: Cloudflare Workers AI, Pioneer, or
anything else that serves ``POST {base}/chat/completions`` works by setting
three environment variables. The adapter was pinned to one vendor before, that
vendor returned 404 to every call, and the pinning is what made the outage
un-routable.

Three tiers, the same shape as ``adapters/terac.py``, because the same rule
applies: a demo that silently falls back is a demo that misleads.

1. **live** — the model answers the question that was actually asked.
2. **heuristic** — the model is unreachable; score pessimistically from the
   question's shape and answer nothing. The company gets more cautious, not
   more confident.
3. **recorded** — the committed fixture. Never fails, and never claims to be an
   answer to a question it has not seen.

Every tier stamps ``source``, which is what lets the pipeline tell a customer
that an answer is a recorded demonstration rather than quietly shipping one.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from company.adapters.http import open_https

# Cloudflare Workers AI, via its OpenAI-compatible base. Any host serving the
# same shape works; see .env.example for the Pioneer form.
DEFAULT_MODEL = "@cf/meta/llama-3.1-8b-instruct"

# Asked for one JSON object and nothing else. Small models wrap JSON in prose
# more often than not, which _parse is built to survive.
PROMPT = (
    "You answer a question, then judge whether you can answer it reliably alone.\n"
    'Return ONLY JSON: {{"answer": "<2-3 sentences>", "confidence": <0.0-1.0>, '
    '"unknowns": ["<what you cannot know>", ...]}}\n'
    "High confidence = a well-known fact or a matter of public record.\n"
    "Low confidence = consumer taste, local specifics, anything needing a real "
    "person's judgement or current knowledge. Be honest: a low score is not a "
    "failure, it is what tells us to go and ask people.\n\n"
    "Question: {question}"
)

# Words that signal the answer depends on a person's judgement rather than a
# fact. Used only when no model is reachable.
_SUBJECTIVE = re.compile(
    r"\b(compelling|prefer|better|worse|like|appealing|attractive|"
    r"convincing|opinion|feel|taste|should i|which one)\b",
    re.I,
)


@dataclass(frozen=True)
class Score:
    confidence: float
    source: str  # "live" when the model answered, "heuristic" when degraded
    model: str
    note: str = ""


def _config(api_key: str | None, base: str | None, model: str | None) -> tuple[str, str, str]:
    key = api_key if api_key is not None else os.environ.get("MODEL_API_KEY", "").strip()
    root = (base or os.environ.get("MODEL_API_BASE", "").strip()).rstrip("/")
    name = model or os.environ.get("MODEL_NAME", "").strip() or DEFAULT_MODEL
    return key, root, name


def _complete(question: str, key: str, base: str, model: str, timeout: float) -> str:
    """One completion. Raises; callers degrade."""
    body = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": PROMPT.format(question=question)}],
            "max_tokens": 300,
            # Nudges the same question towards the same answer. It does not make
            # a hosted model reproducible, which is why the recorded tier -- not
            # this one -- is what --replay runs on.
            "temperature": 0,
        }
    ).encode()
    req = urllib.request.Request(
        f"{base}/chat/completions",
        data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    # The base is environment-supplied, so the scheme is checked before opening.
    with open_https(req, timeout) as resp:
        payload = json.load(resp)
    return payload["choices"][0]["message"]["content"]


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
    """How confident the agent is that it can answer without buying help."""
    key, root, name = _config(api_key, base, model)
    if not key or not root:
        return _heuristic(question, "MODEL_API_KEY or MODEL_API_BASE not set")
    try:
        content = _complete(question, key, root, name, timeout)
    except urllib.error.HTTPError as exc:
        return _heuristic(question, f"model HTTP {exc.code}")
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError, IndexError) as exc:
        return _heuristic(question, f"model unavailable: {type(exc).__name__}")

    parsed = _parse(content)
    if parsed is None or not 0.0 <= parsed.get("confidence", -1) <= 1.0:
        return _heuristic(question, "model returned no parsable confidence")
    return Score(confidence=float(parsed["confidence"]), source="live", model=name)


def obtain_draft(
    recorded: dict[str, Any],
    *,
    question: str | None = None,
    api_key: str | None = None,
    base: str | None = None,
    model: str | None = None,
    allow_live: bool | None = None,
    timeout: float = 20.0,
) -> dict[str, Any]:
    """Return the agent's draft and say which tier produced it.

    ``recorded`` is the floor: returned unchanged and marked as such when
    nothing better is available. That is what keeps ``--replay`` byte-identical
    and the demo alive with no network — and what stops the company presenting a
    fixture as an answer to a question it never saw.
    """
    if allow_live is None:
        allow_live = os.environ.get("REPLAY_MODE", "").strip().lower() not in {"1", "true", "yes"}

    key, root, name = _config(api_key, base, model)
    if not allow_live or not question or not key or not root:
        return {**recorded, "source": "recorded"}

    try:
        content = _complete(question, key, root, name, timeout)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError, IndexError) as exc:
        print(f"model unreachable: {type(exc).__name__}", flush=True)
        return {**recorded, "source": "recorded"}

    parsed = _parse(content)
    if not parsed or not str(parsed.get("answer", "")).strip():
        print("model returned nothing usable", flush=True)
        return {**recorded, "source": "recorded"}

    confidence = parsed.get("confidence")
    if not isinstance(confidence, (int, float)) or not 0.0 <= confidence <= 1.0:
        # An answer we cannot score is an answer we must not sell on our own
        # judgement. Keep it, and be pessimistic about it.
        confidence = _heuristic(question, "").confidence

    unknowns = [str(u) for u in parsed.get("unknowns", []) if str(u).strip()][:20]
    return {
        "answer": str(parsed["answer"]).strip(),
        "confidence": float(confidence),
        "unknowns": unknowns,
        "source": "live",
        "model": name,
    }


def _parse(content: str) -> dict[str, Any] | None:
    """Pull the JSON object out. Small models wrap it in prose more often than not."""
    text = content or ""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        parsed = json.loads(text[start : end + 1])
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None
