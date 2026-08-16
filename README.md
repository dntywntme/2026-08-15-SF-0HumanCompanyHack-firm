# Broker — an agent-run company that employs humans

*An agent-run company and the agent that hires it — two repos, no human at either
end, and the only humans in the loop are the ones it pays for judgement.*

Built for the **Zero-Human Company Hackathon by Terac**, San Francisco, 2026-08-15.

This repo is **the firm**. It takes work in, decides whether it can do that work
alone, and when it cannot, it **buys human expertise on the open market**, marks
it up, and sells the result. Its cost of goods is other people's time; its margin
is the spread. The point is not that agents replace humans — it is that a company
run by agents still has to make a hard call about **what it does not know**, and
pay for the answer. That call, and its unit economics, are what this repo is.

## See it live

- **Dashboard:** <https://dntywntme.github.io/2026-08-15-SF-0HumanCompanyHack-firm/>
- **Ledger (JSON)** — the live P&L: <https://dntywntme.github.io/2026-08-15-SF-0HumanCompanyHack-firm/runs/ledger.json>
- **Counterparty:** [`…-client`](https://github.com/dntywntme/2026-08-15-SF-0HumanCompanyHack-client) — the assistant agent that orders, judges, and pays
- **What was submitted, and to which tracks:** [`docs/SUBMISSION.md`](docs/SUBMISSION.md)
- **Architecture, and the measurements behind it:** [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- **Diagrams and file cross-reference:** [`docs/FLOWS.md`](docs/FLOWS.md)
- **Demo runbook, and the offline fallback:** [`docs/DEMO.md`](docs/DEMO.md)
- **Picking this up next session:** [`docs/NEXT-SESSION.md`](docs/NEXT-SESSION.md)

Every figure this project claims lives in the ledger above or in
[`docs/SUBMISSION.md`](docs/SUBMISSION.md). None is restated in this file, so
none can go stale here.

## Verify it yourself

Start with replay, because it needs nothing from you. It re-emits a complete run
from committed checkpoints — no network, no API keys — so a fresh clone
reproduces the published run byte for byte.

```bash
make setup && make replay
```

`runs/demo/` is committed, which is what makes that work offline. The deployed
dashboard and the offline replay render the same artifact.

```bash
make test     # pytest
make lint     # ruff check + ruff format --check
make run      # live run -> runs/demo/   (needs keys; falls back if absent)
```

`make run` and `make replay` emit byte-identical stdout. Override the run id with
`make run RUN_ID=foo`.

```
company [--run-id ID]           run identifier (default: UTC timestamp)
        [--replay RUN_ID]       re-emit a prior run from checkpoints, calls nothing live
        [--runs-dir PATH]       where checkpoints live (default: runs/)
        [--max-turns N]         hard turn budget for the whole run (default: 12)
        [--stage-timeout S]     per-stage wall-clock budget in seconds (default: 30)
```

Every variable the code reads is documented in [`.env.example`](.env.example);
copy it to `.env`, which is gitignored.

## How it works

Six stages, each checkpointed to `runs/<id>/` as it completes:

```
  intake ──▶ triage ──▶ source ──▶ verify ──▶ price ──▶ deliver
  validate   confidence  buy the    approve    from     issue
  as data    vs 0.65     judgement  = paid     real     comment
                │                              cost
                └── above threshold? answer alone, cost of goods $0.00
```

`triage` is the whole idea in one stage: the firm scores its own confidence, and
below threshold it stops answering and escalates to a human instead of guessing.
`verify` is the sharpest frame — `approve_submission` is the agent deciding
whether a human gets paid.

### The trust boundary

The counterparty is treated as an **untrusted external party**. The two repos
share no secrets and no runner; the channel between them is a GitHub Issue
carrying a fenced JSON work order, which the firm validates as data and never as
instructions. Every artifact crossing the boundary is verified by an identity
that did not produce it.

Credential scope is what enforces it: the client's token can write Issues on this
repo and nothing else, and the firm holds a read-only `rk_` Stripe key, so it can
observe that payment arrived but never move money. **A supplier who can charge
you at will is not a counterparty.** Full trust model and enforcement:
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md#trust-model).

### Settlement, and the rails we did not use

Today the client pays the firm through **Stripe**, because this event runs on
fiat rails and real revenue is the thing being proven. In production, a
zero-trust boundary between two agents is exactly where agent-native payment
protocols belong, and we deliberately integrated neither:

- **x402** — HTTP 402 settlement, under the Linux Foundation since July 2026.
  Its `exact` and `upto` schemes let one agent pay another for a single call with
  no prior account or contract. Roughly 30 minutes to integrate; it buys nothing
  this event measures.
- **AP2** — Google's Agent Payments Protocol, donated to the FIDO Alliance in
  April 2026. Its signed `IntentMandate → CartMandate → PaymentMandate` chain
  makes autonomy *auditable*: an agent can transact human-not-present while
  proving it stayed inside a pre-authorised intent.

AP2's mandate chain is the closer fit for what we are actually building. It is
the accountability primitive our review gate approximates in software.

## Limitations

Honest accounting, because a "zero human company" claim invites scrutiny.

| Component | State |
|---|---|
| Deterministic harness: stages, turn cap, wall-clock timeout, checkpoints, replay | **Built, tested, green** |
| Error-mode instrumentation (Pydantic validation → visible recovery) | **Built** |
| Terac: buy human expertise, measure before/after | **Live** — see the ledger |
| Stripe: collect revenue | **Live in a sandbox**, labelled as such on the site |
| Trust boundary: firm ⟷ client across separate repos | Enforced by credential scope today |
| Governance rails (Builder/Integrator split) | Architecture, not operating history — branch protection is off |

The per-stage timeout runs the stage on a worker thread and abandons it on
expiry. Python cannot forcibly kill a thread, so a runaway stage keeps burning
CPU until the process exits. The harness itself always returns promptly, which is
what the wall-clock guarantee covers. Subprocess isolation is the fix if a stage
ever needs to be truly killable.

`WorkOrder` is defined in both repositories — a deliberate single-source-of-truth
violation at the trust boundary, explained from the client's side in
[its README](https://github.com/dntywntme/2026-08-15-SF-0HumanCompanyHack-client#limitations).
