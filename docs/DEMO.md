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

## The four panels

The UI renders from `runs/<run_id>/*.json`, so it works identically in live and
replay mode.

1. **P&L** — revenue in (Stripe), cost of goods out (Terac), margin. The company
   having unit economics is the thing no one else will show.
2. **Terac before/after** — AI-only answer beside the human-verified answer, with
   the price paid. This is a mandatory rubric item; it is a panel, not a slide.
3. **Stage timeline** — each stage with turn spend, wall-clock, checkpoint status.
4. **Incidents** — errors caught and what the company did about them. Schema
   violations, turn-cap aborts, timeouts, and any artifact blocked at the trust
   boundary.

## Two-minute video beat sheet

The platform caps the demo video at **2 minutes**. Budget:

| Time | Beat |
|---|---|
| 0:00–0:15 | The claim: a company with no employees that still has to decide what it does not know |
| 0:15–0:45 | A request arrives. The agent triages, decides it is not confident, and **buys human expertise** — show the Terac call and the price |
| 0:45–1:10 | Before/after on screen. The answer measurably improves |
| 1:10–1:30 | The customer pays. Stripe settles. **P&L updates live** |
| 1:30–1:50 | An induced failure — schema violation or timeout — is caught and handled on the incidents panel |
| 1:50–2:00 | The trust boundary: an artifact crossing firm ⟷ client blocked until a different identity approves |

Record the fallback version too. If the live capture is clean, ship that; if not,
the replay-driven capture is indistinguishable to a viewer and always works.

## Failure drills to rehearse

| Induce | Expected behaviour |
|---|---|
| Kill the network mid-run | tools return degraded values; the run completes; incidents panel shows the degradation |
| Force a malformed model response | `ValidationError` caught, retried with the error fed back, visible on the incidents panel |
| Set `--max-turns` below the pipeline's cost | run aborts before the offending stage; no partial checkpoint |
| Point a stage at a hanging endpoint | wall-clock timeout fires; harness returns promptly; stage marked degraded |

## Known limitation to disclose if asked

The per-stage timeout abandons a stage on a worker thread rather than killing it.
The harness returns promptly, which is what the wall-clock guarantee covers, but
a runaway stage keeps consuming CPU until the process exits. Subprocess isolation
is the fix. Say this plainly if a judge probes — it is a design trade-off made
under time pressure, not an oversight.
