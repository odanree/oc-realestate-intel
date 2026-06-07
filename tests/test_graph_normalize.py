"""Owner-name normalization is the only piece of graph.py that doesn't need a live Neo4j."""

from __future__ import annotations

from app.services.graph import _normalize_owner


def test_normalize_strips_the_prefix():
    assert _normalize_owner("THE SMITH FAMILY TRUST") == "SMITH FAMILY TR"


def test_normalize_collapses_trust_suffix():
    assert _normalize_owner("Smith Family Trust") == "SMITH FAMILY TR"


def test_normalize_handles_llc_comma():
    assert _normalize_owner("Irvine Company, LLC") == "IRVINE COMPANY LLC"


def test_normalize_strips_whitespace():
    assert _normalize_owner("  ACME HOLDINGS LLC  ") == "ACME HOLDINGS LLC"
