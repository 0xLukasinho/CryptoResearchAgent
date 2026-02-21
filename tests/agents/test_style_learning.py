# tests/agents/test_style_learning.py
import sys
sys.path.insert(0, '.')
from unittest.mock import MagicMock, patch
import json


def test_generate_style_card_returns_dict_with_required_keys():
    with patch('agents.anthropic_client.anthropic') as mock_anthropic:
        mock_client_instance = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client_instance
        style_card_json = json.dumps({
            "tone": "analytical",
            "sentence_patterns": "mix of short and long",
            "vocabulary": {"preferred": ["on-chain"], "avoided": ["massive"]},
            "paragraph_structure": "claim, evidence, implication",
            "section_openings": "questions or bold assertions",
            "transitions": ["That said,"],
            "example_excerpts": ["Example excerpt one."]
        })
        mock_client_instance.messages.create.return_value = MagicMock(
            content=[MagicMock(text=style_card_json)]
        )

        from agents.style_learning import StyleLearningAgent
        agent = StyleLearningAgent()
        style_materials = {
            'samples': [{'filename': 'sample.txt', 'content': 'My writing sample here.'}],
            'instructions': 'Be concise.'
        }
        card = agent.generate_style_card(style_materials)

        assert isinstance(card, dict)
        assert 'tone' in card
        assert 'example_excerpts' in card
        assert isinstance(card['example_excerpts'], list)


def test_format_style_card_for_prompt_returns_formatted_string():
    from agents.style_learning import StyleLearningAgent
    agent = StyleLearningAgent()
    card = {
        "tone": "analytical but conversational",
        "sentence_patterns": "short and punchy",
        "vocabulary": {"preferred": ["on-chain"], "avoided": ["massive"]},
        "paragraph_structure": "claim then evidence",
        "section_openings": "bold assertions",
        "transitions": ["That said,"],
        "example_excerpts": ["Sample excerpt here. This shows the voice."]
    }
    result = agent.format_style_card_for_prompt(card)
    assert "analytical but conversational" in result
    assert "Sample excerpt here." in result
    assert "## Writing Style Guide" in result
    assert "Vocabulary to avoid" in result
