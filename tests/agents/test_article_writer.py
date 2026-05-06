from unittest.mock import MagicMock

from crypto_research_agent.agents.article_writer import ArticleWriter, SectionInfo


def _conv_returning(*responses):
    conv = MagicMock()
    conv.send.side_effect = list(responses)
    return conv


def test_start_article_creates_file_and_primes(tmp_path):
    conv = _conv_returning("Acknowledged.")
    aw = ArticleWriter(conv, output_path=tmp_path / "article.md")
    path = aw.start_article(title="Bitcoin ETF",
                             outline="## 1. Intro", research_summary="summary")
    assert path.exists()
    assert "# Bitcoin ETF" in path.read_text(encoding="utf-8")
    assert conv.send.call_count == 1


def test_write_section_appends_to_file(tmp_path):
    conv = _conv_returning("Acknowledged.", "## Intro\n\nbody")
    aw = ArticleWriter(conv, output_path=tmp_path / "article.md")
    aw.start_article(title="T", outline="o", research_summary="s")
    body = aw.write_section(SectionInfo(title="Intro", content="cover basics"), sources={})
    assert body.startswith("## Intro")
    assert "## Intro" in (tmp_path / "article.md").read_text(encoding="utf-8")
    assert len(aw.accepted_sections) == 1


def test_revise_section_does_not_append_to_file(tmp_path):
    conv = _conv_returning("Acknowledged.", "## Intro\n\nv1", "## Intro\n\nv2")
    aw = ArticleWriter(conv, output_path=tmp_path / "article.md")
    aw.start_article(title="T", outline="o", research_summary="s")
    aw.write_section(SectionInfo(title="Intro", content="x"), sources={})
    revised = aw.revise_section("Intro", instructions="rewrite", current_content="## Intro\nv1")
    assert "v2" in revised
    # file still has v1 until accept_revision
    assert "v1" in (tmp_path / "article.md").read_text(encoding="utf-8")


def test_write_section_strips_llm_preamble(tmp_path):
    """LLM may include chatty preamble before the heading; strip it so the
    article file contains only proper sections."""
    chatty = "Sure, let me write that section now.\n\n## Intro\n\nbody"
    conv = _conv_returning("Acknowledged.", chatty)
    aw = ArticleWriter(conv, output_path=tmp_path / "article.md")
    aw.start_article(title="T", outline="o", research_summary="s")
    body = aw.write_section(SectionInfo(title="Intro", content="x"), sources={})
    assert body.startswith("## Intro")
    assert "let me write" not in body
    file_text = (tmp_path / "article.md").read_text(encoding="utf-8")
    assert "let me write" not in file_text


def test_accept_revision_rewrites_file(tmp_path):
    conv = _conv_returning("Acknowledged.", "## Intro\n\nv1", "## Intro\n\nv2")
    aw = ArticleWriter(conv, output_path=tmp_path / "article.md")
    aw.start_article(title="T", outline="o", research_summary="s")
    aw.write_section(SectionInfo(title="Intro", content="x"), sources={})
    aw.accept_revision("Intro", "## Intro\n\nv2")
    text = (tmp_path / "article.md").read_text(encoding="utf-8")
    assert "v2" in text
    assert "v1" not in text
