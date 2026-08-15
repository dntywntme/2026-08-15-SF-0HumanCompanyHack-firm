"""Confidence scoring degrades rather than stopping the company trading."""

from __future__ import annotations

import pytest

from company.adapters.pioneer import Score, _parse, score_confidence


def test_no_key_degrades_to_heuristic(monkeypatch):
    monkeypatch.delenv("PIONEER_API_KEY", raising=False)
    s = score_confidence("Which headline is more compelling?", api_key="")
    assert s.source == "heuristic"
    assert "not set" in s.note


def test_the_fallback_is_pessimistic_on_subjective_questions():
    # The expensive mistake is answering confidently from ignorance, so an
    # unmeasurable confidence must bias toward buying help, not away from it.
    subjective = score_confidence("Which headline is more compelling?", api_key="")
    factual = score_confidence("What is the capital of France?", api_key="")
    assert subjective.confidence < factual.confidence
    assert subjective.confidence < 0.65  # below the default buy threshold


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ('{"confidence": 0.31}', 0.31),
        ('Sure! Here is the result:\n{"confidence":0.9}\nHope that helps.', 0.9),
        ("I would say 0.42 confident.", 0.42),
    ],
)
def test_parses_a_number_out_of_messy_model_output(content, expected):
    # Small models wrap JSON in prose more often than not.
    s = _parse(content, "q", "m")
    assert s.source == "pioneer" and s.confidence == expected


@pytest.mark.parametrize("content", ["no number here", "", "confidence: 4.2"])
def test_unparsable_output_falls_back_rather_than_guessing(content):
    s = _parse(content, "Which is better?", "m")
    assert s.source == "heuristic"


def test_score_is_always_in_range():
    for q in ["", "a" * 500, "Which one?"]:
        s = score_confidence(q, api_key="")
        assert isinstance(s, Score) and 0.0 <= s.confidence <= 1.0
