# oc-realestate-intel eval report

- generated: 2026-06-08T01:51:26.961760Z
- judge model: `claude-sonnet-4-6`
- cases: 16
- total judge cost: $0.0692

## Summary

| metric | score |
|---|---|
| `intent_accuracy` | 0.94 |
| `citation_recall` | 1.00 |
| `citation_precision` | 1.00 |
| `refusal_correctness` | 1.00 |
| `faithfulness` | 9.94 |
| `answer_relevance` | 6.81 |

## Per-case detail

### `lookup_apn_basic` — intent `lookup` (expected `lookup`)
**Query:** What is parcel 461-211-62?

**Answer:**
> **APN 461-211-62** is a parcel located at **73 Bridgeport Rd, Irvine**, in the city of Irvine, Orange County. The year built is not available in the retrieved data. The listed owner of record is **Flores Family Trust** (a trust).
> 
> *Owner / title-chain data for this parcel is illustrative and not from authoritative records. For verified ownership and transfer history, consult the OC Assessor's office or the OC Clerk-Recorder's office.*

**Citations:** 461-211-62
**Scores:** intent_accuracy=True · citation_recall=1.00 · faithfulness=10.00 · answer_relevance=8.50

### `lookup_apn_in_sentence` — intent `summarize` (expected `lookup`)
**Query:** Tell me about APN 461-211-62 — who owns it?

**Answer:**
> APN 461-211-62 is a parcel located at 73 Bridgeport Rd, Irvine. The retrieved data lists the owner as **FLORES FAMILY TRUST** (a trust). No year-built information is available for this parcel.
> 
> *Owner / title-chain data for this parcel is illustrative only and not sourced from authoritative records. For verified ownership information, contact the OC Assessor's office or the OC Clerk-Recorder's office.*

**Citations:** 461-211-62
**Scores:** intent_accuracy=False · citation_recall=1.00 · faithfulness=10.00 · answer_relevance=9.00

### `lookup_street_proper_noun` — intent `lookup` (expected `lookup`)
**Query:** Find parcels on Bridgeport Road in Irvine

**Answer:**
> Based on the retrieved facts, one parcel on Bridgeport Road in Irvine was found:
> 
> | APN | Address | Owner | Year Built |
> |---|---|---|---|
> | 461-211-62 | 73 Bridgeport Rd, Irvine | Flores Family Trust | Unknown |
> 
> No other Bridgeport Road parcels in Irvine appear in the retrieved data.
> 
> *Owner / title-chain data for the parcel above is illustrative only and not from authoritative records.*

**Citations:** 461-211-62
**Scores:** intent_accuracy=True · citation_recall=1.00 · faithfulness=10.00 · answer_relevance=8.50

### `lookup_common_street` — intent `lookup` (expected `lookup`)
**Query:** What's on Irvine Park Road?

**Answer:**
> The retrieved facts contain no parcels located on Irvine Park Road. The addresses returned reference Irvine Avenue (Newport Beach), S. Mitchell in Irvine, and Park Plaza in Irvine — none of which is Irvine Park Road.
> 
> For parcels on Irvine Park Road, you would need to consult the OC Assessor's office or the OC Clerk-Recorder's office directly.
> 
> *Owner / title-chain data in the retrieved facts is illustrative only and not from authoritative records.*

**Scores:** intent_accuracy=True · faithfulness=10.00 · answer_relevance=5.00

### `refuse_unknown_apn` — intent `lookup` (expected `lookup`)
**Query:** What is parcel 999-999-99?

**Answer:**
> The retrieved facts contain no record for parcel 999-999-99. I cannot provide information about it based on the available data.
> 
> For authoritative information, you may contact the OC Assessor's office or the OC Clerk-Recorder's office.
> 
> *Owner/title-chain data for the parcels listed in the supporting facts is illustrative and not from authoritative records.*

**Scores:** intent_accuracy=True · citation_precision=1.00 · refusal_correctness=1.00 · faithfulness=9.50 · answer_relevance=8.50

