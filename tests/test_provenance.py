"""Provenance classification + disclaimer guard.

Covers ADR-0004 (synthetic owners with provenance flagging) and threat
model T1 (output-side disclaimer assertion) and T3 (structured provenance
field). See docs/threat-model.md.
"""

from __future__ import annotations

from app.agents.supervisor import (
    CANONICAL_DISCLAIMER,
    _compute_provenance,
    _enforce_disclaimer,
)


# ---------------------------------------------------------------------------
# _compute_provenance
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# _enforce_disclaimer
# ---------------------------------------------------------------------------


def test_disclaimer_appended_when_model_drops_it():
    answer = "Parcel 461-211-62 is owned by FLORES FAMILY TR."
    prov = {"owner_data_source": "synthetic", "disclaimer": CANONICAL_DISCLAIMER}
    result = _enforce_disclaimer(answer, prov)
    assert CANONICAL_DISCLAIMER in result
    assert result.startswith("Parcel 461-211-62")


def test_disclaimer_not_duplicated_when_model_includes_italic_synthetic_note():
    answer = (
        "Parcel 461-211-62 is owned by FLORES FAMILY TR.\n\n"
        "*Owner data is synthetic and illustrative only.*"
    )
    prov = {"owner_data_source": "synthetic", "disclaimer": CANONICAL_DISCLAIMER}
    result = _enforce_disclaimer(answer, prov)
    assert result == answer  # untouched


def test_disclaimer_not_duplicated_for_underscore_italic():
    answer = (
        "Parcel 461-211-62.\n\n_Note: owner data is illustrative only._"
    )
    prov = {"owner_data_source": "synthetic", "disclaimer": CANONICAL_DISCLAIMER}
    result = _enforce_disclaimer(answer, prov)
    assert result == answer


def test_disclaimer_not_duplicated_when_phrased_not_from_authoritative():
    answer = (
        "Parcel 461-211-62.\n\n"
        "*Title chain data is not from authoritative records.*"
    )
    prov = {"owner_data_source": "synthetic", "disclaimer": CANONICAL_DISCLAIMER}
    result = _enforce_disclaimer(answer, prov)
    assert result == answer


def test_disclaimer_not_appended_when_provenance_is_authoritative():
    answer = "Parcel 461-211-62 is owned by REAL OWNER."
    prov = {"owner_data_source": "authoritative", "disclaimer": None}
    result = _enforce_disclaimer(answer, prov)
    assert result == answer
    assert "synthetic" not in result.lower()


def test_disclaimer_not_appended_when_no_owner_data():
    answer = "No matching parcels were found."
    prov = {"owner_data_source": "none", "disclaimer": None}
    result = _enforce_disclaimer(answer, prov)
    assert result == answer


def test_unrelated_italic_text_does_not_satisfy_guard():
    """An italic phrase that doesn't mention provenance shouldn't suppress
    the canonical disclaimer — the guard is about *what* is italicized."""
    answer = "Parcel 461-211-62 was *recently* updated."
    prov = {"owner_data_source": "synthetic", "disclaimer": CANONICAL_DISCLAIMER}
    result = _enforce_disclaimer(answer, prov)
    assert CANONICAL_DISCLAIMER in result
