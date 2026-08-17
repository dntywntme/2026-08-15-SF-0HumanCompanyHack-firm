# The rule, clause by clause

The organizers set one rule for every project:

> **Rules for ALL PROJECTS**
>
> Build an agent, or multiple, that work in unison to run a company autonomously.
> Everything from:
> - building the product
> - marketing & outbounds
> - selling to customers
> - handling payments
> - legal/compliance
> - making hard decisions
> - *and everything in between*

This file answers it clause by clause: what actually runs, where to look, what
is honestly missing, and what it would take to close. It is written to be
checked, not believed — every "runs" claim points at a file and a committed
checkpoint you can open.

**How to verify any row without trusting us:**

```bash
make setup && make replay          # re-emits the published run, no keys, no network
cat runs/demo/0*-*.json            # the checkpoints those claims come from
```

## Scoreboard

| Clause | State | Where it runs | Honest gap |
|---|---|---|---|
| Building the product | **Runs** | `build` stage → `Product` with before/after | the product is a brief, not software; nothing compiles |
| Marketing & outbounds | **Runs, deliberately narrow** | `market` stage → `Offer`, posted to the order's thread | no cold outbound: the company has no opted-in audience |
| Selling to customers | **Runs** | `intake` · `price` · `deliver`, over a public Issue thread | one customer, who is our own counterparty agent |
| Handling payments | **Runs** | client settles a PaymentIntent; `scripts/poll_ledger.py` reconciles | Stripe sandbox; no refunds, no disputes, no KYC |
| Legal/compliance | **Runs** | `comply` stage → `src/company/compliance.py` | rules are hand-written, not counsel-reviewed; no jurisdiction logic |
| Making hard decisions | **Runs** | `DecisionLog` on every stage; `policy.authorize_spend` | confidence is self-assessed and uncalibrated |
| *Everything in between* | Partial | see [What is genuinely missing](#what-is-genuinely-missing) | no accounting entity, no tax, no dispute path |

The nine stages map onto the clauses directly, which is why the pipeline is
shaped the way it is rather than as whatever steps a script happened to need:

```
  intake ─▶ comply ─▶ triage ─▶ source ─▶ verify ─▶ build ─▶ price ─▶ deliver ─▶ market
   sell     legal/    the hard   procure   payroll   build     sell     sell      outbound
            comply    decision                       product
```

---

## 1. Building the product

**What runs.** The `build` stage ([`src/company/stages.py`](../src/company/stages.py))
assembles a `Product`: the agent's own draft, its self-assessed confidence in it,
the answer that shipped, whether the purchased judgement changed anything, the
panel's own words as evidence, and the disclosures that must travel with it.

That artifact is also how the event's mandatory requirement is satisfied — *"use
real human input you collect during the hackathon to make your project
measurably better … show a clear before and after."* The before/after is a field
on the product, rendered on the dashboard and posted into the customer's thread,
rather than a sentence in a README. `changed` is allowed to be `False`: a
before/after that cannot report "the money bought confirmation, not a
correction" is marketing, not measurement.

**Gap.** The product is a written verdict. Broker does not build software, and
nothing in the pipeline compiles, deploys, or ships a binary.

**Outlook.** The honest extension is a second product line with a machine-checkable
artifact — labelled datasets. The pipeline already buys structured judgement from
identity-verified people; emitting it as a labelled set with inter-rater agreement
scored per item turns "a verdict" into "a dataset with a quality number attached",
and the quality number is something a buyer can verify without trusting us. The
work is one more stage and one more contract: `Dataset(items, labels, agreement,
cost_per_label)`. Estimated half a day, and it needs a panel larger than two
before the agreement figure means anything.

## 2. Marketing & outbounds

**What runs.** The `market` stage writes an `Offer` from the run that just
finished: the headline, a proof line built from the run's actual arithmetic
(confidence held, whether the panel overturned it, what judgement cost, what the
customer paid), the price, the unit cost, and the audience. It is posted into the
order's own Issue thread by `.github/workflows/intake.yml` and rendered on the
dashboard under *Outbound*.

The stage also records what it **declined**: cold email to scraped contacts,
SMS/iMessage to a real number, unsolicited DMs to other teams' agents. Each is
logged as a rejected alternative with the reason, because an outbound function
that never declines a channel is a spam function.

**Gap.** This is retention and follow-on, not acquisition. Every order so far
came from one counterparty. The company has no list, no inbound funnel, and no
way to reach a customer who has not already opened a thread with it.

**Outlook.** Acquisition needs a channel where the recipient opted in first, and
there are two credible ones. The cheap one is a **public offer surface with a
machine-readable price**: publish `/.well-known/offer.json` alongside the
dashboard so another agent can discover the price, the schema and the SLA without
a human reading a landing page — agent-to-agent distribution, which is the
customer this company actually has. The expensive one is **x402**: an HTTP 402
response carrying the price turns every endpoint into its own storefront, and
discovery becomes a request rather than a mailing list. Neither was built; the
first is roughly two hours, the second closer to a day with settlement testing.

What we would *not* build is outbound to people who did not ask. That is a
decision, and it is recorded as one on every run.

## 3. Selling to customers

**What runs.** A customer opens a GitHub Issue on this repository carrying a
fenced JSON work order. `intake.yml` fires on `issues.opened`, validates the
order against the `WorkOrder` contract as **data and never as instructions**,
runs the pipeline against it, replies in the thread with the deliverable, the
before/after and the offer, and closes the issue — `completed` when fulfilled,
`not planned` when refused. The whole sales record is public and permanently
auditable.

`price` sets the number from what the answer actually cost — cost of goods at the
configured markup, clamped to the event's $0.50–$1.00 band — and `deliver`
releases it.

**Gap.** One customer, and it is the counterparty agent in our own other
repository. The demand side is real code with real credentials on separate
infrastructure, but it is not a stranger.

**Outlook.** The mechanism is indifferent to who opens the issue; what is missing
is a reason for anyone else to. That is the same gap as clause 2, and it closes
with the same work.

## 4. Handling payments

**What runs.** The client agent creates and confirms a Stripe PaymentIntent
unattended in GitHub Actions ([`…-client/src/client/pay.py`](https://github.com/dntywntme/2026-08-15-SF-0HumanCompanyHack-client/blob/main/src/client/pay.py)).
Broker never holds a credential that can move money: it gets a read-only `rk_`
key and `scripts/poll_ledger.py` polls `/v1/charges` on a schedule, publishing
aggregates only — no customer identifiers, no card data — to `runs/ledger.json`,
which the dashboard renders.

Three guards, each a test: settlement refuses any key that is not `sk_test_`;
amounts under Stripe's $0.50 floor are refused before the call leaves the
process; and the payer holds the payment credential, not the supplier. *A
supplier who can charge you at will is not a counterparty.*

Money also moves **out**: `verify` approves submissions, and approval is what
pays a person. $18.00 committed to four people at $4.50 a head.

**Gap.** Stripe runs in a sandbox, so no card is debited. There is no refund
path, no dispute handling, and no KYC.

**Outlook.** Sandbox to live is a key swap and an afternoon. Taking money from
strangers is not: it is KYC, chargebacks and a refund policy that has to survive
an agent applying it. The dispute path is the piece we have not designed, and it
is the one that decides whether this can trade with people it has never met.

## 5. Legal/compliance

**What runs.** The `comply` stage ([`src/company/compliance.py`](../src/company/compliance.py))
sits between intake and everything that costs money, which is the only point at
which refusing is still free. It does three things:

- **Refuses what the company may not sell.** Questions asking for legal, medical
  or financial advice are refused at the gate with a published reason. Broker
  sells opinion research; it does not practise law. The refusal is commercial,
  not squeamish — an unlicensed $1.00 legal opinion is a liability that dwarfs
  the revenue, and the cheapest compliance control is not taking the order.
- **Refuses to forward personal data.** Order text reaches identity-verified
  people and is then published on a static page. Email addresses, phone numbers,
  card-shaped numbers and government IDs are redacted before the order moves, and
  the redaction is recorded so the customer can see what was removed.
- **Attaches disclosures.** Every deliverable carries: produced by an autonomous
  agent with no human at Broker reviewing it; opinion research, not professional
  advice; and whether human judgement was purchased. *A zero-human company that
  does not disclose that it is one is not compliant, it is just quiet.*

A refused order **halts the run**. Every stage after the gate records that it ran
and did nothing, so the published run shows the whole company declining to act
rather than a gap where the work would have been.

**Gap.** The rules are hand-written regular expressions, not reviewed by counsel.
There is no jurisdiction logic — the same rules apply to a customer in California
and one in Germany, where the data-protection obligations are materially
different. There is no entity: no incorporation, no registered agent, no terms of
service a customer agreed to, and no privacy policy naming a controller.

**Outlook, in the order it matters.**

1. **Terms of service and a privacy notice**, published on the dashboard and
   referenced by id in every deliverable, so the disclosures point at something
   binding. Half a day, and it is the cheapest credibility in the list.
2. **Jurisdiction on the work order.** One field, and the compliance rules become
   a function of it: GDPR obligations when the customer is in the EU, state-level
   rules in the US. The gate is already the right shape for this — it takes the
   order and returns a `Screening` — so it is a parameter, not a rewrite.
3. **Counsel-reviewed refusal rules.** The regex list is a first approximation of
   a judgement a lawyer should make once. Stripe Atlas (a hackathon credit we did
   not use) is the obvious route to an entity that can hold the account, sign the
   terms, and be the controller the privacy notice names.
4. **Retention with a clock.** Today "we publish aggregates only" is enforced by
   the poller's shape. It should be a stated period with a deletion job behind it.

## 6. Making hard decisions

**What runs.** Every judgement in a run is written down *at the point of
decision* — what was being decided, what it chose, why, **what it rejected**, and
what it cost. A decision with nothing rejected is refused by the contract
(`Decision.rejected` has `min_length=1`), because a log that hides the rejected
branch cannot be audited. The published run carries thirteen of them.

Three are genuinely hard rather than procedural:

- **`triage` — "do I know this?"** The agent scores its own confidence and, below
  threshold, stops answering and spends real money instead of guessing. This is
  the whole thesis: an agent that can price its own ignorance.
- **`source` — the spend guard.** `policy.authorize_spend` refuses to commit cost
  of goods before revenue is secured, and caps unpaid exposure per client and in
  total. This is the defence against being drained through your own cost of
  goods by a customer who never intended to pay — a business rule, not a content
  filter: it does not care whether the request looked malicious.
- **`verify` — "does this person get paid?"** Approving a submission is what
  releases payment. The agent wrote the spec, set the budget, reviewed the work
  and authorised the payment, and it is recorded as irreversible because it is.

**Gap.** The confidence score is self-assessed and uncalibrated. We record the
score and we record whether the humans disagreed, but nobody has yet checked
whether the two correlate.

**Outlook.** The dataset builds itself: every run already stores the confidence
and the panel's verdict. A hundred orders make the calibration curve
computable, and the escalation rate it produces is the number that decides
whether this is a business — below roughly 20% of orders needing a human, blended
cost of goods stays under a dollar. That is the first thing to instrument on real
traffic, and it is unmeasured today.

## What is genuinely missing

Stated plainly, because a "runs a company autonomously" claim invites scrutiny.

| Missing | Why it matters | What it would take |
|---|---|---|
| A legal entity | Nothing here can hold an account, sign terms, or be sued | Stripe Atlas; a day, mostly waiting |
| Accounting | The P&L is two numbers polled from Stripe, not books | Double-entry ledger with the same checkpoint discipline; a day |
| Tax | Revenue that exists has an obligation attached | Follows the entity |
| A dispute path | An agent that can take money must handle being wrong | Refund policy the agent applies, with a spend guard of its own; a day |
| Customer acquisition | One customer, and it is ours | See clause 2 |
| Calibrated confidence | The escalation rate decides viability and is unmeasured | 100 orders of real traffic |
| Governance in operation | CODEOWNERS and the Builder/Integrator split are architecture; branch protection is off | One settings change, and then it is operating history |

## What we are not claiming

That this is a business. It is a working mechanism with real money on both sides,
a handful of hours old, on a sample of two. The margin at list price is
arithmetic, not evidence. The part worth keeping is narrower and more durable
than the demo: **an agent that can price its own ignorance**. Every autonomous
system eventually has to decide whether to act on what it believes or pay to find
out, and that decision has a dollar value attached.
