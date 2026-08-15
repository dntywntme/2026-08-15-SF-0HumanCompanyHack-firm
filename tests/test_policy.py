"""The standing rules, and the record of applying them."""

from __future__ import annotations

import json
from decimal import Decimal

import pytest
from pydantic import ValidationError

from company.decisions import Decision, DecisionLog
from company.policy import Policy, authorize_spend

ZERO = Decimal("0.00")


def test_a_decision_must_name_what_it_rejected():
    # A decision with one option is not a decision, and a log that hides the
    # rejected branch cannot be audited. Enforced by the contract.
    with pytest.raises(ValidationError):
        Decision(
            kind="set_price",
            stage="price",
            question="what to charge?",
            chose="39.00",
            because="markup on cost of goods",
            rejected=[],
        )


def test_the_cogs_attack_is_refused():
    # Expensive work ordered by someone who never intends to pay: the defence is
    # a business rule, not a content filter.
    d = authorize_spend(
        Policy(), requested_usd=Decimal("22.50"), unpaid_exposure_usd=ZERO, paid=False
    )
    assert not d.allowed
    assert "payment not secured" in d.reason


def test_spend_is_allowed_once_revenue_is_secured():
    d = authorize_spend(
        Policy(), requested_usd=Decimal("18.00"), unpaid_exposure_usd=ZERO, paid=True
    )
    assert d.allowed


def test_relaxing_the_guard_still_leaves_a_cap():
    # The demo relaxes payment-first so a judge sees work start before paying.
    # The blast radius must still be bounded.
    relaxed = Policy(require_payment_before_cogs=False)
    d = authorize_spend(
        relaxed, requested_usd=Decimal("22.50"), unpaid_exposure_usd=ZERO, paid=False
    )
    assert not d.allowed
    assert "cap" in d.reason


def test_per_client_exposure_cap_binds_before_the_total():
    relaxed = Policy(require_payment_before_cogs=False)
    d = authorize_spend(
        relaxed, requested_usd=Decimal("4.50"), unpaid_exposure_usd=Decimal("4.50"), paid=False
    )
    assert not d.allowed
    assert "unpaid exposure" in d.reason


def test_a_refused_spend_costs_nothing_and_stays_reversible():
    log = DecisionLog()
    authorize_spend(
        Policy(), requested_usd=Decimal("22.50"), unpaid_exposure_usd=ZERO, paid=False, log=log
    )
    (d,) = log.payload()
    assert d["kind"] == "spend_guard"
    assert d["cost_usd"] == "0.00"
    assert d["reversible"] is True
    assert log.spent_usd == ZERO


def test_committing_money_is_recorded_as_irreversible():
    log = DecisionLog()
    authorize_spend(
        Policy(), requested_usd=Decimal("18.00"), unpaid_exposure_usd=ZERO, paid=True, log=log
    )
    assert log.spent_usd == Decimal("18.00")
    assert [d.kind for d in log.irreversible] == ["buy_labor"]


def test_the_log_is_checkpointable_and_stable():
    log = DecisionLog()
    log.record(
        kind="pay_worker",
        stage="verify",
        question="approve submission sub-1?",
        chose="approve",
        because="answer is on-topic and gives a reason",
        rejected=["reject", "request another response"],
        cost_usd=Decimal("4.50"),
        reversible=False,
    )
    once = json.dumps(log.payload(), sort_keys=True)
    assert once == json.dumps(log.payload(), sort_keys=True)
    assert '"cost_usd": "4.50"' in once  # exact string, not a float


def test_policy_reads_env_and_survives_garbage(monkeypatch):
    monkeypatch.setenv("MAX_TOTAL_COGS_USD", "not-a-number")
    monkeypatch.setenv("PRICE_MARKUP", "3.0")
    monkeypatch.setenv("REQUIRE_PAYMENT_BEFORE_COGS", "false")
    p = Policy.from_env()
    assert p.markup == Decimal("3.0")
    assert p.require_payment_before_cogs is False
    assert p.max_total_cogs_usd == Decimal("27.00")  # fell back, did not crash
