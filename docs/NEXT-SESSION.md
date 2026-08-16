# Next session

Written at the end of the hackathon build, 2026-08-15 17:40 PDT. Everything here
is verified against the state at that moment; check it still holds before acting.

## Where things stand

| | |
|---|---|
| Firm site | <https://dntywntme.github.io/2026-08-15-SF-0HumanCompanyHack-firm/> |
| Client site | <https://dntywntme.github.io/2026-08-15-SF-0HumanCompanyHack-client/> |
| Terac | Two studies **fulfilled** (`e39vxoxasopgrblq6tchgf68`, `w4pxs0mrufeqo9kzuruzsvui`) — $18.00 paid to 4 people at $4.50 CPI, 30 screened (22 + 8), balance $125 → $107. Study #2 was created *and* launched by the agent |
| Stripe | $4.00 settled across 4 charges by the client agent, unattended, **sandbox** (`livemode: false`) |
| Tests | Broker 49, client 22, ruff clean |
| Replay | Byte-identical on the recorded tier with no keys |
| CI | ci · pages · ledger (Broker), pages · pay (client) — all green |

Working copy note: Broker repo's `origin` still points at the stale **qte77**
fork, which has red CI and no secrets. The live remote is **`dw`** →
`dntywntme`. Push with `git push dw HEAD:main` or repoint origin.

## 1. Secrets to add before a full end-to-end

Two are missing. Both values already exist in the respective gitignored `.env`.

| Repo | Secret | Unlocks |
|---|---|---|
| Broker | **`TERAC_API_KEY`** | Tier 1 live sourcing. Without it every CI run silently drops to the recorded tier |
| client | **`CLIENT_GITHUB_TOKEN`** | The client agent opening work orders as Issues. Scope it to **Issues: write on Broker repo only** — that scope *is* the trust boundary |

Already set and working: `STRIPE_RESTRICTED_KEY` (Broker), `CLIENT_STRIPE_KEY` (client).

**Do not automate a Terac launch.** `adapters/terac.py` only reads submissions,
which costs nothing. Launching spends real money and stays a human decision,
once — otherwise the `*/5` ledger cron becomes a spending loop.

## 2. Remediate replay through the API

Two replay bugs were found and fixed today by *running* the thing rather than
reading it. Both were invisible to the test suite, and that is the actual
finding: **replay needs assertions that exercise it the way a judge would.**

**What broke, and why the tests missed it.**

- `load_checkpoints` globbed every `*.json` in the run directory, so the
  `index.json` manifest added for the dashboard was read as a checkpoint and
  replay died on `KeyError: 'output'`. CI ran the same command and had been
  failing since the manifest landed.
- The three-tier sourcing made `make run` and `make replay` diverge for anyone
  without a `TERAC_API_KEY`: the committed run said `terac`, a fresh clone
  produced `recorded`.

**What to build.**

1. A test that writes a stray non-checkpoint file into a run directory and
   asserts `load_checkpoints` ignores it. That is the exact bug, and it is two
   lines.
2. A test asserting `run_pipeline` and `replay` produce identical stdout **with
   the environment stripped** (`TERAC_API_KEY`, `STRIPE_RESTRICTED_KEY`,
   `PIONEER_API_KEY` unset, `REPLAY_MODE=true`). Byte-identity is a headline
   claim in the README; it deserves a test rather than a manual `diff`.
3. A CI step that clones the repo to a temp directory and runs
   `make setup && make test && make replay` there. Everything found today came
   from doing that by hand.
4. `adapters/terac.py` ships with **no tests**. It is GET-only and degrades
   safely, but the tier-selection logic — live, then human override, then
   recorded — is exactly the kind of branch that rots silently. Test all three
   with a stubbed fetch.

**Use the API to verify, not just the CLI.** Read submissions with
`GET /opportunities/{id}/submissions` (Bearer auth; `x-api-key` returns 401
despite the docs listing both) and assert the tier-1 payload shape matches what
`stages.py` expects. The screening answers are returned; the task text is
dashboard-only, which the adapter already documents.

## 3. Honesty items to close

- **The Issues channel is now exercised, but unevenly.** `intake.yml` is wired
  and Broker issue #2 carries a full bot reply with the decision list. Issue #1,
  opened 19 seconds earlier, got **no reply at all** — so a judge opening the
  Issues tab sees one customer order that was ignored. Find out why intake
  skipped it, and close both once the orders are delivered.
- Both work orders are titled `order: wo-1`. The client reuses the same id for
  different questions, which reads as a bug in work-order identity.
- `adapters/pioneer.py` is effectively dead: every inference call returned
  **404** with a valid API key and a redeemed voucher on the account. Either get
  it answering or delete the adapter.
- The four Terac approvals happened in the dashboard, not through
  `approve_submission`. The payment is real; the approval decision was not
  exercised through the API. Study #2's *launch*, by contrast, was the agent's.

## 4. The client repo specifically

It was built last and shows it. Nothing is broken, but three things are thinner
than Broker side.

- **`web/activity.json` is hand-written.** The client page renders a static
  record of what the agent did rather than something the agent emitted. Have
  `agent.py` write it on each run — same shape, no page change — and the client
  surface becomes generated rather than asserted.
- **The client UI has no test coverage.** Broker's e2e sweep at
  `tools/uitest/e2e.js` covers Broker's two views across six viewports; the
  client page was checked once by hand. Add it to the same suite: the
  reconciliation step (does it read Broker's ledger?) is the assertion worth
  having, because it is the cross-repo claim.
- **Styles are duplicated between the two pages.** The mobile grid bug was fixed
  on Broker page and shipped broken on the client for an hour because the
  `.step` rules exist twice. Either vendor a shared stylesheet into both, or
  accept the duplication deliberately and note it.

Longer term, the client is where the societies.io-shaped idea would go: replace
the single `evaluate()` with a handful of mandate profiles differing on risk
tolerance and price sensitivity, and pay on quorum rather than one boolean. That
adds a distribution of judgement to the demand side only, so Terac stays the
sole source of *human* judgement and the mandatory requirement is untouched.
Frame them as mandate profiles, never as simulated people.

## 4b. Worth building next, in order

1. **Before/after panel** — agent draft beside the human verdict, difference
   highlighted. It is the mandatory Terac deliverable and currently only appears
   as prose inside a decision's `because`.
2. **Real participant quotes** — the task responses are dashboard-only; paste
   them into `HUMAN_INPUT.responses` and regenerate the golden run.
3. **Money-flow strip** — one proportional bar, `IN $4.00 ▏ OUT $18.00`, so the
   negative margin reads instantly instead of needing a paragraph.
4. **Confidence gauge** on the triage row. The threshold crossing is the whole
   thesis and is currently prose.

## 5. Do not do

Superserve, Band, Perflo, Linq, Arize. Each is a bolt-on that weakens the
"deliberately not claimed" section, which is currently a credibility asset.
Arize specifically would render an almost-empty dashboard: the pipeline runs on
recorded fixtures, so there are barely any LLM spans to trace.

## Reproduce anything

```bash
make setup && make test && make lint         # 49 tests
make replay                                  # byte-identical, no network, no keys
make e2e                                     # 12 viewport/page combos, real Chromium
```
