"""End-to-end WritingStage test with a stubbed LLM (no real claude calls).

Wires together a real ArticleWriter + real SectionReview + real WritingStage
and verifies that revise / accept_revision / edited paths produce the correct
final article.md when driven through the production code paths.

Covers what the unit tests miss: the integration of SectionReview's revise-loop
with ArticleWriter's accept_revision file-rewrite, including multiple
revisions on the same section.
"""
from unittest.mock import MagicMock

from crypto_research_agent.agents.article_writer import ArticleWriter
from crypto_research_agent.agents.style_card import StyleCard
from crypto_research_agent.feedback.section_review import SectionReview
from crypto_research_agent.pipeline.writing import WritingStage


class _FakeConversation:
    """Stub of the Conversation wrapper. Returns the next pre-queued response
    on each .send(prompt) call. Records the prompts it received."""

    def __init__(self, responses: list[str]):
        self._queue = list(responses)
        self.received_prompts: list[str] = []

    def send(self, prompt: str) -> str:
        self.received_prompts.append(prompt)
        if not self._queue:
            raise AssertionError(
                f"FakeConversation exhausted but got another send() call. "
                f"Last prompt prefix: {prompt[:200]!r}"
            )
        return self._queue.pop(0)


def _make_inputs(values):
    it = iter(values)
    def fake_input(prompt=""):
        return next(it)
    return fake_input


def test_writing_stage_e2e_accept_revise_edited_paths(tmp_path, monkeypatch):
    """Three sections, three different feedback paths:

    Section 1 → user types 'accept'         → file gets the original LLM output
    Section 2 → user revises twice, accepts → file gets the 2nd revision only
                                              (no leftover original or v1)
    Section 3 → user types 'edited'         → file gets the LLM output (the
                                              file content "as edited" is just
                                              what's already there)

    Verifies file ordering, no preamble bleed, no duplicate sections, and
    style_card.json persistence — all through real production classes with
    only the LLM call stubbed.
    """
    # 6 LLM responses in the order WritingStage will trigger them
    fake_conv = _FakeConversation([
        "Acknowledged. I'll match the style.",          # 1: priming
        "## 1. Intro\n\nFirst sentence about ETFs.",    # 2: section 1 written
        "## 2. Body\n\nOriginal body of section 2.",    # 3: section 2 written
        "## 2. Body\n\nRevised body v1.",               # 4: section 2 revise #1
        "## 2. Body\n\nRevised body v2 (final).",       # 5: section 2 revise #2
        "## 3. Conclusion\n\nWrap-up paragraph.",       # 6: section 3 written
    ])

    # 5 user inputs corresponding to the SectionReview prompts
    monkeypatch.setattr("builtins.input", _make_inputs([
        "accept",                       # section 1
        "revise tighten the prose",     # section 2: ask to revise
        "revise make it even shorter",  # section 2: revise again
        "accept",                       # section 2: now accept v2
        "edited",                       # section 3: pretend user edited file
    ]))

    style_learner = MagicMock()
    style_learner.get_raw_materials.return_value = {"samples": [], "instructions": ""}
    style_learner.generate_style_card.return_value = StyleCard.fallback()

    captured_paths: dict[str, object] = {}
    def factory(*, card, output_path):
        captured_paths["article"] = output_path
        return ArticleWriter(fake_conv, output_path=output_path)

    ctx = MagicMock(output_dir=tmp_path, query="Bitcoin ETF")
    stage = WritingStage(
        ctx=ctx,
        style_learner=style_learner,
        article_writer_factory=factory,
        section_review=SectionReview(),
    )

    sections = [
        {"title": "1. Intro", "content": "Introduce the topic."},
        {"title": "2. Body", "content": "Develop the argument."},
        {"title": "3. Conclusion", "content": "Summarize."},
    ]

    article_path = stage.write(
        outline="# Outline\n## 1. Intro\n## 2. Body\n## 3. Conclusion",
        sections=sections,
        articles=[], videos=[], user_content=[],
        research_summary="research summary text",
        user_content_only=False,
    )

    # File path matches what the factory was given
    assert article_path == captured_paths["article"]
    assert article_path.exists()

    text = article_path.read_text(encoding="utf-8")

    # Title initialised correctly
    assert text.startswith("# Bitcoin ETF\n")

    # Section 1 — accepted as-is
    assert "First sentence about ETFs." in text

    # Section 2 — only the second revision survives; v1 and original are gone
    assert "Revised body v2 (final)." in text
    assert "Revised body v1." not in text, (
        "First revision still present — accept_revision didn't overwrite cleanly"
    )
    assert "Original body of section 2." not in text, (
        "Original section 2 content still present — accept_revision didn't rewrite"
    )

    # Section 3 — written via 'edited' path: just keeps what was written
    assert "Wrap-up paragraph." in text

    # Sections in correct order
    intro_idx = text.index("First sentence about ETFs.")
    body_idx = text.index("Revised body v2 (final).")
    concl_idx = text.index("Wrap-up paragraph.")
    assert intro_idx < body_idx < concl_idx

    # No "Acknowledged" priming-response leak into article body
    assert "Acknowledged" not in text

    # Section headings appear exactly once each
    assert text.count("## 1. Intro") == 1
    assert text.count("## 2. Body") == 1
    assert text.count("## 3. Conclusion") == 1

    # Style card persisted (WritingStage's other responsibility)
    assert (tmp_path / "style_card.json").exists()

    # All 6 stubbed responses were consumed (catches ordering bugs)
    assert fake_conv._queue == []

    # Sanity: prompts received include the priming + 3 section prompts +
    # 2 revise prompts. We don't assert on their text content (would be brittle),
    # only the count.
    assert len(fake_conv.received_prompts) == 6


def test_writing_stage_e2e_eof_treated_as_accept(tmp_path, monkeypatch):
    """If user closes stdin (EOF) at a section review prompt, the section is
    accepted as-is and writing continues to the next section. Validates the
    safe_input EOF handling end-to-end (not just the unit test of safe_input).
    """
    fake_conv = _FakeConversation([
        "Ready.",
        "## 1. Intro\n\nIntro body.",
        "## 2. Body\n\nBody body.",
    ])

    def eof_input(prompt=""):
        raise EOFError()

    monkeypatch.setattr("builtins.input", eof_input)

    style_learner = MagicMock()
    style_learner.get_raw_materials.return_value = {"samples": [], "instructions": ""}
    style_learner.generate_style_card.return_value = StyleCard.fallback()

    def factory(*, card, output_path):
        return ArticleWriter(fake_conv, output_path=output_path)

    stage = WritingStage(
        ctx=MagicMock(output_dir=tmp_path, query="Q"),
        style_learner=style_learner,
        article_writer_factory=factory,
        section_review=SectionReview(),
    )

    sections = [
        {"title": "1. Intro", "content": "x"},
        {"title": "2. Body", "content": "y"},
    ]
    article_path = stage.write(
        outline="o", sections=sections, articles=[], videos=[], user_content=[],
        research_summary="s", user_content_only=False,
    )

    text = article_path.read_text(encoding="utf-8")
    assert "Intro body." in text
    assert "Body body." in text
    # Both sections written despite no real input — no crash
    assert fake_conv._queue == []
