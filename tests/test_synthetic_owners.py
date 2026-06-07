"""Synthetic owner generator — determinism and temporal-consistency invariants."""

from __future__ import annotations

from datetime import date

from app.ingestion.synthetic_owners import generate_for_parcels


def _enrich(parcels):
    return list(generate_for_parcels(parcels, today=date(2026, 6, 7)))


def test_each_parcel_gets_owner_and_chain():
    out = _enrich([{"apn": "461-211-62", "address": "73 Bridgeport Rd", "city": "IRVINE"}])
    assert len(out) == 1
    assert out[0]["owner"]
    assert out[0]["owner_kind"] in ("person", "llc", "trust", "other")
    assert len(out[0]["title_chain"]) >= 1


def test_output_is_deterministic_per_apn():
    """Re-runs of the generator must produce identical owner data for the same APN."""
    a = _enrich([{"apn": "461-211-62"}])[0]
    b = _enrich([{"apn": "461-211-62"}])[0]
    assert a["owner"] == b["owner"]
    assert a["title_chain"] == b["title_chain"]


def test_chain_is_temporally_consistent():
    """Each transfer's grantor must be the next-older transfer's grantee."""
    parcels = [{"apn": f"100-001-{i:02d}"} for i in range(20)]
    out = _enrich(parcels)
    for parcel in out:
        chain = parcel["title_chain"]
        # chain[0] is most recent, chain[-1] is oldest
        for newer, older in zip(chain, chain[1:]):
            assert newer["grantor"] == older["grantee"], (
                f"APN {parcel['apn']}: grantor of {newer['date']} "
                f"({newer['grantor']}) != grantee of {older['date']} ({older['grantee']})"
            )


def test_most_recent_grantee_is_current_owner():
    """The newest transfer's grantee must be the parcel's current owner."""
    parcels = [{"apn": f"200-002-{i:02d}"} for i in range(20)]
    out = _enrich(parcels)
    for parcel in out:
        assert parcel["title_chain"][0]["grantee"] == parcel["owner"]


def test_dates_are_in_descending_order():
    parcels = [{"apn": f"300-003-{i:02d}"} for i in range(10)]
    out = _enrich(parcels)
    for parcel in out:
        dates = [t["date"] for t in parcel["title_chain"]]
        assert dates == sorted(dates, reverse=True)


def test_only_most_recent_transfer_has_price():
    parcels = [{"apn": f"400-004-{i:02d}"} for i in range(10)]
    out = _enrich(parcels)
    for parcel in out:
        chain = parcel["title_chain"]
        assert chain[0]["price"] is not None
        for t in chain[1:]:
            assert t["price"] is None
