# tests/utils/test_token_utils.py
import sys
sys.path.insert(0, '.')
from utils.token_utils import truncate_to_token_limit


def test_short_text_unchanged():
    text = "Hello world. This is a short sentence."
    result = truncate_to_token_limit(text, "claude-haiku-4-5-20251001", 1000)
    assert result == text


def test_long_text_gets_truncated():
    text = "This is a sentence. " * 500
    result = truncate_to_token_limit(text, "claude-haiku-4-5-20251001", 100)
    assert len(result) < len(text)


def test_truncated_text_fits_limit():
    import tiktoken
    enc = tiktoken.get_encoding("cl100k_base")
    text = "word " * 2000
    result = truncate_to_token_limit(text, "claude-haiku-4-5-20251001", 200)
    assert len(enc.encode(result)) <= 200


def test_truncates_at_sentence_boundary_when_available():
    """If a sentence boundary exists near the truncation point, truncate there not mid-word."""
    # Build text: lots of filler then a clear sentence ending near the truncation point
    # ~200 tokens of filler, ending with "This is a sentence. " (sentence boundary)
    # then more words after
    sentence_ending = "This ends here. "
    filler = "word " * 150   # ~150 tokens
    after = "more words after " * 50  # tokens we won't reach anyway
    text = filler + sentence_ending + after
    
    result = truncate_to_token_limit(text, "claude-haiku-4-5-20251001", 160)
    # Result should end with a period (sentence boundary) not mid-word
    stripped = result.strip()
    assert stripped.endswith('.') or stripped.endswith('?') or stripped.endswith('!')
