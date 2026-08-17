"""Sourcing tiers: live, human override, recorded floor.

The tier-selection branch is exactly the kind that rots silently -- it only runs
when a key is present, which is never in CI -- so all three are driven here with
a stubbed fetch.
"""

from __future__ import annotations

import json

import pytest

from company.adapters import terac
from company.adapters.http import SchemeRefused, open_https

RECORDED = {
    "opportunity_id": "rec-1",
    "responses": ["recorded answer"],
    "cost_usd": "9.00",
    "participants": 2,
}

APPROVED = {
    "data": [
        {
            "status": "approved",
            "screening_answers": [{"answer": ["B — it names the benefit"]}],
        },
        {"status": "rejected", "screening_answers": [{"answer": ["ignored"]}]},
    ]
}


def test_tier_1_reads_approved_submissions(monkeypatch):
    monkeypatch.setattr(terac, "_get", lambda path, key, timeout=15.0: APPROVED)
    out = terac.obtain_human_input(RECORDED, opportunity_id="op-1", api_key="k", allow_live=True)

    assert out["source"] == "terac"
    assert out["participants"] == 1  # the rejected submission is not judgement
    assert out["responses"] == ["B — it names the benefit"]
    # Cost carries over from the recorded floor: the API does not price it.
    assert out["cost_usd"] == "9.00"


def test_tier_2_takes_over_when_the_api_is_unreachable(monkeypatch, tmp_path):
    def boom(path, key, timeout=15.0):
        raise OSError("no route to host")

    override = tmp_path / "human_override.json"
    override.write_text(json.dumps({"responses": ["a person wrote this"]}))
    monkeypatch.setattr(terac, "_get", boom)
    monkeypatch.setattr(terac, "OVERRIDE", override)

    out = terac.obtain_human_input(RECORDED, opportunity_id="op-1", api_key="k", allow_live=True)
    assert out["source"] == "human"
    assert out["responses"] == ["a person wrote this"]
    assert out["opportunity_id"] == "op-1"


def test_tier_3_is_the_floor_and_says_so(monkeypatch, tmp_path):
    def boom(path, key, timeout=15.0):
        raise OSError("no route to host")

    monkeypatch.setattr(terac, "_get", boom)
    monkeypatch.setattr(terac, "OVERRIDE", tmp_path / "absent.json")

    out = terac.obtain_human_input(RECORDED, opportunity_id="op-1", api_key="k", allow_live=True)
    assert out["source"] == "recorded"
    assert out["responses"] == RECORDED["responses"]


def test_replay_mode_never_calls_out(monkeypatch):
    def explode(path, key, timeout=15.0):
        raise AssertionError("replay must not reach the network")

    monkeypatch.setattr(terac, "_get", explode)
    monkeypatch.setenv("REPLAY_MODE", "true")
    assert terac.obtain_human_input(RECORDED)["source"] == "recorded"


def test_an_empty_study_falls_through_rather_than_returning_nothing(monkeypatch, tmp_path):
    monkeypatch.setattr(terac, "_get", lambda path, key, timeout=15.0: {"data": []})
    monkeypatch.setattr(terac, "OVERRIDE", tmp_path / "absent.json")
    out = terac.obtain_human_input(RECORDED, opportunity_id="op-1", api_key="k", allow_live=True)
    assert out["source"] == "recorded"


def test_a_redirected_base_url_cannot_become_a_file_read(monkeypatch):
    # The base is environment-supplied, so the scheme is a runtime value.
    monkeypatch.setenv("TERAC_API_BASE", "file:///etc")
    with pytest.raises(SchemeRefused):
        terac._get("/passwd", "k")


def test_the_opener_allows_https(monkeypatch):
    import urllib.request

    seen = {}

    def fake(req, timeout):
        seen["url"] = req.full_url
        return "ok"

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    assert open_https(urllib.request.Request("https://example.com/x"), 1.0) == "ok"
    assert seen["url"] == "https://example.com/x"


def test_the_opener_refuses_plain_http():
    import urllib.request

    with pytest.raises(SchemeRefused):
        open_https(urllib.request.Request("http://example.com/x"), 1.0)
