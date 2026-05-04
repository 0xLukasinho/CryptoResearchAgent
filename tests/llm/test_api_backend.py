from unittest.mock import patch, MagicMock

from crypto_research_agent.llm.api_backend import AnthropicAPIBackend


def _mock_message(text="reply"):
    m = MagicMock()
    m.content = [MagicMock(text=text)]
    m.usage = MagicMock(input_tokens=11, output_tokens=22)
    return m


def test_complete_calls_anthropic_messages_create():
    with patch("crypto_research_agent.llm.api_backend.anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_client.messages.create.return_value = _mock_message("hi")

        backend = AnthropicAPIBackend(api_key="sk-test")
        r = backend.complete(prompt="hello", model="claude-haiku-4-5-20251001",
                             system_prompt="be brief")

    args = mock_client.messages.create.call_args.kwargs
    assert args["model"] == "claude-haiku-4-5-20251001"
    assert args["system"] == "be brief"
    assert args["messages"] == [{"role": "user", "content": "hello"}]
    assert r.text == "hi"
    assert r.input_tokens == 11
    assert r.output_tokens == 22


def test_complete_with_resume_session_uses_stored_history():
    with patch("crypto_research_agent.llm.api_backend.anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_client.messages.create.return_value = _mock_message("turn-2")

        backend = AnthropicAPIBackend(api_key="sk-test")
        # first turn
        backend.complete(prompt="hi", model="m")
        # second turn, "resume" session id from first turn (synthetic)
        backend.complete(prompt="again", model="m", resume_session=backend._last_session_id)

    second_call = mock_client.messages.create.call_args_list[1].kwargs
    assert len(second_call["messages"]) == 3  # user1, assistant1, user2


def test_session_id_is_returned_and_distinct_per_root_call():
    with patch("crypto_research_agent.llm.api_backend.anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_client.messages.create.return_value = _mock_message("ok")

        backend = AnthropicAPIBackend(api_key="sk-test")
        a = backend.complete(prompt="a", model="m")
        b = backend.complete(prompt="b", model="m")

    assert a.session_id and b.session_id
    assert a.session_id != b.session_id


def test_complete_json_uses_strict_prompt():
    with patch("crypto_research_agent.llm.api_backend.anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_client.messages.create.return_value = _mock_message('{"a": 1}')

        backend = AnthropicAPIBackend(api_key="sk-test")
        out = backend.complete_json(prompt="x", model="m", system_prompt="be helpful")

    assert out == {"a": 1}
    sys_prompt = mock_client.messages.create.call_args.kwargs["system"]
    assert "valid JSON only" in sys_prompt
