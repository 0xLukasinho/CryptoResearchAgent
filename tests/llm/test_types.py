from crypto_research_agent.llm.types import ClaudeResponse


def test_claude_response_holds_fields():
    r = ClaudeResponse(
        text="hello",
        session_id="abc-123",
        cost_usd=0.0042,
        input_tokens=100,
        output_tokens=50,
    )
    assert r.text == "hello"
    assert r.session_id == "abc-123"
    assert r.cost_usd == 0.0042
    assert r.input_tokens == 100
    assert r.output_tokens == 50


def test_claude_response_session_id_optional():
    r = ClaudeResponse(text="hi", session_id=None, cost_usd=0.0,
                      input_tokens=0, output_tokens=0)
    assert r.session_id is None
