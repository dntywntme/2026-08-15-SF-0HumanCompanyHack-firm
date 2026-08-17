"""The published surface: what the site says, and what it cannot contradict.

Three claims are checked here because each one has already cost something when
it drifted: the terms id on a deliverable must name a document that exists, the
machine-readable offer must describe the contract the pipeline actually
enforces, and the site must never carry a credential.
"""

from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path

import pytest

from company.compliance import POLICY_VERSION, PRIVACY_ID, TERMS_ID
from company.harness import run_pipeline
from company.models import WorkOrder
from company.stages import ORDER_SCHEMA, PIPELINE, initial_state

REPO = Path(__file__).resolve().parent.parent


def _load_build_site():
    """Load the script by path: it is not part of the installed package.

    scripts/ is deliberately importless -- the ledger job runs it with a bare
    interpreter and no `uv sync` -- so the tests reach it the same way the shell
    does, by file.
    """
    spec = importlib.util.spec_from_file_location("build_site", REPO / "scripts/build_site.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


build_site = _load_build_site()
build, latest_offer = build_site.build, build_site.latest_offer


def test_the_terms_the_deliverable_cites_actually_exist():
    # A deliverable that references broker-terms-X is worthless if the page
    # publishes broker-terms-Y. This is the whole point of versioning them.
    legal = (REPO / "web" / "legal.html").read_text(encoding="utf-8")
    assert TERMS_ID in legal, f"{TERMS_ID} is cited on deliverables but not published"
    assert PRIVACY_ID in legal
    assert POLICY_VERSION in legal


def test_the_terms_admit_what_they_are():
    # The one thing this page must never do is read like counsel wrote it.
    legal = (REPO / "web" / "legal.html").read_text(encoding="utf-8").lower()
    assert "not an incorporated entity" in legal
    assert "not reviewed by a lawyer" in legal
    assert "sandbox" in legal


def test_the_advertised_schema_matches_the_contract_we_enforce():
    # ORDER_SCHEMA is hand-written so that a pydantic upgrade cannot change the
    # bytes of a committed run. This is the drift protection that buys back.
    assert set(ORDER_SCHEMA) == set(WorkOrder.model_fields)


def test_the_published_offer_comes_from_the_run(tmp_path, monkeypatch):
    monkeypatch.setenv("REPLAY_MODE", "true")
    monkeypatch.chdir(tmp_path)
    (tmp_path / "web").mkdir()
    (tmp_path / "web" / "index.html").write_text("<!doctype html>ok")

    run_pipeline(
        PIPELINE,
        "demo",
        runs_dir=tmp_path / "runs",
        initial_state=initial_state(),
        out=io.StringIO(),
    )
    assert build(tmp_path / "_site", "demo") == 0

    # /offer.json is the address we advertise; Pages will not serve the
    # dot-prefixed one. Both are written, and both have to stay in step.
    canonical = (tmp_path / "_site" / "offer.json").read_text()
    assert canonical == (tmp_path / "_site" / ".well-known" / "offer.json").read_text()

    offer = json.loads(canonical)
    assert offer["run_id"] == "demo"
    assert offer["terms_id"] == TERMS_ID
    assert set(offer["order_schema"]) == set(WorkOrder.model_fields)
    # The proof line is the run's own arithmetic, not a claim about it.
    assert offer["unit_cost_usd"] == "9.00"


def test_a_refused_order_advertises_nothing(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("REPLAY_MODE", "true")
    monkeypatch.chdir(tmp_path)
    (tmp_path / "web").mkdir()
    (tmp_path / "web" / "index.html").write_text("<!doctype html>ok")

    refused = {
        "id": "wo-legal",
        "client_id": "c",
        "question": "Is a 2-year non-compete enforceable in California?",
        "budget_usd": "1.00",
    }
    run_pipeline(
        PIPELINE,
        "refused",
        runs_dir=tmp_path / "runs",
        initial_state=initial_state(order=refused),
        out=io.StringIO(),
    )
    assert build(tmp_path / "_site", "refused") == 0
    # A company that refused the order has nothing to advertise from it, and the
    # job log has to say so rather than skipping quietly.
    assert not (tmp_path / "_site" / "offer.json").exists()
    assert not (tmp_path / "_site" / ".well-known" / "offer.json").exists()
    assert "published no offer" in capsys.readouterr().err


def test_a_run_that_never_happened_is_not_an_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "web").mkdir()
    (tmp_path / "web" / "index.html").write_text("<!doctype html>ok")
    assert build(tmp_path / "_site", "ghost") == 0
    assert latest_offer(tmp_path / "runs" / "ghost") is None


def test_a_site_without_an_index_fails_loudly(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert build(tmp_path / "_site", "demo") == 1


@pytest.mark.parametrize("page", ["index.html", "legal.html"])
def test_no_page_carries_a_credential(page):
    # The site is static and public. Any key on it is a key that has leaked.
    text = (REPO / "web" / page).read_text(encoding="utf-8")
    for prefix in ("sk_test_", "sk_live_", "rk_test_", "rk_live_", "ghp_", "tk_"):
        assert prefix not in text, f"{page} carries something shaped like a {prefix} key"


def test_every_knob_the_code_reads_is_in_the_env_template():
    # The direction that has actually broken: a variable the code consults and
    # the template never mentions is a trap for whoever deploys this next.
    template = (REPO / ".env.example").read_text(encoding="utf-8")
    sources = [p for p in (REPO / "src").rglob("*.py")] + list((REPO / "scripts").glob("*.py"))
    read = set()
    for path in sources:
        for line in path.read_text(encoding="utf-8").splitlines():
            if "os.environ.get(" in line:
                name = line.split("os.environ.get(", 1)[1].strip()[1:].split('"')[0].split("'")[0]
                if name.isupper():
                    read.add(name)
    assert read, "sanity: the code should read at least one documented knob"
    missing = sorted(name for name in read if name not in template)
    assert not missing, f"read by the code, absent from .env.example: {missing}"
