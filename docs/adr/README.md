# Architecture Decision Records

This directory captures the non-obvious technical decisions behind oc-realestate-intel. Each ADR follows [MADR 4.0](https://adr.github.io/madr/) — Status / Context / Decision / Consequences / Alternatives — so a new engineer or reviewer can recover *why* a choice was made without reading the git log.

ADRs are append-only. When a decision is reversed, write a new ADR that supersedes the old one and update the old one's status. Do not edit historical decisions in place.

## Index

| # | Decision | Status |
|---|---|---|
| [0001](0001-langgraph-for-agent-orchestration.md) | LangGraph for agent orchestration | Accepted |
| [0002](0002-qdrant-with-bm25-sparse-vectors.md) | Qdrant with BM25 + dense sparse vectors over pgvector | Accepted |
| [0003](0003-neo4j-for-owner-title-graph.md) | Neo4j for owner / title-chain graph | Accepted |
| [0004](0004-synthetic-owners-with-provenance-flagging.md) | Synthetic owner data with end-to-end provenance flagging | Accepted |
| [0005](0005-langfuse-evalkit-for-eval-driven-dev.md) | Langfuse + evalkit for the eval-driven dev loop | Accepted |
| [0006](0006-mcp-as-consumption-interface.md) | MCP as the programmatic consumption interface | Accepted |
