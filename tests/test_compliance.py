"""The compliance gate: what we refuse to sell, and what we refuse to forward."""

from __future__ import annotations

import pytest

from company.compliance import BASE_DISCLOSURES, redact, screen

DEMO_QUESTION = (
    "Which headline is more compelling: 'Ship faster with AI' or "
    "'Your on-call engineer that never sleeps'?"
)


def test_opinion_research_clears():
    s = screen(DEMO_QUESTION)
    assert s.cleared
    assert s.refused_rule == ""
    assert s.safe_question == DEMO_QUESTION


@pytest.mark.parametrize(
    ("question", "rule"),
    [
        ("Is a 2-year non-compete enforceable in California?", "legal_advice"),
        ("Have a licensed attorney review this 40-page contract in detail.", "legal_advice"),
        ("What dosage of ibuprofen should I take for this?", "medical_advice"),
        ("Should I buy NVDA before earnings?", "financial_advice"),
    ],
)
def test_regulated_advice_is_refused(question, rule):
    s = screen(question)
    assert not s.cleared
    assert s.refused_rule == rule
    # The reason is published to the customer, so it has to read like a reason.
    assert "Broker" in s.refused_because


def test_a_refusal_still_carries_its_disclosures():
    # A refused order is still a decision we have to be able to show.
    s = screen("Is this clause legally binding?")
    assert not s.cleared
    assert BASE_DISCLOSURES[0] in s.disclosures


def test_personal_data_never_reaches_the_panel():
    q = "Ask them to email me at ada@example.com or call +1 415 555 0134."
    safe, found = redact(q)
    assert "ada@example.com" not in safe
    assert "555" not in safe
    assert sorted(found) == ["email", "phone"]


def test_redaction_is_recorded_on_the_screening():
    s = screen("Which logo do people prefer? Reply to ada@example.com")
    assert s.cleared  # redacted, not refused: the question itself is fine
    assert s.redactions == ["email"]
    assert "ada@example.com" not in s.safe_question


def test_the_sourcing_disclosure_follows_the_sourcing():
    bought = screen(DEMO_QUESTION, escalating=True).disclosures
    alone = screen(DEMO_QUESTION, escalating=False).disclosures
    assert any("Terac" in d for d in bought)
    assert not any("Terac" in d for d in alone)
    assert any("agent alone" in d for d in alone)


def test_screening_is_deterministic():
    # It lands in a checkpoint that --replay must reproduce byte for byte.
    assert screen(DEMO_QUESTION).payload() == screen(DEMO_QUESTION).payload()
