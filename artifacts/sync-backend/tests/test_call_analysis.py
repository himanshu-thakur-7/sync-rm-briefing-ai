"""Post-call analysis engine tests (heuristic fallback path, no OpenAI key)."""
import pytest
from services.call_analysis_engine import analyze_call, _NBA_TOOLS


@pytest.mark.asyncio
async def test_empty_transcript():
    result = await analyze_call("", None, "save_call")
    assert result.summary  # graceful, non-crashing


@pytest.mark.asyncio
async def test_positive_call_reduces_churn(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    transcript = (
        "SYNC: We've found a way to save you money this year.\n"
        "Client: Yes, that would be good. Thank you, perfect."
    )
    result = await analyze_call(transcript, None, "save_call")
    assert result.sentiment_label in ("positive", "cautiously_positive")
    assert result.churn_label == "reduced"
    assert result.churn_delta < 0


@pytest.mark.asyncio
async def test_negative_call_increases_churn(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    transcript = (
        "SYNC: Calling about your account.\n"
        "Client: No. I'm really frustrated and not happy. I want to cancel."
    )
    result = await analyze_call(transcript, None, "save_call")
    assert result.sentiment_label == "concerned"
    assert result.churn_label == "increased"


@pytest.mark.asyncio
async def test_nba_tool_is_valid(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    transcript = "Client: Yes, call me back this week. Good."
    result = await analyze_call(transcript, None, "save_call")
    assert result.next_best_action.get("tool") in _NBA_TOOLS


@pytest.mark.asyncio
async def test_commitment_extracted(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    transcript = "Client: Yes, that would be good. Maybe call me later this week."
    result = await analyze_call(transcript, None, "save_call")
    assert any("callback" in c["text"].lower() or "week" in c["text"].lower()
               for c in result.commitments)
