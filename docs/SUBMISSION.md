# Submission

**Zero-Human Company Hackathon by Terac** · Humanmade, San Francisco · 2026-08-15
**Submissions lock 18:45 PDT.** Internal freeze 17:45.

| Field | Value |
|---|---|
| Team | `agentrun-inc` |
| Project | **Broker** |
| Tagline | *An agent-run company that buys human judgement, marks it up, and sells the result.* |
| Repo | <https://github.com/dntywntme/2026-08-15-SF-0HumanCompanyHack-firm> |
| Counterparty repo | <https://github.com/dntywntme/2026-08-15-SF-0HumanCompanyHack-client> |
| Live | <https://dntywntme.github.io/2026-08-15-SF-0HumanCompanyHack-firm/> |

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
| Terac study | **Live.** $9.00 committed, 2 participants, 19 applicants screened |
| Stripe | **$1.00 settled** by the client agent, unattended, in GitHub Actions |
| Decisions published | **8**, each with what it rejected and what it cost |
| Balance moved | Terac $125.00 → $116.00 |

The agent wrote the job spec, set the budget, reviewed the work, and authorised
payment. `approve_submission` is the agent deciding whether a human gets paid.

## Tracks claimed

**Best Overall Agent-Run Company** — revenue settled by an agent with no human in
the loop, real money committed to real people, and a live P&L that shows the
loss as readily as the gain.

**Best Overall Project** — a deterministic harness with turn caps, wall-clock
timeouts, checkpointed replay, an enforced spend guard, a credential-scoped
trust boundary between two repositories, and an architecture decision backed by
published measurement rather than preference (see
[`ARCHITECTURE.md`](ARCHITECTURE.md)).

**Best use of Replay** — QA run against the live site, clean report after fixes.

## Tracks deliberately not claimed

Stated because the omissions are decisions, not gaps.

- **Pioneer** — the classifier is built and pinned to an open-weight model
  (`Qwen/Qwen3-8B`), but inference returns 403 despite an active Pro plan. No
  model ran, so we do not claim a track whose criterion is that one did. The
  code degrades to a pessimistic heuristic instead of failing.
- **Linq** — the track rewards a real phone number on iMessage and we chose not
  to route inbound messages to a personal one. There is no honest partial claim.
- **Band** — our two agents already coordinate, through a public GitHub Issue
  thread that anyone can audit. Adding Band would either duplicate that channel
  (decorative, which their own criteria reject) or replace it with a room a
  judge cannot inspect.
- **Superserve** — nothing in our pipeline runs long enough to pause. Claiming
  it would be a bolt-on.
- **Render, Perflo** — dropped when the stack went GitHub-native; Perflo never
  authenticated.

## How the money actually moved

**Out to humans: real.** $9.00 of incentive committed to two people, funded by
hackathon credit rather than our own capital. That changes whose money it is,
not whether a person gets paid.

**In from customers: sandboxed.** Stripe runs in a sandbox, so the charge is a
test-mode object. The path is real and exercised end to end — the client agent
creates and confirms a PaymentIntent, the charge lands in `/v1/charges`, a
scheduled job publishes it, the P&L renders it — but no card is debited. We did
not want to claim revenue we did not earn.

## Known limitations

- The per-stage timeout abandons a stage on a worker thread rather than killing
  it; Python cannot kill a thread. The harness always returns promptly, which is
  what the wall-clock guarantee covers.
- `WorkOrder` is defined in both repositories. That is a deliberate
  single-source-of-truth violation at the trust boundary, and the two schemas
  can drift.
- The governance rails are architecture, not operating history.

## Verify it yourself

```bash
make setup && make test && make lint   # 49 tests
make replay                            # byte-identical, no network, no keys
```

`runs/demo/` is committed, so replay works on a fresh clone. The deployed
dashboard and the offline replay render the same artifact.
