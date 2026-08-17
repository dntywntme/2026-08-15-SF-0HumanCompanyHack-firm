"""Human judgement, with three tiers of degradation.

The company would rather be slow than wrong, and rather be stale than stopped.
So sourcing human input falls back twice before it gives up:

1. **live** — read the study's submissions from Terac. Authoritative and current.
2. **human** — a committed override file a person can drop in when the API is
   unreachable or a study has not filled. Slower, still real judgement.
3. **recorded** — the last known-good result, replayed from disk. Never fails,
   never lies about where it came from.

Every tier stamps ``source`` onto its result, so the checkpoint and the
dashboard always say which one answered. A demo that silently falls back is a
demo that misleads; this one degrades in public.

Reading submissions costs nothing. Launching a study spends real money and is
deliberately not done here -- that decision belongs to a person, once.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Literal

from company.adapters.http import open_https

TERAC_API = "https://terac.com/api/external/v2"
OVERRIDE = Path("runs/human_override.json")

Source = Literal["terac", "human", "recorded"]


def _base() -> str:
    """The API root. Overridable so a test or a staging run can redirect it."""
    return os.environ.get("TERAC_API_BASE", "").strip().rstrip("/") or TERAC_API


def _get(path: str, key: str, timeout: float = 15.0) -> dict[str, Any]:
    # Bearer works; x-api-key returns 401 despite the docs listing both.
    req = urllib.request.Request(f"{_base()}{path}", headers={"Authorization": f"Bearer {key}"})
    # The base is environment-supplied, so the scheme is checked before opening.
    with open_https(req, timeout) as resp:
        return json.load(resp)


def _from_terac(opportunity_id: str, key: str) -> dict[str, Any] | None:
    """Tier 1. Returns None rather than raising, so the caller can degrade."""
    try:
        data = _get(f"/opportunities/{opportunity_id}/submissions", key).get("data", [])
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        print(f"terac unreachable: {type(exc).__name__}", flush=True)
        return None

    approved = [s for s in data if s.get("status") == "approved"]
    if not approved:
        return None

    # The task response is not exposed on the submissions endpoint; the screening
    # answers are. Report what the API actually gives us rather than inventing
    # the quote, and say so.
    responses = []
    for s in approved:
        answers = [a for q in s.get("screening_answers", []) for a in q.get("answer", [])]
        responses.append("; ".join(answers) if answers else "(no answer returned)")

    return {
        "opportunity_id": opportunity_id,
        "responses": responses,
        "participants": len(approved),
        "source": "terac",
        "note": "screening answers from approved submissions; task text is dashboard-only",
    }


def _from_human(path: Path | None = None) -> dict[str, Any] | None:
    """Tier 2. A person drops in judgement the API could not supply.

    ``OVERRIDE`` is resolved on each call rather than bound as a default, so the
    location is a module constant and not a value frozen at import time.
    """
    path = OVERRIDE if path is None else path
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None
    if not isinstance(payload, dict) or not payload.get("responses"):
        return None
    payload["source"] = "human"
    return payload


def obtain_human_input(
    recorded: dict[str, Any],
    *,
    opportunity_id: str | None = None,
    api_key: str | None = None,
    allow_live: bool | None = None,
) -> dict[str, Any]:
    """Return human judgement and say which tier produced it.

    ``recorded`` is the floor: it is returned unchanged, marked as such, when
    nothing better is available. That is what keeps ``--replay`` byte-identical
    and the demo alive with no network.
    """
    if allow_live is None:
        allow_live = os.environ.get("REPLAY_MODE", "").strip().lower() not in {"1", "true", "yes"}

    if allow_live:
        key = api_key if api_key is not None else os.environ.get("TERAC_API_KEY", "").strip()
        oid = opportunity_id or recorded.get("opportunity_id", "")
        if key and oid:
            live = _from_terac(oid, key)
            if live:
                live.setdefault("cost_usd", recorded.get("cost_usd", "0.00"))
                return live

        human = _from_human()
        if human:
            human.setdefault("opportunity_id", oid)
            human.setdefault("cost_usd", recorded.get("cost_usd", "0.00"))
            return human

    return {**recorded, "source": "recorded"}
