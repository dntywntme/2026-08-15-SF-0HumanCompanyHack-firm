from __future__ import annotations

import io
import json
import time

import pytest

from company.harness import (
    RunContext,
    Stage,
    checkpoint_path,
    load_checkpoints,
    replay,
    run_pipeline,
)
from company.stages import PIPELINE


def _recorder(name: str, log: list[str]) -> Stage:
    def fn(ctx: RunContext, state: dict) -> dict:
        log.append(name)
        return {name: True, "seen": len(log)}

    return Stage(name, fn)


def test_stages_run_in_order(tmp_path):
    log: list[str] = []
    stages = [_recorder(n, log) for n in ("alpha", "beta", "gamma")]
    result = run_pipeline(stages, "r1", runs_dir=tmp_path, out=io.StringIO())

    assert result.ok, result.error
    assert log == ["alpha", "beta", "gamma"]
    assert [r["stage"] for r in result.records] == ["alpha", "beta", "gamma"]
    assert [r["index"] for r in result.records] == [0, 1, 2]


def test_state_flows_through_the_real_pipeline(tmp_path):
    result = run_pipeline(
        PIPELINE,
        "r-real",
        runs_dir=tmp_path,
        initial_state={"brief": "make it go"},
        out=io.StringIO(),
    )
    assert result.ok, result.error
    assert result.state["item_count"] == 3
    assert result.state["artifact"] == "make-it-go"
    assert result.turns_used == 3


def test_turn_cap_trips(tmp_path):
    log: list[str] = []
    stages = [_recorder(n, log) for n in ("alpha", "beta", "gamma")]
    result = run_pipeline(stages, "r2", runs_dir=tmp_path, max_turns=2, out=io.StringIO())

    assert not result.ok
    assert "MaxTurnsExceeded" in result.error
    # The third stage never executed and never checkpointed.
    assert log == ["alpha", "beta"]
    assert result.turns_used == 2
    assert checkpoint_path(tmp_path, "r2", 1, "beta").exists()
    assert not checkpoint_path(tmp_path, "r2", 2, "gamma").exists()


def test_turn_cap_also_trips_on_extra_spend_inside_a_stage(tmp_path):
    def greedy(ctx: RunContext, state: dict) -> dict:
        ctx.spend_turn(5)
        return {"never": "reached"}

    result = run_pipeline(
        [Stage("greedy", greedy)], "r3", runs_dir=tmp_path, max_turns=3, out=io.StringIO()
    )
    assert not result.ok
    assert "MaxTurnsExceeded" in result.error


def test_wall_clock_timeout_trips(tmp_path):
    def slow(ctx: RunContext, state: dict) -> dict:
        time.sleep(5)
        return {"slow": True}

    started = time.monotonic()
    result = run_pipeline(
        [Stage("slow", slow)], "r4", runs_dir=tmp_path, stage_timeout=0.2, out=io.StringIO()
    )
    elapsed = time.monotonic() - started

    assert not result.ok
    assert "StageTimeout" in result.error
    # The harness returned promptly rather than waiting out the stage.
    assert elapsed < 3
    assert not checkpoint_path(tmp_path, "r4", 0, "slow").exists()


def test_checkpoints_are_written(tmp_path):
    run_pipeline(PIPELINE, "r5", runs_dir=tmp_path, out=io.StringIO())

    names = sorted(p.name for p in (tmp_path / "r5").iterdir())
    assert names == [
        "00-intake.json",
        "00-intake.timing.json",
        "01-process.json",
        "01-process.timing.json",
        "02-deliver.json",
        "02-deliver.timing.json",
    ]
    payload = json.loads(checkpoint_path(tmp_path, "r5", 0, "intake").read_text())
    assert payload["stage"] == "intake"
    assert payload["run_id"] == "r5"
    assert payload["output"]["item_count"] == 5

    records = load_checkpoints("r5", runs_dir=tmp_path)
    assert [r["stage"] for r in records] == ["intake", "process", "deliver"]


def test_replay_reproduces_a_prior_run_byte_identically(tmp_path):
    live = io.StringIO()
    result = run_pipeline(
        PIPELINE, "r6", runs_dir=tmp_path, out=live, initial_state={"brief": "a b c"}
    )
    assert result.ok, result.error

    replayed = io.StringIO()
    replay_result = replay("r6", runs_dir=tmp_path, out=replayed)

    assert replayed.getvalue() == live.getvalue()
    assert replayed.getvalue() != ""
    assert replay_result.state == result.state


def test_replay_is_stable_across_repeats(tmp_path):
    run_pipeline(PIPELINE, "r7", runs_dir=tmp_path, out=io.StringIO())
    first = io.StringIO()
    second = io.StringIO()
    replay("r7", runs_dir=tmp_path, out=first)
    replay("r7", runs_dir=tmp_path, out=second)
    assert first.getvalue() == second.getvalue()


def test_replay_of_unknown_run_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        replay("nope", runs_dir=tmp_path, out=io.StringIO())


def test_non_dict_stage_output_is_rejected(tmp_path):
    bad = Stage("bad", lambda ctx, state: "not a dict")
    result = run_pipeline([bad], "r8", runs_dir=tmp_path, out=io.StringIO())
    assert not result.ok
    assert "TypeError" in result.error
