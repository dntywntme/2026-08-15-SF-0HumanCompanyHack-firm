"""The compliance gate: what we refuse to sell, and what we refuse to forward."""

from __future__ import annotations

import pytest

from company.compliance import (
    BASE_DISCLOSURES,
    PRIVACY_ID,
    TERMS_ID,
    obligations,
    redact,
    screen,
)

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


# ── Where the customer is ─────────────────────────────────────────────────────


def test_every_deliverable_names_the_terms_it_was_sold_under():
    s = screen(DEMO_QUESTION)
    assert s.terms_id == TERMS_ID and s.privacy_id == PRIVACY_ID
    assert any(TERMS_ID in d for d in s.disclosures)


def test_a_stated_jurisdiction_gets_its_own_notices():
    eu = screen(DEMO_QUESTION, jurisdiction="eu")
    assert eu.jurisdiction == "eu"
    assert any("GDPR" in d for d in eu.disclosures)
    assert not any("CCPA" in d for d in eu.disclosures)


def test_an_unstated_jurisdiction_gets_the_strictest_set():
    # Not knowing where a customer is, is not a reason to give them fewer
    # rights. The union is the safe default, not the empty set.
    unknown = screen(DEMO_QUESTION).disclosures
    assert any("GDPR" in d for d in unknown)
    assert any("CCPA" in d for d in unknown)


def test_an_unrecognised_jurisdiction_degrades_to_the_strictest_set():
    assert screen(DEMO_QUESTION, jurisdiction="zz").disclosures == screen(DEMO_QUESTION).disclosures


def test_nobody_is_refused_for_where_they_live():
    # Refusing a customer for their address is a decision this company has no
    # basis to make; jurisdiction only adds notices.
    for where in ("eu", "uk", "us", "us-ca", "unspecified", "zz"):
        assert screen(DEMO_QUESTION, jurisdiction=where).cleared


def test_obligations_are_ordered_and_deduplicated():
    # They land in a checkpoint, so set iteration order would break replay.
    assert obligations("zz") == obligations("zz")
    assert len(obligations("zz")) == len(set(obligations("zz")))
