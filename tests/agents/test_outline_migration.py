# tests/agents/test_outline_migration.py
import sys
sys.path.insert(0, '.')
import inspect


def test_outline_generator_has_no_openai_import():
    import agents.outline_generator as mod
    source = inspect.getsource(mod)
    assert 'from openai import OpenAI' not in source


def test_outline_generator_uses_quality_model_constant():
    import agents.outline_generator as mod
    source = inspect.getsource(mod)
    assert 'CLAUDE_QUALITY_MODEL' in source


def test_outline_feedback_has_no_openai():
    import agents.outline_feedback as mod
    source = inspect.getsource(mod)
    assert 'from openai' not in source
    assert 'OpenAI(' not in source
