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
