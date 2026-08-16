# Next session

Written at the end of the hackathon build, 2026-08-15 17:40 PDT. Everything here
is verified against the state at that moment; check it still holds before acting.

## Where things stand

| | |
|---|---|
| Firm site | <https://dntywntme.github.io/2026-08-15-SF-0HumanCompanyHack-firm/> |
| Client site | <https://dntywntme.github.io/2026-08-15-SF-0HumanCompanyHack-client/> |
| Terac | Study `e39vxoxasopgrblq6tchgf68` **fulfilled** — $9.00 paid to 2 people, 22 screened, balance $125 → $116 |
| Stripe | $1.00 settled by the client agent, unattended, **sandbox** (`livemode: false`) |
| Tests | firm 49, client 22, ruff clean |
| Replay | Byte-identical on the recorded tier with no keys |
| CI | ci · pages · ledger (firm), pages · pay (client) — all green |

Working copy note: the firm repo's `origin` still points at the stale **qte77**
fork, which has red CI and no secrets. The live remote is **`dw`** →
`dntywntme`. Push with `git push dw HEAD:main` or repoint origin.

## 1. Secrets to add before a full end-to-end

Two are missing. Both values already exist in the respective gitignored `.env`.

| Repo | Secret | Unlocks |
|---|---|---|
| firm | **`TERAC_API_KEY`** | Tier 1 live sourcing. Without it every CI run silently drops to the recorded tier |
| client | **`CLIENT_GITHUB_TOKEN`** | The client agent opening work orders as Issues. Scope it to **Issues: write on the firm repo only** — that scope *is* the trust boundary |

Already set and working: `STRIPE_RESTRICTED_KEY` (firm), `CLIENT_STRIPE_KEY` (client).

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

- **The Issues channel has never been exercised.** The firm repo has zero
  issues and no `issues.opened` workflow. `channel.py` works and is tested, but
  the README calls the Issue "the only channel between them", which overstates
  it. Either wire the workflow or soften the claim.
- `adapters/pioneer.py` is effectively dead while Pioneer returns 403 despite an
  active Pro plan. Either get the entitlement fixed or delete the adapter.
- The two Terac approvals happened in the dashboard, not through
  `approve_submission`. The payment is real; the decision was not exercised
  through the API.

## 4. Worth building next, in order

1. **Before/after panel** — agent draft beside the human verdict, difference
   highlighted. It is the mandatory Terac deliverable and currently only appears
   as prose inside a decision's `because`.
2. **Real participant quotes** — the task responses are dashboard-only; paste
   them into `HUMAN_INPUT.responses` and regenerate the golden run.
3. **Money-flow strip** — one proportional bar, `IN $1.00 ▏ OUT $9.00`, so the
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
cd /tmp/uitest && node e2e.js                # 12 viewport/page combos, real Chromium
```
