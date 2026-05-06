from unittest.mock import MagicMock

from crypto_research_agent.agents.style_card import StyleCard
from crypto_research_agent.pipeline.writing import WritingStage


def test_writing_stage_persists_style_card_and_loops_sections(tmp_path):
    style_learner = MagicMock()
    style_learner.get_raw_materials.return_value = {"samples": [], "instructions": ""}
    style_learner.generate_style_card.return_value = StyleCard.fallback()
    article_writer_factory = MagicMock()
    article_writer = MagicMock()
    article_writer.article_path = tmp_path / "article.md"
    article_writer.write_section.side_effect = lambda s, sources: f"## {s.title}\nbody"
    article_writer_factory.return_value = article_writer
    section_review = MagicMock()
    section_review.run.side_effect = lambda **kw: kw["section_content"]

    stage = WritingStage(
        ctx=MagicMock(output_dir=tmp_path, query="q"),
        style_learner=style_learner,
        article_writer_factory=article_writer_factory,
        section_review=section_review,
    )
    sections = [{"title": "Intro", "content": "outline"},
                {"title": "Body", "content": "outline"}]
    stage.write(outline="# o", sections=sections, articles=[], videos=[], user_content=[],
                research_summary="summary", user_content_only=False)
    assert (tmp_path / "style_card.json").exists()
    assert article_writer.write_section.call_count == 2
