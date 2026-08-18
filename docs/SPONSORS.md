# Sponsors and rules

Source: `[GUIDEBOOK] - Zero Human Company Hackathon by Terac` (Notion), fetched
2026-08-15, plus each sponsor's own docs. Two gates are mandatory; the rest is
optional upside. **Gate 1 — Terac MCP:** every project must use it, and the
criterion is real human input collected *during* the event that makes the project
*measurably* better, shown as a clear before/after. **Gate 2 — Stripe:** a
personal account, one Payment Link, and a read-only restricted key handed to
organizers, which is how they attribute revenue to you. Beyond that: *"You may
compete in as many tracks as you want, as long as your project meets the criteria
for those tracks. The more tracks you compete in, the higher your odds are of
winning."* Extra tracks are free, and each is judged only against its own
criterion.

## Prize tracks

Eight tracks. Criteria quoted verbatim.

| Track | Prize | Verbatim criterion |
|---|---|---|
| Best Overall Project | $2,500 | "The best overall project, decided on by the main panel of judges. Creativity, technical skill, and it's impressiveness, overall!" |
| Best Overall Agent-Run Company | $2,500 | "The agent-run company that earns real revenue during the hackathon and also has the most potential to be a successful company, post-hackathon." |
| Best use of Linq | 1st $1,500 / 2nd $1,000 | "Linq gives your agent a real phone number on iMessage — iMessage, RCS and SMS from one API, plus rich media, Find My location, effects, reactions, typing indicators, read receipts, and realtime webhooks on every event. The part most people don't know about: iMessage Apps, an interactive card that renders inside iMessage … And with Agent Pay, checkout happens right there: the payment card opens an Apple Pay App Clip, and the money settles to your own Stripe account." |
| Best use of Replay | 1st $1,000 / 2nd $500 | "Build a great app and get a clean report from QA after fixing the bugs it finds" — plus a side bounty, "Report a QA false positives for a $50 amazon gift card" |
| Best use of Superserve | 1st $1,000 / 2nd $500 | "Teams must use Superserve as core part of their project stack to qualify for winner prizes. Teams can give their agents virtual machines in the cloud with Superserve. Any time agents need to execute code, manage files, run bash commands, use a browser, etc. they can do so safely in Superserve sandboxes. Between turns, agents can pause the sandbox preserving full VM state, and resume instantly on subsequent turns." |
| Best use of Pioneer | 1st $500 | "Use open-weight model(s) on Pioneer to build a compelling product". Bonus points: "Use Fastino Labs models / GLiNER2, GLiGuard, or GLiNER2-PII / OR Fine-tune an open model using Pioneer fine-tuning API." |
| Best use of Band | 1st $500 | "Project uses Band meaningfully. What is 'meaningfully'? it's when the coordination between agents happens in Band, and taking Band out breaks the project. Meaningful use of Band means the chat room actually drives the collaboration, not just displays it, remove the room and the app should break, not keep working the same way. That requires at least one real dependency: a handoff where one agent's answer changes because of another's finding, a specialist added at runtime based on the specific case, a boundary Band enforces between accounts, or a verdict one agent can genuinely block." |
| Best use of Render | 1st $500 / 2nd $300 / 3rd $100, all in Render credits | "Projects must use Render Workflows to qualify for the winner prizes." |

All-projects rule, verbatim: *"Use real human input you collect during the
hackathon to make your project measurably better, whether that's product
feedback, user testing, expert judgment, or labeled data."* Then: build something
real people can respond to; call the Terac API/MCP to bring them; show a clear
before and after; and *"Please launch studies geared towards the General
Population, so you get the fastest & best results."*

## Terac — mandatory

The supply layer for verified human labour. An agent scopes a job, Terac recruits
and screens identity-verified people, structured results come back as JSON, and
you pay on verified completion.

- **MCP endpoint:** `https://terac.com/api/mcp`, streamable HTTP. Install with
  `claude mcp add --transport http terac https://terac.com/api/mcp`, then `/mcp`
  in Claude Code to authenticate.
- **Auth:** OAuth on first connect (nothing to paste). The endpoint also accepts a
  key directly — `x-api-key: <key>` or `Authorization: Bearer tk_...` — which is
  what the harness should use, since OAuth needs an interactive browser step.
- **Tool names**, observed on terac.com/mcp: `terac_get_context`,
  `terac_request_feasibility`, `terac_get_feasibility_request`,
  `terac_list_opportunities`, `terac_launch_draft_opportunity` (shown shortened as
  `terac_launch_draft`), `terac_pause_opportunity`, `terac_get_submissions`. The
  docs publish no tool list, so spellings are **unverified** until `tools/list`.
