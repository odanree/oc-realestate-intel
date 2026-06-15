"""Provenance classification — `_compute_provenance` in the summarize node.

The runtime disclaimer guard (formerly `_enforce_disclaimer`) moved to the
standalone [agent-governance](https://github.com/odanree/agent-governance)
package; its behavior is tested upstream there. The wiring is covered by
`tests/test_governance_wiring.py`.

See ADR-0004 (provenance) and ADR-0007 (governance node refactor).
"""

from __future__ import annotations

from app.agents.supervisor import CANONICAL_DISCLAIMER, _compute_provenance


def test_provenance_none_when_no_owner_data():
    parcels = [{"apn": "1", "address": "X"}, {"apn": "2", "address": "Y"}]
    prov = _compute_provenance(parcels, [])
    assert prov == {"owner_data_source": "none", "disclaimer": None}


def test_provenance_none_when_parcels_have_no_owner_field():
    """Parcel objects without `owner` populated should not flag synthetic."""
    parcels = [{"apn": "1", "owner_source": "synthetic"}]  # no `owner` value
    prov = _compute_provenance(parcels, [])
    assert prov["owner_data_source"] == "none"
    assert prov["disclaimer"] is None


def test_provenance_synthetic_when_owner_is_synthetic():
    parcels = [{"apn": "1", "owner": "FLORES FAMILY TR", "owner_source": "synthetic"}]
    prov = _compute_provenance(parcels, [])
    assert prov["owner_data_source"] == "synthetic"
    assert prov["disclaimer"] == CANONICAL_DISCLAIMER


def test_provenance_synthetic_when_graph_facts_present():
    """Title-chain transfers are synthetic today — any graph_facts triggers
    the disclaimer even if no parcel owner is named."""
    parcels = [{"apn": "1", "address": "X"}]
    graph_facts = [{"date": "2020-01-01", "grantor": "A", "grantee": "B"}]
    prov = _compute_provenance(parcels, graph_facts)
    assert prov["owner_data_source"] == "synthetic"
    assert prov["disclaimer"] == CANONICAL_DISCLAIMER


def test_provenance_authoritative_when_real_provider():
    parcels = [{"apn": "1", "owner": "REAL OWNER", "owner_source": "attom"}]
    prov = _compute_provenance(parcels, [])
    assert prov["owner_data_source"] == "authoritative"
    assert prov["disclaimer"] is None


def test_provenance_mixed_when_both_sources_present():
    parcels = [
        {"apn": "1", "owner": "X", "owner_source": "synthetic"},
        {"apn": "2", "owner": "Y", "owner_source": "attom"},
    ]
    prov = _compute_provenance(parcels, [])
    assert prov["owner_data_source"] == "mixed"
    assert prov["disclaimer"] == CANONICAL_DISCLAIMER
