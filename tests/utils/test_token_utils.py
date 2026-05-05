from crypto_research_agent.utils.token_utils import truncate_to_token_limit


def test_short_text_unchanged():
    text = "Hello world. This is a short sentence."
    assert truncate_to_token_limit(text, "claude-haiku-4-5-20251001", 1000) == text


def test_long_text_gets_truncated():
    text = "This is a sentence. " * 500
    result = truncate_to_token_limit(text, "claude-haiku-4-5-20251001", 100)
    assert len(result) < len(text)


def test_truncates_at_sentence_boundary_when_available():
    sentence_ending = "This ends here. "
    filler = "word " * 150
    after = "more words after " * 50
    text = filler + sentence_ending + after
    result = truncate_to_token_limit(text, "claude-haiku-4-5-20251001", 160)
    stripped = result.strip()
    assert stripped.endswith(('.', '?', '!'))
