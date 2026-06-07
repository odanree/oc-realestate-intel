"""Citation extraction — only cite APNs that actually appear in the answer."""

from __future__ import annotations

from app.agents.supervisor import _citations_from_answer

PARCELS = [
    {"apn": "934-21-145", "address": "100 Pacific Coast Hwy"},
    {"apn": "456-78-901", "address": "1 Park Plaza"},
    {"apn": "123-45-678", "address": "42 Main St"},
]


def test_returns_only_mentioned_apns():
    answer = "Irvine Company owns APN 934-21-145 at 100 PCH."
    cites = _citations_from_answer(answer, PARCELS)
    assert cites == [{"apn": "934-21-145", "address": "100 Pacific Coast Hwy"}]


def test_returns_multiple_when_multiple_mentioned():
    answer = "We found 934-21-145 and 123-45-678 in the dataset."
    cites = _citations_from_answer(answer, PARCELS)
    apns = {c["apn"] for c in cites}
    assert apns == {"934-21-145", "123-45-678"}


def test_returns_empty_when_no_apns_mentioned():
    answer = "No matching parcels were found for that query."
    assert _citations_from_answer(answer, PARCELS) == []


def test_ignores_apns_not_in_retrieved():
    answer = "Found 999-99-999 in some other dataset."
    assert _citations_from_answer(answer, PARCELS) == []


def test_handles_4_digit_third_group():
    parcels = [{"apn": "111-22-3456", "address": "X"}]
    answer = "Parcel 111-22-3456 sold last year."
    assert _citations_from_answer(answer, parcels) == [
        {"apn": "111-22-3456", "address": "X"}
    ]
