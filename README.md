# Broker — an agent-run company that employs humans

Built for the **Zero-Human Company Hackathon by Terac**, San Francisco, 2026-08-15.

Broker is a company with no human employees. It takes work in, decides whether it
can do that work alone, and when it cannot, it **buys human expertise on the open
market**, marks it up, and sells the result. Its cost of goods is other people's
time. Its margin is the spread.

The point is not that agents replace humans. It is that a company run by agents
still has to **make a hard call about what it does not know** — and pay for the
answer. That call, and its unit economics, are what this repo demonstrates.

- **Live dashboard:** <https://dntywntme.github.io/2026-08-15-SF-0HumanCompanyHack-firm/>
- **Live ledger (JSON):** <https://dntywntme.github.io/2026-08-15-SF-0HumanCompanyHack-firm/runs/ledger.json>
- **Counterparty repo:** [`…-client`](https://github.com/dntywntme/2026-08-15-SF-0HumanCompanyHack-client) — the assistant agent that orders, judges, and pays
- **Architecture and the evidence behind it:** [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- **Diagrams and file cross-reference:** [`docs/FLOWS.md`](docs/FLOWS.md)
- **What was submitted, and to which tracks:** [`docs/SUBMISSION.md`](docs/SUBMISSION.md)
- **How to run the demo, including the offline fallback:** [`docs/DEMO.md`](docs/DEMO.md)

## Quickstart

```bash
make setup    # uv sync (Python 3.12)
make test     # pytest
make lint     # ruff check + ruff format --check
make run      # live run -> runs/demo/
make replay   # re-emit runs/demo/ from checkpoints, calls nothing live
```

`make run` and `make replay` emit byte-identical stdout. Override the run id with
`make run RUN_ID=foo`.

## Status

Honest accounting, because a "zero human company" claim invites scrutiny:

| Component | State |
|---|---|
| Deterministic harness: stages, turn cap, wall-clock timeout, checkpoints, replay | **Built, tested, green** |
| Error-mode instrumentation (Pydantic validation → visible recovery) | In progress |
| Terac MCP: buy human expertise, measure before/after | In progress |
| Stripe: collect real revenue | In progress |
| Trust boundary: firm ⟷ client across separate repos | Enforced by credential scope today |

## Two actors

This repo is **the firm**. Its counterparty lives in a separate repository,
[`2026-08-15-SF-0HumanCompanyHack-client`](https://github.com/dntywntme/2026-08-15-SF-0HumanCompanyHack-client),
and is treated as an untrusted external party. They share no secrets and no
runner; the only channel between them is a GitHub Issue carrying a fenced JSON
work order, which the firm validates as data and never as instructions.

Every artifact crossing a boundary is verified by an identity that did not
produce it. Full trust model, enforcement mechanisms, and the evidence behind
them: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md#trust-model).

## Settlement across the trust boundary

Today the client pays the firm through **Stripe**, because this event runs on
fiat rails and real revenue is the thing being proven.

In production, a zero-trust boundary between two agents is exactly where
agent-native payment protocols belong, and we deliberately did **not** integrate
either of these:

- **x402** — HTTP 402 settlement, under the Linux Foundation since July 2026.
  Its `exact` and `upto` schemes let one agent pay another for a single call
  with no prior account or contract. Roughly 30 minutes to integrate; it buys
  nothing this event measures.
- **AP2** — Google's Agent Payments Protocol, donated to the FIDO Alliance in
  April 2026. Its signed `IntentMandate → CartMandate → PaymentMandate` chain
  makes autonomy *auditable*: an agent can transact human-not-present while
  proving it stayed inside a pre-authorised intent.

AP2's mandate chain is the closer fit for what we are actually building. It is
the accountability primitive our review gate approximates in software.

## Known limitation

The per-stage timeout runs the stage on a worker thread and abandons it on
expiry. Python cannot forcibly kill a thread, so a runaway stage keeps burning
CPU until the process exits. The harness itself always returns promptly, which
is what the wall-clock guarantee covers. Subprocess isolation is the fix if a
stage ever needs to be truly killable.
