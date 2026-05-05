from unittest.mock import MagicMock

from crypto_research_agent.agents.analyzer import Analyzer, AnalyzedItem
from crypto_research_agent.services.substack import Article


def _article():
    return Article(title="Bitcoin ETF approved",
                   author="A", date="2026-01-01",
                   text="The SEC approved Bitcoin ETF.", url="u")


def test_analyze_article_returns_analyzed_item():
    backend = MagicMock()
    backend.complete_json.return_value = {
        "relevance_score": "High",
        "key_insights": ["SEC approved"],
        "mentioned_projects": ["Bitcoin"],
        "thesis_alignment": "Not Applicable",
    }
    analyzer = Analyzer(backend, model="m")
    result = analyzer.analyze(_article(), main_topic="Bitcoin ETF", thesis=None)
    assert isinstance(result, AnalyzedItem)
    assert result.relevance_score == "High"
    assert result.key_insights == ["SEC approved"]


def test_analyze_returns_none_for_non_english():
    backend = MagicMock()
    backend.complete_json.return_value = {"non_english": True, "language_detected": "Spanish"}
    analyzer = Analyzer(backend, model="m")
    assert analyzer.analyze(_article(), main_topic="x", thesis=None) is None


def test_analyze_uses_thesis_alignment_when_provided():
    backend = MagicMock()
    backend.complete_json.return_value = {
        "relevance_score": "Medium",
        "thesis_alignment": "High",
        "thesis_alignment_explanation": "matches",
        "key_insights": [],
        "mentioned_projects": [],
    }
    analyzer = Analyzer(backend, model="m")
    result = analyzer.analyze(_article(), main_topic="x", thesis="my thesis")
    assert result.relevance_score == "High"  # promoted from thesis_alignment


def test_analyze_batch_short_circuits_in_test_mode():
    backend = MagicMock()
    backend.complete_json.return_value = {
        "relevance_score": "High", "key_insights": [], "mentioned_projects": [],
        "thesis_alignment": "Not Applicable",
    }
    analyzer = Analyzer(backend, model="m")
    results = analyzer.analyze_batch(
        [_article(), _article(), _article(), _article()],
        main_topic="x", thesis=None, test_mode=True,
    )
    assert len(results) == 2  # stops after 2 high/medium
