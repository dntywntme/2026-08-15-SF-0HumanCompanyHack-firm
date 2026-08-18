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


# ── What a reply is built from ────────────────────────────────────────────────


def test_the_deliverable_is_not_in_the_final_record(tmp_path):
    """The exact shape of the bug, pinned so it cannot come back.

    ``market`` runs after ``deliver`` and returns no deliverable, so anything
    reading ``records[-1]`` finds nothing and concludes the order was refused.
    A live customer was told their fulfilled order had been rejected at intake.
    """
    result = _run(tmp_path)
    assert "deliverable" not in result.records[-1]["output"]
    assert result.emitted("deliverable")["work_order_id"] == "wo-1"


def test_emitted_finds_each_artifact_from_the_stage_that_made_it(tmp_path):
    result = _run(tmp_path)
    for key in ("deliverable", "product", "offer", "screening"):
        assert result.emitted(key), f"{key} is not reachable from the run result"


def test_a_refused_order_emits_nothing_rather_than_raising(tmp_path):
    # A halted run legitimately produces no artifacts. That is an outcome the
    # caller has to be able to render, not an error.
    result = _run(tmp_path, order={"id": "bad", "client_id": "", "question": ""})
    assert result.emitted("deliverable") is None
    assert result.emitted("product") is None
    # ...but the decisions explaining the refusal are still reachable.
    assert result.records[-1]["output"]["decisions"]


def test_an_order_asking_something_new_says_the_answer_is_recorded(tmp_path):
    """The problem a real end-to-end order exposed.

    The pipeline runs on committed fixtures so replay stays byte-identical,
    which means a customer asking something new gets the demo answer. That is
    defensible as a mechanism demo and indefensible if it is not said out loud.
    """
    order = {**DEMO_ORDER, "id": "wo-new", "question": "Which onboarding step feels clearer?"}
    result = _run(tmp_path, order=order)

    product = result.emitted("product")
    assert product["answers_question"] is False
    assert any("RECORDED DEMONSTRATION" in d for d in product["disclosures"])
    # And it is an incident, so it shows on the published page too.
    assert any(i["category"] == "recorded_answer" for i in result.state["incidents"])


def test_the_demo_order_makes_no_such_claim(tmp_path):
    product = _run(tmp_path).emitted("product")
    assert product["answers_question"] is True
    assert not any("RECORDED DEMONSTRATION" in d for d in product["disclosures"])


def test_a_caller_supplying_its_own_draft_is_answering_the_question(tmp_path):
    # A wired model would arrive this way, and must not be labelled recorded.
    order = {**DEMO_ORDER, "id": "wo-live", "question": "Anything at all?"}
    draft = {"answer": "A real answer for that question.", "confidence": 0.2, "unknowns": []}
    product = _run(tmp_path, order=order, draft=draft).emitted("product")
    assert product["answers_question"] is True


# ── The adapter boundary ──────────────────────────────────────────────────────


def test_the_guard_sees_what_the_tier_actually_charges(tmp_path, monkeypatch):
    """The spend guard was authorising one number and the run was spending another.

    It read the fixture's cost while the pipeline committed whatever the adapter
    returned, so a cost_usd of 500.00 from a human override sailed past a 27.00
    total cap and the run reported success. This is the control the README calls
    the COGS-attack defence.
    """
    override = tmp_path / "human_override.json"
    override.write_text('{"responses": ["x"], "cost_usd": "500.00", "participants": 1}')
    monkeypatch.setattr("company.adapters.terac.OVERRIDE", override)
    monkeypatch.delenv("REPLAY_MODE", raising=False)

    result = _run(tmp_path, run_id="drain")

    assert result.ok, result.error
    asked = [d for d in result.state["decisions"] if "commit" in d["question"]][0]
    assert "500.00" in asked["question"], "the guard must see the tier's number, not the fixture's"
    assert asked["chose"] == "refuse"
    assert result.state["cogs_usd"] == "0.00"


def test_a_malformed_tier_degrades_instead_of_raising(tmp_path, monkeypatch):
    # The adapter never raises, but the dict it returned was used unvalidated,
    # so a bad figure surfaced as a traceback three stages later -- after
    # checkpoints were written and the money was recorded as spent.
    override = tmp_path / "human_override.json"
    override.write_text('{"responses": ["x"], "cost_usd": "4.5678", "participants": 1}')
    monkeypatch.setattr("company.adapters.terac.OVERRIDE", override)
    monkeypatch.delenv("REPLAY_MODE", raising=False)

    result = _run(tmp_path, run_id="malformed")

    assert result.ok, result.error
    assert result.state["source_tier"] == "recorded"
    assert result.state["cogs_usd"] == "9.00"
    assert any(i["category"] == "schema_violation" for i in result.state["incidents"])
