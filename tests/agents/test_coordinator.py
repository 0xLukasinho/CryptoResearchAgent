# tests/agents/test_coordinator.py
import sys
sys.path.insert(0, '.')
import inspect


def test_coordinator_has_no_openai():
    import agents.coordinator as mod
    source = inspect.getsource(mod)
    assert 'from openai' not in source
    assert 'OpenAI(' not in source


def test_coordinator_ask_returns_json_string():
    from unittest.mock import MagicMock, patch
    with patch('agents.claude_agent_base.AnthropicClient') as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.generate_content.return_value = '{"main_topic": "Bitcoin", "keywords": ["Bitcoin"], "required_terms": ["Bitcoin"], "subtopics": [], "search_strategy": "test", "competing_projects": []}'

        from agents.coordinator import CoordinatorAgent
        agent = CoordinatorAgent()
        result = agent.ask("Bitcoin ETF")
        assert result is not None
        assert "Bitcoin" in result
