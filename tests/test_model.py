"""The draft adapter: it degrades rather than stopping the company trading.

These cover ``obtain_draft``, which is the function the pipeline calls. The
module previously tested only ``score_confidence`` -- a superseded path with no
caller in ``src/`` -- so the tested code and the running code were different
code.
"""

from __future__ import annotations

import pytest

from company.adapters.model import _heuristic_confidence, _parse, obtain_draft

RECORDED = {"answer": "the recorded answer", "confidence": 0.31, "unknowns": ["taste"]}
LIVE = '{"answer": "a live answer", "confidence": 0.8, "unknowns": ["nothing"]}'


def _live(monkeypatch, content):
    monkeypatch.setattr("company.adapters.model._complete", lambda *a, **k: content)


def test_no_key_falls_back_to_the_recorded_floor():
    out = obtain_draft(RECORDED, question="anything", api_key="", base="", allow_live=True)
    assert out["source"] == "recorded"
    assert out["answer"] == RECORDED["answer"]


def test_replay_mode_never_calls_out(monkeypatch):
    monkeypatch.setattr(
        "company.adapters.model._complete",
        lambda *a, **k: pytest.fail("replay must not reach the network"),
    )
    monkeypatch.setenv("REPLAY_MODE", "true")
    assert (
        obtain_draft(RECORDED, question="q", api_key="k", base="https://x/v1")["source"]
        == "recorded"
    )


def test_a_live_answer_is_used_and_labelled(monkeypatch):
    _live(monkeypatch, LIVE)
    out = obtain_draft(RECORDED, question="q", api_key="k", base="https://x/v1", allow_live=True)
    assert out["source"] == "live"
    assert out["answer"] == "a live answer"
    assert out["confidence"] == 0.8


@pytest.mark.parametrize("content", ["no json at all", "", '{"confidence": 0.5}'])
def test_an_unusable_response_degrades_to_the_floor(monkeypatch, content):
    # An answer we cannot read is not an answer. Falling back is the safe move;
    # shipping an empty deliverable is not.
    _live(monkeypatch, content)
    out = obtain_draft(RECORDED, question="q", api_key="k", base="https://x/v1", allow_live=True)
    assert out["source"] == "recorded"


def test_an_unreachable_model_degrades_rather_than_raising(monkeypatch):
    def boom(*a, **k):
        raise OSError("no route to host")

    monkeypatch.setattr("company.adapters.model._complete", boom)
    out = obtain_draft(RECORDED, question="q", api_key="k", base="https://x/v1", allow_live=True)
    assert out["source"] == "recorded"


def test_an_answer_we_cannot_score_is_kept_but_scored_pessimistically(monkeypatch):
    # The model answered; its confidence was unusable. Keep the answer, and be
    # pessimistic about it, because the expensive mistake is selling a guess.
    _live(monkeypatch, '{"answer": "a real answer", "confidence": 7}')
    out = obtain_draft(
        RECORDED,
        question="Which headline is more compelling?",
        api_key="k",
        base="https://x/v1",
        allow_live=True,
    )
    assert out["source"] == "live"
    assert out["answer"] == "a real answer"
    assert out["confidence"] < 0.65  # below the default buy threshold


def test_the_fallback_is_pessimistic_on_subjective_questions():
    # An unmeasurable confidence must bias toward buying help, not away from it.
    assert _heuristic_confidence("Which headline is more compelling?") < _heuristic_confidence(
        "What is the capital of France?"
    )


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
