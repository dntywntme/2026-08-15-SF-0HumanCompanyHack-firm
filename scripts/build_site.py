#!/usr/bin/env python3
"""Assemble the published site. One path, used by every workflow that deploys.

Three workflows publish this site -- pages, ledger and run -- and each carried
its own copy of the same shell. Three copies of an assembly step is three places
for the published artifact to quietly differ depending on which job happened to
deploy last.

Beyond copying, this derives ``/.well-known/offer.json`` from the run's own
market checkpoint. That is the company's acquisition channel: the customer is
another agent, so the offer has to be machine-readable, and deriving it from the
run means it cannot make a claim the run did not make. A hand-written offer file
would go stale the first time the price moved.

Stdlib only, no package import: the ledger job runs this with a bare interpreter
and no ``uv sync``.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

WEB = Path("web")
RUNS = Path("runs")
MANIFEST = "index.json"


def copy_tree(src: Path, dst: Path) -> None:
    if src.is_dir():
        shutil.copytree(src, dst, dirs_exist_ok=True)


def latest_offer(run_dir: Path) -> dict | None:
    """Pull the offer out of the run's market checkpoint, if it made one.

    Goes through the manifest rather than guessing a filename. A halted run --
    one refused at intake or by the compliance gate -- never reaches ``market``
    and therefore has no offer, which is not an error: a company that refused
    the order has nothing to advertise from it.
    """
    manifest = run_dir / MANIFEST
    if not manifest.is_file():
        return None
    try:
        stages = json.loads(manifest.read_text(encoding="utf-8")).get("stages", [])
    except ValueError:
        return None
    stem = next((s for s in stages if s.endswith("-market")), None)
    if not stem:
        return None
    try:
        record = json.loads((run_dir / f"{stem}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return record.get("output", {}).get("offer")


def build(out: Path, run_id: str) -> int:
    out.mkdir(parents=True, exist_ok=True)
    copy_tree(WEB, out)
    copy_tree(RUNS, out / "runs")
    # GitHub Pages runs Jekyll otherwise, which drops files beginning with a dot
    # -- including the well-known directory this writes into.
    (out / ".nojekyll").write_text("", encoding="utf-8")

    if not (out / "index.html").is_file():
        print("no index.html in the assembled site", file=sys.stderr)
        return 1

    offer = latest_offer(RUNS / run_id)
    if offer:
        well_known = out / ".well-known"
        well_known.mkdir(parents=True, exist_ok=True)
        (well_known / "offer.json").write_text(
            json.dumps({**offer, "run_id": run_id}, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"published offer from run {run_id}: {offer.get('price_usd')} USD")
    else:
        # Said out loud rather than skipped silently: no offer means either a
        # refused order or a run that never got that far, and both are worth
        # seeing in the job log.
        print(f"run {run_id} published no offer", file=sys.stderr)

    print(f"assembled {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="build_site", description=__doc__)
    parser.add_argument("--out", default="_site", type=Path)
    parser.add_argument("--run-id", default="demo")
    args = parser.parse_args(argv)
    return build(args.out, args.run_id)


if __name__ == "__main__":
    raise SystemExit(main())
