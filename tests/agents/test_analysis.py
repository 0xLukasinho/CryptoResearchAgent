# tests/agents/test_analysis.py
import sys
sys.path.insert(0, '.')
import inspect


def test_analysis_has_no_openai():
    import agents.analysis as mod
    source = inspect.getsource(mod)
    assert 'from openai' not in source
    assert 'OpenAI(' not in source


def test_analyze_article_returns_dict_with_expected_keys():
    from unittest.mock import MagicMock, patch
    with patch('agents.claude_agent_base.AnthropicClient') as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.generate_content.return_value = '''{
            "relevance_score": "High",
            "relevance_explanation": "Very relevant",
            "key_insights": ["Insight 1"],
            "mentioned_projects": ["Bitcoin"],
            "thesis_alignment": "Not Applicable",
            "thesis_alignment_explanation": "No thesis"
        }'''

        from agents.analysis import AnalysisAgent
        agent = AnalysisAgent()
        article = {
            "title": "Bitcoin ETF News", "text": "Bitcoin ETF approved by SEC...",
            "author": "Author", "date": "2024-01-01", "url": "http://example.com"
        }
        result = agent.analyze_article(article, '{"main_topic": "Bitcoin"}')
        assert result is not None
        assert result['relevance_score'] == 'High'
        assert result['title'] == 'Bitcoin ETF News'
