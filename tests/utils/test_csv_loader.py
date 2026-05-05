from crypto_research_agent.utils.csv_loader import load_substack_urls, load_youtube_channels


def test_load_substack_urls_filters_empty(tmp_path):
    csv_path = tmp_path / "subs.csv"
    csv_path.write_text(
        "Name,Substack URL\nFoo,https://foo.substack.com\nEmpty,\nBar,bar.substack.com\n"
    )
    urls = load_substack_urls(csv_path)
    assert "https://foo.substack.com" in urls
    assert "https://bar.substack.com" in urls  # protocol added
    assert all(u.startswith("https://") for u in urls)
    assert "" not in urls


def test_load_youtube_channels_returns_dataframe(tmp_path):
    csv_path = tmp_path / "yt.csv"
    csv_path.write_text("Name,Channel ID,YouTube URL\nFoo,UC123,https://youtube.com/@foo\n")
    df = load_youtube_channels(csv_path)
    assert len(df) == 1
    assert df.iloc[0]["Channel ID"] == "UC123"


def test_load_substack_urls_missing_file_returns_empty(tmp_path):
    assert load_substack_urls(tmp_path / "missing.csv") == []
