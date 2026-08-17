"""Every autonomous decision, recorded with its rationale.

This module is the evidence for the claim in the README. "No human is in the
loop" is easy to assert and hard to believe, so the company writes down each
decision as it makes it: what was being decided, what it chose, why, what it
rejected, and what the choice cost. The record is checkpointed with the rest of
the run and rendered on the dashboard.

Three properties make it evidence rather than decoration:

- **It is written at the point of decision**, not reconstructed afterwards. A
  rationale composed later is a story; this is a log.
- **It names the alternatives.** A decision with one option is not a decision,
  and a log that hides the rejected branch cannot be audited.
- **It carries the money.** Decisions that spend cost of goods say so in
  dollars, so the dashboard can show what the company's judgement cost it.

Records are deterministic: no timestamps, no ids drawn from a clock. They land
in stage output, which must stay byte-identical under ``--replay``.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# What kind of judgement this was. Each maps to a decision a human employee
# would otherwise make.
Kind = Literal[
    "accept_work",  # take this order, or refuse it
    "screen_order",  # legal/compliance: may we sell this at all, and on what terms
    "self_assess",  # do I know the answer, or not
    "buy_labor",  # spend cost of goods on human input
    "spend_guard",  # refuse to spend, protecting the balance
    "pay_worker",  # approve a submission: a human gets paid
    "withhold_pay",  # reject a submission: a human does not get paid
    "build_product",  # what to ship, and whether the bought judgement changed it
    "set_price",  # what to charge the customer
    "release",  # hand over the deliverable, or hold it
    "go_to_market",  # what to say about this run, and where to say it
]

Money = Annotated[Decimal, Field(ge=0, decimal_places=2)]


class Decision(BaseModel):
    """One judgement the company made without asking anyone."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Kind
    stage: str
    question: str = Field(min_length=1)
    chose: str = Field(min_length=1)
    because: str = Field(min_length=1)
    # A decision with nothing rejected is not a decision. Enforced, not advised.
    rejected: list[str] = Field(min_length=1)
    cost_usd: Money = Decimal("0.00")
    # False when the decision moved money or released work to a counterparty.
    reversible: bool = True

    def payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class DecisionLog:
    """The company's minute book for one run."""

    def __init__(self) -> None:
        self._items: list[Decision] = []

    def record(
        self,
        kind: Kind,
        stage: str,
        question: str,
        chose: str,
        because: str,
        rejected: list[str],
        cost_usd: Decimal = Decimal("0.00"),
        reversible: bool = True,
    ) -> Decision:
        decision = Decision(
            kind=kind,
            stage=stage,
            question=question,
            chose=chose,
            because=because,
            rejected=rejected,
            cost_usd=cost_usd,
            reversible=reversible,
        )
        self._items.append(decision)
        return decision

    def payload(self) -> list[dict[str, Any]]:
        return [d.payload() for d in self._items]

    @property
    def spent_usd(self) -> Decimal:
        """Total cost of goods committed by decisions in this run."""
        return sum((d.cost_usd for d in self._items), Decimal("0.00"))

    @property
    def irreversible(self) -> list[Decision]:
        """Decisions that moved money or released work. The ones that matter."""
        return [d for d in self._items if not d.reversible]

    def __len__(self) -> int:
        return len(self._items)
