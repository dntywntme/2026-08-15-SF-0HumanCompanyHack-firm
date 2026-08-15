"""Stub stages: intake -> process -> deliver.

These are deliberately trivial and fully offline. They exist so the harness is
testable and demoable with zero API keys and zero network. Real stages replace
the bodies; the signature ``(ctx, state) -> dict`` and the determinism
requirement (same inputs => same output bytes) are the contract.
"""

from __future__ import annotations

from typing import Any

from company.harness import RunContext, Stage

DEFAULT_BRIEF = "ship a deterministic agent harness"


def intake(ctx: RunContext, state: dict[str, Any]) -> dict[str, Any]:
    """Normalise the incoming brief into work items."""
    brief = str(state.get("brief", DEFAULT_BRIEF))
    items = [w for w in brief.split() if w]
    return {"brief": brief, "items": items, "item_count": len(items)}


def process(ctx: RunContext, state: dict[str, Any]) -> dict[str, Any]:
    """The one bounded fan-out point: one unit of work per intake item."""
    items: list[str] = list(state.get("items", []))
    results = [
        {"item": item, "slug": item.lower().strip(".,"), "size": len(item)} for item in items
    ]
    return {"processed": results, "total_size": sum(r["size"] for r in results)}


def deliver(ctx: RunContext, state: dict[str, Any]) -> dict[str, Any]:
    """Assemble the artifact handed back to the caller."""
    processed: list[dict[str, Any]] = list(state.get("processed", []))
    return {
        "artifact": "-".join(r["slug"] for r in processed),
        "delivered_count": len(processed),
        "run_id": ctx.run_id,
    }


PIPELINE: tuple[Stage, ...] = (
    Stage("intake", intake),
    Stage("process", process),
    Stage("deliver", deliver),
)
