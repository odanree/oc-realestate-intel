# ADR-0006: MCP as the programmatic consumption interface

- **Status:** Accepted
- **Date:** 2025-11-12
- **Deciders:** Danh Le

## Context

The agent has two consumers today: the Next.js chat UI (humans) and other agents (a Claude Code session, a future supervisor, anything that speaks the **Model Context Protocol**). The chat UI uses the SSE endpoint and is well-served. The second consumer needs something different:

- A typed tool surface that an LLM caller can discover (`oc_parcel_query`, `oc_submit_feedback`).
- A way to round-trip the **Langfuse trace ID** back to the caller so it can later attach feedback to the exact run that produced an answer.
- A description that tells the calling agent how to choose between tools and what citations mean.

REST works for humans but not for agents. An agent has to *know* the endpoint exists, infer the schema, and guess at semantics. MCP servers solve all three with a single `list_tools` handshake.

## Decision

Expose the agent as an **MCP server** with two tools:

- `oc_parcel_query(query: str) → {answer, intent, citations[], trace_id, provenance_disclaimer?}`
- `oc_submit_feedback(trace_id: str, score: int)` — round-trips +1/-1 back to Langfuse.

The MCP server is a thin wrapper over the FastAPI `/query` and `/feedback` endpoints — no agent logic lives in the MCP layer. The MCP tool descriptions explicitly state that owner data is synthetic and that the answer text carries an italicized provenance disclaimer when applicable (see [ADR-0004](0004-synthetic-owners-with-provenance-flagging.md)).

## Consequences

**Positive**
- A Claude Code session, or any MCP-aware agent, can call `oc_parcel_query` with no integration code. The tool's description disambiguates "use this for any natural-language question about an OC parcel."
- Feedback round-trip via `trace_id` closes the loop: an upstream supervisor that judges an answer poorly can attach `-1` to the specific trace, and that signal lands in the same Langfuse store as direct UI thumbs.
- Citations (APN list) come back as structured data, so a calling agent can chain — e.g., take the APNs from a portfolio query and feed them into a downstream comparison call.
- The MCP layer is a forcing function for *good tool descriptions*. The description is what a calling LLM reads to decide whether to use the tool; weak descriptions cause silent misuse.

**Negative**
- Two interfaces to keep in sync. Whenever the FastAPI schema changes, the MCP tool schema has to follow. Mitigated by the MCP layer being a thin pass-through — the response model is shared.
- MCP is a young protocol; tooling and conventions are still moving. We accepted that for visibility (multi-client agentic systems are clearly where the ecosystem is heading) but pinned the SDK version.
- The provenance disclaimer is carried in the *answer text*, not as a structured field. A naive caller could strip it. The MCP description warns against this, but it is an honor-system contract until we add a structured `provenance` field.

## Alternatives considered

- **REST only** — workable for the chat UI, weak for agent integration. Agent callers would have to be told the endpoint URL out-of-band and given hand-written tool descriptions.
- **Function-calling JSON over OpenAI/Anthropic SDK** — provider-coupled. We did not want the agent's discoverability to depend on which model the caller happened to be using.
- **gRPC** — strong typing, weak discoverability for LLM agents. The whole point of MCP is that the LLM reads the tool description; gRPC's `.proto` is for developers, not models.

## Follow-ups

- ~~Add a structured `provenance` field to the MCP response so callers cannot strip the disclaimer.~~ Shipped 2026-06-14: `QueryResponse.provenance: {owner_data_source, disclaimer}` is now in the schema, set by `_compute_provenance` in the summarize node, and surfaced on the SSE `summarize` event. The MCP wrapper inherits it.
- Document expected ratings semantics for `oc_submit_feedback` (1 = correct, -1 = incorrect) in the MCP tool description.

## Links

- MCP server instructions (deployed): see `oci` entry in the parent `~/.claude/` MCP configuration.
- Related: [ADR-0005](0005-langfuse-evalkit-for-eval-driven-dev.md)
