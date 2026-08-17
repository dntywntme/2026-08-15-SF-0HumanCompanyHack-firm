"""The company as a whole: what a full turn of work produces, and what stops it.

These drive the real ``PIPELINE`` rather than a toy one, because the claims
being checked are business claims -- an order we may not sell costs nothing, a
malformed order costs nothing, and the thing we ship carries its own before and
after.
"""

from __future__ import annotations

import io
from decimal import Decimal

import pytest

from company.harness import run_pipeline
from company.stages import DEMO_ORDER, PIPELINE, initial_state


def _run(tmp_path, run_id="t", **overrides):
    return run_pipeline(
        PIPELINE,
        run_id,
        runs_dir=tmp_path,
        initial_state=initial_state(**overrides),
        out=io.StringIO(),
    )


@pytest.fixture(autouse=True)
def recorded_only(monkeypatch):
    """No live sourcing in tests: the recorded tier is the assertion surface."""
    monkeypatch.setenv("REPLAY_MODE", "true")


def test_a_full_turn_of_work_covers_every_company_function(tmp_path):
    result = _run(tmp_path)
    assert result.ok, result.error
    assert [r["stage"] for r in result.records] == [
        "intake",
        "comply",
        "triage",
        "source",
        "verify",
        "build",
        "price",
        "deliver",
        "market",
    ]
    # Eleven turns: nine stages, plus the model call in triage and the purchase
    # in source. The default cap has to sit above that or success trips it.
    assert result.turns_used == 11


def test_the_product_carries_its_own_before_and_after(tmp_path):
    product = _run(tmp_path).state["product"]
    assert product["before"] != product["after"]
    assert product["changed"] is True
    assert product["before_confidence"] == pytest.approx(0.31)
    # The panel's own words are what the customer is buying.
    assert len(product["evidence"]) == 2
    assert product["disclosures"]


def test_an_answer_the_agent_was_confident_about_reports_no_change(tmp_path):
    confident = {"answer": "42.", "confidence": 0.95, "unknowns": []}
    product = _run(tmp_path, draft=confident).state["product"]
    assert product["changed"] is False
    assert product["before"] == product["after"]
    assert product["evidence"] == []


def test_the_offer_quotes_the_run_rather_than_a_claim(tmp_path):
    state = _run(tmp_path).state
    offer = state["offer"]
    assert Decimal(offer["price_usd"]) == Decimal(state["price_usd"])
    assert Decimal(offer["unit_cost_usd"]) == Decimal(state["cogs_usd"])
    # Outbound that never declines a channel is a spam function.
    assert offer["declined_channels"]
    assert offer["channel"] == "issue-thread"


def test_an_order_we_may_not_sell_costs_nothing(tmp_path):
    order = {**DEMO_ORDER, "question": "Is a 2-year non-compete enforceable in California?"}
    result = _run(tmp_path, order=order)

    assert result.ok, result.error  # a refusal is an outcome, not a crash
    assert result.state["cleared"] is False
    # Nothing downstream ran: no draft, no purchase, no deliverable.
    assert "product" not in result.state
    assert "deliverable" not in result.state
    assert result.state.get("cogs_usd") is None
    spent = sum(Decimal(d["cost_usd"]) for d in result.state["decisions"])
    assert spent == Decimal("0.00")


def test_a_malformed_order_never_reaches_procurement(tmp_path):
    # The regression this exists for: a rejected work order used to draft an
    # answer, buy human judgement and produce a priced deliverable anyway.
    result = _run(tmp_path, order={"id": "atk 6 with spaces", "client_id": "", "question": ""})

    assert result.ok, result.error
    assert result.state["accepted"] is False
    assert "deliverable" not in result.state
    spent = sum(Decimal(d["cost_usd"]) for d in result.state["decisions"])
    assert spent == Decimal("0.00")
    assert any(i["category"] == "schema_violation" for i in result.state["incidents"])


def test_every_stage_after_a_refusal_still_checkpoints(tmp_path):
    # A skipped stage is recorded as skipped rather than missing, so the
    # published run shows the whole company deciding not to act.
    result = _run(tmp_path, order={"id": "bad", "client_id": "", "question": ""})
    skipped = [r["output"].get("skipped_because") for r in result.records[1:]]
    assert all(skipped), skipped


def test_an_unpaid_order_buys_nothing(tmp_path):
    result = _run(tmp_path, paid=False)
    assert result.ok, result.error
    assert result.state["human"] is None
    assert result.state["cogs_usd"] == "0.00"
    assert any(d["kind"] == "spend_guard" for d in result.state["decisions"])
    # It still ships: the agent's own draft, priced at the floor.
    assert result.state["deliverable"]["sourced_from"] == "agent"
