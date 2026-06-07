"""
Synthetic owner + title-chain generator.

WHY THIS EXISTS
---------------
The OC public ArcGIS endpoints redact owner names ("Name" field returns "1"
as a placeholder). Real owner data requires either:

  1. A respectful HTML scrape of ocassessor.gov (per-parcel, rate-limited,
     captcha-fragile).
  2. A paid feed: ParcelQuest (~$3k/yr for OC), ATTOM Data API, or
     CoreLogic.

For development + demo purposes, this module generates deterministic synthetic
owners with realistic ownership patterns:

  ~50% individual owners
  ~25% LLCs / corporations (some hold multiple parcels — portfolio queries)
  ~15% family trusts (with common variants like "TRUST" vs "TR")
  ~10% other entities (estates, partnerships)

And realistic title chains:
  1–4 transfers per parcel over the last 30 years, with grantor → grantee
  chains, document numbers, recorded dates, and (for the final transfer) sale
  prices in the OC range.

The output is identical in shape to what a real provider would emit, so the
seed pipeline + Neo4j tools (owner_holdings, title_chain) can be exercised
end-to-end. To swap in real data, implement a provider with the same
interface and point seed.py at it.
"""

from __future__ import annotations

import hashlib
import random
from collections.abc import Iterable
from datetime import date, timedelta

# ---------------------------------------------------------------------------
# Owner pools — drawn from to fabricate realistic names.
# ---------------------------------------------------------------------------

_FIRST_NAMES = [
    "JAMES", "MARY", "ROBERT", "PATRICIA", "JOHN", "JENNIFER", "MICHAEL", "LINDA",
    "WILLIAM", "ELIZABETH", "DAVID", "BARBARA", "RICHARD", "SUSAN", "JOSEPH",
    "JESSICA", "THOMAS", "SARAH", "CHARLES", "KAREN", "CHRISTOPHER", "NANCY",
    "DANIEL", "LISA", "MATTHEW", "MARGARET", "ANTHONY", "BETTY", "DONALD",
    "SANDRA", "MARK", "ASHLEY", "PAUL", "DOROTHY", "STEVEN", "KIMBERLY",
    "ANDREW", "EMILY", "KENNETH", "DONNA", "GEORGE", "MICHELLE", "JOSHUA",
    "CAROL", "KEVIN", "AMANDA", "BRIAN", "MELISSA", "EDWARD", "DEBORAH",
]

_LAST_NAMES = [
    "SMITH", "JOHNSON", "WILLIAMS", "BROWN", "JONES", "GARCIA", "MILLER",
    "DAVIS", "RODRIGUEZ", "MARTINEZ", "HERNANDEZ", "LOPEZ", "GONZALEZ",
    "WILSON", "ANDERSON", "THOMAS", "TAYLOR", "MOORE", "JACKSON", "MARTIN",
    "LEE", "PEREZ", "THOMPSON", "WHITE", "HARRIS", "SANCHEZ", "CLARK",
    "RAMIREZ", "LEWIS", "ROBINSON", "WALKER", "YOUNG", "ALLEN", "KING",
    "WRIGHT", "SCOTT", "TORRES", "NGUYEN", "HILL", "FLORES", "GREEN",
    "ADAMS", "NELSON", "BAKER", "HALL", "RIVERA", "CAMPBELL", "MITCHELL",
    "CARTER", "ROBERTS", "CHEN", "WANG", "KIM", "PARK", "LIU",
]

_LLC_PREFIXES = [
    "PACIFIC COAST", "IRVINE PARK", "NEWPORT HARBOR", "TURTLE RIDGE",
    "QUAIL HILL", "WOODBRIDGE", "PORTOLA SPRINGS", "ORCHARD HILLS",
    "GROVE PARK", "SADDLEBACK", "BACK BAY", "LAGUNA HEIGHTS",
    "FASHION ISLAND", "DIAMOND BAR", "RIDGEPOINT", "BLUFFS",
]

_LLC_SUFFIXES = ["HOLDINGS LLC", "PROPERTIES LLC", "REALTY LLC", "INVESTMENTS LLC",
                 "PARTNERS LLC", "GROUP LLC", "CAPITAL LLC"]

_TRUST_SUFFIXES = ["FAMILY TRUST", "REVOCABLE TRUST", "LIVING TRUST", "FAMILY TR",
                   "REV TRUST", "LIVING TR"]

_OTHER_SUFFIXES = ["ESTATE OF", "BANK OF", "REAL ESTATE INC", "DEVELOPMENT CORP"]


