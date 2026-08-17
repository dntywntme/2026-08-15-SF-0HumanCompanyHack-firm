"""Failures, recorded rather than raised.

The demo thesis is that the company catches its own failures, so a failure has
to be an artifact you can render, not a traceback that ends the run. Every
category below maps to a measured failure mode of multi-agent systems (MAST,
arXiv:2503.13657); the three most common ones there -- step repetition (15.7%),
reasoning-action mismatch (13.2%) and unaware-of-termination (12.4%) -- are the
ones the harness's turn cap and wall-clock timeout exist to catch.

Records carry no timestamps: they land in stage output, which must stay
byte-identical under ``--replay``.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Category = Literal[
    "schema_violation",  # model returned something the contract rejects
    "turn_cap",  # step repetition / runaway loop
    "timeout",  # unaware of termination conditions
    "tool_failure",  # an adapter degraded instead of raising
    "budget_refused",  # the COGS guard declined to spend
    "injection_attempt",  # work order tried to issue instructions
    "payment_failed",  # charge declined, abandoned or underpaid
    "compliance_refusal",  # the order asked for something we may not sell
    "personal_data",  # order text carried data that must not reach a panel
]


class Incident(BaseModel):
    """One caught failure, and what the company did about it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    category: Category
    stage: str
    detail: str
    recovery: str
    # Structured validation errors, when the category is schema_violation.
    errors: list[dict[str, Any]] = Field(default_factory=list)

    def payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class IncidentLog:
    """Collects incidents for a run so stages can hand them to the dashboard."""

    def __init__(self) -> None:
        self._items: list[Incident] = []

    def record(
        self,
        category: Category,
        stage: str,
        detail: str,
        recovery: str,
        errors: list[dict[str, Any]] | None = None,
    ) -> Incident:
        incident = Incident(
            category=category,
            stage=stage,
            detail=detail,
            recovery=recovery,
            errors=errors or [],
        )
        self._items.append(incident)
        return incident

    def payload(self) -> list[dict[str, Any]]:
        return [i.payload() for i in self._items]

    def __len__(self) -> int:
        return len(self._items)


def summarize_validation_error(exc: Exception) -> list[dict[str, Any]]:
    """Reduce a Pydantic ValidationError to a stable, renderable shape.

    ``loc`` is joined and the input value is dropped: the input can be
    arbitrary, unbounded, or attacker-controlled, and none of it belongs in a
    checkpoint that gets published to a static site.
    """
    errors = getattr(exc, "errors", None)
    if not callable(errors):
        return [{"type": type(exc).__name__, "loc": "", "msg": str(exc)}]
    return [
        {
            "type": e.get("type", ""),
            "loc": ".".join(str(p) for p in e.get("loc", ())),
            "msg": e.get("msg", ""),
        }
        for e in errors()
    ]
