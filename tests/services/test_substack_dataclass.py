from crypto_research_agent.services.substack import Article


def test_article_required_fields():
    a = Article(
        title="Hello",
        author="Alice",
        date="2026-01-01",
        text="body",
        url="https://example.com",
    )
    assert a.title == "Hello"
    assert a.url.startswith("https://")