def _stable_rng(seed: str) -> random.Random:
    """Deterministic per-parcel RNG so re-runs produce the same data."""
    h = hashlib.sha256(seed.encode()).digest()
    return random.Random(int.from_bytes(h[:8], "big"))


def _generate_owner(rng: random.Random, llc_pool: list[str]) -> tuple[str, str]:
    """Return (owner_name, owner_kind)."""
    roll = rng.random()
    if roll < 0.50:
        first = rng.choice(_FIRST_NAMES)
        last = rng.choice(_LAST_NAMES)
        return f"{first} {last}", "person"
    if roll < 0.75:
        # Reuse an LLC sometimes so they hold multiple parcels.
        if llc_pool and rng.random() < 0.4:
            return rng.choice(llc_pool), "llc"
        name = f"{rng.choice(_LLC_PREFIXES)} {rng.choice(_LLC_SUFFIXES)}"
        llc_pool.append(name)
        return name, "llc"
    if roll < 0.90:
        family = rng.choice(_LAST_NAMES)
        return f"{family} {rng.choice(_TRUST_SUFFIXES)}", "trust"
    suffix = rng.choice(_OTHER_SUFFIXES)
    if suffix.startswith("ESTATE OF"):
        return f"ESTATE OF {rng.choice(_LAST_NAMES)}", "other"
    return f"{rng.choice(_LLC_PREFIXES)} {suffix}", "other"


def _doc_number(rng: random.Random, year: int) -> str:
    """OC recorder doc numbers look like 2023-000123456."""
    return f"{year}-{rng.randint(100_000, 999_999):06d}"


def _price(rng: random.Random) -> int:
    """OC-range residential / commercial price."""
    tier = rng.random()
    if tier < 0.10:
        return rng.randint(300_000, 800_000)  # condos / older
    if tier < 0.75:
        return rng.randint(800_000, 2_500_000)  # SFH median band
    if tier < 0.95:
        return rng.randint(2_500_000, 6_000_000)  # luxury
    return rng.randint(6_000_000, 25_000_000)  # ultra-luxury / commercial


def generate_for_parcels(
    parcels: Iterable[dict],
    today: date | None = None,
) -> Iterable[dict]:
    """For each parcel dict, yield an enriched dict with owner + title_chain.

    Output schema (per parcel):
        {
            ...original parcel fields...,
            "owner": "JOHN SMITH",
            "owner_kind": "person" | "llc" | "trust" | "other",
            "title_chain": [
                {
                    "date": "2024-03-14",
                    "doc_number": "2024-000123456",
                    "grantor": "JANE DOE",
                    "grantee": "JOHN SMITH",
                    "price": 1450000,
                },
                ...
            ],
        }

    The function is generator-based so the seed script can stream-process.
    """
    today = today or date.today()
    llc_pool: list[str] = []

    for parcel in parcels:
        apn = parcel.get("apn") or ""
        rng = _stable_rng(apn)

        current_owner, current_kind = _generate_owner(rng, llc_pool)
        n_transfers = rng.randint(1, 4)

        # Generate transfer dates in chronological order so the chain stays
        # temporally consistent: each grantor must have been a prior grantee.
        chrono_dates = sorted(
            today - timedelta(days=rng.randint(1, 30) * 365 + rng.randint(0, 364))
            for _ in range(n_transfers)
        )

        # Build the chain forward in time. The original (pre-first-transfer)
        # owner is a fresh synthetic name; each subsequent grantee inherits
        # ownership; the FINAL transfer hands it to current_owner.
        prev_grantee, _ = _generate_owner(rng, llc_pool)
        transfers: list[dict] = []
        for i, xfer_date in enumerate(chrono_dates):
            if i == len(chrono_dates) - 1:
                new_grantee = current_owner
            else:
                new_grantee, _ = _generate_owner(rng, llc_pool)
            transfers.append({
                "date": xfer_date.isoformat(),
                "doc_number": _doc_number(rng, xfer_date.year),
                "grantor": prev_grantee,
                "grantee": new_grantee,
                # Most recent transfer gets a price; older ones often don't.
                "price": _price(rng) if i == len(chrono_dates) - 1 else None,
            })
            prev_grantee = new_grantee

        # Output most-recent-first.
        transfers.reverse()

        yield {
            **parcel,
            "owner": current_owner,
            "owner_kind": current_kind,
            "title_chain": transfers,
        }
