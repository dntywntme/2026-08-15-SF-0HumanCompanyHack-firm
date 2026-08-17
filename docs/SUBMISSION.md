# Submission

**Zero-Human Company Hackathon by Terac** · Humanmade, San Francisco · 2026-08-15
**Submissions lock 18:45 PDT.** Internal freeze 17:45.

| Field | Value |
|---|---|
| Team | `agentrun-inc` |
| Project | **Broker** |
| Tagline | *An agent-run company and the agent that hires it — two repos, no human at either end, and the only humans in the loop are the ones it pays for judgement.* |
| Repo | [Broker, the company](https://github.com/dntywntme/2026-08-15-SF-0HumanCompanyHack-firm) |
| Counterparty repo | [the client agent that orders and pays](https://github.com/dntywntme/2026-08-15-SF-0HumanCompanyHack-client) |
| Live | [Broker's dashboard](https://dntywntme.github.io/2026-08-15-SF-0HumanCompanyHack-firm/) |

Out of band to organizers: team name + Stripe Payment Link + restricted key
(`rk_`, Balance and Charges read-only). The secret key is never shared.

## What it is

Every "AI does your X" product fails at the ten percent the agent does not know.
Broker prices that boundary. When its self-assessed confidence drops below
threshold it stops answering and **buys a real human's judgement**, marks it up,
and sells the result. Humans are cost of goods, not employees.

Its customers are other agents: personal assistants acting for their humans
under a standing mandate. **No human works at either end of the transaction.**

## What actually happened today

| | |
|---|---|
| Terac studies | **Two, both fulfilled.** $18.00 committed, 4 participants paid, 30 applicants screened |
| Stripe | **$4.00 settled** across 4 charges by the client agent, unattended, in GitHub Actions |
| Decisions published | **13**, each with what it rejected and what it cost |
| Balance moved | Terac $125.00 → $107.00 |

The agent wrote the job spec, set the budget, reviewed the work, and authorised
payment. `approve_submission` is the agent deciding whether a human gets paid.
The second study went further: the agent created *and* launched it on its own,
so the decision to spend another $9.00 on human judgement was never ours.

## The hero frame

One screen carries the argument. Revenue is real money settled by an agent; cost
of goods is real money paid to real people; the margin is negative because we
capped the price at a dollar while human judgement costs $4.50 a head.

```
    LEDGER                                  UNIT ECONOMICS
    Revenue                     $4.00       Price per verdict          $1.00
    Cost of goods             -$18.00       Model inference (open-wt)  $0.01
    ─────────────────────────────────       ───────────────────────────────
    Margin (at event pricing) -$14.00       Gross margin                 99%
    4 settled · live from Stripe
```

A company selling below cost in public, so the cost is visible.

## The call to action

> **Ask something you cannot look up.** The agent will tell you when it does not
> know — and then it will go and buy the answer from a person, for $4.50, and
> sell it to you for a dollar.

## The organizers' rule, clause by clause

The rule for every project is a list of company functions, so the pipeline is a
list of company functions. Full mapping, with what is missing and what each gap
would take: [`REQUIREMENTS.md`](REQUIREMENTS.md).

| Clause | Runs as | State |
|---|---|---|
| Building the product | `build` → `Product`, before/after as a field | **Runs** — a written verdict, not software |
| Marketing & outbounds | `market` → `Offer`, posted to the order's thread and to [`/offer.json`](https://dntywntme.github.io/2026-08-15-SF-0HumanCompanyHack-firm/offer.json) | **Runs, narrow** — no cold outbound, by decision |
| Selling to customers | `intake` · `price` · `deliver` over a public Issue | **Runs** — one customer, our counterparty |
| Handling payments | client settles a PaymentIntent; `poll_ledger.py` reconciles | **Runs** — Stripe sandbox |
| Legal/compliance | `comply` → refuse · redact · disclose; [terms and privacy](https://dntywntme.github.io/2026-08-15-SF-0HumanCompanyHack-firm/legal.html) cited by id | **Runs** — rules are ours, not counsel's; no entity behind them |
| Making hard decisions | `DecisionLog`, `authorize_spend`, the escalation gate | **Runs** — confidence uncalibrated |

Absent, and stated as absent: a legal entity, accounting, tax, a dispute path,
and any customer we did not build ourselves.

## How it works

```
  HUMAN                ASSISTANT (client repo)        BROKER (this repo)
    │
    │ calendar: "investor pitch 18:00"
    └── standing mandate ──▶ decides to buy
        ($4.50 ceiling —         │
         one expert, enforced    │
         in code)                │
                                 ├── GitHub Issue ────▶ intake    validate
                                 │   (fenced JSON)      comply    may we sell it?
                                 │                      triage    confidence 0.31
                                 │                        │
                                 │                 ┌──────┴──────┐
                                 │                 │ "I cannot   │
                                 │                 │  know this" │
                                 │                 └──────┬──────┘
                                 │                      source ──▶ TERAC ──▶ 🧑🧑
                                 │                      verify   approve = PAID
                                 │                      build    before / after
                                 │                      price    from real cost
                                 │  ◀── issue comment ── deliver
                                 │  ◀── the offer ────── market   the next order
                                 │
                                 ├── PaymentIntent ──▶ STRIPE
                                 │                        │
                                 │                   poll_ledger.py
                                 ▼                        ▼
                          client site  ◀── reconciles ── ledger.json ──▶ P&L
```

Both sides publish. The client asserts it paid; Broker independently reports
receiving it; the two pages agree without sharing a database.

```
  TRUST          Broker ⟷ client     separate repos, separate credentials
                 client token  = Issues:write on the Broker repo only
                 client key    = sk_test_ (settles)
                 Broker key    = rk_      (reads only)
  A supplier who can charge you at will is not a counterparty.
```

## Tracks claimed

**Best Overall Agent-Run Company** — revenue settled by an agent with no human in
the loop (in a Stripe sandbox, labelled as such on the site), real money paid to
real people through Terac, and a live P&L that shows the loss as readily as the
gain.

**Best Overall Project** — a deterministic harness with turn caps, wall-clock
timeouts, checkpointed replay, an enforced spend guard, a credential-scoped
trust boundary between two repositories, and an architecture decision backed by
published measurement rather than preference (see
[`ARCHITECTURE.md`](ARCHITECTURE.md)).

**Best use of Replay** — QA run against the live site, clean report after fixes.

## Tracks deliberately not claimed

Stated because the omissions are decisions, not gaps.

- **Pioneer** — the classifier is built and pinned to an open-weight model
  (`Qwen/Qwen3-8B`), but every inference call returned **404**, with a valid API
  key and a redeemed voucher on the account. We could not get a single
  completion back, so we do not claim a track whose criterion is that an
  open-weight model ran. The code degrades to a pessimistic heuristic instead of
  failing, which is why the pipeline still completes without it.
- **Linq** — the track rewards a real phone number on iMessage and we chose not
  to route inbound messages to a personal one. There is no honest partial claim.
- **Band** — we ran out of time to integrate it properly, and a partial
  integration would have failed their own bar: *"remove the room and the app
  should break, not keep working the same way."* What we do instead is
  coordinate the two agents through a **public GitHub Issue thread** — the
  client opens a work order as fenced JSON, Broker replies as a comment.
  Every message is permanently auditable by anyone, with no vendor in the path.
  Band would have been the better-instrumented version of that; the audit trail
  is the version we could ship and verify today.
- **Superserve** — same constraint, and nothing in our pipeline runs long enough
  to pause. What we do instead is degrade in three labelled tiers when a
  long-running dependency is slow: live Terac, then a human override file, then
  the recorded floor. The checkpoint always says which tier answered. Superserve
  would let us pause and resume rather than degrade, which is strictly better,
  and it is the first thing we would add with another day.
- **Render, Perflo** — dropped when the stack went GitHub-native; Perflo never
  authenticated.

## How the money actually moved

**Out to humans: real.** $18.00 of incentive committed across two studies to
four people at $4.50 a head, funded by hackathon credit rather than our own
capital. That changes whose money it is, not whether a person gets paid.

**In from customers: sandboxed.** Stripe runs in a sandbox, so the charge is a
test-mode object. The path is real and exercised end to end — the client agent
creates and confirms a PaymentIntent, the charge lands in `/v1/charges`, a
scheduled job publishes it, the P&L renders it — but no card is debited. We did
not want to claim revenue we did not earn.

## What it would take to run this for real

Nothing here is speculative; each item is a known gap with a known fix.

**Unit economics.** At list price the shape works: one expert response costs
$4.50, a three-response verdict costs $13.50, and $39 leaves a 65% gross margin
— in the range research panels already charge. The demo runs at a loss only
because we capped the price at $1 for the event. The number that decides
viability is the **escalation rate**: below roughly 20% of orders needing a
human, the blended cost of goods stays under a dollar. We have not measured it
on real traffic, and that is the first thing we would instrument.

**The three things missing for production.**

1. *Confidence has to be earned.* Today the escalation decision comes from a
   self-assessed score with a heuristic fallback. It needs calibration against
   outcomes — did the humans actually disagree when confidence was low? Every
   run already records both, so the dataset builds itself.
2. *Terac's turnaround sets the product.* Recruitment plus screening took ~40
   minutes for two responses. That rules out synchronous use and rules in
   asynchronous work: overnight verdicts, batched panels, standing questions.
3. *Payments need a real account.* Sandbox to live is a key swap; taking money
   from strangers is KYC, disputes, and refunds. The dispute path is the one we
   have not built.

**Where the revenue would come from.** Not from selling to consumers one dollar
at a time. The buyer is another agent with a budget: assistants that need a
defensible answer, tools that need a human check before acting, pipelines that
need labelled judgement on demand. Per-call pricing with a monthly floor is the
obvious shape, and the marketplace analogues are established.

**What we are not claiming.** That this is a business today. It is a working
mechanism with real money on both sides, roughly eight hours old, on a sample
of two. The margin at list price is arithmetic, not evidence, and the escalation
rate that decides everything is unmeasured.

**The part worth keeping.** An agent that can price its own ignorance is useful
well beyond this product. Every autonomous system eventually needs to decide
whether to act on what it believes or pay to find out, and that decision has a
dollar value attached. That is the piece we would build on.

## Known limitations

- The per-stage timeout abandons a stage on a worker thread rather than killing
  it; Python cannot kill a thread. The harness always returns promptly, which is
  what the wall-clock guarantee covers.
- `WorkOrder` is defined in both repositories. That is a deliberate
  single-source-of-truth violation at the trust boundary, and the two schemas
  can drift.
- The governance rails are architecture, not operating history.
- The compliance rules are hand-written regular expressions, not reviewed by
  counsel, and carry no jurisdiction logic.
- Outbound reaches the customer already in the thread and nobody else. That is a
  recorded decision, but it is also the reason there is one customer.

## Where everything lives

| | |
|---|---|
| The organizers' rule, clause by clause, with the gaps | [`docs/REQUIREMENTS.md`](REQUIREMENTS.md) |
| Architecture, and the measurements behind it | [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) |
| The compliance gate | [`src/company/compliance.py`](../src/company/compliance.py) |
| Full diagrams + file-by-file cross-reference | [`docs/FLOWS.md`](FLOWS.md) |
| Demo runbook and the offline fallback | [`docs/DEMO.md`](DEMO.md) |
| Sponsor rules and verbatim track criteria | [`docs/SPONSORS.md`](SPONSORS.md) |
| The spine | [`src/company/harness.py`](../src/company/harness.py) |
| The nine stages | [`src/company/stages.py`](../src/company/stages.py) |
| The spend guard | [`src/company/policy.py`](../src/company/policy.py) |
| Every decision, with what it rejected | [`src/company/decisions.py`](../src/company/decisions.py) |
| Client agent, channel, and payment | [`…-client/src/client/`](https://github.com/dntywntme/2026-08-15-SF-0HumanCompanyHack-client/tree/main/src/client) |
| Live client surface | [what the client agent did](https://dntywntme.github.io/2026-08-15-SF-0HumanCompanyHack-client/) |

## Verify it yourself

```bash
make setup && make test && make lint   # 95 tests here, 40 in the client repo
make replay                            # byte-identical, no network, no keys
make e2e                               # 18 viewport/page combos, both sites
```

`runs/demo/` is committed, so replay works on a fresh clone. The deployed
dashboard and the offline replay render the same artifact.