### `owner_query_now_has_data` — intent `lookup` (expected `lookup`)
**Query:** Who owns 461-211-62?

**Answer:**
> Based on the retrieved facts, APN 461-211-62 (73 Bridgeport Rd, Irvine) shows **FLORES FAMILY TRUST** as the owner of record.
> 
> *Owner / title-chain data is illustrative only and not drawn from authoritative records. For verified ownership information, contact the OC Assessor's office or the OC Clerk-Recorder's office.*

**Citations:** 461-211-62
**Scores:** intent_accuracy=True · citation_recall=1.00 · faithfulness=10.00 · answer_relevance=9.00

### `title_chain_now_has_data` — intent `title_chain` (expected `title_chain`)
**Query:** Show the title chain for 461-211-62

**Answer:**
> **Title Chain — APN 461-211-62**
> 73 Bridgeport Rd, Irvine
> 
> | Order | Doc Date | Doc Number | Grantor | Grantee | Recorded Price |
> |-------|------------|------------------|-------------------------------|----------------------|----------------|
> | 1 (most recent) | 2019-10-23 | 2019-673577 | DAVID MARTIN | FLORES FAMILY TR | $2,369,389 |
> | 2 | 2012-10-25 | 2012-947955 | SADDLEBACK DEVELOPMENT CORP | DAVID MARTIN | not recorded |
> | 3 (earliest) | 1997-01-05 | 1997-903433 | MARGARET PARK | SADDLEBACK DEVELOPMENT CORP | not recorded |
> 
> Current owner of record: FLORES FAMILY TRUST (trust).
> 
> Three transfers are reflected in the retrieved data. Two of the three show no recorded price. No further details about the nature of any transfer are available from the retrieved facts.
> 
> *Owner and title-chain data for this parcel are illustrative (synthetic) and are not drawn from authoritative OC Assessor or Clerk-Recorder records. Address and APN are real.*

**Citations:** 461-211-62
**Scores:** intent_accuracy=True · citation_recall=1.00 · faithfulness=10.00 · answer_relevance=9.00

### `compare_explicit` — intent `compare` (expected `compare`)
**Query:** Compare 1 Park Plaza in Irvine to nearby properties

**Answer:**
> The retrieved facts do not contain any data for 1 Park Plaza, Irvine. None of the 11 parcels in the retrieved facts are located in Irvine or carry that address — all are on Irvine Ave in Newport Beach. A comparison between 1 Park Plaza, Irvine and nearby properties cannot be made from these facts.
> 
> For authoritative parcel and ownership data on 1 Park Plaza, Irvine, you could contact the OC Assessor's office or the OC Clerk-Recorder's office.

**Scores:** intent_accuracy=True · faithfulness=10.00 · answer_relevance=6.50

### `title_chain_intent` — intent `title_chain` (expected `title_chain`)
**Query:** Trace the title chain on parcel 461-211-62

**Answer:**
> Here is the recorded title chain for APN 461-211-62 (73 Bridgeport Rd, Irvine), most recent first:
> 
> | Seq | Doc Number | Date | Grantor | Grantee | Consideration |
> |-----|------------|------|---------|---------|---------------|
> | 1 | 2019-673577 | 2019-10-23 | DAVID MARTIN | FLORES FAMILY TR | $2,369,389 |
> | 2 | 2012-947955 | 2012-10-25 | SADDLEBACK DEVELOPMENT CORP | DAVID MARTIN | not recorded |
> | 3 | 1997-903433 | 1997-01-05 | MARGARET PARK | SADDLEBACK DEVELOPMENT CORP | not recorded |
> 
> The current vested owner of record is the FLORES FAMILY TRUST. Three conveyances appear in the chain spanning 1997 through 2019. No consideration was recorded for the two earlier transfers. For full instrument details, the OC Clerk-Recorder's office would be the authoritative source.
> 
> *Owner names and title-chain data above are illustrative only and are not drawn from authoritative OC Assessor or Clerk-Recorder records.*

