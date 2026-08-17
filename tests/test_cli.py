from __future__ import annotations

import pytest

from company.harness import main

# Every variable that could make a live run diverge from the recorded one.
LIVE_KEYS = ("TERAC_API_KEY", "TERAC_API_BASE", "STRIPE_RESTRICTED_KEY", "PIONEER_API_KEY")


@pytest.fixture
def no_credentials(monkeypatch):
    """A fresh clone: no keys, nothing to call out to."""
    for key in LIVE_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("REPLAY_MODE", "true")


def test_run_and_replay_are_byte_identical_on_a_fresh_clone(tmp_path, capsys, no_credentials):
    """The README's headline claim, asserted rather than diffed by hand.

    This is the one that has broken twice: a manifest file globbed in as a
    checkpoint, and a sourcing tier that answered differently depending on which
    keys happened to be present. Both were invisible to every other test.
    """
    assert main(["--run-id", "fresh", "--runs-dir", str(tmp_path)]) == 0
    live = capsys.readouterr().out

    assert main(["--replay", "fresh", "--runs-dir", str(tmp_path)]) == 0
    replayed = capsys.readouterr().out

    assert replayed == live
    assert live.count("\n") == 9  # one line per stage, all nine of them


def test_cli_run_then_replay_match(tmp_path, capsys):
    argv = ["--run-id", "cli1", "--runs-dir", str(tmp_path)]
    assert main(argv) == 0
    live = capsys.readouterr().out

    assert main(["--replay", "cli1", "--runs-dir", str(tmp_path)]) == 0
    replayed = capsys.readouterr().out

    assert live == replayed
    assert live.strip() != ""


def test_cli_replay_missing_run_exits_nonzero(tmp_path, capsys):
    assert main(["--replay", "ghost", "--runs-dir", str(tmp_path)]) == 2
    assert "replay failed" in capsys.readouterr().err


def test_cli_turn_cap_exits_nonzero(tmp_path, capsys):
    code = main(["--run-id", "cli2", "--runs-dir", str(tmp_path), "--max-turns", "1"])
    assert code == 1
    assert "MaxTurnsExceeded" in capsys.readouterr().err
