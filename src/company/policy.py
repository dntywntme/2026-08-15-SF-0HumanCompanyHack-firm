"""The company's standing rules. No human applies these at runtime.

Two of them are load-bearing and both exist because a company that buys real
inputs can be attacked through its own cost of goods:

``REQUIRE_PAYMENT_BEFORE_COGS``
    Never commit cost of goods before revenue is secured. Without this an
    adversary submits expensive work, the agent dutifully buys human labor, and
    the company loses real money on a customer who never intended to pay. This
    is a business rule, not a content filter -- it does not care whether the
    request looked malicious.

``MAX_UNPAID_COGS_PER_CLIENT_USD`` / ``MAX_TOTAL_COGS_USD``
    Bound the blast radius when the first rule is relaxed (as it is for a live
    demo, where a judge should see work start before they pay).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal

from company.decisions import DecisionLog
from company.models import SpendDecision


def _dec(name: str, default: str) -> Decimal:
    raw = os.environ.get(name, "").strip() or default
    try:
        return Decimal(raw)
    except (ValueError, ArithmeticError):
        return Decimal(default)


def _flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    return default if not raw else raw in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Policy:
    confidence_threshold: float = 0.65
    markup: Decimal = Decimal("2.5")
    min_price_usd: Decimal = Decimal("5.00")
    max_price_usd: Decimal = Decimal("49.00")
    require_payment_before_cogs: bool = True
    max_unpaid_cogs_per_client_usd: Decimal = Decimal("5.00")
    max_total_cogs_usd: Decimal = Decimal("20.00")

    @classmethod
    def from_env(cls) -> Policy:
        return cls(
            confidence_threshold=float(os.environ.get("CONFIDENCE_THRESHOLD", "0.65")),
            markup=_dec("PRICE_MARKUP", "2.5"),
            min_price_usd=_dec("MIN_PRICE_USD", "5.00"),
            max_price_usd=_dec("MAX_PRICE_USD", "49.00"),
            require_payment_before_cogs=_flag("REQUIRE_PAYMENT_BEFORE_COGS", True),
            max_unpaid_cogs_per_client_usd=_dec("MAX_UNPAID_COGS_PER_CLIENT_USD", "5.00"),
            max_total_cogs_usd=_dec("MAX_TOTAL_COGS_USD", "20.00"),
        )


def authorize_spend(
    policy: Policy,
    *,
    requested_usd: Decimal,
    unpaid_exposure_usd: Decimal,
    paid: bool,
    log: DecisionLog | None = None,
    stage: str = "source",
) -> SpendDecision:
    """Decide whether the company may commit cost of goods right now.

    Checks run cheapest-first and the first failure wins, so the recorded reason
    is the binding constraint rather than the last one evaluated.
    """
    cap = policy.max_unpaid_cogs_per_client_usd
    projected = unpaid_exposure_usd + requested_usd

    if policy.require_payment_before_cogs and not paid:
        decision = SpendDecision(
            allowed=False,
            reason="payment not secured; policy requires revenue before cost of goods",
            requested_usd=requested_usd,
            unpaid_exposure_usd=unpaid_exposure_usd,
            cap_usd=cap,
        )
    elif projected > policy.max_total_cogs_usd:
        decision = SpendDecision(
            allowed=False,
            reason=f"total cost-of-goods cap {policy.max_total_cogs_usd} would be exceeded",
            requested_usd=requested_usd,
            unpaid_exposure_usd=unpaid_exposure_usd,
            cap_usd=policy.max_total_cogs_usd,
        )
    elif not paid and projected > cap:
        decision = SpendDecision(
            allowed=False,
            reason=f"unpaid exposure for this client would reach {projected}, cap is {cap}",
            requested_usd=requested_usd,
            unpaid_exposure_usd=unpaid_exposure_usd,
            cap_usd=cap,
        )
    else:
        decision = SpendDecision(
            allowed=True,
            reason="within policy" if paid else "unpaid, but inside the exposure cap",
            requested_usd=requested_usd,
            unpaid_exposure_usd=unpaid_exposure_usd,
            cap_usd=cap,
        )

    if log is not None:
        log.record(
            kind="buy_labor" if decision.allowed else "spend_guard",
            stage=stage,
            question=f"commit {requested_usd} USD of cost of goods?",
            chose="spend" if decision.allowed else "refuse",
            because=decision.reason,
            rejected=["refuse"] if decision.allowed else ["spend"],
            cost_usd=requested_usd if decision.allowed else Decimal("0.00"),
            reversible=not decision.allowed,
        )
    return decision
