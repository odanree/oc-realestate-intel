# Threat Model — oc-realestate-intel

A STRIDE-style threat model for the agent and its surrounding data plane, with emphasis on LLM-specific risks (prompt injection, output disclosure, training-data provenance, cost abuse). Scope is the deployed system as drawn in [docs/architecture/c4-container.puml](architecture/c4-container.puml).

## Assets

| Asset | Why it matters |
|---|---|
| User queries | Free text from the public internet. Possible vector for prompt injection. |
| Parcel cache (Postgres) | Public OC data; integrity matters more than confidentiality. |
| Synthetic owner generator | Deterministic per-APN. **Looks like authoritative data**; the disclaimer chain is what keeps it honest. |
| Anthropic API key | High-value secret. Cost and reputation impact if leaked. |
| Langfuse keys | Trace store; carries user query text, which could include PII. |
| Live ArcGIS quota | Free public endpoint, no auth — but rate-limited and geo-blocked. Burning quota breaks the live-fallback path. |
| MCP tool surface | Programmatic agent callers consume this. Bad descriptions → silent misuse downstream. |

## Trust boundaries

1. **Browser ↔ FastAPI gateway** — public internet; treat all input as hostile.
2. **MCP client ↔ gateway** — semi-trusted upstream agent; we control the description, not the caller's prompt.
3. **Gateway ↔ Anthropic** — outbound TLS to a third-party LLM provider.
4. **Gateway ↔ ArcGIS** — outbound TLS to a public government endpoint, geo-blocked in some regions.
5. **Gateway ↔ Langfuse / Postgres / Qdrant / Neo4j** — internal compose network, but Langfuse holds query text which can carry PII.

## STRIDE table

Severity is `H` / `M` / `L` based on likelihood × impact for the *current* deployment (public demo, synthetic owner data, no PII intentionally collected).

