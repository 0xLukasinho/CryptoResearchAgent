from unittest.mock import MagicMock

import pytest

from crypto_research_agent.agents.analyzer import Analyzer, AnalyzedItem
from crypto_research_agent.llm.errors import (
    AuthMissing, ClaudeCodeError, QuotaExceeded, TransientError,
)
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


def test_analyze_returns_error_item_on_timeout():
    """A single LLM timeout must not abort the batch — produce an Error item."""
    backend = MagicMock()
    backend.complete_json.side_effect = ClaudeCodeError(
        "`claude -p` timed out after 300s"
    )
    analyzer = Analyzer(backend, model="m")
    result = analyzer.analyze(_article(), main_topic="x", thesis=None)
    assert result is not None
    assert result.relevance_score == "Error"
    assert "ClaudeCodeError" in result.relevance_explanation


def test_analyze_returns_error_item_on_transient_error():
    backend = MagicMock()
    backend.complete_json.side_effect = TransientError("network flap")
    analyzer = Analyzer(backend, model="m")
    result = analyzer.analyze(_article(), main_topic="x", thesis=None)
    assert result is not None
    assert result.relevance_score == "Error"


def test_analyze_propagates_quota_and_auth_errors():
    """Quota / auth must bubble up — the router needs them to trigger fallback
    or fail fast on misconfiguration."""
    backend = MagicMock()
    backend.complete_json.side_effect = QuotaExceeded("limit hit")
    analyzer = Analyzer(backend, model="m")
    with pytest.raises(QuotaExceeded):
        analyzer.analyze(_article(), main_topic="x", thesis=None)

    backend.complete_json.side_effect = AuthMissing("not signed in")
    with pytest.raises(AuthMissing):
        analyzer.analyze(_article(), main_topic="x", thesis=None)


def test_analyze_batch_continues_after_per_article_failure():
    """Batch must process all items even if some LLM calls fail."""
    backend = MagicMock()
    # 1st: ok High, 2nd: timeout, 3rd: ok Medium
    backend.complete_json.side_effect = [
        {"relevance_score": "High", "key_insights": [], "mentioned_projects": [],
         "thesis_alignment": "Not Applicable"},
        ClaudeCodeError("timeout"),
        {"relevance_score": "Medium", "key_insights": [], "mentioned_projects": [],
         "thesis_alignment": "Not Applicable"},
    ]
    analyzer = Analyzer(backend, model="m")
    results = analyzer.analyze_batch(
        [_article(), _article(), _article()],
        main_topic="x", thesis=None, test_mode=False,
    )
    assert len(results) == 3
    assert [r.relevance_score for r in results] == ["High", "Error", "Medium"]


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