- **REST alternative:** base `https://terac.com/api/external/v2`, v2 **beta**,
  `Authorization: Bearer YOUR_API_KEY`, 100 req/min. `POST /feasibility/requests`,
  `GET /feasibility/requests/{requestId}`, `POST /projects`, `POST /opportunities`,
  `POST /opportunities/{id}/launch` plus `/pause` `/resume` `/stop`,
  `GET /opportunities/{id}/submissions`, `POST /submissions/{id}/approve` and
  `/reject`, webhook CRUD. Events: `submission.approved`,
  `submission.status.change`. The reference prints `http://localhost:3000` as the
  base on every page — docs bug, use `https://terac.com`.
- **Billing:** prepaid organization balance (`balanceDollars` from
  `getOrganizationContext`); a launch fails if it will not cover the spend. Pricing
  is CPI, driven by each task's `duration_minutes` — a duration you guess is a
  price you invent. Feasibility quotes before you spend. Payout is set per task by
  `review_type`: `auto_approve` pays on completion, `self_report` pays on the
  participant's own attestation and cannot be withheld, `manual_review` parks it in
  `AWAITING_REVIEW` and pays only when you approve.
- **Fastest pool:** the guidebook says it twice — general population, not narrow
  expert targeting. Use `business_type: "b2c"` and keep filters loose.

## Stripe — mandatory for the revenue prize

- **Setup:** personal account, no business verification; Dashboard → Payment links
  → Create; *"Customer chooses price"* if amounts vary. Use **one** link for
  everything — *"if you create a new one mid-hackathon, your revenue tracking will
  miss it."* Then Developers → API keys → restricted key with **Balance = Read**,
  **Charges = Read**, all else **None**. Submit team name + link + `rk_` key;
  never share `sk_`.
- **Hardest requirement:** a real settled charge before 18:45; test-mode payments
  do not read as revenue.
- **Scope conflict.** The rules list scopes Stripe to one track: *"To collect
  payments, and be eligible for the 'Best Overall Agent-Run Company,' you must
  setup a stripe individual account."* The payment section scopes it to two: *"To
  be eligible for the main prize (Best Overall Project & Best Overall Agent-Run
  Company)…"* Assume the wider reading; ask in Slack.

## Render — not used

Dropped deliberately. Render Workflows was our candidate for two jobs: hosting
the dashboard and running the ledger poller. Both are now GitHub-native — Pages
serves the site from the `gh-pages` branch and a scheduled Action polls Stripe —
which removes a dependency, a signup, and an unverified requirement (whether
deploying a Workflow needs a payment method) from the critical path.

The cost is the track: $500 / $300 / $100, and it pays in credits rather than
cash. Reinstating it would mean deploying a Workflow, since a web service on
Render explicitly does not qualify.

## Replay

Autonomous QA agent: point it at a running app, it explores, writes and runs
Playwright tests, and files bugs with root cause and a suggested fix.

- **REST:** base `https://qa.replay.io/api/v1`, spec at `openapi.json`.
  `POST /projects` (`name`, `target_url`, `budget`, `finished_webhook_url`),
  `GET /projects/{id}/status`, `GET /projects/{id}/bugs?status=open`, and
  `PATCH /bugs/{id}` `{"status":"fixed"}` — which **auto-retries the affected
  journey** and is the cheap route to cycle two. Auth `Bearer lqa_...`.
- localhost works via `use_reverse_proxy: true` plus the `replayqa` npm package.
- **Hardest requirement:** the criterion needs a *clean* report after fixing, so
  two cycles minimum. Runs are metered (~20 credits for an average app, 25/month
  free); an event code unlocks unlimited access for the day. Credit available —
  see team notes.

## Superserve

Durable Firecracker microVMs that pause indefinitely and resume instantly.

- **SDK:** `pip install superserve` → `from superserve import Sandbox`, or
  `npm install @superserve/sdk`. Docs index at `docs.superserve.ai/llms.txt`.
- **Core calls:** `Sandbox.create(...)` returns already active, no readiness poll;
  then `commands.run`, `files.write` / `read_text`, `pause()`, `resume()`,
  `kill()`, `Sandbox.connect(id)`. Paused sandboxes auto-resume on `connect()` or
  `commands.run()`. Auth `SUPERSERVE_API_KEY`; no card needed. Per-second billing,
  and **storage bills while paused**.
- **Hardest requirement:** "core part of their project stack" means pause/resume
  must be load-bearing. Trap: `timeout_seconds` caps **active** time, not idle
  time, so a long task gets paused mid-run and reads as a hang.

## Linq — not used

Dropped deliberately. The track rewards a real phone number on iMessage, and we
did not want inbound messages routed to a personal number. There is no honest
partial claim here: the criteria are about the messaging surface itself, so we
skip it rather than gesture at it.

