"""Confidence scoring degrades rather than stopping the company trading."""

from __future__ import annotations

import pytest

from company.adapters.model import _parse, score_confidence


def test_no_key_degrades_to_heuristic(monkeypatch):
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
    ("content", "answer", "confidence"),
    [
        ('{"answer": "A.", "confidence": 0.31, "unknowns": ["taste"]}', "A.", 0.31),
        ('Sure! Here it is:\n{"answer": "B.", "confidence": 0.9}\nHope that helps.', "B.", 0.9),
        ('```json\n{"answer": "C.", "confidence": 0.5}\n```', "C.", 0.5),
    ],
)
def test_json_is_recovered_from_messy_model_output(content, answer, confidence):
    # Small models wrap JSON in prose more often than not. Refusing to parse
    # that would send every order to the recorded floor for no good reason.
    parsed = _parse(content)
    assert parsed["answer"] == answer
    assert parsed["confidence"] == confidence


@pytest.mark.parametrize("content", ["no json here", "", "{unterminated", "[1,2,3]"])
def test_unparsable_output_is_refused_rather_than_guessed(content):
    assert _parse(content) is None
