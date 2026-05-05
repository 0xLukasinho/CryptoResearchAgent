import json
from unittest.mock import MagicMock

from crypto_research_agent.agents.style_card import StyleCard
from crypto_research_agent.agents.style_learner import StyleLearner


def test_load_samples_handles_txt(tmp_path):
    samples = tmp_path / "samples"
    samples.mkdir()
    (samples / "a.txt").write_text("Sample one.")
    (samples / "README.txt").write_text("ignore me")
    learner = StyleLearner(MagicMock(), model="m",
                           samples_dir=samples,
                           instructions_file=tmp_path / "missing.txt")
    materials = learner.get_raw_materials()
    titles = [s["filename"] for s in materials["samples"]]
    assert "a.txt" in titles
    assert "README.txt" not in titles


def test_generate_style_card_parses_llm_json(tmp_path):
    backend = MagicMock()
    backend.complete.return_value = MagicMock(text=json.dumps({
        "tone": "analytical",
        "sentence_patterns": "short",
        "vocabulary": {"preferred": ["on-chain"], "avoided": ["huge"]},
        "paragraph_structure": "claim then evidence",
        "section_openings": "bold assertions",
        "transitions": ["That said,"],
        "example_excerpts": ["Sample."],
    }))
    learner = StyleLearner(backend, model="m",
                           samples_dir=tmp_path, instructions_file=tmp_path / "i.txt")
    card = learner.generate_style_card({"samples": [], "instructions": ""})
    assert isinstance(card, StyleCard)
    assert card.tone == "analytical"


def test_generate_style_card_falls_back_on_garbage(tmp_path):
    backend = MagicMock()
    backend.complete.return_value = MagicMock(text="not json at all")
    learner = StyleLearner(backend, model="m",
                           samples_dir=tmp_path, instructions_file=tmp_path / "i.txt")
    card = learner.generate_style_card({"samples": [], "instructions": ""})
    assert card == StyleCard.fallback()
