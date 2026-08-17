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

# ── What the customer agreed to ───────────────────────────────────────────────
# The terms and the privacy notice are published at web/legal.html and referenced
# by id on every deliverable, so a customer can say which version they were sold
# under and we cannot quietly change what they agreed to.
#
# Bumped by hand when web/legal.html changes. Deliberately not derived from a
# file hash or a clock: it lands in a checkpoint that --replay must reproduce
# byte for byte, and a version that moves on its own would break that.
POLICY_VERSION = "2026-08-17"
TERMS_ID = f"broker-terms-{POLICY_VERSION}"
PRIVACY_ID = f"broker-privacy-{POLICY_VERSION}"

# ── Where the customer is ─────────────────────────────────────────────────────
# Notices we publish per jurisdiction. These are disclosure obligations a static
# page can actually satisfy. They are NOT a compliance programme, nothing here
# was reviewed by counsel, and Broker is not an incorporated entity in any of
# these places -- which is itself disclosed.
UNSPECIFIED = "unspecified"
JURISDICTION_NOTICES: dict[str, list[str]] = {
    "eu": [
        "GDPR: your order text is processed only to fulfil the order, and is "
        "published in the public order thread. To request erasure, reply in that "
        "thread. Broker is not established in the EU and has no representative "
        "there.",
    ],
    "uk": [
        "UK GDPR: your order text is processed only to fulfil the order, and is "
        "published in the public order thread. To request erasure, reply in that "
        "thread.",
    ],
    "us-ca": [
        "CCPA: no personal information is sold or shared. Your order text is "
        "published in the public order thread; to request deletion, reply there.",
    ],
    "us": [
        "Your order text is published in the public order thread and is not sold "
        "or shared with anyone but the panel that answers it.",
    ],
}


def obligations(jurisdiction: str) -> list[str]:
    """The notices this jurisdiction requires, in a stable order.

    An unknown or unstated jurisdiction gets the union of everything we
    implement. Not knowing where a customer is, is not a reason to give them
    fewer rights -- it is a reason to assume the strictest set we can satisfy.
    """
    key = (jurisdiction or UNSPECIFIED).strip().lower()
    if key in JURISDICTION_NOTICES:
        return list(JURISDICTION_NOTICES[key])
    seen: set[str] = set()
    union: list[str] = []
    for name in sorted(JURISDICTION_NOTICES):
        for notice in JURISDICTION_NOTICES[name]:
            if notice not in seen:
                seen.add(notice)
                union.append(notice)
    return union


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
    # Which version of the published terms this order was sold under, and where
    # the customer said they are. Both travel on the deliverable.
    jurisdiction: str = UNSPECIFIED
    terms_id: str = TERMS_ID
    privacy_id: str = PRIVACY_ID


def redact(question: str) -> tuple[str, list[str]]:
    """Strip personal data out of order text. Returns (safe text, categories)."""
    found: list[str] = []
    safe = question
    for name, pattern in PERSONAL_DATA:
        safe, hits = pattern.subn(REDACTION, safe)
        if hits:
            found.append(name)
    return safe, found


def screen(question: str, *, escalating: bool = True, jurisdiction: str = UNSPECIFIED) -> Screening:
    """Decide whether this order may be worked at all, and on what terms.

    ``escalating`` only selects which sourcing disclosure applies; it does not
    affect whether the order clears. ``jurisdiction`` only adds notices --
    nothing is refused for being somewhere in particular, because refusing a
    customer for their address is a decision this company has no basis to make.
    Checks run refusal-first, so a refused order is never
    redacted-and-forwarded by accident.
    """
    jurisdiction = (jurisdiction or UNSPECIFIED).strip().lower()
    disclosures = [
        *BASE_DISCLOSURES,
        HUMAN_DISCLOSURE if escalating else AGENT_ONLY_DISCLOSURE,
        *obligations(jurisdiction),
        f"Sold under {TERMS_ID} and {PRIVACY_ID}, both published at /legal.html.",
    ]
    safe, redactions = redact(question)
    common = {
        "redactions": redactions,
        "safe_question": safe,
        "disclosures": disclosures,
        "jurisdiction": jurisdiction,
    }

    for name, pattern, why in RESTRICTED:
        if pattern.search(question):
            return Screening(cleared=False, refused_rule=name, refused_because=why, **common)

    return Screening(cleared=True, **common)