| # | STRIDE | Threat | Vector | Impact | Sev | Mitigation in code today | Residual / TODO |
|---|---|---|---|---|---|---|---|
| T1 | Tampering / Information Disclosure | **Prompt injection via parcel query** — user crafts a query that exfiltrates the system prompt or coerces the summarize node to drop its provenance disclaimer | `POST /query` body | Hallucinated authoritative ownership claims; loss of honesty contract | H | RULE 6 in `SUMMARIZE_SYSTEM` is reinforced by the `_format_facts` NOTE block, which appends a non-overridable instruction to the *user* message context. Eval cases assert the disclaimer is present. **Runtime guard added in `_enforce_disclaimer` (`app/agents/supervisor.py`): if synthetic data is in context and the answer lacks an italic provenance note, the canonical disclaimer is appended and the drop is logged.** Test coverage in `tests/test_provenance.py`. | Track injection-attempt patterns in Langfuse for tuning. |
| T2 | Information Disclosure | **Output disclosure of training-data leakage** — model invents a plausible-looking OC government URL (`ocassessor.gov`) and presents it as authoritative | Summarize node | User clicks a fabricated URL; reputational harm | H | RULE 4 in `SUMMARIZE_SYSTEM` forbids inventing URLs/phone numbers; eval case originally surfaced this exact bug (see README "Three bugs the eval caught"). | Add post-generation URL extraction; assert every URL in the answer text appears in a small allow-list (or the retrieved facts). |
| T3 | Spoofing | **Synthetic owner data interpreted as authoritative** — user / downstream agent strips the italic disclaimer or ignores the amber chip | UI rendering, MCP caller | False ownership claims propagate downstream | H | `owner_source: "synthetic"` tag on every parcel + `(SYNTHETIC OWNER DATA …)` tag in `_format_facts` + amber UI chip + RULE 6 disclaimer + eval gate. See [ADR-0004](adr/0004-synthetic-owners-with-provenance-flagging.md). **Structured `provenance: {owner_data_source, disclaimer}` field added to `QueryResponse` and the SSE summarize event** (`app/schemas/query.py`, computed by `_compute_provenance`). MCP callers can read the field instead of parsing the answer prose. | — |
| T4 | Tampering | **Training-data poisoning of seeded parcels** — adversary with Postgres/Qdrant write access flips an APN's owner or address | Compromised seed script or DB credentials | Wrong answers; trust collapse | M | Seed is deterministic and re-runnable from ArcGIS; APN + address fields are real OC data so divergence is detectable. Owner data is synthetic, so "tampering" with it is bounded. | Add a `verify-seed` step in CI that re-pulls a sample from ArcGIS and asserts equality on real fields (APN, address, year_built). |
| T5 | Denial of Service | **Cost amplification via expensive queries** — user submits a stream of long queries to drive Anthropic + Langfuse usage | `POST /query/stream` | Anthropic spend; Langfuse storage growth | M | Sonnet 4.6 + `max_tokens=2048` caps per-call cost. Eval cost is ~$0.07/run. | Per-IP rate limit at the Caddy or FastAPI layer. Daily Anthropic spend cap via `client.limits`. Reject queries longer than N tokens upfront. |
| T6 | Denial of Service | **Live ArcGIS amplification** — query patterns engineered to defeat the relevance gate and force ArcGIS calls on every request | Crafted addresses that never match the seed | OC ArcGIS rate limit; live fallback degrades | M | Relevance gate (`_hits_match_address`) only triggers fallback on real address shapes. Live failures degrade silently to no-results. | Cache live-fallback results by query hash with TTL; circuit-breaker after N consecutive ArcGIS errors. |
| T7 | Information Disclosure | **User query PII in Langfuse traces** — a user types an SSN or email into the query box; it lands in Langfuse | All ingress | Inadvertent PII storage | M | Langfuse trace metadata is truncated to `query[:200]` in `_trace_config`, but the full query still appears as the LangGraph input. | Add a PII redactor (regex for SSN/email/phone) at the trace boundary. Document Langfuse retention. Add a `--no-trace` query flag. |
| T8 | Elevation of Privilege / Tampering | **Cypher / SQL injection via owner_name** — router extracts `owner_name` from query; service layer interpolates into Cypher / SQL | Portfolio queries | Arbitrary DB read or write | L | All DB access uses parameterized queries (`$name` binding in Cypher, asyncpg parameters in SQL). | Pin and verify with a static check (`bandit`, `semgrep` rule for raw SQL/Cypher concatenation). |
| T9 | Spoofing | **MCP tool description rot** — a future schema change leaves the MCP description stale; upstream agents misuse the tool based on outdated semantics | MCP `list_tools` handshake | Wrong intent → wrong answer | M | Description is co-located with the wrapper; review checklist requires updating it on schema changes. | Add a contract test: assert MCP tool description matches a canonical fixture; CI fails on drift. |
| T10 | Repudiation | **Untraceable agent behavior** — without trace IDs, a "the agent was wrong about parcel X" complaint is unauditable | Production usage | No way to reproduce a bad answer | L | Every query returns `trace_id`; the UI keeps it for thumbs feedback; the eval suite tags traces by case ID. | Surface `trace_id` in error responses too, not just success. |
| T11 | Information Disclosure | **Secret leakage in trace metadata** — Anthropic key or Langfuse key accidentally interpolated into a logged prompt | Misconfigured logging | Credential compromise | L | Settings load from env via `pydantic-settings`; no key strings appear in `_format_facts` or `_trace_config`. `.env.example` excludes real keys. | Pre-commit hook (`detect-secrets`) on the repo; periodic privacy-scrub (see [privacy-scrub skill](../../../.claude/skills)). |
| T12 | Tampering | **Adversarial sample bypasses router** — query crafted to be classified `unknown` by the router (which short-circuits to END), evading safety analysis | `POST /query` | Bypass of downstream summarize-rules; not currently a high-impact bypass because END returns no answer | L | Router output is constrained to a fixed `valid` set; unknown → empty answer. | Log unknown-intent queries to Langfuse with tag `intent:unknown` for adversarial-pattern review. |

## Compliance posture

- **CCPA / personal data**: the system does not intentionally collect personal data. Synthetic owner names that resemble real individuals are coincidental; the disclaimer chain (T3) is the user-facing mitigation. Live-mode owner data, when wired in from a paid provider, would change this and require a privacy review.
- **OC data redistribution**: parcel geometry/address/year-built is public; we cache, do not redistribute as a dataset, and do not derive paid-provider data without an explicit license switch.
- **AI Act-style obligations** (if scope ever expands to EU): the agent provides "information" not "decisions"; it does not perform automated decision-making about persons. The disclaimer is the substantive guard.

## Out of scope (today)

- Multi-tenant isolation. Single-tenant demo.
- User authentication on the public chat UI. The MCP server has caller-side auth via the parent agent's identity, not endpoint-level.
- Encryption at rest beyond what the underlying compose volumes provide.
- Adversarial robustness to fine-tuned LLM attackers (model-vs-model probing). Mitigations are *defense in depth* via the structured NOTE block and eval gates, not adversarial training.

## Review cadence

- Re-review on any change to `SUMMARIZE_SYSTEM`, `_format_facts`, the router prompt, or the MCP tool description.
- Re-review when a real owner provider is wired in (the synthetic-data mitigations T1/T2/T3 change shape).
- Quarterly sweep regardless.
