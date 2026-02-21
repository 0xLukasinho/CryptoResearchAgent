# tests/agents/test_article_writer.py
import sys
sys.path.insert(0, '.')
from unittest.mock import MagicMock
import os
import tempfile


def make_mock_client(section_response="## Section\n\nContent here."):
    mock = MagicMock()
    mock.generate_with_history.return_value = section_response
    mock.generate_content.return_value = "Understood. Ready to begin."
    return mock


def test_start_article_creates_file_with_title():
    mock_client = make_mock_client()
    with tempfile.TemporaryDirectory() as tmpdir:
        from agents.article_writer import ArticleWriterAgent
        agent = ArticleWriterAgent(mock_client)
        result = agent.start_article(
            title="Bitcoin ETF Analysis",
            query_output_dir=tmpdir,
            style_card_str="## Writing Style Guide\nTone: analytical",
            outline="## Section 1\n## Section 2",
            research_summary="Summary here"
        )
        assert os.path.exists(result)
        with open(result) as f:
            content = f.read()
        assert "Bitcoin ETF Analysis" in content


def test_start_article_initializes_conversation_history():
    mock_client = make_mock_client()
    with tempfile.TemporaryDirectory() as tmpdir:
        from agents.article_writer import ArticleWriterAgent
        agent = ArticleWriterAgent(mock_client)
        agent.start_article("Title", tmpdir, "Style", "Outline", "Summary")
        assert len(agent.conversation_history) >= 2  # initial user message + ack


def test_write_section_appends_to_conversation():
    mock_client = make_mock_client("## Introduction\n\nThis is the intro.")
    with tempfile.TemporaryDirectory() as tmpdir:
        from agents.article_writer import ArticleWriterAgent
        agent = ArticleWriterAgent(mock_client)
        agent.start_article("Title", tmpdir, "Style", "Outline", "Research")
        initial_len = len(agent.conversation_history)

        agent.write_section({'title': 'Introduction', 'content': 'Cover basics'}, {})
        assert len(agent.conversation_history) == initial_len + 2  # user msg + assistant response


def test_revise_section_appends_to_existing_conversation():
    mock_client = make_mock_client("## Introduction\n\nRevised content.")
    with tempfile.TemporaryDirectory() as tmpdir:
        from agents.article_writer import ArticleWriterAgent
        agent = ArticleWriterAgent(mock_client)
        agent.start_article("Title", tmpdir, "Style", "Outline", "Research")
        agent.write_section({'title': 'Introduction', 'content': 'Cover basics'}, {})
        after_write = len(agent.conversation_history)

        agent.revise_section('Introduction', 'Make it shorter', '## Introduction\n\nOriginal.')
        assert len(agent.conversation_history) == after_write + 2


def test_accept_revision_rewrites_article_file():
    mock_client = make_mock_client()
    with tempfile.TemporaryDirectory() as tmpdir:
        from agents.article_writer import ArticleWriterAgent
        agent = ArticleWriterAgent(mock_client)
        agent.start_article("Title", tmpdir, "Style", "Outline", "Research")
        agent.write_section({'title': 'Intro', 'content': 'outline'}, {})

        agent.accept_revision('Intro', '## Intro\n\nRevised and improved.')
        with open(agent.article_file) as f:
            content = f.read()
        assert 'Revised and improved.' in content
