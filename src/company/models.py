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
    # Where the customer says they are, which decides which notices travel with
    # the answer. Optional, because the two orders already on the tracker
    # predate the field and a contract that rejects yesterday's valid order is
    # a contract that breaks its own customers. Absent means "unspecified",
    # which the compliance gate treats as the strictest case rather than the
    # loosest.
    jurisdiction: str = Field(
        default="unspecified", max_length=16, pattern=r"^[a-z]{2}(-[a-z]{2})?$|^unspecified$"
    )


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


class Product(Contract):
    """What the company actually built, with the improvement made visible.

    The event's mandatory requirement is real human input that makes the project
    *measurably* better, shown as a clear before and after. That is a property of
    an artifact, not of a paragraph, so it is one: ``before`` is what the agent
    would have shipped alone, ``after`` is what shipped once judgement was
    bought, and ``changed`` says whether the purchase moved the answer at all.

    ``changed`` is allowed to be False. An honest before/after has to be able to
    report that the money bought confirmation rather than a correction.
    """

    work_order_id: str
    before: str = Field(min_length=1)
    before_confidence: float = Field(ge=0.0, le=1.0)
    after: str = Field(min_length=1)
    changed: bool
    # False when the answer is a recorded fixture rather than one produced for
    # this customer's question. The pipeline runs on committed fixtures so that
    # --replay stays byte-identical, which means an order asking something new
    # gets an answer to a question it did not ask. That is defensible as a
    # mechanism demo and indefensible if it is not said out loud, so it is a
    # field on the artifact rather than a caveat in a README.
    answers_question: bool = True
    # The panel's own words, which are what the customer is really buying.
    evidence: list[str] = Field(default_factory=list)
    disclosures: list[str] = Field(default_factory=list)


class Offer(Contract):
    """The outbound artifact: what the company says to win the next order.

    Written from the run that just completed, so the claim on it is the run's
    own arithmetic rather than copy. ``channel`` records where it was actually
    put, and ``declined_channels`` records the ones the company chose not to use
    and why — an outbound function that never says no is a spam function.
    """

    headline: str = Field(min_length=1)
    proof: str = Field(min_length=1)
    price_usd: Money
    unit_cost_usd: Money
    channel: Literal["issue-thread", "own-surface", "none"]
    audience: str = Field(min_length=1)
    declined_channels: list[str] = Field(default_factory=list)
    # How another agent places an order, and under which terms. This is the
    # whole of the acquisition channel: the customer is a program, so the offer
    # has to be readable by one.
    order_how: str = ""
    order_schema: dict[str, str] = Field(default_factory=dict)
    terms_id: str = ""
    privacy_id: str = ""


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
