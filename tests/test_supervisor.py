"""Supervisor unit tests — router classification + node wiring, no live LLM calls."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.agents.supervisor import route_after_router


def test_route_unknown_goes_to_end():
    assert route_after_router({"intent": "unknown"}) == "end"


def test_route_compare_goes_to_comparison():
    assert route_after_router({"intent": "compare"}) == "comparison"


@pytest.mark.parametrize("intent", ["lookup", "summarize", "title_chain"])
def test_route_retrieval_intents(intent):
    assert route_after_router({"intent": intent}) == "retrieval"


def test_route_missing_intent_goes_to_end():
    assert route_after_router({}) == "end"


@pytest.mark.asyncio
async def test_router_node_classifies_intent_from_llm_response():
    from app.agents.supervisor import router_node

    mock_response = type("M", (), {"content": "compare"})()
    with patch("app.agents.supervisor._judge_llm") as mock_llm:
        mock_llm.return_value.ainvoke = AsyncMock(return_value=mock_response)
        result = await router_node({"query": "compare 100 Main St to nearby comps"})

    assert result["intent"] == "compare"


@pytest.mark.asyncio
async def test_router_node_falls_back_to_unknown_on_invalid_response():
    from app.agents.supervisor import router_node

    mock_response = type("M", (), {"content": "explode the parcel"})()
    with patch("app.agents.supervisor._judge_llm") as mock_llm:
        mock_llm.return_value.ainvoke = AsyncMock(return_value=mock_response)
        result = await router_node({"query": "something weird"})

    assert result["intent"] == "unknown"
