# Submission

**Event:** Zero-Human Company Hackathon by Terac — Humanmade, 655 Bryant St,
San Francisco — 2026-08-15.

**Submission portal:** https://www.hackathoncompany.com/platform/hackathons/the-world-s-first-zero-human-company-hackathon

## Deadline

| Source | Stated time |
|---|---|
| Guidebook run-of-show | **18:45 PDT — "Submissions LOCK"** |
| Platform record (`endDate` 2026-08-16T02:00:00Z, page text) | 19:00 PDT |
| Luma `end_at` | 20:30 PDT — end of event incl. closing ceremony, not a submission time |

**We treat 18:45 PDT as binding** and freeze internally at **17:45**, submitting
the required fields then and editing until the lock.

## Fields

| Field | Required | Value |
|---|---|---|
| Project name | yes | Broker |
| Tagline | yes | *An agent-run company that buys human expertise, marks it up, and sells the result.* |
| Public GitHub repo | yes | https://github.com/dntywntme/2026-08-15-SF-0HumanCompanyHack-firm |
| Live demo URL | no | https://dntywntme.github.io/2026-08-15-SF-0HumanCompanyHack-firm/ |
| Demo video (YouTube, 2 min max) | no | _TBD_ |

**Out of band to organizers:** team name + Stripe Payment Link + restricted key
(`rk_`, Balance=Read and Charges=Read only). The secret key (`sk_`) is never
shared.

## Pre-submission checklist

- [ ] Both repos public — `-firm` and `-client`
- [ ] Team of 2–4 registered (solo is not eligible)
- [ ] `make setup && make test && make lint` green on a fresh clone
- [ ] `make replay` works with no network and no API keys
- [ ] Terac before/after captured and visible in the UI
- [ ] At least one real Stripe transaction settled
- [ ] Restricted key + Payment Link sent to organizers
- [ ] Demo video under 2 minutes

## Tracks claimed

Entering multiple tracks is explicitly encouraged by the rules.

| Track | Our claim |
|---|---|
| **Best Overall Agent-Run Company** ($2,500) | Real revenue collected through Stripe during the event, with unit economics shown live: revenue in, Terac spend as cost of goods, margin |
| **Best Overall Project** ($2,500) | Deterministic harness with measured error handling, an enforced two-actor trust boundary, and an architecture decision backed by published evidence rather than preference |
| **Best Use of Terac** | Terac is the supply chain, not a survey bolted on. Remove it and the company has no product — its cost of goods disappears. Before/after is structural: AI-only answer versus human-verified answer, side by side, with the price paid |
| Best use of Replay | _run their QA against the dashboard_ |
| Best use of Superserve | _if agents need pausable sandboxes_ |

## What we did not do

Stated plainly, because judges ask:

- **No x402 or AP2 integration.** Both are referenced in the README with a
  reasoned position on where they belong. This event runs on fiat rails.
- **No swarm or graph framework.** See `docs/ARCHITECTURE.md` for the measured
  reasons.
- **The governance rails are architecture, not operating history.** The trust
  boundary is enforced today; the goal/eval loop it descends from has not run on
  real goals.
