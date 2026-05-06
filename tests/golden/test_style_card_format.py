from pathlib import Path

from crypto_research_agent.agents.style_card import StyleCard, Vocabulary


def test_style_card_format_matches_golden():
    card = StyleCard(
        tone="analytical and informative", sentence_patterns="short and punchy",
        vocabulary=Vocabulary(preferred=["on-chain"], avoided=["massive"]),
        paragraph_structure="claim then evidence", section_openings="bold assertions",
        transitions=["That said,"], example_excerpts=["Excerpt 1.", "Excerpt 2."],
    )
    expected = (Path(__file__).parent / "style_card_prompt.txt").read_text(encoding="utf-8")
    assert card.format_for_prompt() == expected.rstrip("\n")
