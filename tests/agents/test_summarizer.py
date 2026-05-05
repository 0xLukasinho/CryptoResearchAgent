from unittest.mock import MagicMock

from crypto_research_agent.agents.analyzer import AnalyzedItem
from crypto_research_agent.agents.summarizer import Summarizer


def _item(title="t", score="High"):
    return AnalyzedItem(title=title, author="a", date="d", url="u", text="t",
                        relevance_score=score, key_insights=["i"])


def test_summarize_returns_markdown():
    backend = MagicMock()
    backend.complete.return_value = MagicMock(text="# AI Agent Search Results\n...")
    summer = Summarizer(backend, model="m")
    out = summer.summarize(
        articles=[_item("A1")], videos=[],
        query="bitcoin", thesis=None,
    )
    assert out.startswith("# AI Agent Search Results")


def test_summarize_returns_no_results_message_when_empty():
    summer = Summarizer(MagicMock(), model="m")
    out = summer.summarize(articles=[], videos=[], query="x", thesis=None)
    assert "No relevant content found" in out
