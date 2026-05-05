from crypto_research_agent.services.youtube import (
    Video, filter_by_required_terms, score_relevance,
)


def _v(title="", description=""):
    return Video(title=title, channel="C", date="2026-01-01",
                 description=description, video_id="vid", url="u")


def test_filter_requires_all_terms_in_content_and_at_least_one_in_title():
    v_ok = _v(title="Bitcoin ETF news", description="discussion of approval")
    v_no_title = _v(title="Crypto chat", description="Bitcoin ETF mentioned")
    v_missing = _v(title="Bitcoin", description="bitcoin only")
    out = filter_by_required_terms([v_ok, v_no_title, v_missing], ["bitcoin", "etf"])
    assert v_ok in out
    assert v_no_title not in out
    assert v_missing not in out


def test_filter_passes_all_when_no_required_terms():
    vs = [_v(title="x"), _v(title="y")]
    assert filter_by_required_terms(vs, []) == vs


def test_score_relevance_sets_high_for_interview_with_query_match():
    v = _v(title="Bitcoin ETF interview with founder", description="")
    scored = score_relevance(v, query="Bitcoin ETF")
    assert scored.relevance_score == "High"
    assert scored.interview_score >= 10


def test_score_relevance_default_medium():
    v = _v(title="Random video", description="random")
    scored = score_relevance(v, query="Bitcoin ETF")
    assert scored.relevance_score == "Medium"
