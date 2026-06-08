"""Tests for the live-fallback trigger heuristic."""

from __future__ import annotations

from app.agents.supervisor import _hits_match_address


def _p(addr: str) -> dict:
    return {"address": addr}


def test_no_address_in_query_skips_fallback():
    """Queries without a street number shouldn't trigger live fallback."""
    assert _hits_match_address("Who owns 461-211-62?", [])
    assert _hits_match_address("recent sales in Irvine", [_p("100 Main St")])


def test_address_with_matching_hit_skips_fallback():
    assert _hits_match_address(
        "Find 73 Bridgeport Rd Irvine",
        [_p("73 BRIDGEPORT RD IRVINE")],
    )


def test_address_with_no_matching_hit_triggers_fallback():
    """Hits are all top-k semantic noise — none contain our street number."""
    assert not _hits_match_address(
        "find parcel for address 470 s alpine rd orange ca",
        [
            _p("100 Pacific Coast Hwy"),
            _p("1 Park Plaza"),
            _p("73 BRIDGEPORT RD IRVINE"),
        ],
    )


def test_address_with_number_match_but_wrong_street_triggers_fallback():
    """House number matches but street name doesn't."""
    assert not _hits_match_address(
        "find 470 Alpine",
        [_p("470 BRIDGEPORT RD IRVINE")],
    )


def test_partial_match_on_street_token_satisfies():
    """If a hit contains both the number and the street word, no fallback."""
    assert _hits_match_address(
        "find 470 Alpine",
        [_p("470 S ALPINE RD ORANGE")],
    )


def test_empty_hits_with_address_triggers_fallback():
    assert not _hits_match_address("find 470 Alpine Rd", [])