The cost is the richest sponsor pool ($1,500 / $1,000) and Agent Pay's in-thread
checkout. Customer intake is a GitHub Issue instead. Payment is **not** a
Payment Link: hosted checkout needs a browser, so an agent cannot use one. The
client agent creates and confirms a PaymentIntent over the API, which is what
makes that leg autonomous.

## Band

Chat rooms where agents from any framework, on your own infra and keys, coordinate
with humans via `@mention` routing, with cross-account governance.

- **SDK:** PyPI `band-sdk`, import `band` (`from band import Agent`); npm
  `@band-ai/sdk`. Shape is adapter → `Agent.create(adapter=..., agent_id=...,
  api_key=...)` → `await agent.run()`, which opens the WebSocket and auto-joins.
- **REST:** `https://app.band.ai/api/v1/agent` — `/me`, `/peers`, `/chats`,
  `/chats/{id}/messages`, `/chats/{id}/participants`. Auth `X-API-Key: <key>`.
  Register agents at `app.band.ai/agents`; key shown once. Free tier, 10 agents.
- Default tools map onto the criterion: `band_send_message` with an `@mention` for
  a dependent handoff, `band_lookup_peers` + `band_add_participant` for a runtime
  specialist, bilateral contacts consent for a cross-account boundary. A blockable
  verdict is a **prompt convention, not an API primitive**.
- **Hardest requirement:** passing the delete test. Two traps: one process
  switching personas fails, because Band allows **one live WebSocket per
  `agent_id`** and a new connection silently drops the old one; and execution
  events are **off by default** — without `emit={Emit.EXECUTION}` the room shows
  chat only and your judging evidence stays in a terminal.

## Pioneer by Fastino Labs

Fine-tune and serve open-weight models without managing GPUs.

- **Inference:** OpenAI-compatible `POST https://api.pioneer.ai/v1/chat/completions`
  and Anthropic-compatible `POST https://api.pioneer.ai/v1/messages` — point an
  existing SDK's `base_url` at `https://api.pioneer.ai/v1`. Auth `X-API-Key`.
- **Fine-tuning:** `POST /felix/training-jobs`, rows shaped
  `{"messages":[{"role":..., "content":...}]}`; poll `GET /felix/training-jobs/:id`
  through `requested → running → complete → deployed`, then pass the job id as
  `model_id`. Bonus-point models: GLiNER2 Large, GLiGuard 300M, GLiNER2-PII.
- **Hardest requirement:** the track wants *open-weight* models — the Claude and
  GPT passthrough does not count. Fine-tune wall-clock is not published
  (**unverified**), so treat a same-day fine-tune as a risk, not a plan.

## Traps

- **18:45 PDT is the lock.** Run-of-show reads `6:45 — Submissions LOCK`. The
  platform page's 19:00 and Luma's 20:30 are not submission times.
- **Terac feasibility is async and priced by a human out of band.** `POST
  /feasibility/requests` returns `RECEIVED` with `costPerParticipant: null`; you
  poll until `RESPONDED`. Fire it first, before the app is finished.
- **Terac `expected_days_to_complete` has a 5-calendar-day minimum** (default 7).
  You cannot declare a same-day window; fills may come sooner, nothing guarantees it.
- **Three Terac calls fail in ways teams discover late:** a draft cannot launch
  without a screening question (optional at create, required at launch);
  `createOpportunity` is rejected if you send neither `filters` nor
  `unrestricted_audience: true`; and a launch fails on an unfunded balance.
- **Terac `task_url` must be a public `https://` URL** — participants open it
  directly, so localhost will not do. Terac appends `submissionId` /
  `teracSubmissionId` / `taskId`, and completion is signalled by redirecting to
  `https://<host>/api/external/callback`. Deploy before launching a study.
- **Linq sandbox provisioning can route to manual review**, which no amount of
  building unblocks today. Sign up before writing any Linq code.
- **Replay needs two QA cycles**, and the free allowance does not cover them
  without the event code. **Render pays in credits, not cash.** Render Workflows
  and Terac REST v2 are both beta, with breaking changes possible.
- **Track criteria are checked literally.** Render means Workflows; Superserve means
  "core part of their project stack"; Band means removing the room breaks the app;
  Replay means a *clean* report after fixing.
- **Team size is not stated in the guidebook.** The 2–4 rule the team is working to
  comes from elsewhere and is **unverified** against this source.

Credits exist for Terac, Stripe Atlas, Render, Replay, Superserve, Pioneer, Band,
Lovable, Solari, and Interview Cake. Redemption links and codes are
participant-only and deliberately absent from this repo — credit available, see
team notes.