**Citations:** 461-211-62
**Scores:** intent_accuracy=True · faithfulness=10.00 · answer_relevance=6.50

### `refuse_title_chain_unknown_apn` — intent `title_chain` (expected `title_chain`)
**Query:** Show the title chain for parcel 999-999-99

**Answer:**
> No facts were retrieved for parcel 999-999-99. I cannot construct a title chain without source data.
> 
> If you need the actual title chain for this parcel, the OC Assessor's office and the OC Clerk-Recorder's office are places to look.

**Scores:** intent_accuracy=True · refusal_correctness=1.00 · faithfulness=9.50 · answer_relevance=8.50

### `summarize_address` — intent `summarize` (expected `summarize`)
**Query:** Summarize 73 Bridgeport Rd Irvine

**Answer:**
> **73 Bridgeport Rd, Irvine — APN 461-211-62**
> 
> - **Address:** 73 Bridgeport Rd, Irvine
> - **APN:** 461-211-62
> - **Year Built:** Unknown
> - **Current Owner of Record (illustrative):** Flores Family Trust
> 
> No additional details — such as lot size, square footage, assessed value, sale history, or zoning — are present in the retrieved facts.
> 
> *Owner and title-chain data for APN 461-211-62 is illustrative only and not drawn from authoritative records.*

**Citations:** 461-211-62
**Scores:** intent_accuracy=True · citation_recall=1.00 · faithfulness=10.00 · answer_relevance=3.50

### `route_unknown` — intent `unknown` (expected `unknown`)
**Query:** What's the weather in San Diego today?

**Answer:**
> 

**Scores:** intent_accuracy=True · faithfulness=10.00 · answer_relevance=0.00

### `route_unknown_vague` — intent `unknown` (expected `unknown`)
**Query:** tell me stuff

**Answer:**
> 

**Scores:** intent_accuracy=True · faithfulness=10.00 · answer_relevance=0.00

### `portfolio_simple` — intent `portfolio` (expected `portfolio`)
**Query:** What does FLORES FAMILY TR own?

**Answer:**
> Based on the retrieved facts, FLORES FAMILY TR (a trust) is associated with two parcels:
> 
> | APN | Address |
> |---|---|
> | 447-281-05 | 61 Finisterra, Irvine |
> | 461-211-62 | 73 Bridgeport Rd, Irvine |
> 
> No year-built data is available for either parcel.
> 
> *Owner / title-chain data for these parcels is illustrative only and is not drawn from authoritative records.*

**Citations:** 447-281-05, 461-211-62
**Scores:** intent_accuracy=True · citation_recall=1.00 · faithfulness=10.00 · answer_relevance=9.00

### `portfolio_alt_phrasing` — intent `portfolio` (expected `portfolio`)
**Query:** Show all parcels held by FLORES FAMILY TR

**Answer:**
> Here are the parcels held by FLORES FAMILY TR in the retrieved data:
> 
> | APN | Address |
> |---|---|
> | 447-281-05 | 61 Finisterra, Irvine |
> | 461-211-62 | 73 Bridgeport Rd, Irvine |
> 
> Both are recorded as trust holdings. Year built is not available for either parcel.
> 
> *Owner and title-chain data for these parcels is illustrative only and not drawn from authoritative records.*

**Citations:** 447-281-05, 461-211-62
**Scores:** intent_accuracy=True · citation_recall=1.00 · faithfulness=10.00 · answer_relevance=8.50

### `portfolio_unknown_owner` — intent `portfolio` (expected `portfolio`)
**Query:** What does NONEXISTENT FAMILY TRUST own?

**Answer:**
> No facts were retrieved for "NONEXISTENT FAMILY TRUST." The available data contains no record of that entity owning any property.

**Scores:** intent_accuracy=True · refusal_correctness=1.00 · faithfulness=10.00 · answer_relevance=9.00
