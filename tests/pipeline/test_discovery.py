from unittest.mock import MagicMock

from crypto_research_agent.agents.analyzer import AnalyzedItem
from crypto_research_agent.agents.coordinator import SearchPlan
from crypto_research_agent.pipeline.discovery import DiscoveryStage
from crypto_research_agent.pipeline.runner import RunContext, SourceConfig
from crypto_research_agent.services.substack import Article


def _ctx(tmp_path, substack=True, youtube=True):
    return RunContext(query="q", thesis=None, output_dir=tmp_path,
                      test_mode=False, search_mode=False,
                      sources=SourceConfig(substack=substack, youtube=youtube),
                      max_age_days=None)


def test_discovery_runs_substack_only(tmp_path):
    article = Article(title="Bitcoin ETF", author="A", date="2026", text="bitcoin etf", url="u")
    substack = MagicMock()
    substack.discover.return_value = [article]
    youtube = MagicMock()
    analyzer = MagicMock()
    analyzer.analyze_batch.return_value = [
        AnalyzedItem(title="Bitcoin ETF", author="A", date="2026", url="u", text="t",
                     relevance_score="High")
    ]

    stage = DiscoveryStage(
        ctx=_ctx(tmp_path, substack=True, youtube=False),
        substack_service=substack, youtube_service=youtube, analyzer=analyzer,
    )
    articles, videos = stage.run(SearchPlan(main_topic="x", required_terms=["bitcoin", "etf"]))
    assert len(articles) == 1
    assert videos == []
    youtube.search.assert_not_called()


def test_discovery_filters_with_required_terms(tmp_path):
    keep = Article(title="Bitcoin ETF", author="A", date="2026", text="bitcoin etf yes", url="u1")
    drop = Article(title="Bitcoin only", author="A", date="2026", text="just bitcoin", url="u2")
    substack = MagicMock()
    substack.discover.return_value = [keep, drop]
    analyzer = MagicMock()
    analyzer.analyze_batch.return_value = [
        AnalyzedItem(title="Bitcoin ETF", author="A", date="2026", url="u1", text="t",
                     relevance_score="High")
    ]
    stage = DiscoveryStage(
        ctx=_ctx(tmp_path, substack=True, youtube=False),
        substack_service=substack, youtube_service=MagicMock(), analyzer=analyzer,
    )
    stage.run(SearchPlan(main_topic="x", required_terms=["bitcoin", "etf"]))
    pre_filter_passed = analyzer.analyze_batch.call_args.kwargs.get("items") or analyzer.analyze_batch.call_args.args[0]
    assert len(pre_filter_passed) == 1
