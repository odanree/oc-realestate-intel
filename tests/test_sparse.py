"""Tokenizer + sparse-vector building — the pieces that don't need a live Qdrant."""

from __future__ import annotations

from app.services.vector import _to_sparse, _token_index, _tokenize


def test_tokenize_lowercases_and_splits_on_punctuation():
    assert _tokenize("73 BRIDGEPORT RD, Irvine!") == ["73", "bridgeport", "rd", "irvine"]


def test_tokenize_handles_empty():
    assert _tokenize("") == []


def test_token_index_is_stable():
    """Same token → same index, every process, every run."""
    assert _token_index("bridgeport") == _token_index("bridgeport")


def test_token_index_differs_per_token():
    assert _token_index("bridgeport") != _token_index("irvine")


def test_token_index_within_31_bits():
    idx = _token_index("anything")
    assert 0 <= idx < (1 << 31)


def test_sparse_vector_indices_match_unique_tokens():
    sv = _to_sparse("Irvine Irvine Bridgeport")
    # Two unique tokens — two entries.
    assert len(sv.indices) == 2
    assert len(sv.values) == 2
    # "Irvine" appeared twice — its value should be 2.0.
    by_idx = dict(zip(sv.indices, sv.values))
    assert by_idx[_token_index("irvine")] == 2.0
    assert by_idx[_token_index("bridgeport")] == 1.0


def test_sparse_vector_for_empty_text_is_not_rejected():
    """Qdrant rejects truly-empty sparse vectors. We send a placeholder."""
    sv = _to_sparse("")
    assert len(sv.indices) >= 1
    assert len(sv.values) >= 1
