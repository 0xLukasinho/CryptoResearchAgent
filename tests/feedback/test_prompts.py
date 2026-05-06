from crypto_research_agent.feedback.prompts import parse_feedback_input


def test_accept_word_and_number():
    assert parse_feedback_input("accept") == {"action": "accept", "details": None}
    assert parse_feedback_input("1") == {"action": "accept", "details": None}


def test_edited_word_and_number():
    assert parse_feedback_input("edited") == {"action": "edited", "details": None}
    assert parse_feedback_input("3") == {"action": "edited", "details": None}


def test_revise_with_instructions_word_form():
    out = parse_feedback_input("revise make it shorter")
    assert out == {"action": "revise", "details": "make it shorter"}


def test_revise_with_instructions_number_form():
    out = parse_feedback_input("2 make it shorter")
    assert out == {"action": "revise", "details": "make it shorter"}


def test_revise_without_instructions_returns_invalid():
    assert parse_feedback_input("revise") == {"action": "invalid", "details": None}
    assert parse_feedback_input("2") == {"action": "invalid", "details": None}


def test_unknown_input_returns_invalid():
    assert parse_feedback_input("xyz")["action"] == "invalid"


def test_handles_extra_whitespace_and_case():
    out = parse_feedback_input("  ACCEPT  ")
    assert out == {"action": "accept", "details": None}
