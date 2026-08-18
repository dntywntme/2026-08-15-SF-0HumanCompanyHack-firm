"""Deterministic pipeline runner.

The spine of the company: an ordered list of stages, executed one at a time,
under a hard global turn cap and a per-stage wall-clock timeout. Every stage
result is checkpointed to ``runs/<run_id>/<NN>-<stage>.json`` so that a run can
later be replayed from disk without calling anything live.

Replay is the demo fallback: ``--replay <run_id>`` re-emits the checkpointed
results byte-for-byte identically to what the live run emitted.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_RUNS_DIR = Path("runs")
# Nine stages, two of which spend a second turn on inner work, so a clean run
# costs eleven. The cap is the runaway guard, not a target: it has to sit above
# the honest cost of the pipeline or it fires on success.
DEFAULT_MAX_TURNS = 16
DEFAULT_STAGE_TIMEOUT = 30.0
# The dashboard reads this rather than guessing checkpoint filenames: probing
# names that do not exist fills a judge's console with 404s.
MANIFEST_NAME = "index.json"

# A stage is a pure-ish function: (ctx, state) -> dict. It must be deterministic
# given the same inputs, otherwise replay cannot reproduce it.
StageFn = Callable[["RunContext", dict[str, Any]], dict[str, Any]]


class HarnessError(RuntimeError):
    """Base class for harness control-flow failures."""


class MaxTurnsExceeded(HarnessError):
    """The global turn budget was exhausted."""


class StageTimeout(HarnessError):
    """A stage exceeded its wall-clock budget."""


@dataclass(frozen=True)
class Stage:
    name: str
    run: StageFn


@dataclass
class RunContext:
    """Handed to each stage. Carries the turn budget and the run identity."""

    run_id: str
    max_turns: int
    turns_used: int = 0
    stage_name: str = ""

    def spend_turn(self, n: int = 1) -> int:
        """Consume ``n`` turns. Raises MaxTurnsExceeded when the budget is gone."""
        if self.turns_used + n > self.max_turns:
            raise MaxTurnsExceeded(
                f"turn cap {self.max_turns} exceeded at stage {self.stage_name!r} "
                f"(used {self.turns_used}, requested {n})"
            )
        self.turns_used += n
        return self.turns_used


@dataclass
class RunResult:
    run_id: str
    records: list[dict[str, Any]] = field(default_factory=list)
    state: dict[str, Any] = field(default_factory=dict)
    turns_used: int = 0
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None

    def emitted(self, key: str) -> Any:
        """Find what a run produced, from whichever stage produced it.

        Reading the last checkpoint is the obvious thing and it is wrong: state
        accumulates across stages but each *record* holds only what its own
        stage returned. Adding a stage after ``deliver`` therefore moved the
        deliverable out of the final record, and a reply built from
        ``records[-1]`` told a paying customer their fulfilled order had been
        "rejected at intake".

        Returns the first truthy value found in stage order, or None. A halted
        run legitimately produces nothing, which is not an error.
        """
        for record in self.records:
            value = record.get("output", {}).get(key)
            if value:
                return value
        return None


def checkpoint_path(runs_dir: Path, run_id: str, index: int, stage_name: str) -> Path:
    return runs_dir / run_id / f"{index:02d}-{stage_name}.json"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # sort_keys + fixed separators: the on-disk bytes must be reproducible.
    path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _write_manifest(runs_dir: Path, run_id: str, stems: list[str]) -> None:
    """Record which checkpoints this run produced, for the dashboard to read.

    Written by the run itself rather than by CI, so a local ``make run`` and a
    scheduled one leave the same artifact and the published page never renders a
    stage list from a previous shape of the pipeline.
    """
    if not stems:
        return
    _write_json(runs_dir / run_id / MANIFEST_NAME, {"stages": sorted(stems)})


def _emit(record: dict[str, Any], out) -> None:
    """Emit one deterministic line. No timestamps, no durations -- replay must match."""
    out.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")


def _call_with_timeout(fn: Callable[[], Any], timeout: float, stage_name: str) -> Any:
    """Run ``fn`` on a worker thread and give up after ``timeout`` seconds.

    Python cannot forcibly kill a thread, so an over-running stage keeps burning
    CPU in the background; the executor is left un-joined on purpose and its
    daemon thread dies with the process. The harness itself stops immediately,
    which is what the wall-clock guarantee is about.
    """
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"stage-{stage_name}")
    future = executor.submit(fn)
    try:
        return future.result(timeout=timeout)
    except FuturesTimeoutError as exc:
        future.cancel()
        raise StageTimeout(f"stage {stage_name!r} exceeded {timeout}s wall-clock budget") from exc
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def run_pipeline(
    stages: Sequence[Stage],
    run_id: str,
    *,
    runs_dir: Path = DEFAULT_RUNS_DIR,
    max_turns: int = DEFAULT_MAX_TURNS,
    stage_timeout: float = DEFAULT_STAGE_TIMEOUT,
    initial_state: dict[str, Any] | None = None,
    out=None,
) -> RunResult:
    """Execute ``stages`` in order, checkpointing each result.

    Stops at the first failure; everything completed before that point stays on
    disk and remains replayable.
    """
    out = sys.stdout if out is None else out
    runs_dir = Path(runs_dir)
    ctx = RunContext(run_id=run_id, max_turns=max_turns)
    state: dict[str, Any] = dict(initial_state or {})
    result = RunResult(run_id=run_id, state=state)
    written: list[str] = []

    try:
        for index, stage in enumerate(stages):
            ctx.stage_name = stage.name
            started = time.monotonic()
            try:
                # Entering a stage always costs one turn: this is the hard cap.
                ctx.spend_turn()
                output = _call_with_timeout(
                    lambda s=stage: s.run(ctx, state), stage_timeout, stage.name
                )
            except HarnessError as exc:
                result.error = f"{type(exc).__name__}: {exc}"
                result.turns_used = ctx.turns_used
                return result

            if not isinstance(output, dict):
                result.error = f"TypeError: stage {stage.name!r} returned {type(output).__name__}"
                result.turns_used = ctx.turns_used
                return result

            state.update(output)
            record = {"index": index, "run_id": run_id, "stage": stage.name, "output": output}
            path = checkpoint_path(runs_dir, run_id, index, stage.name)
            _write_json(path, record)
            written.append(path.stem)
            result.records.append(record)
            _emit(record, out)

            # Timing is deliberately kept out of the replayable record.
            _write_json(
                runs_dir / run_id / f"{index:02d}-{stage.name}.timing.json",
                {"stage": stage.name, "seconds": round(time.monotonic() - started, 6)},
            )
    finally:
        # A partial run still publishes an honest manifest of what it reached.
        _write_manifest(runs_dir, run_id, written)

    result.turns_used = ctx.turns_used
    return result


def load_checkpoints(run_id: str, *, runs_dir: Path = DEFAULT_RUNS_DIR) -> list[dict[str, Any]]:
    """Read back every checkpointed stage record for a run, in stage order."""
    run_dir = Path(runs_dir) / run_id
    if not run_dir.is_dir():
        raise FileNotFoundError(f"no such run: {run_dir}")
    # Match the checkpoint name, rather than listing the files to skip. A run
    # directory accumulates neighbours -- the dashboard's index.json manifest,
    # timing sidecars, a human override someone dropped in -- and a denylist has
    # to be updated every time one appears. It was not, once: index.json was
    # globbed in as a checkpoint and replay died on KeyError: 'output'.
    files = sorted(
        p for p in run_dir.glob("[0-9][0-9]-*.json") if not p.name.endswith(".timing.json")
    )
    if not files:
        raise FileNotFoundError(f"run {run_id!r} has no checkpoints")
    return [json.loads(p.read_text(encoding="utf-8")) for p in files]


def replay(run_id: str, *, runs_dir: Path = DEFAULT_RUNS_DIR, out=None) -> RunResult:
    """Re-emit a previous run from its checkpoints. Calls nothing live."""
    out = sys.stdout if out is None else out
    records = load_checkpoints(run_id, runs_dir=runs_dir)
    state: dict[str, Any] = {}
    for record in records:
        state.update(record["output"])
        _emit(record, out)
    return RunResult(run_id=run_id, records=records, state=state, turns_used=len(records))


def _default_run_id() -> str:
    return os.environ.get("RUN_ID", "").strip() or time.strftime("%Y%m%dT%H%M%S", time.gmtime())


def _env_number(name: str, default: float) -> float:
    """Read a numeric knob from the environment, ignoring anything unusable.

    The env template documents these, so the code has to actually read them --
    a documented variable nothing consumes is a lie in a config file.
    """
    raw = os.environ.get(name, "").strip()
    try:
        return float(raw) if raw else default
    except ValueError:
        return default


def main(argv: Sequence[str] | None = None) -> int:
    from company.stages import PIPELINE, initial_state

    parser = argparse.ArgumentParser(prog="company", description=__doc__)
    parser.add_argument(
        "--run-id", default=None, help="run identifier (default: $RUN_ID, else a UTC timestamp)"
    )
    parser.add_argument("--replay", metavar="RUN_ID", help="re-emit a prior run from checkpoints")
    parser.add_argument("--runs-dir", default=str(DEFAULT_RUNS_DIR), type=Path)
    parser.add_argument(
        "--max-turns", type=int, default=int(_env_number("MAX_TURNS", DEFAULT_MAX_TURNS))
    )
    parser.add_argument(
        "--stage-timeout",
        type=float,
        default=_env_number("STAGE_TIMEOUT_S", DEFAULT_STAGE_TIMEOUT),
    )
    args = parser.parse_args(argv)

    if args.replay:
        try:
            replay(args.replay, runs_dir=args.runs_dir)
        except FileNotFoundError as exc:
            print(f"replay failed: {exc}", file=sys.stderr)
            return 2
        return 0

    result = run_pipeline(
        PIPELINE,
        run_id=args.run_id or _default_run_id(),
        runs_dir=args.runs_dir,
        max_turns=args.max_turns,
        stage_timeout=args.stage_timeout,
        initial_state=initial_state(),
    )
    if not result.ok:
        print(f"run {result.run_id} failed: {result.error}", file=sys.stderr)
        return 1
    print(f"run {result.run_id} ok ({result.turns_used} turns)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
