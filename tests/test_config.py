from crypto_research_agent.config import (
    CLAUDE_FAST_MODEL, CLAUDE_PREMIUM_MODEL, CLAUDE_SONNET_MODEL,
    get_model_for_role,
)


def test_model_constants_present():
    assert CLAUDE_FAST_MODEL == "claude-haiku-4-5-20251001"
    assert CLAUDE_PREMIUM_MODEL == "claude-opus-4-7"
    assert CLAUDE_SONNET_MODEL == "claude-sonnet-4-6"


def test_get_model_for_role_test_mode_uses_haiku_everywhere():
    assert get_model_for_role("fast", test_mode=True) == CLAUDE_FAST_MODEL
    assert get_model_for_role("premium", test_mode=True) == CLAUDE_FAST_MODEL


def test_get_model_for_role_normal_mode():
    assert get_model_for_role("fast", test_mode=False) == CLAUDE_FAST_MODEL
    assert get_model_for_role("premium", test_mode=False) == CLAUDE_PREMIUM_MODEL


def test_get_model_for_role_invalid_raises():
    import pytest
    with pytest.raises(KeyError):
        get_model_for_role("nonsense", test_mode=False)
