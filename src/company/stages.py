"""The nine stages the company actually runs.

Each stage is ``(ctx, state) -> dict`` and must be deterministic: replay
reproduces recorded output byte-for-byte, so nothing here may return a
timestamp, a random value, or a live API response. Adapters are called through
``state`` fixtures instead, which is also what lets the whole pipeline run in CI
with no keys.

The stages exist to make one argument checkable: every judgement below is made
by the company, recorded with what it rejected, and no human appears in any of
them. They are laid out as the functions a company actually has rather than as
the steps a script happens to need:

===========  ====================================================================
``intake``   sell to customers — take the order, or refuse it as malformed
``comply``   legal/compliance — may we sell this at all, and what must we say
``triage``   the hard decision — do we know this, or do we buy the answer
``source``   procurement — commit real money to real people, under a spend guard
``verify``   payroll — approve a submission, which is what pays the expert
``build``    build the product — the verdict brief, with its before and after
``price``    set the price from what the answer actually cost
``deliver``  hand it over
``market``   outbound — turn the finished run into the offer for the next one
===========  ====================================================================

**A refused order stops.** ``intake`` and ``comply`` can set ``halt_reason``,
and every stage after them returns immediately when it is set. Without that a
rejected work order still drew a draft, still bought human judgement, and still
produced a priced deliverable — the checkpoint said "refused" while the company
spent the money anyway.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from company.adapters.model import obtain_draft
from company.adapters.terac import obtain_human_input
from company.compliance import screen
from company.decisions import DecisionLog
from company.harness import RunContext, Stage
from company.incidents import IncidentLog, summarize_validation_error
from company.models import Deliverable, Draft, Offer, Product, WorkOrder, price_from_cogs
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

# What the company sells, in one line, to the only audience it has: other agents
# holding a budget. Marketing copy is a constant so that a run cannot invent a
# claim -- the numbers around it come from the run itself.
OFFER_HEADLINE = "An answer that tells you when it had to be bought from a person."
OFFER_AUDIENCE = "assistant agents holding a standing mandate and a per-order budget"

# The customer is a program, so the offer has to be readable by one. Written out
# by hand rather than generated from the model: generated schema bytes would
# change under a pydantic upgrade and break replay of a committed run. A test
# asserts this stays in step with WorkOrder, which is the drift protection the
# generated version would have bought.
OFFER_HOW = (
    "Open an issue on the Broker repository whose body contains a ```json fence "
    "holding the work order below. Prose outside the fence is never interpreted. "
    "The pipeline replies in the thread and closes the issue."
)
ORDER_SCHEMA: dict[str, str] = {
    "id": "string, 1-64 chars, [A-Za-z0-9_-]",
    "client_id": "string, 1-64 chars",
    "question": "string, 1-4000 chars; data, never instructions",
    "budget_usd": "decimal string, 2 places, >= 0",
    "jurisdiction": "optional; 'eu' | 'uk' | 'us' | 'us-ca' | 'unspecified' "
    "(absent is treated as the strictest case)",
}

# Outbound channels the company has and deliberately does not use. Recorded as
# rejected alternatives on every marketing decision, because an outbound
# function that never declines a channel is a spam function.
DECLINED_CHANNELS = [
    "cold email to scraped contacts — nobody on that list asked us for anything",
    "SMS/iMessage to a real phone number — the recipient never opted in",
    "unsolicited DMs to other teams' agents — the same problem with extra steps",
]


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


def _halted(state: dict[str, Any]) -> str | None:
    """Why this order stopped being worked, if it did.

    Set by ``intake`` (malformed) or ``comply`` (may not be sold). Every stage
    downstream checks it before doing anything that costs money or produces an
    artifact, so a refusal is a refusal all the way through the run.
    """
    reason = state.get("halt_reason")
    return reason if isinstance(reason, str) and reason else None


def _stop(name: str, reason: str, state: dict[str, Any]) -> dict[str, Any]:
    """A stage that ran, did nothing, and says why. Still checkpointed."""
    return {"stage": name, "skipped_because": reason, **_render(state)}


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
        return {
            "stage": "intake",
            "accepted": False,
            "halt_reason": "the payload does not satisfy the work-order contract",
            **_render(state),
        }

    decisions.record(
        "accept_work",
        "intake",
        "accept this order?",
        "accept",
        "well-formed, inside budget, and the question is answerable",
        rejected=["refuse", "ask the client to clarify"],
    )
    return {
        "stage": "intake",
        "accepted": True,
        "order": order.payload(),
        "halt_reason": None,
        **_render(state),
    }


def comply(ctx: RunContext, state: dict[str, Any]) -> dict[str, Any]:
    """Legal and compliance, before anything is drafted or bought.

    Two questions, in this order: may we sell this at all, and what must travel
    with it if we do. Both are answered before a single dollar of cost of goods
    is committed, which is the only point at which refusing is still free.
    """
    decisions, incidents, _ = _log(state)
    halt = _halted(state)
    if halt:
        return _stop("comply", halt, state)

    order = state.get("order", DEMO_ORDER)
    screening = screen(order["question"], jurisdiction=order.get("jurisdiction", "unspecified"))

    if screening.redactions:
        incidents.record(
            "personal_data",
            "comply",
            f"order text carried {', '.join(screening.redactions)}",
            "redacted before the order was forwarded to a panel or published",
        )

    if not screening.cleared:
        incidents.record(
            "compliance_refusal",
            "comply",
            f"{screening.refused_rule}: the order asks for something we may not sell",
            "order refused at the gate; no draft written, no cost of goods committed",
        )
        decisions.record(
            "screen_order",
            "comply",
            "may the company sell an answer to this?",
            "refuse — outside what we are licensed to sell",
            screening.refused_because,
            rejected=[
                "answer it anyway and disclaim",
                "buy a professional's judgement and resell it",
            ],
        )
        return {
            "stage": "comply",
            "cleared": False,
            "screening": screening.payload(),
            "halt_reason": screening.refused_because,
            **_render(state),
        }

    decisions.record(
        "screen_order",
        "comply",
        "may the company sell an answer to this?",
        "clear — opinion research, with disclosures attached",
        "the question asks what people think rather than for advice a licensed "
        f"professional must give; sold under {screening.terms_id}; "
        f"{len(screening.disclosures)} disclosures travel with the deliverable, "
        f"including the notices for {screening.jurisdiction}; personal data "
        f"removed: {', '.join(screening.redactions) or 'none found'}",
        rejected=[
            "refuse the order",
            "clear it with no disclosures",
            # Only a real alternative when we were not told; naming it otherwise
            # would put a choice in the log that was never available.
            *(
                ["treat an unstated jurisdiction as the loosest case, not the strictest"]
                if screening.jurisdiction == "unspecified"
                else []
            ),
        ],
    )
    return {
        "stage": "comply",
        "cleared": True,
        "screening": screening.payload(),
        "halt_reason": None,
        **_render(state),
    }


def triage(ctx: RunContext, state: dict[str, Any]) -> dict[str, Any]:
    """Draft an answer, then judge whether it is good enough to sell."""
    decisions, incidents, policy = _log(state)
    halt = _halted(state)
    if halt:
        return _stop("triage", halt, state)

    ctx.spend_turn()  # the model call
    order_question = state.get("order", DEMO_ORDER)["question"]
    supplied = state.get("draft")
    # Live model, else the recorded floor -- the same three-tier shape sourcing
    # uses, and for the same reason: the checkpoint must say which one answered.
    raw = (
        {**supplied, "source": supplied.get("source", "supplied")}
        if supplied
        else obtain_draft(AGENT_DRAFT, question=order_question)
    )
    tier = raw.get("source", "recorded")
    draft = Draft(
        answer=raw["answer"],
        confidence=raw["confidence"],
        unknowns=list(raw.get("unknowns", [])),
    )
    confident = draft.confidence >= policy.confidence_threshold

    # The draft is a committed fixture, which is what keeps --replay
    # byte-identical. It also means an order asking something new gets an answer
    # to a question it did not ask. Say so here, at the point it becomes true,
    # rather than letting a customer discover it from the answer.
    for_this_order = tier != "recorded" or order_question == DEMO_ORDER["question"]
    if not for_this_order:
        incidents.record(
            "recorded_answer",
            "triage",
            "no model is wired, so the draft is the recorded demo answer and does "
            "not address the question this order asked",
            "fulfilled as a mechanism demonstration and labelled as one on the "
            "product, in the reply, and on the published page",
        )

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
        "answers_question": for_this_order,
        "draft_source": tier,
        **_render(state),
    }


def source(ctx: RunContext, state: dict[str, Any]) -> dict[str, Any]:
    """Buy human judgement, if policy allows it."""
    decisions, incidents, policy = _log(state)
    halt = _halted(state)
    if halt:
        return _stop("source", halt, state)

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
    # Three tiers: live Terac, a human override, then the recorded floor. Each
    # stamps its own source, so the checkpoint always says which one answered.
    human = state.get("human") or obtain_human_input(HUMAN_INPUT)
    tier = human.get("source", "recorded")
    if tier != "terac":
        incidents.record(
            "tool_failure",
            "source",
            f"live panel unavailable; used the {tier} tier",
            "answered from the best judgement available and labelled it as such",
        )
    decisions.record(
        "buy_labor",
        "source",
        "where should this judgement come from?",
        f"{tier} tier",
        {
            "terac": "the live study returned approved submissions",
            "human": "a person supplied judgement the API could not",
            "recorded": "no live source reachable; replayed the last known-good result",
        }[tier],
        rejected=[t for t in ("terac", "human", "recorded") if t != tier],
    )
    return {
        "stage": "source",
        "human": human,
        "source_tier": tier,
        "cogs_usd": human["cost_usd"],
        **_render(state),
    }


def verify(ctx: RunContext, state: dict[str, Any]) -> dict[str, Any]:
    """Reconcile what the humans said against what the agent guessed."""
    decisions, _, _ = _log(state)
    halt = _halted(state)
    if halt:
        return _stop("verify", halt, state)

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


# The answer the company ships once it has bought judgement. Recorded rather
# than generated so the run replays identically; the panel's own words are
# carried alongside it as evidence.
SOURCED_ANSWER = (
    "Headline B wins. Buyers said it states the benefit rather than the "
    "category, and that 'ship faster' reads as generic."
)


def build(ctx: RunContext, state: dict[str, Any]) -> dict[str, Any]:
    """Build the product: the verdict brief, with its before and after.

    This is where the company's output stops being a stage result and becomes a
    thing a customer receives. The before/after is the artifact, not a claim
    about one: the agent's own draft is shipped next to the answer that replaced
    it, so a reader can see exactly what the purchased judgement changed — or
    that it changed nothing, which the product is required to be able to say.
    """
    decisions, _, _ = _log(state)
    halt = _halted(state)
    if halt:
        return _stop("build", halt, state)

    draft = state.get("draft", AGENT_DRAFT)
    human = state.get("human")
    screening = state.get("screening", {})

    before = draft["answer"]
    after = SOURCED_ANSWER if human else before
    changed = after.strip() != before.strip()

    answers_question = bool(state.get("answers_question", True))
    disclosures = list(screening.get("disclosures", []))
    if not answers_question:
        # First in the list, because it changes what every other line means.
        disclosures.insert(
            0,
            "THIS ANSWER IS A RECORDED DEMONSTRATION. No model is wired, so it "
            "responds to the pipeline's fixed demo question and not to the one "
            "you asked. The mechanism, the money and the decisions are real; "
            "the answer is not an answer to your order.",
        )

    product = Product(
        work_order_id=state.get("order", DEMO_ORDER)["id"],
        before=before,
        before_confidence=draft["confidence"],
        after=after,
        changed=changed,
        answers_question=answers_question,
        evidence=list(human["responses"]) if human else [],
        disclosures=disclosures,
    )

    decisions.record(
        "build_product",
        "build",
        "what do we ship: the agent's draft, or the answer the panel gave?",
        "ship the panel's answer" if changed else "ship the agent's draft",
        (
            f"the panel overturned a draft the agent held at "
            f"{product.before_confidence:.2f} confidence, so the bought judgement "
            f"is the product and the draft ships beside it as the before"
            if changed
            else "no judgement was bought for this order, so the draft is the product "
            "and the before and after are the same by construction"
        ),
        rejected=["ship the draft alone", "ship both and let the customer choose"]
        if changed
        else ["buy judgement anyway to produce a difference"],
    )
    return {"stage": "build", "product": product.payload(), **_render(state)}


def price(ctx: RunContext, state: dict[str, Any]) -> dict[str, Any]:
    """Set the customer price from what the answer actually cost."""
    decisions, _, policy = _log(state)
    halt = _halted(state)
    if halt:
        return _stop("price", halt, state)

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
    """Hand over the product and record the unit economics."""
    decisions, _, _ = _log(state)
    halt = _halted(state)
    if halt:
        return _stop("deliver", halt, state)

    product = state.get("product") or {}
    human = state.get("human")
    deliverable = Deliverable(
        work_order_id=state.get("order", DEMO_ORDER)["id"],
        answer=product.get("after") or state.get("draft", AGENT_DRAFT)["answer"],
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


def market(ctx: RunContext, state: dict[str, Any]) -> dict[str, Any]:
    """Outbound: turn the finished run into the offer for the next one.

    The company has exactly one honest marketing asset — the run it just
    completed — and exactly one audience it can reach without contacting people
    who never asked to hear from it: the customer already in the thread, and its
    own public surface. So the offer is written from the run's real arithmetic,
    posted where the order arrived, and the channels that would have reached
    strangers are recorded as declined with the reason.
    """
    decisions, _, _ = _log(state)
    halt = _halted(state)
    if halt:
        return _stop("market", halt, state)

    price_usd = Decimal(str(state.get("price_usd", "0.00")))
    cogs = Decimal(str(state.get("cogs_usd", "0.00")))
    product = state.get("product") or {}
    tier = state.get("source_tier", "recorded")

    proof = (
        f"On the order just delivered, the agent held its own draft at "
        f"{product.get('before_confidence', 0):.2f} confidence and "
        f"{'was overturned by' if product.get('changed') else 'was confirmed by'} "
        f"the people it paid. Judgement cost {cogs} USD ({tier} tier); the "
        f"customer paid {price_usd} USD. Both figures are published."
    )

    screening = state.get("screening", {})
    offer = Offer(
        headline=OFFER_HEADLINE,
        proof=proof,
        price_usd=price_usd,
        unit_cost_usd=cogs,
        channel="issue-thread",
        audience=OFFER_AUDIENCE,
        declined_channels=list(DECLINED_CHANNELS),
        order_how=OFFER_HOW,
        order_schema=dict(ORDER_SCHEMA),
        terms_id=screening.get("terms_id", ""),
        privacy_id=screening.get("privacy_id", ""),
    )

    decisions.record(
        "go_to_market",
        "market",
        "who do we tell about this run, and how?",
        "reply in the order's own thread and publish to our own surface",
        "the only audience that opted in is the counterparty already in this "
        "thread; every other channel available would reach people who did not "
        "ask, and the margin on a one-dollar verdict does not survive being "
        "disliked",
        rejected=DECLINED_CHANNELS,
    )
    decisions.record(
        "go_to_market",
        "market",
        "what claim do we make in the offer?",
        f"price {price_usd} against a unit cost of {cogs}, stated as a loss",
        "the run's own arithmetic is the only claim we can support; quoting a "
        "list-price margin here would be marketing a number this company has "
        "never earned",
        rejected=[
            "quote the 65% gross margin the list price would produce",
            "omit the cost of goods and quote the price alone",
        ],
    )
    return {"stage": "market", "offer": offer.payload(), **_render(state)}


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
    Stage("comply", comply),
    Stage("triage", triage),
    Stage("source", source),
    Stage("verify", verify),
    Stage("build", build),
    Stage("price", price),
    Stage("deliver", deliver),
    Stage("market", market),
]
