from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta

from crypto_research_agent.services.substack import SubstackService, Article


def _make_post(title="T", days_old=0, body="body"):
    p = MagicMock()
    p.url = f"https://foo.substack.com/p/{title.lower()}"
    date = (datetime.now(timezone.utc) - timedelta(days=days_old)).isoformat().replace("+00:00", "Z")
    p.get_metadata.return_value = {
        "title": title,
        "post_date": date,
        "byline": "Author",
        "canonical_url": p.url,
        "description": "intro",
    }
    p.get_content.return_value = f"<p>{body}</p>"
    return p


def test_fetch_posts_converts_to_articles(tmp_path):
    csv = tmp_path / "subs.csv"
    csv.write_text("Name,Substack URL\nFoo,https://foo.substack.com\n")
    svc = SubstackService(csv, request_delay=0.0)
    fake_nl = MagicMock()
    fake_nl.get_posts.return_value = [_make_post("a"), _make_post("b")]
    with patch.object(svc, "_make_newsletter", return_value=fake_nl):
        articles = svc.fetch_posts("https://foo.substack.com",
                                   max_articles=10, max_age_days=None)
    assert len(articles) == 2
    assert isinstance(articles[0], Article)
    assert articles[0].title == "a"


def test_fetch_posts_age_filter_drops_old(tmp_path):
    csv = tmp_path / "subs.csv"
    csv.write_text("Name,Substack URL\nFoo,https://foo.substack.com\n")
    svc = SubstackService(csv, request_delay=0.0)
    fake_nl = MagicMock()
    fake_nl.get_posts.side_effect = [
        [_make_post("fresh", 1), _make_post("old", 100)],
        [],  # end of pagination
    ]
    with patch.object(svc, "_make_newsletter", return_value=fake_nl):
        articles = svc.fetch_posts("https://foo.substack.com",
                                   max_articles=100, max_age_days=30)
    titles = [a.title for a in articles]
    assert "fresh" in titles
    assert "old" not in titles


def test_fetch_posts_respects_max_articles(tmp_path):
    csv = tmp_path / "subs.csv"
    csv.write_text("Name,Substack URL\nFoo,https://foo.substack.com\n")
    svc = SubstackService(csv, request_delay=0.0)
    fake_nl = MagicMock()
    fake_nl.get_posts.return_value = [_make_post(f"p{i}") for i in range(25)]
    with patch.object(svc, "_make_newsletter", return_value=fake_nl):
        articles = svc.fetch_posts("https://foo.substack.com",
                                   max_articles=5, max_age_days=None)
    assert len(articles) == 5
