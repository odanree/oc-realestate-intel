"""
Neo4j wrapper — owner ↔ parcel ↔ deed relationship graph.

Schema:
    (:Owner {name, normalized_name, kind})
        -[:HOLDS {since}]-> (:Parcel {apn, address, zip})
    (:Parcel) -[:TRANSFERRED {date, doc_number, price}]-> (:Owner)

The normalized_name field collapses common entity variants
("THE SMITH FAMILY TRUST" ≈ "SMITH FAMILY TR").
"""

from __future__ import annotations

import logging

from neo4j import AsyncGraphDatabase

from app.config import settings

log = logging.getLogger(__name__)

_driver = None


def _get_driver():
    global _driver
    if _driver is None:
        _driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
    return _driver


async def close() -> None:
    global _driver
    if _driver is not None:
        await _driver.close()
        _driver = None


async def ensure_constraints() -> None:
    driver = _get_driver()
    async with driver.session() as session:
        await session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (p:Parcel) REQUIRE p.apn IS UNIQUE")
        await session.run(
            "CREATE CONSTRAINT IF NOT EXISTS FOR (o:Owner) "
            "REQUIRE o.normalized_name IS UNIQUE"
        )


async def clear_graph() -> None:
    """Drop all Parcel/Owner nodes + their relationships. Used by --recreate."""
    driver = _get_driver()
    async with driver.session() as session:
        await session.run("MATCH (n) WHERE n:Parcel OR n:Owner DETACH DELETE n")


async def upsert_parcel_with_chain(parcel: dict) -> None:
    """Write a parcel + its full title chain into Neo4j in one transaction.

    Expected parcel shape (from synthetic_owners.generate_for_parcels):
        {
            "apn": "461-211-62",
            "address": "73 BRIDGEPORT RD",
            "city": "IRVINE",
            "owner": "JOHN SMITH",
            "owner_kind": "person",
            "title_chain": [
                {"date": "2024-...", "grantor": "...", "grantee": "...", ...},
                ...
            ],
        }
    """
    apn = parcel["apn"]
    driver = _get_driver()
    async with driver.session() as session:
        async with await session.begin_transaction() as tx:
            # Parcel node
            await tx.run(
                """
                MERGE (p:Parcel {apn: $apn})
                SET p.address = $address, p.city = $city, p.zip = $zip
                """,
                apn=apn,
                address=parcel.get("address") or "",
                city=parcel.get("city") or "",
                zip=parcel.get("zip") or "",
            )

            # Current owner + HOLDS edge
            owner = parcel.get("owner")
            if owner:
                await tx.run(
                    """
                    MERGE (o:Owner {normalized_name: $normalized})
                    SET o.name = $name, o.kind = $kind
                    WITH o
                    MATCH (p:Parcel {apn: $apn})
                    MERGE (o)-[:HOLDS]->(p)
                    """,
                    normalized=_normalize_owner(owner),
                    name=owner,
                    kind=parcel.get("owner_kind") or "other",
                    apn=apn,
                )

            # Title transfers: (Parcel)-[:TRANSFERRED]->(Owner-grantee)
            for t in parcel.get("title_chain") or []:
                grantee = t.get("grantee")
                if not grantee:
                    continue
                await tx.run(
                    """
                    MERGE (o:Owner {normalized_name: $normalized})
                    SET o.name = coalesce(o.name, $name), o.kind = coalesce(o.kind, $kind)
                    WITH o
                    MATCH (p:Parcel {apn: $apn})
                    MERGE (p)-[t:TRANSFERRED {doc_number: $doc_number}]->(o)
                    SET t.date = $date, t.price = $price, t.grantor = $grantor
                    """,
                    normalized=_normalize_owner(grantee),
                    name=grantee,
                    kind="other",
                    apn=apn,
                    doc_number=t.get("doc_number") or "",
                    date=t.get("date") or "",
                    price=t.get("price"),
                    grantor=t.get("grantor") or "",
                )
            await tx.commit()


async def owner_holdings(owner_name_or_apn: str) -> list[dict]:
    """Resolve owner by name OR by parcel APN, then return everything they hold."""
    driver = _get_driver()
    normalized = _normalize_owner(owner_name_or_apn)

    cypher = """
    MATCH (o:Owner)-[:HOLDS]->(p:Parcel)
    WHERE o.normalized_name = $normalized
       OR EXISTS { MATCH (o)-[:HOLDS]->(:Parcel {apn: $apn}) }
    RETURN p.apn AS apn, p.address AS address, o.name AS owner,
           o.kind AS owner_kind
    ORDER BY p.address
    """
    async with driver.session() as session:
        result = await session.run(cypher, normalized=normalized, apn=owner_name_or_apn)
        return [dict(record) async for record in result]


async def title_chain(apn: str, limit: int = 20) -> list[dict]:
    cypher = """
    MATCH (p:Parcel {apn: $apn})-[t:TRANSFERRED]->(o:Owner)
    RETURN t.date AS date, t.doc_number AS doc_number, t.price AS price,
           t.grantor AS grantor, o.name AS grantee
    ORDER BY t.date DESC
    LIMIT $limit
    """
    driver = _get_driver()
    async with driver.session() as session:
        result = await session.run(cypher, apn=apn, limit=limit)
        return [dict(record) async for record in result]


def _normalize_owner(name: str) -> str:
    """Collapse common entity variants for fuzzy match."""
    return (
        name.upper()
        .replace("THE ", "")
        .replace(" TRUST", " TR")
        .replace(", LLC", " LLC")
        .replace(",", "")
        .strip()
    )
