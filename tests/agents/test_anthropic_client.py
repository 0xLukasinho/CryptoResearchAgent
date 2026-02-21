# tests/agents/test_anthropic_client.py
import sys
sys.path.insert(0, '.')
from unittest.mock import MagicMock, patch


def make_mock_response(text="test response"):
    mock = MagicMock()
    mock.content = [MagicMock(text=text)]
    return mock


def test_generate_with_history_passes_full_message_list():
    with patch('agents.anthropic_client.anthropic') as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_client.messages.create.return_value = make_mock_response("reply")

        from agents.anthropic_client import AnthropicClient
        client = AnthropicClient()

        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
            {"role": "user", "content": "How are you?"},
        ]
        result = client.generate_with_history(messages, system_prompt="Be helpful")

        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["messages"] == messages
        assert call_kwargs["system"] == "Be helpful"
        assert result == "reply"


def test_generate_with_history_uses_quality_model_by_default():
    with patch('agents.anthropic_client.anthropic') as mock_anthropic:
        from config import CLAUDE_QUALITY_MODEL
        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_client.messages.create.return_value = make_mock_response()

        from agents.anthropic_client import AnthropicClient
        client = AnthropicClient()
        client.generate_with_history([{"role": "user", "content": "test"}])

        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["model"] == CLAUDE_QUALITY_MODEL
