"""What the company may sell, and what it must say when it sells it.

A company that takes orders from strangers and forwards them to identity-verified
people has two obligations before it spends anything, and both of them are
decisions rather than filters:

**What it will not sell.** Broker sells opinion research — what people think,
bought from people. It does not practise law, medicine or financial advice, and
it will not sell an answer that a licensed professional is required to give. The
refusal is commercial, not squeamish: an unlicensed $1.00 legal opinion is a
liability that dwarfs the revenue, and *the cheapest compliance control is not
taking the order*.

**What it must not forward.** The question is passed verbatim to real people on
Terac and is published on a static page afterwards. Personal data in the order —
an email address, a phone number, a card-shaped number — must not travel to a
panel and must not land in a checkpoint. It is redacted before the order moves,
and the redaction is recorded so the customer can see what was removed.

Alongside those, every deliverable carries **disclosures**: that an autonomous
agent produced it with no human at Broker in the loop, whether human judgement
was purchased, and that it is not professional advice. A zero-human company that
does not disclose that it is one is not compliant, it is just quiet.

Everything here is deterministic — a pure function of the order text — because
the result is checkpointed and ``--replay`` must reproduce it byte for byte.
"""

from __future__ import annotations

import re

from pydantic import Field

from company.models import Contract

# ── What we refuse to sell ────────────────────────────────────────────────────
# Each rule is (name, pattern, why we refuse). The "why" is published to the
# customer, so it is written to be read by one.
RESTRICTED: list[tuple[str, re.Pattern[str], str]] = [
    (
        "legal_advice",
        re.compile(
            r"\b(non-?compete|enforceable|legally binding|sue|lawsuit|liable|liability|"
            r"licensed attorney|legal advice|review (this|the|my) contract|"
            r"terms of service|breach of contract)\b",
            re.I,
        ),
        "this asks for legal advice, which requires a licensed attorney; Broker "
        "sells opinion research and is not a law firm",
    ),
    (
        "medical_advice",
        re.compile(
            r"\b(diagnos\w*|symptoms?|prescri\w+|dosage|medication|medical advice|"
            r"treatment for|should i take)\b",
            re.I,
        ),
        "this asks for medical advice, which requires a licensed clinician; Broker "
        "sells opinion research and is not a medical provider",
    ),
    (
        "financial_advice",
        re.compile(
            r"\b(should i (buy|sell|invest|short)|tax advice|securities|insider|"
            r"portfolio allocation|financial advice|invest(ment)? recommendation)\b",
            re.I,
        ),
        "this asks for financial advice, which is a regulated activity; Broker "
        "sells opinion research and is not an adviser",
    ),
]

# ── What we refuse to forward ─────────────────────────────────────────────────
# Order text reaches real people and then a public page. These never do.
PERSONAL_DATA: list[tuple[str, re.Pattern[str]]] = [
    ("email", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")),
    ("phone", re.compile(r"(?<!\w)(?:\+\d{1,3}[ .-]?)?(?:\(?\d{3}\)?[ .-]?)\d{3}[ .-]?\d{4}\b")),
    ("card_number", re.compile(r"\b(?:\d[ -]?){13,19}\b")),
    ("government_id", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
]

REDACTION = "[redacted]"

# Attached to every deliverable the company releases. The first one is the
# whole premise of the event and is never conditional.
BASE_DISCLOSURES = [
    "Produced by an autonomous agent. No human at Broker reviewed this answer.",
    "Opinion research, not legal, medical or financial advice.",
]
HUMAN_DISCLOSURE = (
    "Includes judgement purchased from identity-verified people via Terac, who were paid for it."
)
AGENT_ONLY_DISCLOSURE = (
    "Answered by the agent alone: its self-assessed confidence was above the "
    "threshold, so no human judgement was bought for this order."
)


class Screening(Contract):
    """The compliance gate's verdict on one order.

    Recorded whether or not it cleared, because a control you only log when it
    fires is a control nobody can audit.
    """

    cleared: bool
    # Populated when we refuse: the rule that fired and the reason we publish.
    refused_rule: str = ""
    refused_because: str = ""
    # Categories of personal data removed before the order went any further.
    redactions: list[str] = Field(default_factory=list)
    # The text that is safe to forward to a panel and to publish.
    safe_question: str
    disclosures: list[str] = Field(default_factory=list)


def redact(question: str) -> tuple[str, list[str]]:
    """Strip personal data out of order text. Returns (safe text, categories)."""
    found: list[str] = []
    safe = question
    for name, pattern in PERSONAL_DATA:
        safe, hits = pattern.subn(REDACTION, safe)
        if hits:
            found.append(name)
    return safe, found


def screen(question: str, *, escalating: bool = True) -> Screening:
    """Decide whether this order may be worked at all, and on what terms.

    ``escalating`` only selects which sourcing disclosure applies; it does not
    affect whether the order clears. Checks run refusal-first, so a refused
    order is never redacted-and-forwarded by accident.
    """
    disclosures = [*BASE_DISCLOSURES, HUMAN_DISCLOSURE if escalating else AGENT_ONLY_DISCLOSURE]
    safe, redactions = redact(question)

    for name, pattern, why in RESTRICTED:
        if pattern.search(question):
            return Screening(
                cleared=False,
                refused_rule=name,
                refused_because=why,
                redactions=redactions,
                safe_question=safe,
                disclosures=disclosures,
            )

    return Screening(
        cleared=True,
        redactions=redactions,
        safe_question=safe,
        disclosures=disclosures,
    )
