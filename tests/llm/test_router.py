from unittest.mock import MagicMock
import pytest

from crypto_research_agent.llm.router import LLMRouter
from crypto_research_agent.llm.errors import QuotaExceeded
from crypto_research_agent.llm.types import ClaudeResponse


def _resp(text="ok"):
    return ClaudeResponse(text=text, session_id="s", cost_usd=0.0,
                          input_tokens=0, output_tokens=0)


def test_routes_to_primary_by_default():
    primary = MagicMock()
    primary.complete.return_value = _resp("primary")
    router = LLMRouter(primary=primary)
    r = router.complete(prompt="x", model="m")
    assert r.text == "primary"


def test_quota_error_triggers_callback_and_uses_fallback():
    primary = MagicMock()
    primary.complete.side_effect = QuotaExceeded("out")
    fallback = MagicMock()
    fallback.complete.return_value = _resp("fallback")
    triggered = []
    router = LLMRouter(primary=primary)
    router.set_fallback_factory(lambda choice: fallback)

    def on_quota():
        triggered.append(True)
        return "opus"  # user picked Opus on the API

    router.on_quota_exhausted = on_quota
    r = router.complete(prompt="x", model="m")
    assert triggered == [True]
    assert r.text == "fallback"


def test_subsequent_calls_skip_primary_after_fallback_active():
    primary = MagicMock()
    primary.complete.side_effect = QuotaExceeded("out")
    fallback = MagicMock()
    fallback.complete.return_value = _resp("fallback")
    router = LLMRouter(primary=primary)
    router.set_fallback_factory(lambda choice: fallback)
    router.on_quota_exhausted = lambda: "sonnet"

    router.complete(prompt="a", model="m")
    router.complete(prompt="b", model="m")

    # primary called only once; fallback used twice
    assert primary.complete.call_count == 1
    assert fallback.complete.call_count == 2


def test_abort_choice_propagates_quota_exceeded():
    primary = MagicMock()
    primary.complete.side_effect = QuotaExceeded("out")
    router = LLMRouter(primary=primary)
    router.on_quota_exhausted = lambda: "abort"
    with pytest.raises(QuotaExceeded):
        router.complete(prompt="x", model="m")
