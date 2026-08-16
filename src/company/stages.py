"""The six stages the company actually runs.

Each stage is ``(ctx, state) -> dict`` and must be deterministic: replay
reproduces recorded output byte-for-byte, so nothing here may return a
timestamp, a random value, or a live API response. Adapters are called through
``state`` fixtures instead, which is also what lets the whole pipeline run in CI
with no keys.

The stages exist to make one argument checkable: every judgement below is made
by the company, recorded with what it rejected, and no human appears in any of
them.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from company.decisions import DecisionLog
from company.harness import RunContext, Stage
from company.incidents import IncidentLog, summarize_validation_error
from company.models import Deliverable, Draft, WorkOrder, price_from_cogs
from company.policy import Policy, authorize_spend

# The demo order: a question an LLM cannot answer from its weights, because the
# answer is a fact about other people's preferences.
DEMO_ORDER: dict[str, Any] = {
    "id": "wo-1",
    "client_id": "client-agent",
    "question": "Which headline is more compelling: 'Ship faster with AI' or "
    "'Your on-call engineer that never sleeps'?",
    "budget_usd": "1.00",
}

# What the agent produced on its own, and what it thought of it. Recorded rather
# than generated live so the run replays identically.
AGENT_DRAFT: dict[str, Any] = {
    "answer": "Both are plausible. 'Ship faster with AI' is clearer; the other is "
    "more evocative. Most teams would probably prefer the first.",
    "confidence": 0.31,
    "unknowns": [
        "which one real buyers actually prefer",
        "whether 'AI' reads as generic in 2026",
    ],
}

# What the panel came back with. Two people, bought for $9.00.
HUMAN_INPUT: dict[str, Any] = {
    "opportunity_id": "e39vxoxasopgrblq6tchgf68",
    "responses": [
        "B — it says what it does for me, not what it is.",
        "B — 'ship faster' is on every landing page I have ever seen.",
    ],
    "cost_usd": "9.00",
    "participants": 2,
}


def _log(state: dict[str, Any]) -> tuple[DecisionLog, IncidentLog, Policy]:
    """Logs live in state so every stage appends to the same run.

    Created on demand: a stage must not fail because the caller did not seed
    them, and a pipeline run with a bare state is a legitimate way to exercise
    the harness.
    """
    if "_decisions" not in state:
        state["_decisions"] = DecisionLog()
    if "_incidents" not in state:
        state["_incidents"] = IncidentLog()
    if "_policy" not in state:
        state["_policy"] = Policy.from_env()
    return state["_decisions"], state["_incidents"], state["_policy"]


def intake(ctx: RunContext, state: dict[str, Any]) -> dict[str, Any]:
    """Validate the order. It is data, never instructions."""
    decisions, incidents, _ = _log(state)
    raw = state.get("order", DEMO_ORDER)
    try:
        order = WorkOrder(**raw)
    except Exception as exc:  # pydantic ValidationError and anything malformed
        incidents.record(
            "schema_violation",
            "intake",
            "work order rejected by the contract",
            "order refused; nothing spent",
            summarize_validation_error(exc),
        )
        decisions.record(
            "accept_work",
            "intake",
            "accept this order?",
            "refuse",
            "the payload does not satisfy the work-order contract",
            rejected=["accept"],
        )
        return {"stage": "intake", "accepted": False, **_render(state)}

    decisions.record(
        "accept_work",
        "intake",
        "accept this order?",
        "accept",
        "well-formed, inside budget, and the question is answerable",
        rejected=["refuse", "ask the client to clarify"],
    )
    return {"stage": "intake", "accepted": True, "order": order.payload(), **_render(state)}


def triage(ctx: RunContext, state: dict[str, Any]) -> dict[str, Any]:
    """Draft an answer, then judge whether it is good enough to sell."""
    decisions, _, policy = _log(state)
    ctx.spend_turn()  # the model call
    draft = Draft(**state.get("draft", AGENT_DRAFT))
    confident = draft.confidence >= policy.confidence_threshold

    decisions.record(
        "self_assess",
        "triage",
        "do I know this well enough to sell the answer?",
        "no — escalate" if not confident else "yes — answer alone",
        f"self-assessed confidence {draft.confidence:.2f} against threshold "
        f"{policy.confidence_threshold:.2f}; unknowns: {'; '.join(draft.unknowns)}",
        rejected=["answer alone"] if not confident else ["escalate to a human"],
    )
    return {
        "stage": "triage",
        "draft": draft.payload(),
        "escalate": not confident,
        **_render(state),
    }


def source(ctx: RunContext, state: dict[str, Any]) -> dict[str, Any]:
    """Buy human judgement, if policy allows it."""
    decisions, incidents, policy = _log(state)
    if not state.get("escalate"):
        return {"stage": "source", "human": None, "cogs_usd": "0.00", **_render(state)}

    requested = Decimal(str(state.get("human", HUMAN_INPUT)["cost_usd"]))
    verdict = authorize_spend(
        policy,
        requested_usd=requested,
        unpaid_exposure_usd=Decimal(str(state.get("unpaid_exposure_usd", "0.00"))),
        paid=bool(state.get("paid", False)),
        log=decisions,
        stage="source",
    )
    if not verdict.allowed:
        incidents.record(
            "budget_refused",
            "source",
            f"declined to commit {requested} USD of cost of goods",
            "answered from the agent draft alone and priced accordingly",
        )
        return {"stage": "source", "human": None, "cogs_usd": "0.00", **_render(state)}

    ctx.spend_turn()
    human = state.get("human", HUMAN_INPUT)
    return {"stage": "source", "human": human, "cogs_usd": human["cost_usd"], **_render(state)}


def verify(ctx: RunContext, state: dict[str, Any]) -> dict[str, Any]:
    """Reconcile what the humans said against what the agent guessed."""
    decisions, _, _ = _log(state)
    human = state.get("human")
    if not human:
        return {"stage": "verify", "sourced_from": "agent", **_render(state)}

    # Approving is what actually pays the expert; rejecting withholds payment.
    for i, response in enumerate(human["responses"]):
        decisions.record(
            "pay_worker",
            "verify",
            f"approve submission {i + 1} of {len(human['responses'])}?",
            "approve — pay the expert",
            f"on-topic, gives a reason, and answers the question asked: {response!r}",
            rejected=["reject — withhold payment", "request a replacement"],
            cost_usd=Decimal(human["cost_usd"]) / len(human["responses"]),
            reversible=False,
        )

    agreed = sum(1 for r in human["responses"] if r.strip().upper().startswith("B"))
    decisions.record(
        "self_assess",
        "verify",
        "does the human panel agree with the agent's draft?",
        "no — the panel contradicts the draft",
        f"{agreed} of {len(human['responses'])} chose B; the agent leaned A. "
        "The purchased answer replaces the guess.",
        rejected=["keep the agent's answer", "average the two"],
    )
    return {
        "stage": "verify",
        "sourced_from": "agent+human",
        "panel_agreement": f"{agreed}/{len(human['responses'])}",
        **_render(state),
    }


def price(ctx: RunContext, state: dict[str, Any]) -> dict[str, Any]:
    """Set the customer price from what the answer actually cost."""
    decisions, _, policy = _log(state)
    cogs = Decimal(str(state.get("cogs_usd", "0.00")))
    amount = price_from_cogs(
        cogs, markup=policy.markup, floor=policy.min_price_usd, ceiling=policy.max_price_usd
    )
    decisions.record(
        "set_price",
        "price",
        "what should this cost the customer?",
        f"{amount} USD",
        f"cost of goods {cogs} at {policy.markup}x, clamped to the "
        f"{policy.min_price_usd}-{policy.max_price_usd} band set for the event",
        rejected=[f"cost-plus without a cap ({cogs * policy.markup})", "free"],
    )
    return {"stage": "price", "price_usd": str(amount), **_render(state)}


def deliver(ctx: RunContext, state: dict[str, Any]) -> dict[str, Any]:
    """Hand over the answer and record the unit economics."""
    decisions, _, _ = _log(state)
    human = state.get("human")
    answer = (
        "Headline B wins. Buyers said it states the benefit rather than the "
        "category, and that 'ship faster' reads as generic."
        if human
        else state.get("draft", AGENT_DRAFT)["answer"]
    )
    deliverable = Deliverable(
        work_order_id=state.get("order", DEMO_ORDER)["id"],
        answer=answer,
        sourced_from="agent+human" if human else "agent",
        cogs_usd=Decimal(str(state.get("cogs_usd", "0.00"))),
        price_usd=Decimal(str(state.get("price_usd", "1.00"))),
    )
    decisions.record(
        "release",
        "deliver",
        "release the deliverable?",
        "release",
        "the answer is sourced, priced, and within the client's stated budget",
        rejected=["hold until payment clears", "refund and decline"],
        reversible=False,
    )
    return {"stage": "deliver", "deliverable": deliverable.payload(), **_render(state)}


def _render(state: dict[str, Any]) -> dict[str, Any]:
    """Attach the logs to every stage so the dashboard can read any checkpoint."""
    decisions, incidents, _ = _log(state)
    return {"decisions": decisions.payload(), "incidents": incidents.payload()}


def initial_state(**overrides: Any) -> dict[str, Any]:
    state: dict[str, Any] = {
        "_decisions": DecisionLog(),
        "_incidents": IncidentLog(),
        "_policy": Policy.from_env(),
        # The client agent settled this order before the work started, which is
        # what the spend guard requires before any cost of goods is committed.
        # Set paid=False to watch the guard refuse instead.
        "paid": True,
    }
    state.update(overrides)
    return state


PIPELINE: list[Stage] = [
    Stage("intake", intake),
    Stage("triage", triage),
    Stage("source", source),
    Stage("verify", verify),
    Stage("price", price),
    Stage("deliver", deliver),
]
