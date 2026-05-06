from unittest.mock import MagicMock

from crypto_research_agent.pipeline.synthesis import SynthesisStage


def test_save_summary_writes_file(tmp_path):
    summarizer = MagicMock()
    summarizer.summarize.return_value = "# Results\nbody"
    outline_writer = MagicMock()
    stage = SynthesisStage(
        ctx=MagicMock(output_dir=tmp_path, query="q", thesis=None),
        summarizer=summarizer, outline_writer=outline_writer, outline_review=MagicMock(),
    )
    out = stage.save_summary(articles=[], videos=[])
    assert str(out).endswith("research_results.md")
    assert (tmp_path / "research_results.md").read_text(encoding="utf-8").startswith("# Results")


def test_synthesize_runs_outline_writer_and_review(tmp_path):
    summarizer = MagicMock()
    summarizer.summarize.return_value = "# Summary"
    outline_writer = MagicMock()
    outline_writer.generate.return_value = "# Outline"
    review = MagicMock()
    review.run.return_value = "# Outline approved"
    stage = SynthesisStage(
        ctx=MagicMock(output_dir=tmp_path, query="q", thesis=None),
        summarizer=summarizer, outline_writer=outline_writer, outline_review=review,
    )
    final = stage.synthesize(articles=[], videos=[], user_content=[],
                              user_content_only=False)
    assert final == "# Outline approved"
    assert (tmp_path / "research_outline.md").exists()
