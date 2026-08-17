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
from company.harness import Stage as _Stage

# The harness must be testable independently of whatever business pipeline is
# wired in, so these tests drive their own stages rather than the real six.
PIPELINE = [
    _Stage("intake", lambda ctx, s: {"items": (s.get("brief") or "").split()}),
    _Stage("process", lambda ctx, s: {"item_count": len(s.get("items", []))}),
    _Stage("deliver", lambda ctx, s: {"artifact": "-".join(s.get("items", []))}),
]


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
        "index.json",
    ]
    payload = json.loads(checkpoint_path(tmp_path, "r5", 0, "intake").read_text())
    assert payload["stage"] == "intake"
    assert payload["run_id"] == "r5"
    assert payload["output"]["items"] == []  # no brief was supplied

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
    # Replay rebuilds state from checkpoints alone, so it carries what the
    # stages produced but not what the caller seeded.
    assert {k: v for k, v in result.state.items() if k != "brief"} == replay_result.state


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


def test_the_manifest_lists_what_the_run_produced(tmp_path):
    run_pipeline(PIPELINE, "r9", runs_dir=tmp_path, out=io.StringIO())
    manifest = json.loads((tmp_path / "r9" / "index.json").read_text())
    assert manifest == {"stages": ["00-intake", "01-process", "02-deliver"]}


def test_a_partial_run_still_publishes_an_honest_manifest(tmp_path):
    log: list[str] = []
    stages = [_recorder(n, log) for n in ("alpha", "beta", "gamma")]
    run_pipeline(stages, "r10", runs_dir=tmp_path, max_turns=2, out=io.StringIO())
    manifest = json.loads((tmp_path / "r10" / "index.json").read_text())
    # gamma never ran, so the dashboard must not be told to fetch it.
    assert manifest == {"stages": ["00-alpha", "01-beta"]}


def test_stray_json_in_a_run_directory_is_not_a_checkpoint(tmp_path):
    # The regression this exists for: the dashboard's manifest was globbed in as
    # a checkpoint and replay died on KeyError: 'output'. Anything that is not a
    # NN-stage.json record has to be ignored, not parsed.
    run_pipeline(PIPELINE, "r11", runs_dir=tmp_path, out=io.StringIO())
    (tmp_path / "r11" / "notes.json").write_text('{"not": "a checkpoint"}')
    (tmp_path / "r11" / "human_override.json").write_text('{"responses": ["x"]}')

    records = load_checkpoints("r11", runs_dir=tmp_path)
    assert [r["stage"] for r in records] == ["intake", "process", "deliver"]
    replay("r11", runs_dir=tmp_path, out=io.StringIO())  # must not raise


def test_non_dict_stage_output_is_rejected(tmp_path):
    bad = Stage("bad", lambda ctx, state: "not a dict")
    result = run_pipeline([bad], "r8", runs_dir=tmp_path, out=io.StringIO())
    assert not result.ok
    assert "TypeError" in result.error
