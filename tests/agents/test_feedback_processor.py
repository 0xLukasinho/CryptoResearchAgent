# tests/agents/test_feedback_processor.py
import sys
sys.path.insert(0, '.')
import inspect


def test_feedback_processor_has_no_regex_boundary_detection():
    """The new FeedbackProcessor must not use regex to find section boundaries."""
    import agents.feedback_processor as mod
    source = inspect.getsource(mod)
    assert 'find_section_boundaries' not in source


def test_process_revision_calls_article_writer_revise_section():
    from unittest.mock import MagicMock
    from agents.feedback_processor import FeedbackProcessor

    mock_writer = MagicMock()
    mock_writer.revise_section.return_value = "## Section\n\nRevised content."
    mock_fact_checker = MagicMock()
    mock_fact_checker.check_section.return_value = {'accurate': True}

    processor = FeedbackProcessor()
    feedback = {'action': 'revise', 'details': 'Make it shorter'}
    result = processor.process_revision_request(
        feedback=feedback,
        article_writer=mock_writer,
        section_info={'title': 'Introduction', 'content': 'outline', 'current_content': 'old content'},
        research_data={},
        style_materials={},
        fact_checker=mock_fact_checker
    )

    mock_writer.revise_section.assert_called_once_with(
        section_title='Introduction',
        revision_instructions='Make it shorter',
        current_content='old content'
    )
    assert result == "## Section\n\nRevised content."
