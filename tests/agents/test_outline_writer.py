from unittest.mock import MagicMock

from crypto_research_agent.agents.outline_writer import OutlineWriter


def test_generate_returns_markdown_outline():
    backend = MagicMock()
    backend.complete.return_value = MagicMock(text="# Outline\n## 1. Intro\n- bullet")
    ow = OutlineWriter(backend, model="m")
    out = ow.generate(articles=[], videos=[], user_content=[],
                     query="bitcoin", thesis=None, user_content_only=False)
    assert "## 1." in out


def test_revise_returns_string():
    backend = MagicMock()
    backend.complete.return_value = MagicMock(text="# Outline\n## 1. Updated\n- bullet")
    ow = OutlineWriter(backend, model="m")
    out = ow.revise(current="# Outline\n## 1. Old", instructions="rename",
                    articles=[], videos=[], user_content=[],
                    query="x", thesis=None)
    assert "Updated" in out
