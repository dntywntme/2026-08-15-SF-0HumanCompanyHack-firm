# 0HumanCompanyHack

An agent-run company. The architecture is a **deterministic harness spine**: an
ordered list of stages executed one at a time under a hard turn cap and a
per-stage wall-clock timeout, with every stage result checkpointed to disk. Not
a swarm, not a graph. At most one bounded fan-out, inside a single stage.

## Quickstart

```bash
make setup    # uv sync (Python 3.12)
make test     # pytest
make lint     # ruff check + ruff format --check
make run      # live run -> runs/demo/
make replay   # re-emit runs/demo/ from checkpoints, calls nothing live
```

`make run` and `make replay` emit byte-identical stdout. Override the run id
with `make run RUN_ID=foo`.

## Layout

- `src/company/harness.py` — the spine: `run_pipeline`, `replay`, the CLI.
- `src/company/stages.py` — stub stages `intake -> process -> deliver`. Fully
  offline; no API keys, no network. Replace the bodies with real work.
- `tests/` — order, turn cap, wall-clock timeout, checkpointing, replay fidelity.
- `runs/demo/` — a committed golden run so `make replay` works on a fresh clone.

## The stage contract

A stage is `(ctx: RunContext, state: dict) -> dict`. The returned dict is merged
into the shared run state and checkpointed. Stages must be **deterministic**
given the same inputs — replay reproduces recorded output, so anything that
sneaks a timestamp or a random value into its return breaks replay fidelity.

Use `ctx.spend_turn(n)` to charge extra turns for inner work (e.g. an agent
loop); entering a stage always costs one turn. Exceeding `--max-turns` aborts
the run. Timing metadata is written to sibling `*.timing.json` files and is
deliberately kept out of the replayable record.

## Known limitation

The per-stage timeout runs the stage on a worker thread and abandons it on
expiry. Python cannot forcibly kill a thread, so a runaway stage keeps burning
CPU until the process exits. The harness itself always returns promptly, which
is what the wall-clock guarantee covers. Subprocess isolation is the fix if a
stage ever needs to be truly killable.
