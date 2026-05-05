from crypto_research_agent.agents.style_card import StyleCard, Vocabulary


def test_format_for_prompt_contains_all_sections():
    card = StyleCard(
        tone="analytical", sentence_patterns="short and punchy",
        vocabulary=Vocabulary(preferred=["on-chain"], avoided=["massive"]),
        paragraph_structure="claim then evidence",
        section_openings="bold assertions",
        transitions=["That said,"],
        example_excerpts=["Excerpt 1."],
    )
    out = card.format_for_prompt()
    assert "## Writing Style Guide" in out
    assert "analytical" in out
    assert "on-chain" in out
    assert "massive" in out
    assert "Excerpt 1." in out


def test_to_dict_and_from_dict_roundtrip():
    card = StyleCard.fallback()
    assert StyleCard.from_dict(card.to_dict()) == card
