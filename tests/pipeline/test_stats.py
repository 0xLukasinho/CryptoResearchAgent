from crypto_research_agent.pipeline.stats import RunStats


def test_run_stats_records_calls_and_cost():
    s = RunStats()
    s.record_call(cost_usd=0.01, tier="primary")
    s.record_call(cost_usd=0.02, tier="primary")
    s.record_call(cost_usd=0.03, tier="fallback")
    summary = s.format_summary(query_label="bitcoin_etf")
    assert "Total calls:        3" in summary
    assert "Subscription:       2" in summary
    assert "API fallback:       1" in summary
    assert "$0.06" in summary
