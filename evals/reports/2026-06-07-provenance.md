# oc-realestate-intel eval report

- generated: 2026-06-08T01:35:31.529938Z
- judge model: `claude-sonnet-4-6`
- cases: 13
- total judge cost: $0.0618

## Summary

| metric | score |
|---|---|
| `intent_accuracy` | 0.92 |
| `citation_recall` | 1.00 |
| `citation_precision` | 1.00 |
| `refusal_correctness` | 1.00 |
| `faithfulness` | 9.90 |
| `answer_relevance` | 6.38 |

## Per-case detail

### `lookup_apn_basic` — intent `lookup` (expected `lookup`)
**Query:** What is parcel 461-211-62?

**Answer:**
> APN 461-211-62 is a parcel located at 73 Bridgeport Rd, Irvine, in the city of Irvine. The year built is not available in the retrieved data. The owner of record shown is FLORES FAMILY TRUST (a trust).
> 
> *Owner and title-chain data for this parcel is illustrative only and not drawn from authoritative records.*

**Citations:** 461-211-62
**Scores:** intent_accuracy=True · citation_recall=1.00 · faithfulness=10.00 · answer_relevance=9.00

### `lookup_apn_in_sentence` — intent `summarize` (expected `lookup`)
**Query:** Tell me about APN 461-211-62 — who owns it?

**Answer:**
> APN 461-211-62 is a parcel located at 73 Bridgeport Rd, Irvine. The retrieved data lists the owner as **FLORES FAMILY TRUST** (a trust). No year-built information is available for this parcel.
> 
> *Owner / title-chain data for this parcel is illustrative only and not drawn from authoritative records. For verified ownership information, contact the OC Assessor's office or the OC Clerk-Recorder's office.*

**Citations:** 461-211-62
**Scores:** intent_accuracy=False · citation_recall=1.00 · faithfulness=10.00 · answer_relevance=9.00

### `lookup_street_proper_noun` — intent `lookup` (expected `lookup`)
**Query:** Find parcels on Bridgeport Road in Irvine

**Answer:**
> From the retrieved facts, one parcel on Bridgeport Road in Irvine was found:
> 
> | APN | Address | Owner | Year Built |
> |---|---|---|---|
> | 461-211-62 | 73 Bridgeport Rd, Irvine | Flores Family Trust | Unknown |
> 
> No other Bridgeport Road parcels in Irvine appear in the retrieved data.
> 
> *Owner / title-chain data for the parcel above is illustrative only and not drawn from authoritative records.*

**Citations:** 461-211-62
**Scores:** intent_accuracy=True · citation_recall=1.00 · faithfulness=10.00 · answer_relevance=7.50

### `lookup_common_street` — intent `lookup` (expected `lookup`)
**Query:** What's on Irvine Park Road?

**Answer:**
> The retrieved facts do not contain any parcels located on Irvine Park Road. The addresses returned involve Mitchell Avenue in Irvine, Irvine Avenue in Newport Beach, and Park Plaza in Irvine — none of which match Irvine Park Road.
> 
> For parcels on Irvine Park Road, you would need to query the OC Assessor's office or the OC Clerk-Recorder's office directly.
> 
> *Owner / title-chain data shown in the retrieved facts is illustrative only and not from authoritative records.*

**Scores:** intent_accuracy=True · faithfulness=10.00 · answer_relevance=4.50

### `refuse_unknown_apn` — intent `lookup` (expected `lookup`)
**Query:** What is parcel 999-999-99?

**Answer:**
> The retrieved facts contain no record for parcel 999-999-99. That APN does not appear in the data available to me.
> 
> For authoritative information, you would need to contact the OC Assessor's office or the OC Clerk-Recorder's office directly.
> 
> *Owner / title-chain data for the parcels listed in the underlying facts is illustrative and not from authoritative records.*

**Scores:** intent_accuracy=True · citation_precision=1.00 · refusal_correctness=1.00 · faithfulness=10.00 · answer_relevance=8.50

### `owner_query_now_has_data` — intent `lookup` (expected `lookup`)
**Query:** Who owns 461-211-62?

**Answer:**
> Based on the retrieved facts, APN 461-211-62 (73 Bridgeport Rd, Irvine) is listed as owned by **FLORES FAMILY TRUST**.
> 
> *Owner / title-chain data for this parcel is illustrative only and not sourced from authoritative records. For verified ownership information, contact the OC Assessor's office or the OC Clerk-Recorder's office.*

**Citations:** 461-211-62
**Scores:** intent_accuracy=True · citation_recall=1.00 · faithfulness=10.00 · answer_relevance=9.00

### `title_chain_now_has_data` — intent `title_chain` (expected `title_chain`)
**Query:** Show the title chain for 461-211-62

**Answer:**
> **APN 461-211-62 — 73 Bridgeport Rd, Irvine**
> 
> Title chain (most recent first):
> 
> | Seq | Doc Date | Doc Number | Grantor | Grantee | Consideration |
> |-----|------------|-----------------|-------------------------------|----------------------|---------------|
> | 1 | 2019-10-23 | 2019-673577 | DAVID MARTIN | FLORES FAMILY TR | $2,369,389 |
> | 2 | 2012-10-25 | 2012-947955 | SADDLEBACK DEVELOPMENT CORP | DAVID MARTIN | not recorded |
> | 3 | 1997-01-05 | 1997-903433 | MARGARET PARK | SADDLEBACK DEVELOPMENT CORP | not recorded |
> 
> Current vested owner of record: FLORES FAMILY TRUST. Year built: not available in retrieved data.
> 
> *Owner and title-chain data above are illustrative only (synthetic) and are not drawn from authoritative OC Assessor or Clerk-Recorder records.*

