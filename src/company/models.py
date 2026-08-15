"""The contracts every stage speaks.

These are the source of truth for the pipeline. Two rules follow from the
harness and are load-bearing:

1. **Validation is visible.** We validate with Pydantic rather than a parser
   that silently repairs malformed model output, because a repaired error is an
   error nobody can see. Every ``ValidationError`` becomes an incident record.

2. **Serialization is deterministic.** Stages return ``model_dump(mode="json")``,
   which renders ``Decimal`` as an exact string. No timestamps, no floats for
   money, no random ids -- otherwise ``--replay`` cannot reproduce a run
   byte-for-byte and the demo fallback is worthless.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field

# Money is Decimal everywhere. Cost of goods is real money paid to real people,
# so binary floating point is not acceptable.
Money = Annotated[Decimal, Field(ge=0, decimal_places=2)]


class Contract(BaseModel):
    """Base: reject unknown fields loudly rather than dropping them silently."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    def payload(self) -> dict[str, Any]:
        """Deterministic, JSON-safe dict for a stage return value."""
        return self.model_dump(mode="json")


class WorkOrder(Contract):
    """What a customer asks for. Arrives from an untrusted client.

    This is DATA, never instructions. It is validated into this shape and its
    fields are passed as parameters -- never concatenated into a system prompt.
    That is the whole defence against prompt injection in the intake path.
    """

    id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    client_id: str = Field(min_length=1, max_length=64)
    question: str = Field(min_length=1, max_length=4000)
    budget_usd: Money


class Draft(Contract):
    """The agent's own attempt, plus its self-assessed confidence.

    ``confidence`` is the buy/don't-buy signal: below the configured threshold
    the company stops answering and starts purchasing.
    """

    answer: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    unknowns: list[str] = Field(default_factory=list, max_length=20)


class HumanInput(Contract):
    """What was bought from Terac. This is cost of goods sold."""

    opportunity_id: str = Field(min_length=1)
    responses: list[str] = Field(min_length=1)
    cost_usd: Money
    participants: int = Field(ge=1)


class Deliverable(Contract):
    """What the customer receives, with its unit economics attached."""

    work_order_id: str
    answer: str = Field(min_length=1)
    sourced_from: Literal["agent", "agent+human"]
    cogs_usd: Money
    price_usd: Money

    @computed_field  # type: ignore[prop-decorator]
    @property
    def margin_usd(self) -> Decimal:
        return self.price_usd - self.cogs_usd


class SpendDecision(Contract):
    """The COGS guard's verdict, recorded whether or not it allowed the spend.

    A zero-human company that buys real inputs can be drained by an adversary
    who submits expensive work and never pays. The defence is a business rule,
    not a content filter: never commit cost of goods before revenue is secured,
    and cap unpaid exposure per client.
    """

    allowed: bool
    reason: str
    requested_usd: Money
    unpaid_exposure_usd: Money
    cap_usd: Money


def price_from_cogs(cogs: Decimal, *, markup: Decimal, floor: Decimal, ceiling: Decimal) -> Decimal:
    """Customer price from cost of goods, clamped to the configured band.

    Quantized to cents so the same inputs always produce the same string on
    disk; an unrounded Decimal would break replay fidelity.
    """
    priced = max(floor, min(ceiling, cogs * markup))
    return priced.quantize(Decimal("0.01"))
