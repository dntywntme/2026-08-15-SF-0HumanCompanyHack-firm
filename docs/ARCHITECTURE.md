# Architecture

## The spine

A **deterministic harness**: an ordered list of stages executed one at a time,
under a hard turn cap and a per-stage wall-clock timeout, with every stage result
checkpointed to disk. Not a swarm. Not a graph. At most one bounded fan-out,
inside a single stage, with a mandatory merge step that verifies before
aggregating.

```
intake ──> process ──> deliver
  │          │           │
  └── checkpoint ── checkpoint ──> runs/<run_id>/*.json
                                        │
                                   --replay reads these,
                                   calls nothing live
```

The nine stages wired into that spine are the company's functions rather than a
script's steps — `intake · comply · triage · source · verify · build · price ·
deliver · market` — one per clause of the organizers' rule. The mapping, with
what each one does not yet cover, is in [`REQUIREMENTS.md`](REQUIREMENTS.md).

**A refused order halts the run.** `intake` (malformed) and `comply` (may not be
sold) set `halt_reason`, and every stage after it returns immediately, recording
that it ran and did nothing. Before that existed, a rejected work order still
drew a draft, still bought human judgement and still produced a priced
deliverable: the checkpoint said "refused" while the company spent the money
anyway. A refusal that only appears in the log is not a control.

### The stage contract

A stage is `(ctx: RunContext, state: dict) -> dict`. The returned dict is merged
into shared run state and checkpointed. Stages must be **deterministic** given
the same inputs — replay reproduces the recorded output, so anything that sneaks
a timestamp or random value into its return breaks replay fidelity.

`ctx.spend_turn(n)` charges extra turns for inner work such as an agent loop;
entering a stage always costs one turn. Exceeding `--max-turns` aborts *before*
the stage runs, so no partial checkpoint is written. Timing metadata goes to
sibling `*.timing.json` files, gitignored and excluded from the replayable
record.

## Why not a swarm, and why not a graph

This was a measurement decision, not an aesthetic one.

| Finding | Source |
|---|---|
| Error amplification by topology: single 1.0×, **centralized 4.4×**, hybrid 5.1×, decentralized 7.8×, **independent 17.2×** | [arXiv:2512.08296](https://arxiv.org/abs/2512.08296), 260 configurations |
| Multi-agent systems fail **41–86.7%** of the time across 7 frameworks. Top modes: step repetition 15.7%, reasoning-action mismatch 13.2%, unaware of termination 12.4% | [MAST, arXiv:2503.13657](https://arxiv.org/abs/2503.13657), 1,600+ traces, κ=0.88 |
| Coordination yields **negative** returns (β̂ = −0.404, p<0.001) once the single-agent baseline exceeds ~45% | arXiv:2512.08296 |
| A single agent outperforms multi-agent in **~43.3%** of cases | [arXiv:2602.04234](https://arxiv.org/abs/2602.04234) |
| Any delegated network is decision-theoretically dominated by a centralized decision maker with the same information | [arXiv:2603.26993](https://arxiv.org/abs/2603.26993) |

Two consequences we actually implemented:

1. **Never ship the "independent" topology.** Workers do not write to the output
   without a verification step in between. The merge stage is load-bearing — it
   is what converts 17.2× into ~4.4×, not a formality.
2. **A go/no-go gate on fan-out.** Measure the single-agent baseline first. Above
   ~45%, adding agents is predicted to hurt, so we do not.

The industry moved the same direction over 2025–26: OpenAI Swarm → Agents SDK,
AutoGen + Semantic Kernel → Agent Framework 1.0 (AutoGen now maintenance-only),
CrewAI Crews → Flows, LangGraph's explicit durability modes. The retreat from
free-form agent chatter toward explicit, durable, checkpointed execution is
near-universal.

## Trust model

Three tiers, distinguished by **what enforces them** — not by how much the
agents are told to trust each other.

```
TIER 0 — ZERO TRUST     Broker ⟷ client   (separate repositories)
  enforced by credential scope. The client agent holds a fine-grained
  token carrying Issues:write on Broker repo and nothing else, so it
  can place an order and cannot push code, merge, or alter a workflow.
  Channel: a GitHub Issue. No shared secrets, no shared runner.

TIER 1 — PARTIAL TRUST  Builder ⟷ Integrator, within Broker repo
  enforced by branch protection + CODEOWNERS.
  Builder pushes branches and cannot merge. Integrator merges and
  does not author product code.

TIER 2 — FULL TRUST     subagents inside one actor's worktree
  enforced by nothing. Disjoint write surfaces by convention.
```

| Tier | Mechanism | Can the constrained party bypass it? |
|---|---|---|
| 0 | Fine-grained token scoped to one repo and one permission | No — GitHub refuses the write before any code runs |
| 1 | Branch protection, `CODEOWNERS`, required review | No at runtime |
| 2 | Convention | Yes |

Tier 0 is the load-bearing one. The separation is per-repository and
per-credential, which is what GitHub actually enforces: a token scoped to
Issues on Broker repo cannot be talked into pushing a commit, no matter what
the client agent decides to do. Putting the two repositories under different
*accounts* would add defence against a compromised owner, but the enforcement
mechanism at runtime is identical, and an account whose Actions are restricted
cannot run the pipeline at all — a boundary that cannot execute CI is a
liability rather than a control.

This structure exists because the verification step is what makes multi-agent
work survivable: independent topologies amplify errors 17.2×, centralized ones
4.4× ([arXiv:2512.08296](https://arxiv.org/abs/2512.08296)). Placing the
verifier behind a permission boundary the producer cannot cross is the
difference between a control and a suggestion.

### What this buys that a self-check does not

An agent reviewing its own output shares the failure mode that produced it.
Tier 0 and Tier 1 guarantee the reviewer is a *different* identity with
different credentials, so a compromised or prompt-injected Builder cannot
approve its own artifact. That is the only row in the error table below where
the actor that made the mistake is not the actor that catches it.

## Error modes, and how each is handled

The demo shows failure being *caught*, not failure being hidden. This is why
structured output is validated with **Pydantic** rather than a parser that
silently repairs malformed model output — a repaired error is an error you
cannot show a judge.

| Failure mode | Detection | Recovery |
|---|---|---|
| Schema violation | `pydantic.ValidationError` | retry with `.errors()` fed back to the model |
| Order we may not sell | `comply` gate, before any spend | run halts; every later stage records that it did nothing |
| Personal data in order text | `comply` gate | redacted before it reaches a panel or a published page |
| Redirected API base (`file://`, `http://`) | scheme check in `adapters/http.py` | refused before the opener sees it; the adapter degrades a tier |
| Step repetition (MAST #1, 15.7%) | turn cap | abort before the stage; no partial checkpoint |
| Non-termination (MAST #3, 12.4%) | wall-clock timeout | abandon the stage, return a degraded value |
| Tool failure | exception at the tool boundary | degraded return, never raise into the spine |
| Bad artifact crossing a trust boundary | Integrator review | merge blocked by a different identity |

The last row is the only one where the actor that made the mistake is not the
actor that catches it. That is the difference between an agent checking itself
and a company having a control.

## Deliberate non-goals

- **No graph framework.** LangGraph would be new to this codebase today; the
  spine is ~200 lines and fully under test.
- **No inter-agent messaging.** Fan-out workers have no visibility of each other.
  Disjoint write surfaces, serial merge, conflicts resolved by intent.
- **No agent-native payment rails.** See the README's settlement section — x402
  and AP2 are referenced and understood, not integrated.
