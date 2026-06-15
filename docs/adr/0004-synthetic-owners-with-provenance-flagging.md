# ADR-0004: Synthetic owner data with end-to-end provenance flagging

- **Status:** Accepted
- **Date:** 2025-11-12
- **Deciders:** Danh Le

## Context

OC's public ArcGIS parcel layer is rich on geometry, address, year-built, and use-code — but **owner names are redacted**. Authoritative OC assessor owner data is paywalled (ParcelQuest, ATTOM, Regrid; ~$3k+/year). A working demo cannot block on a paid data deal, but it also cannot pretend synthetic data is real — that is a faithfulness failure the agent would happily hallucinate around if we let it.

The decision is structural: how do we ship a usable demo without ever letting the LLM present fabricated ownership as authoritative?

## Decision

**Generate synthetic owner data deterministically per-APN, and tag every layer of the system with the provenance source.** The agent's summarize prompt is required to surface that provenance when synthetic data is in its context.

The mechanics:

1. `app/ingestion/synthetic_owners.py` generates owner names and title-chain transfers from a seeded PRNG keyed on the APN. Same APN, same owner — no flapping across re-seeds.
2. Every parcel object carries `owner_source: "synthetic"` (or `"live"` for ArcGIS-fallback parcels). The Neo4j model carries the same tag on owner and transfer nodes.
3. The summarize prompt (`SUMMARIZE_SYSTEM` in `app/agents/supervisor.py`, RULE 6) requires an italicized disclaimer in the answer whenever any retrieved fact is flagged synthetic. The fact formatter (`_format_facts`) appends a NOTE block to the context to make this unavoidable.
4. The UI renders an amber `synthetic` chip in the parcel side-panel and shows the disclaimer inline.
5. The eval (`evals/golden.yaml`) includes provenance cases — answers that drop the disclaimer fail `faithfulness`.

When a real owner provider is wired in, the swap is one flag (`owner_source: "attom"` or similar) and the prompt's disclaimer clause stops firing automatically.

## Consequences

**Positive**
- Faithfulness is enforced by data shape, not by prompt-prayer. Even if the LLM "forgets" the rule, the NOTE block in its context plus the eval gate catch it.
- The swap path to a real provider is well-defined: replace the generator, leave the interface alone.
- Public demo is honest about what it is. Reviewers and recruiters reading the trace see exactly what is real (APN, address, year-built) and what is not (owner, transfers).

**Negative**
- Synthetic owners look real enough that a user skimming the UI might miss the disclaimer. Mitigated by the amber chip, but not eliminated.
- The faithfulness contract has *two* moving parts (prompt rule + context NOTE). If either drifts, the other catches it, but maintaining both is overhead. The eval is the third gate.
- Synthetic title chains are not a faithful proxy for real OC transfer patterns. Eval cases that depend on realistic transfer cadence will mislead.

## Alternatives considered

- **Ship with no owner data at all** — rejected. The whole point of the demo is to show portfolio queries and title chains. Removing them gives reviewers no signal about how the agent handles graph-shaped questions.
- **Use real owner data from scraping public records** — rejected. OC's individual document images are public but bulk scraping violates ToS and creates a redistribution problem we do not want.
- **Pay for ATTOM upfront** — rejected for a portfolio project. The provenance-flagged synthetic approach is more interesting *as a design demonstration* than swapping in real data would be.

## Links

- Implementation: `app/ingestion/synthetic_owners.py`, `app/agents/supervisor.py` (`SUMMARIZE_SYSTEM`, `_format_facts`)
- Related: [ADR-0003](0003-neo4j-for-owner-title-graph.md), [threat model § Output Disclosure](../threat-model.md)
