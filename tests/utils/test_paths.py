from pathlib import Path
import datetime
from freezegun import freeze_time

from crypto_research_agent.utils.paths import (
    sanitize_query_slug, build_output_dir,
)


def test_sanitize_simple():
    assert sanitize_query_slug("Bitcoin ETF") == "bitcoin_etf"


def test_sanitize_strips_punctuation():
    assert sanitize_query_slug("Bitcoin's ETF/Approval!") == "bitcoins_etf_approval"


def test_sanitize_collapses_whitespace_and_underscores():
    assert sanitize_query_slug("a   b___c") == "a_b_c"


def test_sanitize_truncates_long_input():
    out = sanitize_query_slug("x" * 200)
    assert len(out) <= 60


def test_sanitize_falls_back_for_empty():
    assert sanitize_query_slug("") == "query"
    assert sanitize_query_slug("!!!") == "query"


@freeze_time("2026-05-04 14:23:01")
def test_build_output_dir_appends_timestamp(tmp_path):
    out = build_output_dir(tmp_path, "Bitcoin ETF")
    assert out == tmp_path / "bitcoin_etf_2026-05-04_142301"
    assert not out.exists()  # caller creates


@freeze_time("2026-05-04 14:23:01")
def test_build_output_dir_unique_when_duplicate(tmp_path):
    first = build_output_dir(tmp_path, "Bitcoin ETF")
    first.mkdir()
    second = build_output_dir(tmp_path, "Bitcoin ETF")
    assert second != first
    assert second.name.startswith("bitcoin_etf_2026-05-04_142301")
