# Architecture, data flow, and user flow

Companion to [`ARCHITECTURE.md`](ARCHITECTURE.md), which carries the reasoning.
This file carries the picture and the file-by-file cross-reference.

Repositories:

- **Broker** — [`dntywntme/2026-08-15-SF-0HumanCompanyHack-firm`](https://github.com/dntywntme/2026-08-15-SF-0HumanCompanyHack-firm) (this one)
- **client** — [`dntywntme/2026-08-15-SF-0HumanCompanyHack-client`](https://github.com/dntywntme/2026-08-15-SF-0HumanCompanyHack-client)

Live surfaces:

- [Dashboard](https://dntywntme.github.io/2026-08-15-SF-0HumanCompanyHack-firm/)
- [Ledger, as JSON](https://dntywntme.github.io/2026-08-15-SF-0HumanCompanyHack-firm/runs/ledger.json)
- [Participant task view](https://dntywntme.github.io/2026-08-15-SF-0HumanCompanyHack-firm/?submissionId=demo&taskId=t1)

## 1. Architecture

```
 ┌── CLIENT REPO ── an assistant acting for a human ──────────────────────────┐
 │                                                                           │
 │  src/client/agent.py       compose · evaluate · decide to pay             │
 │  src/client/contracts.py   its OWN copy of the wire models (not imported) │
 │  src/client/channel.py     GitHub Issues transport                        │
 │  src/client/pay.py         PaymentIntent settlement · sk_test_ only       │
 │  .github/workflows/pay.yml settles unattended                             │
 └───────────┬───────────────────────────────────────────────▲───────────────┘
             │ Issue: fenced JSON work order                  │ issue comment
             │ token scope = Issues:write, nothing else       │ = deliverable
             ▼                                                │
 ┌── BROKER REPO ── the company ─────────────────────────────┴───────────────┐
 │                                                                           │
 │  .github/workflows/ci.yml       lint · test · offline replay              │
 │  .github/workflows/ledger.yml   poll Stripe · commit · publish the site   │
 │  .github/workflows/pages.yml    deploy web/ + runs/ to GitHub Pages       │
 │                                                                           │
 │  src/company/harness.py     the spine: stages, turn cap, timeout, replay  │
 │  src/company/models.py      WorkOrder · Draft · HumanInput · Product ·    │
 │                             Offer · Deliverable                           │
 │  src/company/compliance.py  what we may sell, and what must never travel  │
 │  src/company/policy.py      the spend guard — refuses cost of goods       │
 │  src/company/decisions.py   every judgement, with what it rejected        │
 │  src/company/incidents.py   every caught failure, with its recovery       │
 │  src/company/stages.py      intake → comply → triage → source → verify →  │
 │                             build → price → deliver → market              │
 │  src/company/adapters/http.py      https only, checked before opening     │
 │  src/company/adapters/pioneer.py   confidence on an open-weight model     │
 │  src/company/adapters/terac.py     three sourcing tiers, each labelled    │
 │  scripts/poll_ledger.py     rk_ read-only · publishes aggregates only     │
 │  web/index.html             storefront · task view · P&L · before/after · │
 │                             decisions · outbound                          │
 └────┬──────────────┬───────────────────┬──────────────────┬────────────────┘
      │              │                   │                  │
      ▼              ▼                   ▼                  ▼
  ┌────────┐   ┌───────────┐      ┌────────────┐    ┌──────────────┐
  │ TERAC  │   │  PIONEER  │      │   STRIPE   │    │ GITHUB PAGES │
  │ MCP    │   │ Qwen3-8B  │      │ rk_ read   │    │ static, holds│
  │ humans │   │ confidence│      │ only       │    │ NO secrets   │
  └────────┘   └───────────┘      └────────────┘    └──────────────┘
   cost of      the buy/don't-      revenue in       the published
   goods        buy decision                          artifact
```

Nothing receives a webhook. A static host cannot, and Terac has no webhook API
at all, so **everything polls** — which is also why a pausable sandbox is an
honest fit rather than a bolt-on.

## 2. Data flow

```
  WorkOrder ──▶ Screening ──▶ Draft ──▶ [confidence < threshold?] ──▶ HumanInput
  (pydantic)   MAY WE SELL   (+conf)          THE DECISION            (real money)
      │         THIS AT ALL      │                   │                      │
      │            │             │              ┌────┴────┐                 │
      │      no ───┘             │        no ───┘         └─── yes          │
      │      HALT. every later   │     answer alone     ┌──────────────────▼───────────┐
      │      stage records that  │     $0.01 inference  │ policy.authorize_spend()     │
      │      it did nothing      │                      │ · payment before cost of     │
      │                          │                      │   goods                      │
      │                          │                      │ · per-client exposure cap    │
      │                          │                      │ · total cap                  │
      │                          │                      └──────────────────────────────┘
      │                          │                                  │
      │                          └──────────────┬───────────────────┘
      │                                         ▼
      │                            Product ──▶ Deliverable ──▶ Offer
      │                          before/after    (+margin)     outbound, in
      │                          IS THE ARTIFACT               the order's thread
      ▼           ▼                              ▼                          ▼
  ┌───────────────────────────────────────────────────────────────────────────┐
  │ every stage    ─▶ runs/<id>/NN-stage.json ─▶ --replay  byte-identical      │
  │ every decision ─▶ DecisionLog             ─▶ Decisions panel              │
  │ every failure  ─▶ IncidentLog             ─▶ Incidents panel              │
  │ every charge   ─▶ runs/ledger.json        ─▶ P&L panel                    │
  └───────────────────────────────────────────────────────────────────────────┘

  SECRET BOUNDARY
    GitHub Actions secrets ═══╗  server-side only
      Broker: STRIPE_RESTRICTED_KEY (rk_, read)      ║
      client: CLIENT_STRIPE_KEY     (sk_test_, pay)  ╠══▶ aggregates ──▶ Pages
                                                     ║    no customer ids,
                                                     ╝    no card data
```

## 3. User flow

```
  HUMAN                ASSISTANT (client)          BROKER               PANEL
    │
    │ calendar: "investor pitch 18:00"
    │
    └──── standing mandate ───▶ decides to buy a verdict
                                     │
                                     ├─ opens Issue ─────▶ intake   validate
                                     │                     comply   may we sell it?
                                     │                              redact · disclose
                                     │                     triage   draft + confidence
                                     │                              │
                                     │                     ┌────────┴────────┐
                                     │                     │ "I cannot know  │
                                     │                     │  consumer       │
                                     │                     │  taste" → BUY   │
                                     │                     └────────┬────────┘
                                     │                     source ──┴──▶ Terac ──▶ 🧑
                                     │                                            🧑
                                     │                     verify   human vs draft
                                     │                     ┌──────────────────────┐
                                     │                     │ approve_submission   │
                                     │                     │ = THE HUMAN IS PAID  │
                                     │                     └──────────────────────┘
                                     │                     build    before / after
                                     │                     price    from real cost
                                     │  ◀── deliverable ── deliver
                                     │  ◀── the offer ──── market   the next order,
                                     │                              same thread
                                     ├─ evaluates: acceptable?
                                     ├─ settles PaymentIntent ──▶ Stripe
                                     │                              │
                                     │                        poll_ledger.py
                                     │                              ▼
    ◀──── assistant reports ─────────┘                        revenue $4.00
                                                              live on the P&L
```

The sharpest frame for a reader: **`approve_submission` is the agent deciding
whether a human gets paid.** It writes the job spec, sets the budget, reviews
the work, and authorises payroll — and no human reviewed any of it.
