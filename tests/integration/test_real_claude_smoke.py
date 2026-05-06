import os

import pytest

from crypto_research_agent.config import CLAUDE_FAST_MODEL
from crypto_research_agent.llm.claude_code import ClaudeCodeBackend


@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_TESTS") != "1",
    reason="Live test against real `claude -p`; set RUN_LIVE_TESTS=1 to enable.",
)
def test_one_real_claude_call_completes():
    backend = ClaudeCodeBackend()
    response = backend.complete(
        prompt="Reply with the single word: pong",
        model=CLAUDE_FAST_MODEL,
        system_prompt="Respond with exactly one word.",
    )
    assert "pong" in response.text.lower()
    assert response.session_id is not None
    assert response.cost_usd >= 0.0
