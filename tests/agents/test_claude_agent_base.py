# tests/agents/test_claude_agent_base.py
import sys
sys.path.insert(0, '.')
from unittest.mock import MagicMock, patch


def test_complete_json_parses_valid_json():
    with patch('agents.claude_agent_base.AnthropicClient') as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.generate_content.return_value = '{"key": "value", "num": 42}'

        from agents.claude_agent_base import ClaudeAgentBase
        agent = ClaudeAgentBase()
        result = agent.complete_json("prompt", "system")
        assert result == {"key": "value", "num": 42}


def test_complete_json_extracts_json_from_messy_response():
    with patch('agents.claude_agent_base.AnthropicClient') as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.generate_content.return_value = 'Here is the JSON:\n{"key": "value"}\nDone.'

        from agents.claude_agent_base import ClaudeAgentBase
        agent = ClaudeAgentBase()
        result = agent.complete_json("prompt", "system")
        assert result == {"key": "value"}


def test_complete_json_returns_empty_dict_on_failure():
    with patch('agents.claude_agent_base.AnthropicClient') as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.generate_content.return_value = "This is not JSON at all."

        from agents.claude_agent_base import ClaudeAgentBase
        agent = ClaudeAgentBase()
        result = agent.complete_json("prompt", "system")
        assert result == {}
