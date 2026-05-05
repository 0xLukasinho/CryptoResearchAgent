from crypto_research_agent.utils.filters import (
    contains_all_required_terms, is_likely_english,
)


def test_contains_all_terms_true_when_all_present():
    article = {"title": "Bitcoin ETF News", "text": "The Bitcoin ETF was approved."}
    assert contains_all_required_terms(article, ["bitcoin", "etf"]) is True


def test_contains_all_terms_false_when_missing():
    article = {"title": "Bitcoin News", "text": "Just bitcoin discussion."}
    assert contains_all_required_terms(article, ["bitcoin", "etf"]) is False


def test_contains_all_terms_passes_when_no_required_terms():
    article = {"title": "Anything", "text": "Anything"}
    assert contains_all_required_terms(article, []) is True


def test_contains_all_terms_case_insensitive():
    article = {"title": "BITCOIN", "text": "ETF approved"}
    assert contains_all_required_terms(article, ["bitcoin", "etf"]) is True


def test_contains_all_terms_handles_string_input():
    text = "Bitcoin ETF was approved"
    assert contains_all_required_terms(text, ["bitcoin", "etf"]) is True


def test_is_likely_english_true_for_english():
    text = "The quick brown fox jumps over the lazy dog and runs into the woods."
    assert is_likely_english(text) is True


def test_is_likely_english_false_for_garbage():
    text = "asdfghj qwerty zxcvbnm"
    assert is_likely_english(text) is False
