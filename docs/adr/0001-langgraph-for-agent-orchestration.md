# ADR-0001: LangGraph for agent orchestration

- **Status:** Accepted
- **Date:** 2025-11-12
- **Deciders:** Danh Le

## Context

The agent has to route a user query through one of four retrieval strategies (APN fast-path, hybrid vector search, Neo4j graph traversal, live ArcGIS fallback), optionally enrich it through a graph-only path (title chain), then summarize with strict provenance rules. The control flow is not "tool-using LLM in a loop." The intent classifier picks a path deterministically, and the path itself has known structure — branches and joins, not free-form tool selection.

Three options were on the table:

1. **LangChain agents** (`AgentExecutor`, ReAct, OpenAI Functions). LLM decides each next step.
2. **LangGraph** — explicit `StateGraph` with named nodes, typed state, conditional edges, compile-time topology.
3. **Plain Python orchestration** — a series of `async def` functions called by a router.

## Decision

Use **LangGraph** with a five-node graph: `router → {retrieval | comparison} → summarize → END`. Typed `AgentState` (TypedDict) carries `query`, `intent`, `owner_name`, `parcels`, `graph_facts`, `answer`, `citations`. Routing is via `add_conditional_edges` driven by the router node's output.

## Consequences

**Positive**
- Topology is visible at a glance — `build_graph()` in `app/agents/supervisor.py` is the spec. No need to read prompt text to understand control flow.
- LangGraph's `astream(stream_mode="updates")` integrates cleanly with the SSE endpoint: every node completion becomes an SSE event without bespoke streaming code.
- Langfuse callbacks attach at the graph level and trace each node automatically, so the eval-driven dev loop (see [ADR-0005](0005-langfuse-evalkit-for-eval-driven-dev.md)) gets per-node spans for free.
- Typed state catches missing-field bugs at the boundary rather than at the LLM call.

**Negative**
- Adds two libraries (`langgraph`, `langchain-core`) we do not otherwise need. Plain Python would have zero framework cost.
- LangGraph upgrade churn is real — minor versions have moved `astream` semantics twice this year. We pin and re-eval.
- The LLM has no agency to pick a tool the router did not anticipate. This is a feature for a constrained domain like OC parcels but would be a limitation if the surface area widened.

## Alternatives considered

- **LangChain `AgentExecutor`** — rejected. ReAct-style "think → act → observe" loops added 2–4 LLM calls per query for a routing decision the system can make deterministically from a single classification call. Token cost and latency both bad for our use case.
- **Plain Python orchestration** — rejected, but only narrowly. The router/retrieval/summarize split *could* be three function calls. We chose LangGraph for the streaming-events story and the trace-per-node integration with Langfuse. If those went away, plain Python would be the right call.

## Links

- Implementation: `app/agents/supervisor.py`
- Related: [ADR-0005](0005-langfuse-evalkit-for-eval-driven-dev.md)
