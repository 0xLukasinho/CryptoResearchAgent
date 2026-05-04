from crypto_research_agent.llm._json import parse_json_loose


def test_strict_json_parses():
    assert parse_json_loose('{"key": "value"}') == {"key": "value"}


def test_messy_text_extracts_first_object():
    assert parse_json_loose('Sure!\n{"key": "value"}\nDone.') == {"key": "value"}


def test_nested_object_parses():
    assert parse_json_loose('{"a": {"b": 1}}') == {"a": {"b": 1}}


def test_garbage_returns_empty_dict():
    assert parse_json_loose("totally not json") == {}


def test_empty_string_returns_empty_dict():
    assert parse_json_loose("") == {}


def test_partial_json_returns_empty_dict():
    assert parse_json_loose("{not valid") == {}
