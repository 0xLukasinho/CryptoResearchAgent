from unittest.mock import MagicMock

from crypto_research_agent.feedback.outline_review import OutlineReview


def test_outline_review_accept(tmp_path, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda *_: "accept")
    f = tmp_path / "outline.md"
    f.write_text("# x")
    out = OutlineReview().run(outline_path=f, outline_writer=MagicMock(),
                              articles=[], videos=[], user_content=[],
                              query="q", thesis=None)
    assert out == "# x"


def test_outline_review_revise_calls_writer(tmp_path, monkeypatch):
    inputs = iter(["revise add a section", "accept"])
    monkeypatch.setattr("builtins.input", lambda *_: next(inputs))
    f = tmp_path / "outline.md"
    f.write_text("# v1")
    ow = MagicMock()
    ow.revise.return_value = "# v2"
    final = OutlineReview().run(outline_path=f, outline_writer=ow,
                                articles=[], videos=[], user_content=[],
                                query="q", thesis=None)
    assert final == "# v2"
    assert f.read_text() == "# v2"
