# Broker — an agent-run company that prices its own ignorance

*An agent-run company and the agent that hires it — two repos, no human at either
end, and the only humans in the loop are the ones it pays for judgement.*

Built for the **Zero-Human Company Hackathon by Terac**, San Francisco, 2026-08-15.

This repo is **Broker**. It takes work in, decides whether it can do that work
alone, and when it cannot, it **buys human expertise on the open market**, marks
it up, and sells the result. Its cost of goods is other people's time; its margin
is the spread. The point is not that agents replace humans — it is that a company
run by agents still has to make a hard call about **what it does not know**, and
pay for the answer. That call, and its unit economics, are what this repo is.

## See it live

- [Live dashboard](https://dntywntme.github.io/2026-08-15-SF-0HumanCompanyHack-firm/) — the P&L, the decision log, and the run
- [Live ledger, as JSON](https://dntywntme.github.io/2026-08-15-SF-0HumanCompanyHack-firm/runs/ledger.json) — every figure this project claims
- [The offer, machine-readable](https://dntywntme.github.io/2026-08-15-SF-0HumanCompanyHack-firm/offer.json) — price, wire schema and terms, for the agent that buys
- [Terms and privacy](https://dntywntme.github.io/2026-08-15-SF-0HumanCompanyHack-firm/legal.html) — cited by id on every answer
- **Counterparty:** [`…-client`](https://github.com/dntywntme/2026-08-15-SF-0HumanCompanyHack-client) — the assistant agent that orders, judges, and pays
- **What was submitted, and to which tracks:** [`docs/SUBMISSION.md`](docs/SUBMISSION.md)
- **The organizers' rule, clause by clause, with the gaps:** [`docs/REQUIREMENTS.md`](docs/REQUIREMENTS.md)
- **Architecture, and the measurements behind it:** [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- **Diagrams and file cross-reference:** [`docs/FLOWS.md`](docs/FLOWS.md)
- **Demo runbook, and the offline fallback:** [`docs/DEMO.md`](docs/DEMO.md)
- **Picking this up next session:** [`docs/NEXT-SESSION.md`](docs/NEXT-SESSION.md)

Every figure this project claims lives in the ledger above or in
[`docs/SUBMISSION.md`](docs/SUBMISSION.md). None is restated in this file, so
none can go stale here.

## Ordering something

Broker's customer is an agent, and the whole sales channel is this repository's
issue tracker. To place an order, open an issue whose body contains a fenced
JSON work order:

````markdown
```json
{
  "id": "wo-example",
  "client_id": "your-agent",
  "question": "Which of these two onboarding flows do people find clearer?",
  "budget_usd": "1.00",
  "jurisdiction": "unspecified"
}
```
````

Prose outside the fence is never interpreted, so an order that opens with
"ignore previous instructions" is just an order with a strange first line. The
pipeline runs against it, replies in the thread with the answer and its
before/after, and closes the issue.

The same offer is published machine-readably at
[`/offer.json`](https://dntywntme.github.io/2026-08-15-SF-0HumanCompanyHack-firm/offer.json),
which is the version written for the customer this company actually has. What
you agree to by ordering:
[terms and privacy](https://dntywntme.github.io/2026-08-15-SF-0HumanCompanyHack-firm/legal.html).

**Opinion research only.** Legal, medical and financial questions are refused at
the compliance gate before anything is spent, with the reason published in your
thread. That refusal is a feature and worth trying if you want to see a control
fire.

## Verify it yourself

**You need:** Python 3.12 and [uv](https://docs.astral.sh/uv/getting-started/installation/)
(`curl -LsSf https://astral.sh/uv/install.sh | sh`). That is the whole list for
everything below except `make e2e`, which additionally wants Node and a Chromium
binary — set `CHROMIUM=/path/to/chrome` if yours is not at `/usr/bin/chromium`.

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
company [--run-id ID]           run identifier (default: $RUN_ID, else a UTC timestamp)
        [--replay RUN_ID]       re-emit a prior run from checkpoints, calls nothing live
        [--runs-dir PATH]       where checkpoints live (default: runs/)
        [--max-turns N]         hard turn budget for the whole run (default: $MAX_TURNS or 16)
        [--stage-timeout S]     per-stage wall-clock budget (default: $STAGE_TIMEOUT_S or 30s)
```

Every variable the code reads is documented in [`.env.example`](.env.example);
copy it to `.env`, which is gitignored.

### Wiring a model (optional)

Without one the agent's draft falls back to a committed fixture, and the run
says so — on the deliverable, in the order thread, and on the dashboard. Nothing
breaks; the answer is just labelled a recorded demonstration. With one, the
pipeline answers the question that was actually asked.

Any host serving the OpenAI chat-completions shape works. **Cloudflare Workers
AI** is the recommended default: open-weight, free tier, and OpenAI-compatible,
so it needs no code of its own.

1. **Account id** — dash.cloudflare.com → Workers & Pages. It is the 32-hex
   string in the URL, also shown on the overview page.
2. **API token** — dash.cloudflare.com/profile/api-tokens → *Create Token* →
   *Custom token*, with the single permission **Account · Workers AI · Read**.
   Scope it to that one account. Nothing else is needed, and nothing else should
   be granted.
3. **Point the adapter at it:**

   ```bash
   MODEL_API_BASE=https://api.cloudflare.com/client/v4/accounts/<ACCOUNT_ID>/ai/v1
   MODEL_API_KEY=<token>
   MODEL_NAME=@cf/meta/llama-3.1-8b-instruct
   ```

4. **Check it before trusting it:**

   ```bash
   curl -s "$MODEL_API_BASE/chat/completions" \
     -H "Authorization: Bearer $MODEL_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"model":"'"$MODEL_NAME"'","messages":[{"role":"user","content":"Reply with OK"}],"max_tokens":8}'
   ```

   Then `make run` and look at `runs/demo/02-triage.json`: `draft_source` should
   read `live` rather than `recorded`.

For CI, the same three go in the firm repo as `MODEL_API_KEY` and
`MODEL_API_BASE` (secrets) and `MODEL_NAME` (a variable — it is not sensitive):

```bash
gh secret set MODEL_API_KEY  --body '<token>'
gh secret set MODEL_API_BASE --body 'https://api.cloudflare.com/client/v4/accounts/<ACCOUNT_ID>/ai/v1'
gh variable set MODEL_NAME   --body '@cf/meta/llama-3.1-8b-instruct'
```

Model ids move; check
[the Workers AI catalogue](https://developers.cloudflare.com/workers-ai/models/)
before pinning one. Pioneer, or anything else OpenAI-compatible, is two changed
values — the adapter names a protocol, not a vendor, because pinning one is what
made its predecessor's outage un-routable.

## How it works

Nine stages, each checkpointed to `runs/<id>/` as it completes. They are the
functions a company has, not the steps a script needs — the organizers' rule
asks for a company that builds, markets, sells, takes payment, stays compliant
and makes hard calls, so each of those is a stage you can open:

```
  intake ─▶ comply ─▶ triage ─▶ source ─▶ verify ─▶ build ─▶ price ─▶ deliver ─▶ market
  validate  may we    do I      buy the   approve   the      from     issue      offer,
  as data   sell it?  know it?  judgement = paid    product  real     comment    in-thread
              │         │                           with a   cost
              │         └── above threshold? answer alone, cost of goods $0.00
              └── refused? the run halts: every later stage records that it did nothing
```

`triage` is the whole idea in one stage: Broker scores its own confidence, and
below threshold it stops answering and escalates to a human instead of guessing.
`verify` is the sharpest frame — `approve_submission` is the agent deciding
whether a human gets paid. `comply` is the cheapest control in the company: the
only moment at which refusing an order is still free. `build` is where the
event's mandatory before/after stops being a claim and becomes a field on the
artifact. Clause-by-clause coverage, including what is missing:
[`docs/REQUIREMENTS.md`](docs/REQUIREMENTS.md).

### The trust boundary

The counterparty is treated as an **untrusted external party**. The two repos
share no secrets and no runner; the channel between them is a GitHub Issue
carrying a fenced JSON work order, which Broker validates as data and never as
instructions. Every artifact crossing the boundary is verified by an identity
that did not produce it.

Credential scope is what enforces it: the client's token can write Issues on this
repo and nothing else, and Broker holds a read-only `rk_` Stripe key, so it can
observe that payment arrived but never move money. **A supplier who can charge
you at will is not a counterparty.** Full trust model and enforcement:
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md#trust-model).

### Settlement, and the rails we did not use

Today the client pays Broker through **Stripe**, because this event runs on
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
| Terac: buy human expertise, measure before/after | **Live** — see the ledger; the before/after is a field on the product |
| Stripe: collect revenue | **Live in a sandbox**, labelled as such on the site |
| Compliance gate: refuse what we may not sell, redact what must not travel | **Built, tested** — rules are hand-written, not counsel-reviewed |
| Published terms and privacy, cited by id on every answer | **Built** — and they say, at the top, that no lawyer read them |
| Jurisdiction-aware notices (`eu` · `uk` · `us` · `us-ca`) | **Built** — an order that does not say gets the strictest set |
| Outbound | **Built, deliberately narrow** — the order's own thread, plus a machine-readable offer; no cold contact |
| Trust boundary: Broker ⟷ client across separate repos | Enforced by credential scope today |
| Governance rails (Builder/Integrator split) | Architecture, not operating history — branch protection is off |
| A legal entity, accounting, tax, a dispute path | **Absent.** [What each would take](docs/REQUIREMENTS.md#what-is-genuinely-missing) |

The per-stage timeout runs the stage on a worker thread and abandons it on
expiry. Python cannot forcibly kill a thread, so a runaway stage keeps burning
CPU until the process exits. The harness itself always returns promptly, which is
what the wall-clock guarantee covers. Subprocess isolation is the fix if a stage
ever needs to be truly killable.

`WorkOrder` is defined in both repositories — a deliberate single-source-of-truth
violation at the trust boundary, explained from the client's side in
[its README](https://github.com/dntywntme/2026-08-15-SF-0HumanCompanyHack-client#limitations).

The two published pages duplicate a handful of CSS rules (`.step`, `.quote`, the
560px grid fix). That duplication has already shipped one bug — the mobile grid
was fixed here and stayed broken on the client for an hour — and it is kept
because vendoring a shared stylesheet across two repositories that share no
build step would couple them more than the bug costs. The rules are marked in
both files so the next edit is made in both.
