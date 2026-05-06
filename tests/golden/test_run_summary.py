import datetime
from pathlib import Path

from freezegun import freeze_time

from crypto_research_agent.pipeline.stats import RunStats


@freeze_time("2026-05-04 14:23:01")
def test_run_summary_matches_golden():
    s = RunStats(started_at=datetime.datetime(2026, 5, 4, 14, 14, 1))
    s.record_call(cost_usd=2.0, tier="primary")
    s.record_call(cost_usd=1.5, tier="primary")
    s.record_call(cost_usd=0.77, tier="fallback")
    expected = (Path(__file__).parent / "run_summary.txt").read_text(encoding="utf-8")
    assert s.format_summary(query_label="bitcoin_etf_2026-05-04_142301") == expected
