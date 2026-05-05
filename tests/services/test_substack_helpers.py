import responses
from crypto_research_agent.services.substack import _Newsletter, _Post


@responses.activate
def test_newsletter_get_posts_returns_list():
    responses.add(
        responses.GET,
        "https://foo.substack.com/api/v1/posts",
        json={"posts": [
            {"canonical_url": "https://foo.substack.com/p/article-1", "slug": "article-1"},
            {"canonical_url": "https://foo.substack.com/p/article-2", "slug": "article-2"},
        ]},
        status=200,
    )
    nl = _Newsletter("https://foo.substack.com")
    posts = nl.get_posts(limit=10)
    assert len(posts) == 2
    assert posts[0].url == "https://foo.substack.com/p/article-1"


@responses.activate
def test_post_get_metadata_caches():
    responses.add(
        responses.GET,
        "https://foo.substack.com/api/v1/posts/article-1",
        json={"title": "Hello", "post_date": "2026-01-01T00:00:00Z",
              "byline": "Alice", "canonical_url": "https://foo.substack.com/p/article-1",
              "description": "Intro", "body_html": "<p>body</p>"},
        status=200,
    )
    p = _Post("https://foo.substack.com/p/article-1")
    md1 = p.get_metadata()
    md2 = p.get_metadata()
    assert md1["title"] == "Hello"
    assert md1 is md2 or md1 == md2
    # only one HTTP call
    assert len(responses.calls) == 1
