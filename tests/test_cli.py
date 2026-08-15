from __future__ import annotations

from company.harness import main


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
