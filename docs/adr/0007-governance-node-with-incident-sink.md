# ADR-0007: Governance node via the `agent-governance` package

- **Status:** Accepted
- **Date:** 2026-06-14
- **Deciders:** Danh Le
- **Supersedes (in part):** the inline disclaimer guard from [ADR-0004](0004-synthetic-owners-with-provenance-flagging.md) — policy enforcement moves out of `summarize_node` into a dedicated `governance` node.

## Context

[ADR-0004](0004-synthetic-owners-with-provenance-flagging.md) made provenance honesty structural: a `Provenance` field on the response, an italic disclaimer in the prompt, an `_enforce_disclaimer` runtime guard inside `summarize_node`. That worked for one check. Three things have followed up:

1. **More checks are coming.** Threat-model T2 (URL allowlist on model output), T1 follow-up (track prompt-injection attempts), and T5 (length / cost caps) all want similar shapes — inspect the LLM's input or output, decide if it violates a policy, optionally mutate state, record the result.
2. **The disclaimer guard is buried.** Burying policy enforcement inside the summarize node makes it invisible in traces, hard to test in isolation, and impossible for a reviewer to answer "where does this team gate model output?" without reading helper functions.
3. **Violations need somewhere to go.** Today an `_enforce_disclaimer` fire logs a warning. That's lost in production. Violations are a form of model-behavior incident worth tracking — ideally in the same issue tracker the team already uses to triage real bugs.

Several agent projects sit alongside oc-realestate-intel (clinical-mcp, beacon, future agents). All of them would want the same machinery if it existed. The implementation should be *one* governance layer used by many agents, not a copy/paste pattern.

## Decision

**Extract the policy/check/sink machinery into a standalone Python package, [`agent-governance`](https://github.com/odanree/agent-governance), and consume it here as a versioned dependency.** Add a `governance` node to the LangGraph supervisor that runs between `summarize` and `END`.

```
                          ┌─────────────────────┐
START → … → summarize  →  │   governance        │ → END
                          │                     │
                          │   ┌── checks ────┐  │   ┌── sink ──────────┐
                          │   │ disclaimer   │  │   │ LogSink   (dev)  │
                          │   │ url_allowlist│  │   │ GitHubIssueSink  │
                          │   │ prompt_injct.│  │   │ NullSink         │
                          │   └──────────────┘  │   └──────────────────┘
                          └─────────────────────┘
```

`agent-governance` ships three Protocols (`Check`, `IncidentSink`, `ObservabilityAdapter`) and three concrete checks + four sinks. **This repo holds a 70-line adapter in [`app/governance.py`](../../app/governance.py)** that:

1. Picks the three checks this agent uses (configured with our canonical disclaimer, our URL allowlist).
2. Wraps our `app.observability` Langfuse helpers as an `ObservabilityAdapter` so per-check scores land in the same Langfuse trace.
3. Builds the sink from settings — `LogSink` by default, `GitHubIssueSink` opt-in.
4. Exposes the resulting `governance_node` to `app.agents.supervisor`.

The sink writes to the GitHub repo configured via `GOVERNANCE_GITHUB_REPO` (no hardcoded value — the governance agent files issues against whichever repo it's auditing). For this deployment that's `odanree/oc-realestate-intel`.

### Why a separate package, not an in-tree module

The previous draft of this ADR shipped everything in `app/governance/`. Once a sibling agent (clinical-mcp, beacon) needed the same machinery, the only realistic options were copy/paste or extract. Extraction wins: one place for bug fixes, one set of upstream tests, one versioned API surface. The extraction also forces a cleaner contract — checks talk to state through a dict, sinks talk to GitHub through `httpx`, and observability talks through a three-method Protocol the host implements. No app-specific imports leak into the package.

### Privacy

Issue bodies carry: check name, short detail (e.g. "redacted 1 non-allowlisted URL: ocassessor.gov"), `trace_id` for cross-reference, timestamp. They **never** carry the raw user query or full answer — both are PII surfaces per threat-model T7. Full context is reachable via Langfuse using the `trace_id`, where access is auth-gated.

### Async dispatch

`asyncio.create_task` from inside the node. User responses don't block on GitHub being reachable; sink failures are caught and logged inside the package.

## Consequences

**Positive**
- Reviewer answer to "where do you gate model output?" is "the `governance_node` in `app/governance.py`, backed by [`agent-governance`](https://github.com/odanree/agent-governance)" — one named place, three explicit checks, a tagged Langfuse span per node.
- Each check emits its own Langfuse score so eval analysis can ask "how often does the disclaimer guard fire on real traffic?" with a filter, not a grep.
- New checks are a 30-line file upstream. Adding one for this app is a one-line addition to the registry in `app/governance.py`.
- The sink is pluggable: dev runs `LogSink`, production opts into `GitHubIssueSink` with a token. Same code path.
- Dedup means production incidents don't drown the tracker — recurring failures become one issue with a counter.
- The package is reusable by every other agent in this portfolio.

**Negative**
- A versioned external dependency is one more thing to keep in sync. Pinned to a tag (`v0.1.0`), so upgrades are intentional.
- The state-dict-as-contract has no type safety. Mitigated by `state_key=` constructor args on built-in checks and by `tests/test_governance_wiring.py` which contract-tests the shape end-to-end.
- One more node in the graph means one more thing to keep in sync (state schema, SSE event, web parser, UI). Paid once.

## Alternatives considered

- **Leave `_enforce_disclaimer` inline.** Works for one check; doesn't scale to three. Rejected once T2 + T1 follow-up were on the roadmap.
- **In-tree `app/governance/` package.** First draft. Rejected because the same code would be copy/pasted into the next agent and drift.
- **Use a third-party guardrails library** (NeMo Guardrails, Llama Guard). Rejected for v1 because they add a model dependency for what is, today, three regex/string checks. Worth revisiting if a check needs semantic reasoning ("is this answer biased?", "does this leak PII the prompt asked us to redact?").
- **Run governance as a callback on the existing LangGraph callbacks.** Possible but invisible in the graph topology — the whole point is that "we gate model output" should be a node a reviewer can see.

## Configuration

```bash
# Default: LogSink, no GitHub side effects.
GOVERNANCE_INCIDENT_SINK=log

# Production with GitHub tracking:
GOVERNANCE_INCIDENT_SINK=github
GOVERNANCE_GITHUB_REPO=odanree/oc-realestate-intel
GITHUB_TOKEN=ghp_...                          # needs issues:write
GOVERNANCE_URL_ALLOWLIST=                     # comma-separated, default empty
```

## Follow-ups

- `LengthCapCheck` upstream covering T5.
- `PIIRedactorCheck` upstream covering T7 (redact SSN/email/phone in queries before they hit Langfuse).
- Surface a "governance fired" chip on the chat UI when any check reports a violation.

## Links

- Standalone package: [agent-governance](https://github.com/odanree/agent-governance) (MIT-licensed)
- Adapter in this repo: [`app/governance.py`](../../app/governance.py)
- Wiring in this repo: [`app/agents/supervisor.py`](../../app/agents/supervisor.py) (`build_graph` adds the `governance` node)
- Related: [ADR-0001](0001-langgraph-for-agent-orchestration.md) (topology now includes `governance`), [ADR-0004](0004-synthetic-owners-with-provenance-flagging.md) (provenance classification stays here; enforcement moves upstream), [threat-model](../threat-model.md) T1 / T2 / T13.
