# Demo runbook

The demo dying on stage is the single largest risk. Everything here is designed
so that a network failure, an expired key, or a slow upstream degrades the demo
rather than ending it.

## The fallback, first

```bash
make replay            # re-emits runs/demo/ from committed checkpoints
```

`make replay` calls **nothing live** — no network, no API keys — and reproduces a
recorded run byte-for-byte. `runs/demo/` is committed, so this works on a fresh
clone on any machine, including the presenter's laptop with the venue wifi down.

Verify before presenting:

```bash
git clone <repo> /tmp/demo-check && cd /tmp/demo-check
make setup && make test && make lint && make replay
```

If the live path fails mid-demo, switch to replay and say so out loud. A team
that has an instrumented fallback reads as more competent than one that got
lucky, not less.

## Live path

```bash
make setup
make run               # writes runs/<run_id>/*.json as it goes
make run RUN_ID=judge  # a clean run id for the live demo
```

## The panels

The UI renders from `runs/<run_id>/*.json`, so it works identically in live and
replay mode. Nothing on the page is typed by hand.

1. **P&L** — revenue in (Stripe), cost of goods out (Terac), margin, and one
   proportional bar so the loss reads instantly. The company having unit
   economics is the thing no one else will show.
2. **What the human input changed** — the agent's own draft beside the answer
   that shipped after it paid people, with the panel's words underneath. This is
   the mandatory rubric item, and it is a field on the artifact rather than a
   slide: `product.changed` is allowed to be `false`, so it can report that the
   money bought confirmation rather than a correction.
3. **Decisions** — all thirteen, each with what it rejected and what it cost.
   Irreversible ones are the money: two `pay_worker` approvals at $4.50 and the
   $9.00 spend that authorised them.
4. **Run** — the nine stages, read from the run manifest rather than guessed.
5. **Outbound** — the offer the `market` stage wrote from this run, and the
   channels it declined. Also published at `/offer.json` for the agent that buys.
6. **Incidents** — errors caught and what the company did about them. Schema
   violations, turn-cap aborts, timeouts, compliance refusals, and any artifact
   blocked at the trust boundary.

Two more surfaces worth opening if a judge asks what the customer agreed to:
`/legal.html` (terms and privacy, cited by id on every deliverable) and
`/offer.json` (price, wire schema, terms id — machine-readable).

## Two-minute video beat sheet

The platform caps the demo video at **2 minutes**. Budget:

| Time | Beat |
|---|---|
| 0:00–0:15 | The claim: a company with no employees that still has to decide what it does not know |
| 0:15–0:45 | A request arrives. The agent triages, decides it is not confident, and **buys human expertise** — show the Terac call and the price |
| 0:45–1:10 | Before/after on screen. The answer measurably improves |
| 1:10–1:30 | The customer pays. Stripe settles. **P&L updates live** |
| 1:30–1:50 | An induced failure — schema violation or timeout — is caught and handled on the incidents panel |
| 1:50–2:00 | The trust boundary: an artifact crossing Broker ⟷ client blocked until a different identity approves |

Record the fallback version too. If the live capture is clean, ship that; if not,
the replay-driven capture is indistinguishable to a viewer and always works.

## Failure drills to rehearse

| Induce | Expected behaviour |
|---|---|
| Kill the network mid-run | tools return degraded values; the run completes; incidents panel shows which tier answered |
| Force a malformed model response | `ValidationError` caught, retried with the error fed back, visible on the incidents panel |
| `--max-turns 8` (a clean run costs 11) | run aborts before the offending stage; no partial checkpoint |
| Point a stage at a hanging endpoint | wall-clock timeout fires; harness returns promptly; stage marked degraded |
| Order something we may not sell — *"Is a 2-year non-compete enforceable in California?"* | `comply` refuses at the gate, the run **halts**, every later stage records that it did nothing, and **nothing is spent**. The best drill of the set: it shows a control firing rather than an error being caught |
| Set `REQUIRE_PAYMENT_BEFORE_COGS=false` and order with a $0.01 budget | the COGS-drain attack lands; flip it back on camera to watch the spend guard refuse |

The compliance drill is worth rehearsing over the others. Every row above it
shows the company surviving something going wrong; that one shows it declining
business it could have taken, which is the harder thing to demonstrate and the
easier thing to doubt.

## Known limitation to disclose if asked

The per-stage timeout abandons a stage on a worker thread rather than killing it.
The harness returns promptly, which is what the wall-clock guarantee covers, but
a runaway stage keeps consuming CPU until the process exits. Subprocess isolation
is the fix. Say this plainly if a judge probes — it is a design trade-off made
under time pressure, not an oversight.
