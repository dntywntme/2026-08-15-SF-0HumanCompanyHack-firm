# Next session

Updated 2026-08-17, after a polish pass across both repositories. The original
handoff was written at the end of the hackathon build (2026-08-15 17:40 PDT);
everything below is verified against the state at the later date. Check it still
holds before acting.

## Where things stand

| | |
|---|---|
| Broker site | [Broker's dashboard](https://dntywntme.github.io/2026-08-15-SF-0HumanCompanyHack-firm/) |
| Client site | [the client's surface](https://dntywntme.github.io/2026-08-15-SF-0HumanCompanyHack-client/) |
| Terac | Two studies **fulfilled** (`e39vxoxasopgrblq6tchgf68`, `w4pxs0mrufeqo9kzuruzsvui`) — $18.00 paid to 4 people at $4.50 CPI, 30 screened (22 + 8), balance $125 → $107. Study #2 was created *and* launched by the agent |
| Stripe | $4.00 settled across 4 charges by the client agent, unattended, **sandbox** (`livemode: false`) |
| Pipeline | **Nine stages**: intake · comply · triage · source · verify · build · price · deliver · market |
| Tests | Broker 95, client 40, ruff clean both |
| Replay | Byte-identical on the recorded tier with no keys, and now asserted by a test rather than diffed by hand |
| CI | ci · pages · ledger · run · intake (Broker), **ci** · pages · pay (client) |

Working copy note: both repos' `origin` now points at **dntywntme**. The
scheduled `run` and `ledger` jobs commit to `main` hourly and every five
minutes, so **always `git pull --rebase` before pushing** — your local `main`
goes stale fast.

## What this pass closed

Struck from the previous handoff, with where it went:

- **The organizers' rule was only half covered.** The pipeline did the selling,
  the buying and the hard decisions; it did no product-building, no marketing
  and no compliance. Three stages now exist for those — `comply`, `build`,
  `market` — and the whole rule is mapped clause by clause in
  [`REQUIREMENTS.md`](REQUIREMENTS.md), including what is still missing.
- **A refused order was still worked.** `intake` rejected a malformed order and
  every stage after it carried on: drafted an answer, bought human judgement,
  produced a priced deliverable. `halt_reason` now stops the run, and
  `tests/test_stages.py` asserts a refused order spends nothing.
- **Replay had no test.** Byte-identity is a headline claim and was checked by
  hand. `tests/test_cli.py` now asserts it with the environment stripped.
- **`load_checkpoints` used a denylist.** It skipped `index.json` and timing
  files by name, so any other JSON dropped into a run directory broke replay.
  It now matches `NN-stage.json` positively.
- **`adapters/terac.py` had no tests.** All three tiers are covered, and writing
  them surfaced a real bug: `OVERRIDE` was bound as a default argument, so tier
  2 could never be redirected. Same bug found and fixed in the client's
  `update_activity`.
- **`web/activity.json` was hand-written.** `agent.py` emits it now; every lane
  that does something real records it.
- **The client had no CI and no mandate ceiling.** Both exist. `compose_order`
  refuses a budget above the standing authority, and `evaluate` escalates an
  invoice above it rather than declining quietly.
- **The client reused `wo-1` for every order.** Ids derive from the question.
- **The stage manifest was written by CI.** `run_pipeline` writes it, so a local
  run and a scheduled one leave the same artifact.
- **Three `urlopen` calls opened whatever scheme the URL carried.** All of them
  go through an https-only opener now, in both repos.
- **`tools/uitest/e2e.js` was one 76-line function** flagged at complexity 17. It
  is decomposed per page, and it covers the client page too.

Found on 2026-08-18 by running the loop end to end for the first time, none of
it visible from reading the code:

- **No workflow could place an order.** Settlement ran unattended from day one;
  ordering only ever worked from a laptop, which is why every order on the
  tracker was opened by hand. The client's `order` workflow closes it.
- **The reply told fulfilled customers they had been refused.** Adding `market`
  after `deliver` moved the deliverable out of `records[-1]`, and the reply was
  built from there. `RunResult.emitted()` looks in the stage that produced an
  artifact; a test pins the exact shape.
- **The answer did not answer the question.** Fixtures keep replay
  byte-identical and meant every order got the demo answer. `answers_question`,
  an incident, and a warning above the answer — not under it.
- **The client published nothing after acting.** A `GITHUB_TOKEN` push does not
  trigger another workflow, so its page reported the previous order. Both acting
  workflows deploy the site themselves now, as the firm's always did.
- **`adapters/pioneer.py` was dead and vendor-pinned.** It is `adapters/model.py`
  now and names a protocol instead: anything serving the OpenAI
  chat-completions shape works. The pinning is what made the original 404
  outage un-routable.
- **Issue #1 had been closed as `completed` with no deliverable** — a customer
  order the Issues tab showed as fulfilled and never was. Root cause, which is
  worth not re-investigating: `intake.yml` was committed at `01:10:32Z` and the
  issue was opened at `01:10:33Z`, one second before that commit reached the
  default branch. GitHub dispatches `issues` events only from the default
  branch's workflow file, so no run was ever queued for it; #2, twenty seconds
  later, was answered normally. Re-closed as `not_planned` with the explanation
  in the thread. Nothing was charged and no cost of goods was committed against
  it. The thread stays public: an order the company failed to answer is part of
  the operating record.

## Still open, in order

1. **No secrets are missing.** All five are set, confirmed against
   `gh secret list` on 2026-08-17: `TERAC_API_KEY`, `STRIPE_RESTRICTED_KEY` and
   `PIONEER_API_KEY` on Broker, `CLIENT_GITHUB_TOKEN` and `CLIENT_STRIPE_KEY` on
   the client. A manual `run` the same day returned `tier=terac`, which is the
   proof the Terac key is live rather than merely present.

   What that unlocks, and nobody has exercised end to end since: the client can
   place a work order **as itself**. Every order on the tracker so far was opened
   by hand. `uv run client --question "..."` from the client repo, or the `pay`
   workflow in `judge` mode, closes the loop with no human touching either end —
   and that is the demo, not a chore. Check the token's scope is still **Issues:
   write on the Broker repo only** before running it; that scope *is* the trust
   boundary, and widening it quietly deletes the claim.
2. **The golden run in a fresh clone is on the `recorded` tier**, because a
   clone has no key. The scheduled `run` workflow republishes it on the `terac`
   tier within the hour, so what a judge opens is the live tier. Both are
   labelled in the checkpoint; neither is a fallback that hides itself.
3. **Branch protection is off**, and turning it on is not free. `run.yml` and
   `ledger.yml` push directly to `main` with the default `GITHUB_TOKEN` — that
   is what republishes the ledger every five minutes. Requiring a pull request
   on `main` **breaks both loops** unless the bot is added to the bypass list.
   The honest sequence is: add `github-actions[bot]` to "Allow specified actors
   to bypass required pull requests", *then* require a PR and Code Owner review.
   Doing it in the other order takes the live P&L down, which is the one thing on
   the dashboard a judge is most likely to check.
4. **The model has no key, so every draft is the recorded fixture.** This is
   the highest-value item on the page and it is a secret, not code. Set
   `MODEL_API_KEY` and `MODEL_API_BASE` as repository secrets and the pipeline
   answers the question a customer actually asked; leave them and it keeps
   saying, correctly and loudly, that it did not. Recommended:
   Cloudflare Workers AI on `@cf/meta/llama-3.1-8b-instruct` — open weight, free
   tier, and OpenAI-compatible, so it needs no code of its own. A token with
   **Workers AI: Read** from dash.cloudflare.com/profile/api-tokens is the whole
   setup. Any host serving `POST {base}/chat/completions` works; see
   [`.env.example`](../.env.example).
5. **The four Terac approvals happened in the dashboard**, not through
   `approve_submission`. The payment is real; the approval decision was not
   exercised through the API. Study #2's *launch* was the agent's.
6. **Confidence is uncalibrated**, and item 4 is what unblocks it. Recorded
   drafts all carry the same score, so there is nothing to correlate until real
   ones start arriving. Once they do, every run already stores the score and
   whether the panel disagreed, and the escalation rate that decides viability
   falls straight out of the pair.

**Do not automate a Terac launch.** `adapters/terac.py` only reads submissions,
which costs nothing. Launching spends real money and stays a human decision,
once — otherwise the `*/5` ledger cron becomes a spending loop.

## Worth building next, in order

1. **Real participant quotes.** The task responses are dashboard-only; paste them
   into `HUMAN_INPUT.responses` and regenerate the golden run. The before/after
   panel is built and waiting for them, and it is the single highest-value thing
   left — it makes the mandatory requirement concrete rather than structural.
2. **An adversarial lane that checks the reply.** It sends six attacks over the
   real wire and nothing asserts what Broker did with them; the evidence is a
   human reading the issue thread. The attacks are the security claim, so they
   deserve the same treatment the payment guards got.
3. **An entity.** Terms, privacy and disclosures are all published now, and none
   of them has a legal person behind it. Stripe Atlas is the route; everything in
   [`REQUIREMENTS.md`](REQUIREMENTS.md#5-legalcompliance) below it depends on it.
4. **A dispute path.** An agent that can take money has to be able to be wrong.
   The refund policy is the piece, and it needs a spend guard of its own.

Built in the 2026-08-17 pass: published terms and privacy cited by id,
jurisdiction on the work order, the machine-readable offer at `/offer.json`, and
the money-flow strip.

Built in the 2026-08-18 pass: the client can place an order unattended, the
draft runs on a real model when one is configured, and both stale branches are
gone. Calibration moved from here into "still open" as item 6, because it is now
blocked on a secret rather than on work.

Longer term, the client is where the societies.io-shaped idea would go: replace
the single `evaluate()` with a handful of mandate profiles differing on risk
tolerance and price sensitivity, and pay on quorum rather than one boolean. That
adds a distribution of judgement to the demand side only, so Terac stays the sole
source of *human* judgement and the mandatory requirement is untouched. Frame
them as mandate profiles, never as simulated people.

## Do not do

Superserve, Band, Perflo, Linq, Arize. Each is a bolt-on that weakens the
"deliberately not claimed" section, which is currently a credibility asset.
Arize specifically would render an almost-empty dashboard: the pipeline runs on
recorded fixtures, so there are barely any LLM spans to trace.

## Reproduce anything

```bash
make setup && make test && make lint         # 95 tests
make replay                                  # byte-identical, no network, no keys
make e2e                                     # 18 viewport/page combos, both sites
```
