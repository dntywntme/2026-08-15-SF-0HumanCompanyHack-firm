#!/usr/bin/env python3
"""Poll Stripe for settled revenue and write the ledger the dashboard renders.

This runs server-side (GitHub Actions), never in the browser. The dashboard is a
static page on GitHub Pages, so it can hold no credentials: the restricted key
lives here as a repository secret and only its aggregate output is published.

Degrades instead of raising. A missing key, a network failure or a Stripe error
all produce a ledger marked ``"source": "unavailable"`` rather than a traceback,
because a dead poller must never take the demo page down with it.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from decimal import Decimal
from pathlib import Path

STRIPE_API = "https://api.stripe.com/v1"
OUT = Path("runs/ledger.json")


def _get(path: str, key: str, timeout: float = 10.0) -> dict:
    req = urllib.request.Request(f"{STRIPE_API}{path}", headers={"Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def fetch_charges(key: str, limit: int = 25) -> tuple[list[dict], str]:
    """Return (charges, source). Never raises."""
    try:
        data = _get(f"/charges?limit={limit}", key).get("data", [])
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
        print(f"stripe unavailable: {type(exc).__name__}", file=sys.stderr)
        return [], "unavailable"
    return data, "stripe"


def summarize(charges: list[dict]) -> dict:
    """Aggregate charges into the numbers the P&L panel shows.

    Amounts are minor units (cents) from Stripe, converted with Decimal so the
    published figures are exact.
    """
    captured = [c for c in charges if c.get("status") == "succeeded" and c.get("captured")]
    failed = [c for c in charges if c.get("status") == "failed"]
    refunded = [c for c in charges if c.get("refunded")]

    gross = sum((Decimal(c.get("amount", 0)) for c in captured), Decimal(0)) / 100
    refunds = sum((Decimal(c.get("amount_refunded", 0)) for c in charges), Decimal(0)) / 100

    return {
        "revenue_usd": str((gross - refunds).quantize(Decimal("0.01"))),
        "transactions": len(captured),
        "failed": len(failed),
        "refunded": len(refunded),
        # Per-charge detail, deliberately minimal: no customer identifiers, no
        # card data, nothing that should not be on a public page.
        "recent": [
            {
                "amount_usd": str((Decimal(c.get("amount", 0)) / 100).quantize(Decimal("0.01"))),
                "status": c.get("status", ""),
                "livemode": bool(c.get("livemode")),
            }
            for c in charges[:10]
        ],
    }


def main() -> int:
    key = os.environ.get("STRIPE_RESTRICTED_KEY", "").strip()
    # An unset secret arrives as the empty string; a bare prefix is a half-filled
    # placeholder. Treat both as "no key" and degrade rather than calling Stripe
    # with something that cannot work.
    if not key or key in {"rk_live_", "rk_test_", "rk_"}:
        print("no restricted key configured; writing empty ledger", file=sys.stderr)
        charges, source = [], "unavailable"
    else:
        charges, source = fetch_charges(key)

    ledger = {"source": source, **summarize(charges)}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT}: {ledger['transactions']} txn, {ledger['revenue_usd']} USD ({source})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
