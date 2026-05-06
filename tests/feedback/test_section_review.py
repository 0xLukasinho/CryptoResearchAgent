from unittest.mock import MagicMock

from crypto_research_agent.feedback.section_review import SectionReview


def test_section_review_accept_returns_content_unchanged(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda *_: "accept")
    sr = SectionReview()
    aw = MagicMock()
    out = sr.run(section_title="Intro", section_content="## Intro\nbody",
                 article_writer=aw, sources={})
    assert out == "## Intro\nbody"
    aw.revise_section.assert_not_called()


def test_section_review_revise_calls_writer(monkeypatch):
    inputs = iter(["revise tighten paragraph 2", "accept"])
    monkeypatch.setattr("builtins.input", lambda *_: next(inputs))
    sr = SectionReview()
    aw = MagicMock()
    aw.revise_section.return_value = "## Intro\nv2"
    out = sr.run(section_title="Intro", section_content="## Intro\nv1",
                 article_writer=aw, sources={})
    assert out == "## Intro\nv2"
    aw.revise_section.assert_called_once()
    aw.accept_revision.assert_called_once_with("Intro", "## Intro\nv2")
