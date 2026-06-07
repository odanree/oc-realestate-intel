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
           o.name AS grantee
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