**Citations:** 461-211-62
**Scores:** intent_accuracy=True · citation_recall=1.00 · faithfulness=10.00 · answer_relevance=5.00

### `compare_explicit` — intent `compare` (expected `compare`)
**Query:** Compare 1 Park Plaza in Irvine to nearby properties

**Answer:**
> Here is a comparison of APN 435-042-44 (1 Park Plaza, Irvine) against the nearby properties returned in the data:
> 
> | APN | Address | Owner | Owner Type | Year Built |
> |---|---|---|---|---|
> | 435-042-44 | 1 Park Plaza Irvine | Edward Martin | Person | Unknown |
> | 455-241-01 | 111 Academy Irvine | Matthew Hall | Person | Unknown |
> | 455-042-03 | 4127 Campus Dr Irvine | Dorothy Taylor | Person | 1984 |
> | 455-022-03 | 21 Berkeley Irvine | Saddleback Properties LLC | LLC | 1981 |
> | 455-021-01 | 19191 Harvard Ave Irvine | Christopher Taylor | Person | 1980 |
> | 445-132-16 | 19762 MacArthur Blvd Irvine | Christopher Hall | Person | 1979 |
> | 445-132-11 | 19742 MacArthur Blvd Irvine | Back Bay Properties LLC | LLC | 1979 |
> | 453-262-15 | 18700 Harvard Ave Irvine | Emily Miller | Person | Unknown |
> | 453-011-90 | 1 San Joaquin Irvine | Back Bay Capital LLC | LLC | 1977 |
> | 445-111-06 | 2212 Dupont Dr Irvine | Ashley White | Person | 1970 |
> | 461-321-39 | 1 Ambroise Irvine | Patricia Rivera | Person | Unknown |
> 
> What the data shows:
> 
> - **Year built** is unknown for 1 Park Plaza (APN 435-042-44) as well as for four other parcels (111 Academy, 18700 Harvard Ave, and 1 Ambroise). The remaining nearby properties range from 1970 to 1984.
> - **Owner type**: 1 Park Plaza is held by an individual. Among the nearby properties, two are held by LLCs (Saddleback Properties LLC at 21 Berkeley and Back Bay Properties LLC at 19742 MacArthur Blvd), and one additional LLC holds 1 San Joaquin (Back Bay Capital LLC). The remainder are held by individuals.
> - No sale prices, assessed values, square footage, use codes, or lot sizes were included in the retrieved data, so no comparison on those dimensions is possible.
> 
> For additional detail on any of these parcels, the OC Assessor's office and the OC Clerk-Recorder's office are the authoritative sources.
> 
> *Owner / title-chain data is illustrative and not from authoritative records.*

**Citations:** 435-042-44, 445-111-06, 445-132-11, 445-132-16, 453-011-90, 453-262-15, 455-021-01, 455-022-03, 455-042-03, 455-241-01, 461-321-39
**Scores:** intent_accuracy=True · faithfulness=9.20 · answer_relevance=8.50

### `title_chain_intent` — intent `title_chain` (expected `title_chain`)
**Query:** Trace the title chain on parcel 461-211-62

**Answer:**
> Here is the recorded title chain for APN 461-211-62 (73 Bridgeport Rd, Irvine), most recent first:
> 
> | Order | Doc Number | Date | Grantor | Grantee | Consideration |
> |---|---|---|---|---|---|
> | 1 | 2019-673577 | 2019-10-23 | DAVID MARTIN | FLORES FAMILY TR | $2,369,389 |
> | 2 | 2012-947955 | 2012-10-25 | SADDLEBACK DEVELOPMENT CORP | DAVID MARTIN | Not recorded |
> | 3 | 1997-903433 | 1997-01-05 | MARGARET PARK | SADDLEBACK DEVELOPMENT CORP | Not recorded |
> 
> The current vested owner of record is FLORES FAMILY TRUST. Three transfers appear in the retrieved data going back to 1997. No consideration was recorded for the two earlier transfers. The year built for this parcel is not available in the retrieved data.
> 
> For authoritative verification of this title chain, the OC Assessor's office and the OC Clerk-Recorder's office are the appropriate sources.
> 
> *Owner and title-chain data shown above are illustrative only and are not drawn from authoritative records.*

**Citations:** 461-211-62
**Scores:** intent_accuracy=True · faithfulness=10.00 · answer_relevance=8.50

### `refuse_title_chain_unknown_apn` — intent `title_chain` (expected `title_chain`)
**Query:** Show the title chain for parcel 999-999-99

**Answer:**
> No facts were retrieved for parcel 999-999-99. I cannot construct a title chain without source data.
> 
> For authoritative title and transfer history on this parcel, you would need to consult the OC Assessor's office or the OC Clerk-Recorder's office.

**Scores:** intent_accuracy=True · refusal_correctness=1.00 · faithfulness=9.50 · answer_relevance=8.50

### `summarize_address` — intent `summarize` (expected `summarize`)
**Query:** Summarize 73 Bridgeport Rd Irvine

**Answer:**
> **APN 461-211-62 — 73 Bridgeport Rd, Irvine**
> 
> - **City:** Irvine
> - **Owner of record:** Flores Family Trust (trust)
> - **Year built:** Unknown
> 
> No additional details — assessed value, lot size, square footage, zoning, or transfer history — are present in the retrieved facts.
> 
> ---
> 
> *Owner / title-chain data for APN 461-211-62 is illustrative only and not drawn from authoritative records.*

**Citations:** 461-211-62
**Scores:** intent_accuracy=True · citation_recall=1.00 · faithfulness=10.00 · answer_relevance=5.00

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
